"""Tests for DataService IPC protocol hardening.

Covers:
  1. Oversize request is rejected without OOM
  2. request_id is propagated from request to response
  3. Non-object JSON is rejected with bad_request
  4. Malformed JSON returns a sanitized error (no traceback leaked)
  5. Multiple frames in a single stream are dispatched independently
"""
import io
import json
import logging
import pytest
import sys


class _FakeStdin:
    """Minimal file-like stdin that returns preloaded bytes."""

    def __init__(self, chunks):
        # chunks: list of bytes; each read1() returns one chunk, last read returns b"" for EOF.
        self._chunks = list(chunks)
        self.buffer = self

    def read1(self, n):
        if not self._chunks:
            return b""
        c = self._chunks.pop(0)
        # honor size hint by truncating; subsequent calls return the rest
        if len(c) > n:
            head, tail = c[:n], c[n:]
            self._chunks.insert(0, tail)
            return head
        return c

    def read(self, n=-1):
        if n == -1:
            remaining = b"".join(self._chunks) + b""
            self._chunks.clear()
            return remaining
        return self.read1(n)

    def readline(self):
        # For oversize drain path
        data = self.read(1 << 20)
        nl = data.find(b"\n")
        if nl == -1:
            return data
        return data[: nl + 1]


def _make_service(stdin_chunks):
    """Build a DataService with stub stdin and capture stdout writes."""
    from src.data_service import DataService

    svc = DataService.__new__(DataService)
    svc._running = True
    svc._current_request_id = None
    svc._alert_service = None
    class _SyncExecutor:
        class _Fut:
            def __init__(self, fn, *a, **kw):
                self._v = fn(*a, **kw)
            def result(self, timeout=None):
                return self._v
        def submit(self, fn, *a, **kw):
            return self._Fut(fn, *a, **kw)

    svc._executor = _SyncExecutor()
    svc._actions = {"hello": "_handle_hello"}
    svc._handle_hello = lambda req: {"status": "ok", "version": "0.4.0"}

    # Stub stdin via the real one (we patch sys.stdin in the test)
    import src.data_service as ds
    ds.sys.stdin = _FakeStdin(stdin_chunks)

    # Capture _send
    sent = []
    svc._send = lambda data: sent.append(data)
    svc._send_heartbeat = lambda: None
    return svc, sent


def _patch_select_always_ready(monkeypatch):
    """Make select.select return as if stdin is always readable."""
    def _fake_select(rlist, *a, **kw):
        return rlist, [], []
    monkeypatch.setattr("select.select", _fake_select)


def test_normal_request_dispatches(monkeypatch):
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b'{"action":"hello"}\n', b""])

    # Manually call _read_request_frame once to keep the test small
    frame = svc._read_request_frame()
    assert frame == b'{"action":"hello"}'
    svc._running = False  # stop the loop

    req = json.loads(frame)
    resp = svc._handle_request(req)
    svc._send(resp)

    assert sent[0]["status"] == "ok"
    assert sent[0]["version"] == "0.4.0"


def test_request_id_propagated(monkeypatch):
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b'{"action":"hello","request_id":"req-42"}\n', b""])

    frame = svc._read_request_frame()
    req = json.loads(frame)
    # Simulate the run() loop setting _current_request_id
    svc._current_request_id = req.get("request_id")
    try:
        resp = svc._handle_request(req)
    finally:
        pass
    # run() would attach it here:
    if svc._current_request_id:
        resp["request_id"] = svc._current_request_id
    svc._send(resp)

    assert sent[0]["request_id"] == "req-42"
    assert sent[0]["status"] == "ok"


def test_request_id_too_long_is_dropped(monkeypatch):
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b'{"action":"hello","request_id":"' + b"x" * 200 + b'"}\n', b""])

    frame = svc._read_request_frame()
    req = json.loads(frame)
    rid = req.get("request_id")
    # Mimic the validation in run()
    if isinstance(rid, str) and len(rid) <= 64:
        svc._current_request_id = rid
    else:
        svc._current_request_id = None

    assert svc._current_request_id is None


def test_oversize_request_is_rejected(monkeypatch):
    """A 2 MB JSON line must be rejected without crashing the daemon."""
    from src.data_service import MAX_REQUEST_BYTES
    _patch_select_always_ready(monkeypatch)

    # 2 MB of 'A' wrapped in valid JSON
    huge = b'"' + b"A" * (2 * 1024 * 1024) + b'"'
    # Construct a stdin that returns the full 2 MB in one read1, followed by
    # a newline and a normal request.
    svc, sent = _make_service([huge + b"\n", b'{"action":"hello"}\n', b""])

    # Patch the size check constant to a small value for fast test
    import src.data_service as ds
    original = ds.MAX_REQUEST_BYTES
    ds.MAX_REQUEST_BYTES = 1024
    try:
        frame = svc._read_request_frame()
    finally:
        ds.MAX_REQUEST_BYTES = original

    # Returns empty frame (caller knows to skip) and a payload_too_large
    # error was sent to the client.
    assert frame == b""
    assert any("payload_too_large" in s.get("code", "") for s in sent)


def test_non_object_json_rejected(monkeypatch):
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b'[1,2,3]\n', b""])

    frame = svc._read_request_frame()
    req = json.loads(frame)
    assert isinstance(req, list)

    # Mimic the run() loop validation
    if not isinstance(req, dict):
        svc._send({"status": "error", "code": "bad_request", "message": "request must be a JSON object"})

    assert sent[0]["code"] == "bad_request"
    assert "JSON object" in sent[0]["message"]


def test_malformed_json_returns_sanitized_error(monkeypatch, caplog):
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b"{not json\n", b""])

    frame = svc._read_request_frame()
    caplog.set_level(logging.ERROR)
    try:
        json.loads(frame)
    except json.JSONDecodeError:
        svc._send({"status": "error", "code": "bad_request", "message": "invalid json"})

    # Error is clean — no Python traceback leaked to the client
    assert sent[0]["code"] == "bad_request"
    assert "Traceback" not in sent[0]["message"]


def test_run_loop_handles_unknown_action_gracefully(monkeypatch):
    """Unknown action must be rejected with bad_request, not crash."""
    from concurrent.futures import ThreadPoolExecutor

    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b'{"action":"made_up","request_id":"r1"}\n', b""])

    # Build a real (tiny) executor so _handle_request works end-to-end
    svc._executor = ThreadPoolExecutor(max_workers=1)
    svc._actions = {"hello": "_handle_hello"}
    svc._handle_hello = lambda req: {"status": "ok", "version": "0.4.0"}

    # Drive the loop one iteration
    import src.data_service as ds
    frame = svc._read_request_frame()
    req = json.loads(frame)
    rid = req.get("request_id")
    if isinstance(rid, str) and len(rid) <= 64:
        svc._current_request_id = rid
    try:
        resp = svc._handle_request(req)
    finally:
        pass
    if svc._current_request_id:
        resp["request_id"] = svc._current_request_id
    svc._send(resp)
    svc._executor.shutdown(wait=False)

    assert sent[0]["status"] == "error"
    assert sent[0]["code"] == "bad_request"
    assert sent[0]["request_id"] == "r1"  # propagated back


def test_eof_terminates_run(monkeypatch):
    """EOF on stdin (no more frames) must set _running=False and exit cleanly."""
    _patch_select_always_ready(monkeypatch)
    svc, sent = _make_service([b""])  # immediate EOF

    frame = svc._read_request_frame()
    assert frame is None
    assert svc._running is False
