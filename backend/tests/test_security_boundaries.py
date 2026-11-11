import pytest
from app import rag, policy, llm, worker, services
from app.db import User, Ticket, uid


def test_document_metadata_is_redacted_before_embedding_context():
    chunks = rag.parse_document('客户13812345678.txt', '客户咨询政策'.encode(), 'v1')
    assert '13812345678' not in str(chunks)
    chunks = rag.parse_document('policy.md', '# 客户13812345678\n退款原路返回。'.encode(), 'v2')
    assert '13812345678' not in str(chunks)


def test_generated_auxiliary_fields_are_redacted():
    answer = policy.validate_answer({'reply_text': '需要补充信息', 'missing_information': ['手机号13812345678'],
                                     'suggested_actions': ['邮件test@example.com']}, [])
    assert '13812345678' not in str(answer)
    assert 'test@example.com' not in str(answer)


def test_invalid_llm_output_is_not_persisted_in_job_error(db, monkeypatch):
    user = User(username=uid(), password_hash='unused', role='admin')
    db.add(user); db.flush()
    ticket = Ticket(subject='咨询', content='咨询', customer_id='C1', assignee=user.id)
    db.add(ticket); db.flush()
    job = services.enqueue(db, 'ticket', {'revision': ticket.revision}, uid(), ticket.id)
    class EmptyIndex:
        def search(self, *args):
            return {'hits': [], 'versions': [], 'duration_ms': 0}
    def malformed(*args):
        return policy.validate_answer({'reply_text': {'phone': '13812345678'}}, [])
    monkeypatch.setattr(llm, 'generate', malformed)
    worker.execute(db, job, EmptyIndex())
    assert job.state == 'failed'
    assert '13812345678' not in job.error
    assert 'input_value' not in job.error
