"""A STAT-TAB query that outlives the caller's budget is finished, not dropped.

Live suite of 14.10.2026: the population query timed out at 25s, the repeat the
hint asks for timed out again at 25s, and a third call a few minutes later came
back in 0.9s. STAT-TAB had finished the query in between — the answer existed,
but both calls had cut their request and thrown it away. Cold, the same query
took 36.1s that morning; no budget a 30s client allows can cover it.

So `_post` runs the request as a task and only *waits* within the budget. These
tests pin what that buys and what it must not cost: a later call gets the
result without a second request, and a result that reached its caller is not
kept — freshness is what it was before.

Real clock, small budgets: a fake clock that only moves while sleeping could
not refute a claim about wall time.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
import respx

import swiss_statistics_mcp.server as srv

URL = "https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0102010000_101/px-x-0102010000_101.px"
BODY = {"query": [{"code": "Jahr", "selection": {"filter": "item", "values": ["2024"]}}]}
OTHER = {"query": [{"code": "Jahr", "selection": {"filter": "item", "values": ["2023"]}}]}

BUDGET = 0.2  # the caller's patience
SLOW = 1.0  # the cold query: far past the budget, well inside the detached one


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    srv._inflight.clear()
    srv._detached_results.clear()
    srv._abandoned.clear()
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", BUDGET)
    monkeypatch.setattr(srv, "DETACHED_BUDGET", 5.0)
    yield
    for task in list(srv._inflight.values()):
        task.cancel()
    srv._inflight.clear()
    srv._detached_results.clear()


class _Source:
    """Stands in for one POST attempt; counts how often the source is asked."""

    def __init__(self, delay: float = SLOW, fail: BaseException | None = None):
        self.delay = delay
        self.fail = fail
        self.requests = 0

    async def __call__(self, url, body):
        self.requests += 1
        await asyncio.sleep(self.delay)
        if self.fail is not None:
            raise self.fail
        return {"value": body["query"][0]["selection"]["values"][0], "n": self.requests}


@pytest.fixture
def source(monkeypatch):
    src = _Source()
    monkeypatch.setattr(srv, "_post_once", src)
    return src


async def test_the_caller_still_gets_a_timeout_within_its_budget(source):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)
    assert loop.time() - t0 < SLOW  # the budget, not the source, ended the call


async def test_the_next_call_collects_the_result_without_asking_again(source):
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)
    await asyncio.sleep(SLOW)  # the source finishes while nobody waits
    assert await srv._post(URL, BODY) == {"value": "2024", "n": 1}
    assert source.requests == 1


async def test_a_call_while_the_query_runs_joins_it(monkeypatch, source):
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)  # gives up at 0.2s; the query needs 1.0s
    assert srv._inflight  # still running, nobody waiting
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 5.0)
    assert await srv._post(URL, BODY) == {"value": "2024", "n": 1}
    assert source.requests == 1  # joined, not started anew


async def test_identical_concurrent_calls_share_one_request(monkeypatch, source):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    a, b = await asyncio.gather(srv._post(URL, BODY), srv._post(URL, BODY))
    assert a == b
    assert source.requests == 1


async def test_different_queries_do_not_share(monkeypatch, source):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    a, b = await asyncio.gather(srv._post(URL, BODY), srv._post(URL, OTHER))
    assert (a["value"], b["value"]) == ("2024", "2023")
    assert source.requests == 2


async def test_a_delivered_result_is_not_kept(monkeypatch, source):
    # Freshness unchanged: an answer that reached its caller is not a cache entry.
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    await srv._post(URL, BODY)
    await srv._post(URL, BODY)
    assert source.requests == 2
    assert srv._detached_results == {}


async def test_an_uncollected_result_expires(monkeypatch, source):
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)
    await asyncio.sleep(SLOW)
    monkeypatch.setattr(srv, "DETACHED_RESULT_TTL", 0.0)
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    assert (await srv._post(URL, BODY))["n"] == 2
    assert source.requests == 2


async def test_uncollected_results_are_bounded(monkeypatch, source):
    monkeypatch.setattr(srv, "DETACHED_MAX_RESULTS", 2)
    source.delay = 0.0
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    for year in ("1", "2", "3"):
        body = {"query": [{"code": "Jahr", "selection": {"filter": "item", "values": [year]}}]}
        task = asyncio.create_task(srv._post_detached(URL, body, srv._query_key(URL, body)))
        await task
    assert len(srv._detached_results) == 2


async def test_the_detached_budget_bounds_the_background(monkeypatch, source):
    monkeypatch.setattr(srv, "DETACHED_BUDGET", 0.3)
    source.delay = 60.0  # a source that never answers
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)
    await asyncio.sleep(0.4)
    assert srv._inflight == {}  # the task gave up on its own
    assert srv._detached_results == {}


async def test_a_failure_nobody_awaited_is_logged_and_not_kept(monkeypatch, source, caplog):
    req = httpx.Request("POST", URL)
    source.fail = httpx.HTTPStatusError(
        "400", request=req, response=httpx.Response(400, request=req)
    )
    with pytest.raises(TimeoutError):
        await srv._post(URL, BODY)
    with caplog.at_level(logging.WARNING, logger="swiss_statistics_mcp"):
        await asyncio.sleep(SLOW + 0.1)
    assert "detached STAT-TAB query failed" in caplog.text
    assert srv._inflight == {} and srv._detached_results == {}
    source.fail, source.delay = None, 0.0
    assert (await srv._post(URL, BODY))["n"] == 2  # next call starts afresh


async def test_a_failure_still_reaches_a_caller_who_waits(monkeypatch, source, caplog):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 2.0)
    req = httpx.Request("POST", URL)
    source.fail = httpx.HTTPStatusError(
        "400", request=req, response=httpx.Response(400, request=req)
    )
    source.delay = 0.0
    with caplog.at_level(logging.WARNING, logger="swiss_statistics_mcp"):
        with pytest.raises(httpx.HTTPStatusError):
            await srv._post(URL, BODY)
        await asyncio.sleep(0)  # let the done-callback run
    # The caller got it raised; the tool reports it. No second line for a 400.
    assert "detached STAT-TAB query failed" not in caplog.text


async def test_a_cancelled_caller_counts_as_gone(monkeypatch, source, caplog):
    # The client may cancel the tool call instead of letting the budget run out.
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 5.0)
    req = httpx.Request("POST", URL)
    source.fail = httpx.HTTPStatusError(
        "400", request=req, response=httpx.Response(400, request=req)
    )
    caller = asyncio.create_task(srv._post(URL, BODY))
    await asyncio.sleep(0.1)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert srv._inflight  # the query was not cancelled with its caller
    with caplog.at_level(logging.WARNING, logger="swiss_statistics_mcp"):
        await asyncio.sleep(SLOW + 0.1)
    assert "detached STAT-TAB query failed" in caplog.text


async def test_a_single_attempt_may_take_the_whole_detached_budget(monkeypatch):
    # A cold query sends nothing until it is computed: an attempt cut at
    # HTTP_TIMEOUT would just be the 25s cut again, one level down. Read off the
    # request httpx actually sends, not off a patched `httpx.AsyncClient` —
    # patching the foreign module would change it for the whole process.
    monkeypatch.setattr(srv, "DETACHED_BUDGET", 99.0)
    with respx.mock:
        route = respx.post(URL).mock(return_value=httpx.Response(200, json={"ok": 1}))
        assert await srv._post_once(URL, BODY) == {"ok": 1}
    read = route.calls.last.request.extensions["timeout"]["read"]
    assert read == 99.0  # the detached budget, not HTTP_TIMEOUT (30s)
