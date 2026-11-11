from app.rag import Index
from app.config import settings


def test_milvus_collection_is_searchable_after_creation_and_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), 'data_dir', tmp_path)
    vector = [1.0] + [0.0] * 1023
    index = Index()
    try:
        index.client.upsert('knowledge', [{'id': 'c1', 'vector': vector, 'version_id': 'v1'}])
        index.client.flush('knowledge')
        result = index.client.search('knowledge', data=[vector], limit=1)
        assert result[0][0]['id'] == 'c1'
        index.client.release_collection('knowledge')
    finally:
        index.close()
    reopened = Index()
    try:
        result = reopened.client.search('knowledge', data=[vector], limit=1)
        assert result[0][0]['id'] == 'c1'
    finally:
        reopened.close()
