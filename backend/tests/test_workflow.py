import pytest
from fastapi import HTTPException
from app import services, llm
from app.db import Ticket, Order, User, Job, Document, Version, uid


def fixture_ticket(db):
    user = User(username='test-' + uid(), password_hash='unused', role='agent')
    order = Order(id=uid(), customer_id='C001', product='耳机', amount_cents=19900, status='paid', facts={})
    db.add_all([user, order]); db.flush()
    ticket = Ticket(subject='退款', content='申请退款', customer_id='C001', order_id=order.id, assignee=user.id)
    db.add(ticket); db.flush()
    return user, ticket, order


def test_create_rejects_order_owned_by_another_customer(db):
    user, _, order = fixture_ticket(db)
    with pytest.raises(HTTPException) as exc:
        services.create_ticket(db, user, {'subject': '退款', 'content': '退款', 'customer_id': 'OTHER', 'order_id': order.id})
    assert exc.value.status_code == 403


def test_agent_cannot_access_unassigned_ticket(db):
    user, ticket, _ = fixture_ticket(db)
    ticket.assignee = None
    with pytest.raises(HTTPException) as exc:
        services.access_ticket(db, user, ticket.id)
    assert exc.value.status_code == 403


def test_job_submission_is_idempotent(db):
    key = uid()
    first = services.enqueue(db, 'retrieval', {'query': '退款'}, key)
    second = services.enqueue(db, 'retrieval', {'query': '退款'}, key)
    assert first.id == second.id


def test_approval_requires_current_revision_and_send_requires_approval(db):
    user, ticket, order = fixture_ticket(db)
    with pytest.raises(HTTPException):
        services.send_reply(db, user, ticket.id, ticket.revision)
    ticket.status = 'pending_review'
    ticket.draft = {'reply_text': '请提交退款申请', 'order_revision': order.revision, 'versions': [], 'risk_flags': []}
    with pytest.raises(HTTPException) as exc:
        services.review(db, user, ticket.id, 99, 'approve', '请提交退款申请')
    assert exc.value.status_code == 409
    services.review(db, user, ticket.id, ticket.revision, 'approve', '请提交退款申请')
    services.send_reply(db, user, ticket.id, ticket.revision)
    assert ticket.status == 'replied'
    assert ticket.sent_text == '请提交退款申请'
    revision = ticket.revision
    services.send_reply(db, user, ticket.id, revision)
    assert ticket.revision == revision


def test_changed_order_blocks_approval(db):
    user, ticket, order = fixture_ticket(db)
    ticket.status = 'pending_review'
    ticket.draft = {'order_revision': 1, 'versions': [], 'risk_flags': []}
    order.revision = 2
    with pytest.raises(HTTPException) as exc:
        services.review(db, user, ticket.id, ticket.revision, 'approve', '可以退款')
    assert exc.value.status_code == 409


def test_unbuilt_version_cannot_be_published(db):
    doc = Document(name='政策')
    db.add(doc); db.flush()
    version = Version(document_id=doc.id, filename='a.md', path='unused', checksum='a', state='queued')
    db.add(version); db.flush()
    with pytest.raises(HTTPException) as exc:
        services.publish(db, version.id, 'test')
    assert exc.value.status_code == 409
    assert doc.active_version is None


def test_missing_key_is_explicit_and_not_a_fake_answer(monkeypatch):
    from app.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings(), 'llm_api_key', SecretStr(''))
    with pytest.raises(llm.ModelNotConfigured):
        llm.generate('退款', [], {})


def test_model_json_is_validated_after_real_sdk_response(monkeypatch):
    import httpx
    from openai import OpenAI
    def handler(request):
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 1, 'model': 'test',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '{"reply_text":"退款原路返回。","citations":[{"chunk_id":"c1","quote":"退款原路返回。"}]}'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 30, 'total_tokens': 80}})
    client = OpenAI(api_key='test-only', http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    answer = llm.generate('如何退款', [{'id': 'c1', 'content': '退款原路返回。', 'source': {}}], {}, client=client)
    assert answer['reply_text'] == '退款原路返回。'
    assert answer['usage']['total_tokens'] == 80
    assert answer['citations'][0]['chunk_id'] == 'c1'
