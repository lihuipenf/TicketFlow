import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import session, User, uid
from app.auth import passwords


@pytest.fixture
def client(db):
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
