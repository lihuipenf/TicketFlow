"""Mocked browser regressions for ticket detail races; never contacts the backend.

Run with Vite already serving the frontend:
  D:/CodexData/tools/webapp-testing/.venv/Scripts/python.exe scripts/ui_detail_races.py
"""

import argparse
import os
import time
from urllib.parse import parse_qs, urlsplit

for name, value in {
    'TEMP': 'D:/CodexData/temp',
    'TMP': 'D:/CodexData/temp',
    'NPM_CONFIG_CACHE': 'D:/CodexData/caches/npm',
    'PIP_CACHE_DIR': 'D:/CodexData/caches/pip',
    'UV_CACHE_DIR': 'D:/CodexData/caches/uv',
    'PLAYWRIGHT_BROWSERS_PATH': 'D:/CodexData/caches/playwright',
}.items():
    os.environ[name] = value

from playwright.sync_api import expect, sync_playwright


def ticket(ticket_id, *, running=False):
    return {
        'id': ticket_id,
        'subject': f'Mocked ticket {ticket_id.upper()}',
        'customer_id': 'mock-customer',
        'content': 'Synthetic browser test consultation',
        'status': 'pending_review',
        'priority': 'P2',
        'created_at': '2026-11-11T00:00:00',
        'revision': 1,
        'order': None,
        'events': [],
        'runs': [{'id': 'mock-job-a', 'state': 'running', 'steps': []}] if running else [],
        'draft': {
            'reply_text': f'Original draft {ticket_id.upper()}',
            'evidence_score': 90,
            'score_explanation': 'Synthetic evidence',
            'risk_flags': [],
            'citations': [],
        },
    }


class MockedTickets:
    """Each instance owns an isolated session and intercepts every API request."""

    def __init__(self, browser, base_url, *, hold_initial=False):
        self.context = browser.new_context(
            viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce',
            service_workers='block',
        )
        self.page = self.context.new_page()
        self.errors = []
        self.unexpected = []
        self.held = []
        self.a_requests = 0
        self.hold_initial = hold_initial
        self.a = ticket('a', running=not hold_initial)
        self.b = ticket('b')
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script(
            "sessionStorage.setItem('ticketflow-token', 'mocked-browser-test-token')"
        )
        self.page.route('**/api/v1/**', self.handle)
        self.page.goto(base_url.rstrip('/') + '/#/tickets')
        self.page.wait_for_load_state('networkidle')
        expect(self.page.locator('.queue-desktop .ticket-title')).to_have_count(2)

    def handle(self, route):
        request = route.request
        path = urlsplit(request.url).path.removeprefix('/api/v1')
        if request.method != 'GET':
            self.unexpected.append(f'Business mutation attempted: {request.method} {path}')
            route.fulfill(status=405, json={'detail': 'Writes forbidden in this test'})
            return
        if path == '/auth/me':
            data = {'id': 'mock-admin', 'username': 'admin', 'role': 'admin'}
        elif path == '/system/status':
            data = {'llm_configured': False}
        elif path == '/analytics/overview':
            data = {'total': 2, 'statuses': {'pending_review': 2}, 'priorities': {}}
        elif path == '/users':
            data = []
        elif path == '/tickets':
            data = {'items': [self.a, self.b], 'total': 2}
        elif path == '/tickets/a':
            self.a_requests += 1
            if self.hold_initial or self.a_requests > 1:
                self.held.append(route)
                return
            data = self.a
        elif path == '/tickets/b':
            data = self.b
        else:
            self.unexpected.append(f'Unmocked endpoint: {path}')
            route.fulfill(status=500, json={'detail': 'Endpoint not mocked'})
            return
        route.fulfill(json=data)

    def navigate(self, fragment):
        self.page.evaluate('(fragment) => { location.hash = fragment }', fragment)
        # Give Vue's hash watcher and DOM updates two browser frames to settle.
        self.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

    def wait_for_held_request(self):
        deadline = time.monotonic() + 10
        while not self.held:
            if time.monotonic() >= deadline:
                raise AssertionError('Expected a pending ticket A request within 10 seconds')
            self.page.wait_for_timeout(25)

    def release(self):
        self.held.pop(0).fulfill(json=self.a)
        # Includes the response's async Vue continuation; assertions cannot run early.
        self.page.wait_for_load_state('networkidle')

    def assert_clean(self):
        assert not self.unexpected, self.unexpected
        assert not self.errors, self.errors


def test_pending_detail_cancellation(browser, base_url):
    app = MockedTickets(browser, base_url, hold_initial=True)
    try:
        app.navigate('/tickets?ticket=a')
        app.wait_for_held_request()
        app.navigate('/tickets')
        app.release()
        fragment = urlsplit(app.page.url).fragment
        query = parse_qs(fragment.partition('?')[2])
        assert 'ticket' not in query, f'Canceled detail restored its URL: {fragment}'
        expect(app.page.get_by_role('dialog', name='工单处理与人工审核')).not_to_be_visible()
        app.assert_clean()
    finally:
        app.context.close()


def test_stale_poll_preserves_other_ticket_reply(browser, base_url):
    app = MockedTickets(browser, base_url)
    try:
        app.navigate('/tickets?ticket=a')
        expect(app.page.get_by_role('heading', name=app.a['subject'], exact=True)).to_be_visible()
        app.wait_for_held_request()  # A's first polling refresh remains in flight.
        app.navigate('/tickets?ticket=b')
        expect(app.page.get_by_role('heading', name=app.b['subject'], exact=True)).to_be_visible()
        editor = app.page.get_by_placeholder('编辑客户将收到的回复')
        edited_reply = 'Human edits for ticket B must survive the stale A poll.'
        editor.fill(edited_reply)
        app.release()
        expect(editor).to_have_value(edited_reply)
        expect(app.page.get_by_role('heading', name=app.b['subject'], exact=True)).to_be_visible()
        app.assert_clean()
    finally:
        app.context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:5173')
    args = parser.parse_args()
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for check in (test_pending_detail_cancellation, test_stale_poll_preserves_other_ticket_reply):
                try:
                    check(browser, args.base_url)
                    print(f'PASS: {check.__name__}')
                except Exception as error:
                    failures.append(check.__name__)
                    print(f'FAIL: {check.__name__}: {error}')
        finally:
            browser.close()
    if failures:
        raise SystemExit(f'Failed {len(failures)} mocked race regression(s): {", ".join(failures)}')
    print('PASS: both ticket detail races; isolated mocked sessions, no credentials or backend requests.')


if __name__ == '__main__':
    main()
