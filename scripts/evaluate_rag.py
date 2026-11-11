"""Evaluate actual worker retrieval, never replace embeddings with test vectors."""
from pathlib import Path
import json
import time
import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
config = dotenv_values(ROOT / '.env')
client = httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=30)
response = client.post('/auth/login', json={'username': 'admin', 'password': config['ADMIN_PASSWORD']})
response.raise_for_status()
client.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
docs = client.get('/knowledge/documents').json()
sources = {}
for doc in docs:
    if doc['active_version']:
        for chunk in client.get(f"/knowledge/versions/{doc['active_version']}/chunks").json():
            sources[chunk['id']] = chunk['source']['section']
cases = json.loads((ROOT / 'fixtures/evaluation/retrieval.json').read_text(encoding='utf-8'))
rows = []
for number, case in enumerate(cases, 1):
    response = client.post('/retrieval-tests', json={'query': case['question']})
    response.raise_for_status()
    job = response.json()
    deadline = time.monotonic() + 180
    while job['state'] in ('queued', 'running') and time.monotonic() < deadline:
        time.sleep(0.5)
        response = client.get('/jobs/' + job['id'])
        response.raise_for_status()
        job = response.json()
    if job['state'] != 'succeeded':
        raise RuntimeError(f"Retrieval job failed: {job.get('error')}")
    result = job['result']
    row = {**case, 'duration_ms': result['duration_ms']}
    for channel, key in [('vector', 'vector'), ('bm25', 'bm25'), ('hybrid', 'hits')]:
        ranks = [i + 1 for i, h in enumerate(result[key][:6]) if case['section'] in sources.get(h['id'], '')]
        row[channel + '_hit_at_6'] = bool(ranks)
        row[channel + '_rr_at_6'] = 1 / ranks[0] if ranks else 0
    rows.append(row)
    print(f'{number}/{len(cases)} hybrid={row["hybrid_hit_at_6"]} {result["duration_ms"]}ms', flush=True)
summary = {channel: {'recall_at_6': sum(r[channel + '_hit_at_6'] for r in rows) / len(rows),
                      'mrr_at_6': sum(r[channel + '_rr_at_6'] for r in rows) / len(rows)} for channel in ['vector','bm25','hybrid']}
output = ROOT / 'data/verification'
output.mkdir(parents=True, exist_ok=True)
(output / 'rag-evaluation.json').write_text(json.dumps({'count': len(rows), 'summary': summary, 'cases': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
