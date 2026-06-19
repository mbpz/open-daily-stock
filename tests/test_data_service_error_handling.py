"""Tests for DataService error sanitization and request_id behavior."""
import logging
import pytest

from src.data_service import (
    DataService,
    DataServiceError,
    BadRequestError,
    NotFoundError,
    UpstreamError,
    _safe_call,
)


def _handler_ok(req):
    return {"status": "ok", "data": [1, 2, 3]}


def _handler_known(req):
    raise BadRequestError("missing required field 'code'")


def _handler_unknown(req):
    raise RuntimeError("/Users/secret/path/file.py: SQLite Error: no such column: foo")


def _handler_chain(req):
    raise NotFoundError(f"stock not found: {req.get('code', '?')}")


def test_safe_call_passes_through_ok():
    out = _safe_call(_handler_ok, {"action": "test"})
    assert out == {"status": "ok", "data": [1, 2, 3]}


def test_safe_call_known_error_returns_code_and_safe_message():
    out = _safe_call(_handler_known, {"action": "analyze"})
    assert out["status"] == "error"
    assert out["code"] == "bad_request"
    assert "missing required field" in out["message"]
    # No internal stack info leaked.
    assert "Traceback" not in out["message"]


def test_safe_call_unknown_exception_is_sanitized(caplog):
    caplog.set_level(logging.ERROR)
    out = _safe_call(_handler_unknown, {"action": "analyze"})
    assert out["status"] == "error"
    assert out["code"] == "internal_error"
    assert "request_id" in out
    # Original internal details (file path, SQL) MUST NOT leak to the response.
    assert "/Users/secret" not in out["message"]
    assert "SQLite" not in out["message"]
    # But the original traceback is captured in logs.
    assert any("request_id=" in rec.message for rec in caplog.records)
    # The request_id in the response should match what's in the log.
    log_record = next(r for r in caplog.records if "request_id=" in r.message)
    assert out["request_id"] in log_record.message


def test_safe_call_each_request_gets_unique_id(caplog):
    caplog.set_level(logging.ERROR)
    ids = set()
    for _ in range(5):
        out = _safe_call(_handler_unknown, {"action": "analyze"})
        ids.add(out["request_id"])
    assert len(ids) == 5  # all unique


class _SyncExecutor:
    """Minimal executor stub: submit() runs the callable synchronously and
    returns a Future-like object with .result(timeout=...)."""

    class _Fut:
        def __init__(self, fn, *a, **kw):
            self._v = fn(*a, **kw)
        def result(self, timeout=None):
            return self._v

    def submit(self, fn, *a, **kw):
        return self._Fut(fn, *a, **kw)


def _make_svc(action, handler):
    svc = DataService.__new__(DataService)
    svc._executor = _SyncExecutor()
    svc._actions = {action: "_h"}
    svc._h = handler
    return svc


def test_dispatch_unknown_action_returns_bad_request_code():
    svc = _make_svc("dummy", _handler_ok)
    out = svc._handle_request({"action": "totally_made_up"})
    assert out["status"] == "error"
    assert out["code"] == "bad_request"
    assert "totally_made_up" in out["message"]


def test_dispatch_known_error_includes_stable_code():
    svc = _make_svc("test_known", _handler_known)
    out = svc._handle_request({"action": "test_known"})
    assert out["code"] == "bad_request"


def test_dispatch_unexpected_error_never_leaks_internals(caplog):
    caplog.set_level(logging.ERROR)
    svc = _make_svc("test_bug", _handler_unknown)
    out = svc._handle_request({"action": "test_bug"})
    assert out["code"] == "internal_error"
    assert "request_id" in out
    blob = str(out)
    assert "/Users/secret" not in blob
    assert "SQLite" not in blob
