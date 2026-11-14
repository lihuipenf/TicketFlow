"""Exercise bounded ingress directly, without the multipart parser or disk uploads."""
import asyncio
import pytest


class UploadProbe:
    def __init__(self):
        self.calls = 0
        self.body = b''

    async def __call__(self, scope, receive, send):
        self.calls += 1
        while True:
            message = await receive()
            self.body += message.get('body', b'')
            if not message.get('more_body'):
                break
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})


async def request(app, chunks, headers=(), delay=0):
    scope = {'type': 'http', 'method': 'POST', 'path': '/api/v1/knowledge/documents',
             'root_path': '', 'headers': [(b'authorization', b'Bearer synthetic')] + list(headers)}
    sent, reads = [], []
    async def receive():
        if delay:
            await asyncio.sleep(delay)
        number = len(reads)
        reads.append(number)
        return {'type': 'http.request', 'body': chunks[number], 'more_body': number + 1 < len(chunks)}
    async def send(message):
        sent.append(message)
    await app(scope, receive, send)
    return next(m['status'] for m in sent if m['type'] == 'http.response.start'), reads


def guard(probe, **options):
    from app.ingress import UploadIngress
    return UploadIngress(probe, authorize=lambda token: None, max_request_bytes=64,
                         timeout_seconds=options.get('timeout_seconds', 1), max_concurrent=1)


def test_chunked_upload_limit_stops_before_parser_or_remaining_body():
    probe = UploadProbe()
    status, reads = asyncio.run(request(guard(probe), [b'a' * 40, b'b' * 40, b'not-read']))
    assert status == 413
    assert reads == [0, 1]
    assert probe.calls == 0


def test_valid_body_at_limit_is_replayed_exactly():
    probe = UploadProbe()
    assert asyncio.run(request(guard(probe), [b'a' * 32, b'b' * 32], [(b'content-length', b'64')]))[0] == 204
    assert probe.body == b'a' * 32 + b'b' * 32


@pytest.mark.parametrize('headers,status', [
    ([(b'content-length', b'65')], 413),
    ([(b'content-length', b'-1')], 400),
    ([(b'content-length', b'bad')], 400),
    ([(b'content-length', b'1'), (b'content-length', b'1')], 400),
    ([(b'content-length', b'1'), (b'transfer-encoding', b'chunked')], 400),
])
def test_invalid_or_oversized_lengths_do_not_receive_body(headers, status):
    probe = UploadProbe()
    actual, reads = asyncio.run(request(guard(probe), [b'x'], headers))
    assert actual == status
    assert reads == []
    assert probe.calls == 0


def test_declared_length_cannot_bypass_actual_byte_limit():
    probe = UploadProbe()
    assert asyncio.run(request(guard(probe), [b'a' * 65], [(b'content-length', b'1')]))[0] == 413
    assert probe.calls == 0


def test_slow_upload_times_out_before_parser():
    probe = UploadProbe()
    assert asyncio.run(request(guard(probe, timeout_seconds=0.01), [b'x'], delay=0.1))[0] == 408
    assert probe.calls == 0


def test_receive_deadline_does_not_interrupt_completed_upload_processing():
    class SlowProcessing(UploadProbe):
        async def __call__(self, scope, receive, send):
            await asyncio.sleep(0.03)
            await super().__call__(scope, receive, send)
    probe = SlowProcessing()
    assert asyncio.run(request(guard(probe, timeout_seconds=0.01), [b'x']))[0] == 204


def test_full_capacity_rejects_additional_upload_and_releases_after_cancel():
    async def scenario():
        probe = UploadProbe()
        app = guard(probe)
        entered, finish = asyncio.Event(), asyncio.Event()
        scope = {'type': 'http', 'method': 'POST', 'path': '/api/v1/knowledge/documents', 'headers': [(b'authorization', b'Bearer synthetic')]}
        async def receive():
            entered.set()
            await finish.wait()
            return {'type': 'http.request', 'body': b'x', 'more_body': False}
        async def send(message):
            pass
        first = asyncio.create_task(app(scope, receive, send))
        await entered.wait()
        assert (await request(app, [b'x'])) == (429, [])
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert (await request(app, [b'x']))[0] == 204
    asyncio.run(scenario())


@pytest.mark.parametrize('cancel', [False, True])
def test_abandoned_authentication_keeps_its_own_capacity_until_thread_exits(cancel):
    from threading import Event, Lock
    from app.ingress import UploadIngress
    async def scenario():
        started, release = Event(), Event()
        lock = Lock()
        live, maximum = 0, 0
        def authorize(token):
            nonlocal live, maximum
            with lock:
                live += 1
                maximum = max(maximum, live)
            started.set()
            try:
                release.wait(2)
            finally:
                with lock:
                    live -= 1
        app = UploadIngress(UploadProbe(), authorize=authorize, max_request_bytes=64,
                            timeout_seconds=0.05, max_concurrent=1)
        first = asyncio.create_task(request(app, [b'x']))
        try:
            while not started.is_set():
                await asyncio.sleep(0.001)
            if cancel:
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
            else:
                assert (await first)[0] == 408
            assert (await request(app, [b'x']))[0] == 429
            assert maximum == 1
        finally:
            release.set()
            if not first.done():
                await first
            while live:
                await asyncio.sleep(0.001)
        assert (await request(app, [b'x']))[0] == 204
    asyncio.run(scenario())
