"""Privacy, classification, and grounded answer validation."""
import html
import re
from pydantic import BaseModel, Field


def redact(text: str) -> str:
    text = re.sub(r'<[^>]*>', '', html.unescape(text))
    text = re.sub(r'(?<!\d)\d{17}[\dXx](?!\d)', '[身份证已隐藏]', text)
    text = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[手机已隐藏]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱已隐藏]', text)
    text = re.sub(r'(?:收货地址|地址)\s*[:：]\s*[^\n，。;；]+', '地址：[已隐藏]', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def redact_tree(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_tree(item) for key, item in value.items()}
    return value


INTENTS = {
    '退款': ('退款', '退钱'), '退换货': ('退货', '换货', '质量'),
    '物流': ('物流', '发货', '快递', '配送', '签收'), '支付': ('支付', '付款', '扣款'),
    '发票': ('发票', '开票'), '投诉': ('投诉', '举报', '欺诈'),
    '商品咨询': ('商品', '尺寸', '保价', '优惠券', '规格'),
}


def classify(text: str, urgent_words=None):
    intents = [key for key, terms in INTENTS.items() if any(t in text for t in terms)] or ['其他']
    if any(t in text for t in ('起火', '触电', '人身伤害', '批量扣款', '数据泄露')):
        priority, reason = 'P0', '涉及安全或重大资金异常'
    elif any(t in text for t in (urgent_words or ['投诉', '超时', '逾期', '紧急', '三天没发货'])):
        priority, reason = 'P1', '投诉、时效或紧急售后规则命中'
    elif any(i in intents for i in ['退款', '退换货', '物流', '支付']):
        priority, reason = 'P2', '常规交易售后'
    else:
        priority, reason = 'P3', '一般咨询'
    return {'intent': intents[0], 'intents': intents, 'priority': priority, 'reason': reason, 'method': 'rules'}


class Citation(BaseModel):
    chunk_id: str
    quote: str = Field(min_length=1, max_length=2000)


class Answer(BaseModel):
    reply_text: str = Field(min_length=1, max_length=6000)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    suggested_actions: list[str] = Field(default_factory=list, max_length=10)
    missing_information: list[str] = Field(default_factory=list, max_length=10)


def validate_answer(raw: dict, evidence: list[dict]):
    answer = Answer.model_validate(raw).model_dump()
    lookup = {c['id']: c for c in evidence}
    enriched = []
    for citation in answer['citations']:
        if citation['chunk_id'] not in lookup:
            raise ValueError('引用不属于本次检索证据')
        chunk = lookup[citation['chunk_id']]
        if citation['quote'] not in chunk['content']:
            raise ValueError('引用原文不存在')
        enriched.append({**citation, 'source': chunk['source'], 'content': chunk['content']})
    risks = []
    if not enriched:
        risks.append('无可用知识证据')
    if re.search(r'(保证|一定|百分之百).{0,12}(到账|退款|赔偿)|已为您(退款|取消)', answer['reply_text']):
        risks.append('疑似未经授权的资金或时效承诺')
    cleaned = redact(answer['reply_text'])
    if cleaned != answer['reply_text']:
        risks.append('输出包含敏感信息，已脱敏')
    answer.update(reply_text=cleaned, citations=enriched, risk_flags=risks,
                  evidence_score=0 if not enriched else max(0, 75 - 25 * len(risks)),
                  score_explanation='启发式证据评分：有效原文引用基础分75；每项风险扣25；不是正确率，语义支持需人工复核。',
                  needs_human_review=True)
    return redact_tree(answer)
