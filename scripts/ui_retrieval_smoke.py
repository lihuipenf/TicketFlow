"""Verify retrieval UI with real local indexes; never calls the reply generation model."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
out=ROOT/'data/verification/ui-upgrade/after';out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:5173/#/knowledge')
 page.get_by_placeholder('请输入密码').fill(env['ADMIN_PASSWORD'].strip('"\''))
 page.get_by_role('button',name='进入工作台').click()
 expect(page.get_by_role('heading',name='知识库管理',exact=True)).to_be_visible()
 expect(page.locator('.doc-row').first).to_be_visible()
 page.get_by_role('button',name='测试混合检索',exact=True).click()
 expect(page.get_by_text('命中',exact=True)).to_be_visible(timeout=180000)
 expect(page.locator('.el-tabs .evidence-card').first).to_be_visible()
 expect(page.locator('.el-tabs .evidence-card').first).to_contain_text('退款')
 page.screenshot(path=str(out/'knowledge-retrieval.png'),full_page=True)
 page.get_by_role('tab',name='向量候选',exact=True).click()
 expect(page.get_by_text('余弦',exact=False).first).to_be_visible()
 page.get_by_role('tab',name='BM25 候选',exact=True).click()
 expect(page.locator('.el-tab-pane').filter(visible=True).locator('.timeline-row').first).to_be_visible()
 assert not errors,errors
 print('PASS: real local hybrid retrieval, fused evidence and sources, vector and BM25 candidates; no reply model call or human review changes.')
 browser.close()
