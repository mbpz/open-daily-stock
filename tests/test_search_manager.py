"""Tests for SearchManager — concurrent multi-provider fan-out & key rotation."""
import threading
import time
import pytest

from src.search_pkg.base import SearchResult, BaseSearchProvider
from src.search_pkg.manager import SearchManager


class _FakeProvider(BaseSearchProvider):
    """Provider stub that records call count and returns deterministic results."""

    def __init__(self, api_keys, results, delay=0.0, raise_on_call=False):
        super().__init__(api_keys)
        self._results = results
        self._delay = delay
        self._raise = raise_on_call
        self.call_count = 0
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return bool(self.api_keys)

    def search(self, query, **kwargs):
        with self._lock:
            self.call_count += 1
        if self._raise:
            raise RuntimeError("boom")
        if self._delay:
            time.sleep(self._delay)
        return list(self._results)


def _make_manager(*provider_specs):
    """Build a SearchManager pre-populated with given provider instances."""
    mgr = SearchManager.__new__(SearchManager)
    mgr.bocha_keys = []
    mgr.tavily_keys = []
    mgr.serpapi_keys = []
    mgr.providers = [spec["provider"] for spec in provider_specs]
    return mgr


def test_search_all_runs_providers_in_parallel():
    """search_all should run providers concurrently, not sequentially."""
    p1 = _FakeProvider(["k1"], [SearchResult("a", "u1", "s", "t1")], delay=0.3)
    p2 = _FakeProvider(["k2"], [SearchResult("b", "u2", "s", "t2")], delay=0.3)
    p3 = _FakeProvider(["k3"], [SearchResult("c", "u3", "s", "t3")], delay=0.3)
    mgr = _make_manager(
        {"provider": p1}, {"provider": p2}, {"provider": p3}
    )

    t0 = time.time()
    results = mgr.search_all("q", timeout=5.0)
    elapsed = time.time() - t0

    assert len(results) == 3
    # Sequential would take ~0.9s; parallel should be ~0.3s.
    assert elapsed < 0.7, f"search_all took {elapsed:.2f}s, expected concurrent"
    assert {r.title for r in results} == {"a", "b", "c"}


def test_search_all_dedupes_by_url():
    p1 = _FakeProvider(
        ["k1"],
        [SearchResult("a", "u1", "s1", "t1"), SearchResult("dup", "uX", "s", "t1")],
    )
    p2 = _FakeProvider(
        ["k2"],
        [SearchResult("b", "u2", "s", "t2"), SearchResult("dup2", "uX", "s", "t2")],
    )
    mgr = _make_manager({"provider": p1}, {"provider": p2})
    results = mgr.search_all("q")
    urls = [r.url for r in results]
    assert len(urls) == len(set(urls)), f"duplicate urls leaked: {urls}"
    assert urls.count("uX") == 1


def test_search_all_isolates_provider_failures():
    p1 = _FakeProvider(["k1"], [SearchResult("a", "u1", "s", "t1")])
    p2 = _FakeProvider(["k2"], [], raise_on_call=True)
    p3 = _FakeProvider(["k3"], [SearchResult("c", "u3", "s", "t3")])
    mgr = _make_manager(
        {"provider": p1}, {"provider": p2}, {"provider": p3}
    )
    results = mgr.search_all("q")
    titles = {r.title for r in results}
    assert titles == {"a", "c"}
    assert p2.call_count == 1  # still invoked once, error swallowed


def test_search_all_overall_timeout_cancels_pending():
    p1 = _FakeProvider(["k1"], [SearchResult("a", "u1", "s", "t1")])
    p2 = _FakeProvider(["k2"], [SearchResult("b", "u2", "s", "t2")], delay=2.0)
    mgr = _make_manager({"provider": p1}, {"provider": p2})
    t0 = time.time()
    results = mgr.search_all("q", timeout=0.3)
    elapsed = time.time() - t0
    # Should return the fast provider's result and bail before the slow one finishes.
    assert elapsed < 1.5, f"timeout didn't fire (elapsed={elapsed:.2f}s)"
    assert any(r.title == "a" for r in results)


def test_get_next_key_is_thread_safe():
    p = _FakeProvider(["k1", "k2", "k3"], [])
    seen = []

    def worker():
        for _ in range(100):
            seen.append(p.get_next_key())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 8 threads × 100 calls = 800 reads, all from {k1, k2, k3}.
    assert len(seen) == 800
    assert set(seen) == {"k1", "k2", "k3"}


def test_search_all_empty_providers_returns_empty():
    mgr = SearchManager(bocha_keys=[], tavily_keys=[], serpapi_keys=[])
    assert mgr.search_all("q") == []
