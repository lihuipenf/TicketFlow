"""Document ingestion and hybrid retrieval."""
from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import os
import re
import time
import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from pypdf import PdfReader
from sqlalchemy import select
from app.config import settings
from app.db import Chunk, Document, Version
from app.policy import redact

jieba.setLogLevel(30)
jieba.dt.tmp_dir = os.environ.get('TEMP', 'D:/CodexData/temp')


def parse_document(filename, raw, version_id, max_chars=1100, overlap=None):
    if overlap is None:
        overlap = min(100, max_chars // 10)
    if max_chars < 20 or not 0 <= overlap < max_chars:
        raise ValueError('切块参数无效')
    suffix = Path(filename).suffix.lower()
    blocks = []
    if suffix == '.pdf':
        reader = PdfReader(BytesIO(raw))
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            if not text.strip():
                raise ValueError(f'第 {number} 页没有可提取文字，需要 OCR')
            blocks.append((text, {'section': f'第 {number} 页', 'page_start': number, 'page_end': number, 'line_start': None, 'line_end': None}))
    elif suffix in ('.md', '.txt'):
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('文本请使用 UTF-8 编码') from exc
        headings, lines, start = [], [], 1
        def flush(end):
            if lines:
                blocks.append(('\n'.join(lines), {'section': ' / '.join(headings) or '正文', 'page_start': None, 'page_end': None, 'line_start': start, 'line_end': end}))
                lines.clear()
        for number, line in enumerate(text.splitlines(), 1):
            heading = re.match(r'^(#{1,6})\s+(.+)', line) if suffix == '.md' else None
            if heading:
                flush(number - 1)
                level = len(heading[1])
                headings = headings[:level - 1] + [redact(heading[2].strip())]
            elif not line.strip():
                flush(number - 1)
            else:
                if not lines:
                    start = number
                lines.append(line)
        flush(len(text.splitlines()))
    else:
        raise ValueError('仅支持 PDF / Markdown / TXT')
    chunks = []
    for text, source in blocks:
        text = redact(text)
        offset = 0
        while offset < len(text):
            end = min(offset + max_chars, len(text))
            if end < len(text):
                boundaries = list(re.finditer(r'[。！？.!?\n]', text[offset + max_chars // 2:end]))
                if boundaries:
                    end = offset + max_chars // 2 + boundaries[-1].end()
            part = text[offset:end].strip()
            if part:
                index = len(chunks)
                chunks.append({'id': sha256(f'{version_id}:{index}:{part}'.encode()).hexdigest(), 'content': part,
                               'source': {**source, 'document_name': redact(filename), 'version_id': version_id, 'offset_start': offset, 'offset_end': end}})
            if end == len(text):
                break
            offset = max(offset + 1, end - overlap)
    if not chunks:
        raise ValueError('文档没有有效正文')
    return chunks


def tokenize(text):
    return [t.lower() for t in jieba.cut_for_search(text) if re.search(r'[\w\u4e00-\u9fff]', t)]


def lexical_search(query, chunks, top_k=20):
    if not chunks:
        return []
    tokens = [tokenize(c['content']) or ['_empty_'] for c in chunks]
    query_tokens = tokenize(query)
    # BM25Okapi may yield zero IDF for tiny corpora; a positive floor preserves keyword matches.
    bm25 = BM25Okapi(tokens)
    bm25.idf = {term: max(score, 0.05) for term, score in bm25.idf.items()}
    scores = bm25.get_scores(query_tokens)
    hits = [{'id': chunks[i]['id'], 'score': float(score)} for i, score in enumerate(scores)
            if score > 0 and set(tokens[i]).intersection(query_tokens)]
    return sorted(hits, key=lambda h: (-h['score'], h['id']))[:top_k]


def rrf(vector_ids, lexical_ids, k=60):
    scores = defaultdict(float)
    for ranking in (vector_ids, lexical_ids):
        for rank, key in enumerate(dict.fromkeys(ranking), 1):
            scores[key] += 1 / (k + rank)
    return [{'id': key, 'score': score} for key, score in sorted(scores.items(), key=lambda p: (-p[1], p[0]))]


@lru_cache(maxsize=1)
def embedding_model():
    os.environ['HF_HOME'] = settings().hf_home
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings().embedding_model, cache_folder=settings().hf_home, device=settings().embedding_device)
    model.max_seq_length = 2048
    return model


def embed(texts, query=False):
    prompt = 'Instruct: Given an ecommerce customer question, retrieve relevant policy passages that answer the question\nQuery: ' if query else ''
    return embedding_model().encode(texts, prompt=prompt, normalize_embeddings=True, batch_size=8, show_progress_bar=False).tolist()


class Index:
    def __init__(self):
        from pymilvus import MilvusClient, DataType
        path = settings().storage / 'milvus' / 'ticketflow.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client = MilvusClient(str(path))
        if not self.client.has_collection('knowledge'):
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field('id', DataType.VARCHAR, is_primary=True, max_length=64)
            schema.add_field('vector', DataType.FLOAT_VECTOR, dim=1024)
            schema.add_field('version_id', DataType.VARCHAR, max_length=32)
            params = self.client.prepare_index_params()
            params.add_index(field_name='vector', index_type='FLAT', metric_type='COSINE')
            self.client.create_collection('knowledge', schema=schema, index_params=params)
        self.client.load_collection('knowledge')

    def ingest(self, db, version_id, config):
        version = db.get(Version, version_id)
        version.state = 'indexing'
        db.commit()
        chunks = parse_document(version.filename, Path(version.path).read_bytes(), version_id,
                                config.get('chunk_chars', 1100), config.get('overlap_chars', 100))
        vectors = embed([c['content'] for c in chunks])
        rows = [{'id': c['id'], 'vector': v, 'version_id': version_id} for c, v in zip(chunks, vectors)]
        self.client.upsert('knowledge', rows)
        self.client.flush('knowledge')
        directory = settings().storage / 'bm25'
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f'{version_id}.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(chunks, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
        for c in chunks:
            db.merge(Chunk(id=c['id'], version_id=version_id, content=c['content'], source=c['source']))
        version.index_meta = {'chunk_count': len(chunks), 'embedding_model': settings().embedding_model,
                              'dimension': 1024, 'lexical_path': str(target), 'splitter': 'structure-sentence-chars-v1'}
        version.state = 'ready'
        version.error = None
        db.commit()
        return {'version_id': version_id, **version.index_meta}

    def search(self, db, query, config):
        start = time.perf_counter()
        active = list(db.scalars(select(Document.active_version).where(Document.active_version.is_not(None))))
        if not active:
            return {'hits': [], 'vector': [], 'bm25': [], 'versions': [], 'duration_ms': 0}
        chunks = []
        for version_id in active:
            version = db.get(Version, version_id)
            if version.index_meta.get('embedding_model') != settings().embedding_model:
                raise ValueError('Embedding 模型已变更，请重建知识索引')
            chunks.extend(json.loads(Path(version.index_meta['lexical_path']).read_text(encoding='utf-8')))
        query_vector = embed([query], query=True)
        embedded_at = time.perf_counter()
        self.client.load_collection('knowledge')
        vector_result = self.client.search('knowledge', data=query_vector, filter='version_id in ' + json.dumps(active),
                                           limit=config.get('vector_top_k', 20), output_fields=['version_id'])
        vector_hits = [{'id': str(h['id']), 'score': float(h['distance'])} for h in vector_result[0]]
        vector_hits = [h for h in vector_hits if h['score'] >= config.get('min_similarity', 0.4)]
        vector_at = time.perf_counter()
        lexical = lexical_search(query, chunks, config.get('bm25_top_k', 20))
        fused = rrf([h['id'] for h in vector_hits], [h['id'] for h in lexical])
        lookup = {c['id']: c for c in chunks}
        hits, budget = [], config.get('context_chars', 6500)
        for h in fused:
            c = lookup.get(h['id'])
            if not c or len(c['content']) > budget:
                continue
            hits.append({**c, 'rrf_score': h['score']})
            budget -= len(c['content'])
            if len(hits) >= config.get('context_top_k', 6):
                break
        end = time.perf_counter()
        return {'hits': hits, 'vector': vector_hits, 'bm25': lexical, 'versions': active,
                'duration_ms': round((end - start) * 1000), 'embedding_ms': round((embedded_at - start) * 1000),
                'vector_ms': round((vector_at - embedded_at) * 1000), 'bm25_rrf_ms': round((end - vector_at) * 1000)}

    def close(self):
        self.client.close()
