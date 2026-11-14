import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import session, User, uid
from app.auth import passwords


@pytest.fixture
def client(db, monkeypatch):
    from contextlib import nullcontext
    from app import ingress
    # Share the fixture's uncommitted test transaction with pre-parser auth.
    monkeypatch.setattr(ingress, 'Session', lambda: nullcontext(db))
    app.dependency_overrides[session] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def login(client, db, role='admin'):
    username = uid()
    user = User(username=username, password_hash=passwords.hash('test-password'), role=role)
    db.add(user); db.flush()
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': 'test-password'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_ticket_creation_search_and_run(client, db):
    headers = login(client, db)
    result = client.post('/api/v1/tickets', headers=headers, json={'subject': '发票测试', 'content': '开具发票 13812345678', 'customer_id': 'C001'})
    assert result.status_code == 201
    ticket = result.json()
    assert '13812345678' not in ticket['content']
    assert client.get('/api/v1/tickets?q=发票测试', headers=headers).json()['total'] == 1
    run = client.post(f"/api/v1/tickets/{ticket['id']}/runs", headers=headers, json={'revision': ticket['revision']})
    assert run.status_code == 202
    repeat = client.post(f"/api/v1/tickets/{ticket['id']}/runs", headers=headers, json={'revision': ticket['revision']})
    assert repeat.json()['id'] == run.json()['id']


def test_agent_cannot_publish_config_or_view_global_logs(client, db):
    headers = login(client, db, 'agent')
    assert client.put('/api/v1/workflow/config', headers=headers, json={}).status_code == 403
    assert client.get('/api/v1/audit-events', headers=headers).status_code == 403


def test_upload_rejects_invalid_extension_and_config_rejects_overlap(client, db):
    headers = login(client, db)
    response = client.post('/api/v1/knowledge/documents', headers=headers, files={'file': ('a.exe', b'invalid')})
    assert response.status_code == 415
    response = client.put('/api/v1/workflow/config', headers=headers, json={'chunk_chars': 200, 'overlap_chars': 300})
    assert response.status_code == 422


def test_complete_workflow_approval_and_send_with_provider_transport_stub(client, db, monkeypatch):
    """Only the external provider and expensive retrieval boundary are fixtures; business path is real."""
    import httpx
    from openai import OpenAI
    from pydantic import SecretStr
    from app.config import settings
    from app import llm, worker
    from app.db import Job
    headers = login(client, db)
    ticket = client.post('/api/v1/tickets', headers=headers, json={'subject': '退款咨询', 'content': '退款如何退回？', 'customer_id': 'C001'}).json()
    job_id = client.post(f"/api/v1/tickets/{ticket['id']}/runs", headers=headers, json={'revision': 1}).json()['id']
    def response(request):
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 1, 'model': 'test',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '{"reply_text":"审核通过后原路退款。","citations":[{"chunk_id":"test-evidence","quote":"审核通过后原路退款。"}]}'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 30, 'total_tokens': 80}})
    sdk = OpenAI(api_key='test-only', http_client=httpx.Client(transport=httpx.MockTransport(response)))
    monkeypatch.setattr(llm, 'OpenAI', lambda **kwargs: sdk)
    monkeypatch.setattr(settings(), 'llm_api_key', SecretStr('test-only'))
    class RetrievalFixture:
        def search(self, *args):
            return {'hits': [{'id': 'test-evidence', 'content': '审核通过后原路退款。', 'source': {'document_name': '测试政策'}}], 'versions': [], 'duration_ms': 1}
    job = db.get(Job, job_id)
    worker.execute(db, job, RetrievalFixture())
    assert job.state == 'succeeded'
    details = client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers).json()
    assert details['status'] == 'pending_review'
    assert details['draft']['citations'][0]['quote'] == '审核通过后原路退款。'
    response = client.post(f"/api/v1/tickets/{ticket['id']}/send", headers=headers, json={'revision': details['revision']})
    assert response.status_code == 409
    approved = client.post(f"/api/v1/tickets/{ticket['id']}/reviews", headers=headers,
                          json={'revision': details['revision'], 'action': 'approve', 'text': '审核通过后，款项会原路退回。'})
    assert approved.status_code == 200
    sent = client.post(f"/api/v1/tickets/{ticket['id']}/send", headers=headers, json={'revision': approved.json()['revision']})
    assert sent.status_code == 200
    assert sent.json()['sent_text'] == '审核通过后，款项会原路退回。'
    assert sent.json()['status'] == 'replied'


def test_agent_cannot_gain_order_access_by_creating_a_ticket(client, db):
    from app.db import Order, Ticket
    from sqlalchemy import select, func
    order = Order(id=uid(), customer_id='C-PRIVATE', product='private', amount_cents=100, status='paid')
    db.add(order); db.flush()
    headers = login(client, db, 'agent')
    endpoint = '/api/v1/orders/' + order.id
    assert client.get(endpoint, headers=headers).status_code == 403
    result = client.post('/api/v1/tickets', headers=headers, json={
        'subject': '咨询', 'content': '订单咨询', 'customer_id': 'C-PRIVATE', 'order_id': order.id})
    assert result.status_code == 403
    assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.order_id == order.id)) == 0
    # A freely supplied customer ID on an unlinked ticket must not grant order access either.
    assert client.post('/api/v1/tickets', headers=headers, json={
        'subject': '咨询', 'content': '订单咨询', 'customer_id': 'C-PRIVATE'}).status_code == 201
    assert client.get(endpoint, headers=headers).status_code == 403


def test_manager_assignment_allows_agent_to_create_a_followup_for_that_order(client, db):
    from app.db import Order
    order = Order(id=uid(), customer_id='C-ASSIGNED', product='product', amount_cents=100, status='paid')
    db.add(order); db.flush()
    manager = login(client, db)
    agent = login(client, db, 'agent')
    agent_id = client.get('/api/v1/auth/me', headers=agent).json()['id']
    body = {'subject': '咨询', 'content': '订单咨询', 'customer_id': 'C-ASSIGNED', 'order_id': order.id}
    original = client.post('/api/v1/tickets', headers=manager, json=body)
    assert original.status_code == 201
    result = client.post('/api/v1/tickets/assign/batch', headers=manager,
                         json={'ticket_ids': [original.json()['id']], 'user_id': agent_id})
    assert result.status_code == 200
    assert client.get('/api/v1/orders/' + order.id, headers=agent).status_code == 200
    followup = client.post('/api/v1/tickets', headers=agent, json=body)
    assert followup.status_code == 201
    assert client.get('/api/v1/tickets/' + followup.json()['id'], headers=agent).json()['order']['id'] == order.id


def test_password_rotation_revokes_old_sessions(client, db):
    username = uid()
    user = User(username=username, role='agent', password_hash=passwords.hash('old-test-password'))
    db.add(user); db.flush()
    token = client.post('/api/v1/auth/login', json={'username': username, 'password': 'old-test-password'}).json()['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 200
    user.password_hash = passwords.hash('new-test-password')
    db.flush()
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': username, 'password': 'old-test-password'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': username, 'password': 'new-test-password'}).status_code == 200


def raw_upload(headers=()):
    import asyncio
    reads, sent = [], []
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': 'POST', 'scheme': 'http', 'path': '/api/v1/knowledge/documents',
             'raw_path': b'/api/v1/knowledge/documents', 'root_path': '', 'query_string': b'',
             'headers': [(b'content-type', b'multipart/form-data; boundary=a')] + list(headers),
             'client': ('127.0.0.1', 1234), 'server': ('test', 80)}
    async def receive():
        if reads:
            await asyncio.Event().wait()
        reads.append(True)
        return {'type': 'http.request', 'body': b'--a--\r\n', 'more_body': False}
    async def send(message):
        sent.append(message)
    asyncio.run(app(scope, receive, send))
    return next(message['status'] for message in sent if message['type'] == 'http.response.start'), reads


def test_unauthenticated_upload_is_rejected_without_receiving_body():
    assert raw_upload() == (401, [])


def test_agent_upload_is_rejected_without_receiving_body(client, db):
    headers = login(client, db, 'agent')
    assert raw_upload([(b'authorization', headers['Authorization'].encode())]) == (403, [])


def test_invalid_upload_token_is_rejected_without_receiving_body():
    assert raw_upload([(b'authorization', b'Bearer not-a-token')]) == (401, [])


def test_revoked_upload_token_is_rejected_without_receiving_body(client, db):
    headers = login(client, db)
    user_id = client.get('/api/v1/auth/me', headers=headers).json()['id']
    db.get(User, user_id).password_hash = passwords.hash('rotated-test-password')
    db.flush()
    assert raw_upload([(b'authorization', headers['Authorization'].encode())]) == (401, [])


def test_authorized_upload_still_stores_and_enqueues_document(client, db, tmp_path, monkeypatch):
    from app.config import settings
    from app.db import Version, Job
    from sqlalchemy import select
    monkeypatch.setattr(settings(), 'data_dir', tmp_path)
    headers = login(client, db, 'knowledge')
    response = client.post('/api/v1/knowledge/documents', headers=headers,
                           files={'file': ('policy.md', b'# policy\nRefund policy.', 'text/markdown')})
    assert response.status_code == 202
    version = db.get(Version, response.json()['id'])
    from pathlib import Path
    assert Path(version.path).is_relative_to(tmp_path)
    assert Path(version.path).read_bytes() == b'# policy\nRefund policy.'
    job = db.scalar(select(Job).where(Job.resource_id == version.id))
    assert job.kind == 'ingest' and job.state == 'queued'


def test_original_file_limit_is_retained_inside_total_multipart_limit(client, db):
    headers = login(client, db)
    response = client.post('/api/v1/knowledge/documents', headers=headers,
                           files={'file': ('too-big.txt', b'x' * (10 * 1024 * 1024 + 1))})
    assert response.status_code == 413
