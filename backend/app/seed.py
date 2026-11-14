"""Deterministic synthetic ecommerce fixtures."""
from datetime import timedelta
from pathlib import Path
import json
from sqlalchemy import select
from app.db import User, Order, Ticket, WorkflowConfig, Session, now
from app.config import ROOT, settings
from app.policy import classify
from app.services import DEFAULT_CONFIG, upload
from app.accounts import ensure_seed_accounts, ROLES

FAQS = [
    ('发货时效', '付款成功后，普通现货订单通常在48小时内发货。预售商品以商品详情页约定日期为准。超过约定时间未发货，可联系客服核实库存与履约进度。'),
    ('物流查询', '发货后可在订单详情查看快递单号与物流轨迹。物流超过48小时无更新，可提交物流核查工单；不得直接承诺包裹丢失或固定送达时间。'),
    ('未发货退款', '订单尚未发货时，可在订单详情发起取消与退款申请。系统审核通过后原路退款；客服回复不代表退款已经执行。'),
    ('退款到账', '退款审核通过后，款项原路退回原支付账户。银行卡通常需1至7个工作日，具体到账时间以支付机构处理结果为准。'),
    ('七天无理由退货', '支持七天无理由退货的商品，自签收次日起七天内可申请。商品须保持完好，配件与赠品齐全；定制商品、已拆封影响卫生安全的商品等不适用，具体以商品标识为准。'),
    ('质量问题售后', '商品出现质量问题，请提供故障描述、照片或视频及订单号。售后核验后按适用政策安排维修、换货或退货，不得未经核验承诺赔付。'),
    ('退货运费', '因商家原因或确认的质量问题退货，由商家承担合理退货运费；个人原因退货通常由买家承担。运费险按保险机构规则理赔。'),
    ('换货规则', '申请换货需商品符合售后条件且目标规格有库存。寄回商品验收通过后安排换出，库存不足时由客服提供其他处理建议。'),
    ('电子发票', '订单完成后可在订单详情申请电子普通发票。需提供正确的发票抬头；企业抬头需提供税号。开票内容以实际购买商品为准。'),
    ('发票更正', '发票信息有误时，可提交原发票信息与正确抬头申请更正。财务核验后进行红冲或重新开具，客服不能直接修改已开具的税务凭证。'),
    ('支付失败', '支付失败请先确认支付账户余额与银行限额，再查看订单支付状态。若已扣款但订单显示未支付，请勿重复支付，提交支付流水核查。'),
    ('重复扣款', '疑似重复扣款需核对订单号、支付时间与交易流水。核实后按支付渠道处理；出现批量扣款异常需立即升级主管。'),
    ('修改收货地址', '未发货订单可提交修改收货地址申请，由客服核验后处理；已发货订单需联系物流确认是否支持拦截，不能保证修改成功。请勿在公共咨询中暴露完整地址。'),
    ('优惠券规则', '优惠券需满足有效期、商品范围和最低消费金额。部分优惠不能叠加；退款后的优惠券退回情况以活动页面规则为准。'),
    ('保价申请', '带有保价标识的商品可在标注的保价期内申请差价核验。是否符合条件及差额以订单、活动范围和当期保价规则为准，客服不得直接承诺差额金额。'),
    ('商品规格咨询', '商品尺寸、材质、适用范围以商品详情页为准。缺少具体型号时，请先询问商品名称或链接，避免猜测规格。'),
    ('签收异常', '物流显示签收但未收到时，先核查家人、前台或代收点，再联系快递核验签收记录。无法确认收货时可发起物流异常工单。'),
    ('投诉处理', '客户投诉应记录诉求、订单关联及已尝试的解决方式。严重投诉升级主管处理，并告知后续跟进安排；不得擅自承诺赔偿金额。'),
    ('安全事件', '商品起火、触电或造成人身伤害等情况按P0处理，建议停止使用并远离危险源，立即升级主管；客服不提供未经核实的责任认定。'),
    ('订单取消', '未付款订单可以取消；已付款未发货订单需提交取消申请；已发货订单通常需走退货流程。具体以订单实时状态和审核结果为准。'),
]


def populate(db):
    ensure_seed_accounts(db, {role: getattr(settings(), role + '_password').get_secret_value() for role in ROLES})
    admin = db.scalar(select(User).where(User.username == 'admin'))
    agent = db.scalar(select(User).where(User.username == 'agent'))
    order_states = ['unpaid', 'paid', 'shipping', 'delivered', 'cancelled', 'refunding', 'refunded']
    products = ['无线降噪耳机', '智能电饭煲', '轻量跑步鞋', '保温杯', '机械键盘']
    for i in range(1, 51):
        order_id = f'TF2026{i:04d}'
        if not db.get(Order, order_id):
            state = order_states[(i - 1) % len(order_states)]
            db.add(Order(id=order_id, customer_id=f'C{i:03d}', product=products[(i - 1) % 5],
                         amount_cents=[29900, 39900, 25900, 9900, 49900][(i - 1) % 5], status=state,
                         facts={'synthetic': True, 'shipping_carrier': '模拟速递' if state in ('shipping', 'delivered') else None,
                                'payment_status': 'unpaid' if state == 'unpaid' else 'paid'}))
    db.flush()
    for i in range(1, 501):
        ticket_id = f'seed{i:028d}'
        if db.get(Ticket, ticket_id):
            continue
        order_number = (i - 1) % 50 + 1
        title, answer = FAQS[(i - 1) % 20]
        question = f'我想咨询{title}，订单目前应该怎么处理？'
        if i % 29 == 0:
            question = '商品起火了，需要立即处理安全投诉。'
        elif i % 11 == 0:
            question += '已经超时，我要投诉。'
        label = classify(question)
        status = ['new', 'new', 'replied', 'closed', 'escalated'][i % 5]
        db.add(Ticket(id=ticket_id, subject=title, content=question, customer_id=f'C{order_number:03d}',
                      order_id=f'TF2026{order_number:04d}', status=status, priority=label['priority'], intent=label['intent'],
                      assignee=agent.id if i % 3 == 0 else admin.id,
                      sent_text=f'【模拟历史人工回复】{answer}' if status in ('replied', 'closed') else None,
                      created_at=now() - timedelta(hours=500 - i)))
    if not db.scalar(select(WorkflowConfig.id).limit(1)):
        db.add(WorkflowConfig(config=DEFAULT_CONFIG))
    db.commit()
    return {'orders': 50, 'faqs': 20, 'historical_tickets': 500}


def write_fixtures():
    folder = ROOT / 'fixtures' / 'knowledge'
    folder.mkdir(parents=True, exist_ok=True)
    markdown = '# TicketFlow 电商服务政策（模拟企业）\n\n' + '\n\n'.join(f'## {q}\n{a}' for q, a in FAQS)
    (folder / '电商客服政策.md').write_text(markdown, encoding='utf-8')
    (folder / '物流补充说明.txt').write_text('物流异常处理\n\n物流超过48小时无更新时，可发起物流核查工单。请提供订单号，客服会核对实际发货及物流状态。', encoding='utf-8')
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    canvas = Canvas(str(folder / '售后审核流程.pdf'))
    canvas.setFont('STSong-Light', 14)
    canvas.drawString(50, 780, '售后审核流程（模拟企业政策）')
    canvas.drawString(50, 740, '退款申请须核对订单归属和实时状态，审核通过后原路退回。')
    canvas.showPage(); canvas.setFont('STSong-Light', 14)
    canvas.drawString(50, 780, '投诉升级流程')
    canvas.drawString(50, 740, '安全事件应立即升级主管；客服不能自行承诺赔偿金额。')
    canvas.save()
    evaluation = ROOT / 'fixtures' / 'evaluation'
    evaluation.mkdir(parents=True, exist_ok=True)
    queries = ['付款后多久能发出货？', '快递两天没更新怎么办？', '还没发货能申请退钱吗？', '退的钱什么时候到银行卡？',
               '签收第五天不喜欢商品还能退吗？', '买到坏的商品需要提供什么？', '退货快递费谁来付？', '尺寸不合适怎么换？',
               '公司报销怎么申请开票？', '发票抬头写错能改吗？', '付款失败但银行卡扣钱了怎么办？', '一笔订单扣了两次钱怎么办？',
               '包裹发出后还能换地址吗？', '为什么优惠券用不了？', '买完降价能补差额吗？', '想知道商品材质应该看哪里？',
               '显示签收可是我没收到怎么办？', '严重投诉由谁处理？', '电器起火了怎么处理？', '发货了还能取消订单吗？']
    (evaluation / 'retrieval.json').write_text(json.dumps([{'question': q, 'section': FAQS[i][0]} for i, q in enumerate(queries)], ensure_ascii=False, indent=2), encoding='utf-8')
    return folder


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--knowledge', action='store_true')
    args = parser.parse_args()
    with Session() as db:
        print(populate(db))
        folder = write_fixtures()
        if args.knowledge:
            from app.db import Document
            for file in folder.iterdir():
                doc = db.scalar(select(Document).where(Document.name == file.name))
                version = upload(db, 'seed', file.name, file.read_bytes(), doc.id if doc else None)
                print(file.name, version.state)
