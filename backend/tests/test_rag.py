from io import BytesIO
import pytest
from app import rag, policy


def test_markdown_chunks_preserve_section_and_original_lines():
    chunks = rag.parse_document('policy.md', '# 售后\n\n## 退款\n付款后未发货可以申请退款。\n\n## 发票\n支持电子发票。'.encode(), 'v1', max_chars=100)
    assert len(chunks) == 2
    assert chunks[0]['source']['section'] == '售后 / 退款'
    assert chunks[0]['source']['line_start'] == 4
    assert chunks[0]['source']['page_start'] is None
    assert chunks[1]['source']['line_start'] == 7


def test_pdf_preserves_real_page_and_rejects_empty_pdf():
    from reportlab.pdfgen.canvas import Canvas
    buf = BytesIO()
    canvas = Canvas(buf)
    canvas.drawString(50, 750, 'Refund within seven days.')
    canvas.showPage()
    canvas.drawString(50, 750, 'Invoice policy.')
    canvas.save()
    chunks = rag.parse_document('policy.pdf', buf.getvalue(), 'v1')
    assert [c['source']['page_start'] for c in chunks] == [1, 2]
    empty = BytesIO()
    c = Canvas(empty)
    c.showPage()
    c.save()
    with pytest.raises(ValueError, match='OCR'):
        rag.parse_document('scan.pdf', empty.getvalue(), 'v1')


def test_long_chunks_are_bounded_and_have_unique_stable_ids():
    raw = ('退款规则：商品完好可以申请退货。' * 80).encode()
    chunks = rag.parse_document('a.txt', raw, 'v1', max_chars=120, overlap=20)
    assert len(chunks) > 2
    assert all(len(c['content']) <= 120 for c in chunks)
    assert len({c['id'] for c in chunks}) == len(chunks)
    assert chunks == rag.parse_document('a.txt', raw, 'v1', max_chars=120, overlap=20)


def test_rrf_rewards_cross_channel_agreement_without_duplicate_votes():
    result = rag.rrf(['a', 'b', 'b'], ['b', 'c'])
    assert result[0]['id'] == 'b'
    assert result[0]['score'] == pytest.approx(1 / 62 + 1 / 61)
    assert len(result) == 3


def test_bm25_finds_chinese_keyword_and_drops_zero_matches():
    chunks = [{'id': 'a', 'content': '七天无理由退货，商品需完好。'}, {'id': 'b', 'content': '支持开具电子发票。'}, {'id': 'c', 'content': '物流配送预计三天。'}]
    result = rag.lexical_search('电子发票', chunks, 10)
    assert result[0]['id'] == 'b'
    assert rag.lexical_search('火星移民', chunks, 10) == []


def test_redaction_covers_html_phone_email_identity_and_address():
    clean = policy.redact('<b>联系我</b> 13812345678 test@example.com 身份证110101199001011234 地址：上海市测试路123号')
    for secret in ['<b>', '13812345678', 'test@example.com', '110101199001011234', '上海市测试路123号']:
        assert secret not in clean


def test_priority_rules_and_multiple_intents():
    result = policy.classify('商品起火了，要求退款并投诉')
    assert result['priority'] == 'P0'
    assert '退款' in result['intents']
    assert policy.classify('如何开具发票')['priority'] == 'P3'


def test_citation_validator_rejects_invented_reference_and_unquoted_evidence():
    evidence = [{'id': 'c1', 'content': '退款原路返回。', 'source': {'document_name': '退款政策'}}]
    with pytest.raises(ValueError, match='引用'):
        policy.validate_answer({'reply_text': '当天到账', 'citations': [{'chunk_id': 'fake', 'quote': '当天到账'}]}, evidence)
    with pytest.raises(ValueError, match='原文'):
        policy.validate_answer({'reply_text': '当天到账', 'citations': [{'chunk_id': 'c1', 'quote': '当天到账'}]}, evidence)
    answer = policy.validate_answer({'reply_text': '退款将原路返回。', 'citations': [{'chunk_id': 'c1', 'quote': '退款原路返回。'}]}, evidence)
    assert answer['needs_human_review'] is True
    assert answer['citations'][0]['source']['document_name'] == '退款政策'


def test_no_evidence_does_not_receive_confident_score():
    answer = policy.validate_answer({'reply_text': '需要补充信息', 'citations': []}, [])
    assert answer['evidence_score'] == 0
    assert '无可用知识证据' in answer['risk_flags']
