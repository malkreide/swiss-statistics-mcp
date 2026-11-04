"""Tests for the retry policy against the upstream (ARCH-014).

A portfolio run of the audit catalogue on 2026-08-07 read `_retrying_http` by
hand. What it retries was already right — 5xx, 429 and network errors, other
4xx surfaced immediately. Three properties were missing, and all three are
consequences of `wait_exponential`: no jitter, no `Retry-After`, no bound on
the call as a whole.

Every property has a counter-check. The previous implementation is the honest
thing to measure against, because it was in production until this branch.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace

import httpx
import pytest
import respx
from fixture_data import fixture_json

import swiss_statistics_mcp.server as srv

URL = "https://example.test/x"

# Wall-clock numbers for the deadline test below, spread far enough apart that
# scheduler jitter cannot move the outcome. Measured on 3.11 over 15 runs of
# that test's own body, through pytest so every fixture is in place:
# 0.0507-0.0509s against a 0.05s budget. Unlike the sibling servers there is no
# setup to move out of the way — `_retrying_http` drives a plain coroutine
# factory, no client is built — so the window already holds the budget and
# nothing else. What was missing is absolute room: the old bound of 0.25s left
# 0.199s, and CI jitter is absolute, not proportional. In swiss-efv-mcp a
# loaded runner turned 0.105s into 0.55s on 2026-08-21 and tore the same
# assertion there. Raising the budget does not shrink that stall, it makes the
# stall small *relative to* what is measured.
_BUDGET = 0.5
_CUT_BY = 2.5
_SLOW_RESPONSE = 8.0


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    # The request instance belongs on it: without one, `raise_for_status()`
    # raises RuntimeError instead of the HTTPStatusError the code branches on,
    # and the test would silently measure the wrong path.
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", URL), json={})


def _err(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    resp = _resp(status, retry_after)
    return httpx.HTTPStatusError("x", request=resp.request, response=resp)


def _state(attempt: int, exc: BaseException | None):
    """A minimal stand-in for tenacity's RetryCallState."""
    outcome = SimpleNamespace(exception=lambda: exc) if exc is not None else None
    return SimpleNamespace(attempt_number=attempt, outcome=outcome)


# --- Retry-After: read at all, and both RFC 9110 forms -----------------------


def test_retry_after_reads_delta_seconds():
    assert srv._parse_retry_after(_err(429, "120")) == 120.0


def test_retry_after_reads_an_http_date():
    when = datetime.now(UTC) + timedelta(seconds=60)
    got = srv._parse_retry_after(_err(503, format_datetime(when, usegmt=True)))
    assert got is not None
    assert 55 <= got <= 61


def test_retry_after_treats_a_past_date_as_now():
    when = datetime.now(UTC) - timedelta(hours=1)
    assert srv._parse_retry_after(_err(503, format_datetime(when, usegmt=True))) == 0.0


def test_retry_after_reads_a_naive_date_as_gmt_not_local():
    when = datetime.now(UTC) + timedelta(seconds=30)
    got = srv._parse_retry_after(_err(503, when.strftime("%a, %d %b %Y %H:%M:%S")))
    assert got is not None
    assert 25 <= got <= 31


@pytest.mark.parametrize("raw", ["", "   ", "soon", "not-a-date"])
def test_an_unreadable_retry_after_falls_back_instead_of_crashing(raw):
    assert srv._parse_retry_after(_err(429, raw)) is None


# --- The 429 STAT-TAB really sends (tests/fixtures/pxweb_429.json) -----------
#
# Everything above feeds the parser headers this file made up. The recording is
# what the source answered on 3.11.2026 when its declared limit (50 calls per
# 15 s) was exceeded on purpose: `Retry-After: 15`, delta-seconds, plus a JSON
# body. Recorded by scripts/record_pxweb_429.py, which also logged what the
# retries the server makes today got back (429 at +4.3 s and +8.4 s, 200 after
# waiting the 15 s).


def _recorded_429() -> httpx.HTTPStatusError:
    rec = fixture_json("pxweb_429.json")
    throttled = rec["throttled"]
    resp = httpx.Response(
        throttled["status"],
        headers=throttled["headers"],
        content=throttled["body"].encode("utf-8"),
        request=httpx.Request("GET", rec["_provenance"]["url"]),
    )
    return httpx.HTTPStatusError("x", request=resp.request, response=resp)


def test_the_recorded_stat_tab_429_is_retried():
    assert srv._is_transient(_recorded_429())


def test_the_recorded_stat_tab_429_is_read_as_15_seconds():
    # The value the source sent, in the form it sent it. If a re-recording shows
    # another number or an HTTP-date, the source changed, and this should say so.
    assert srv._parse_retry_after(_recorded_429()) == 15.0


# --- What the ladder does with it: wait in full if it fits, else stop -------
#
# The recording settled it: capped at RETRY_WAIT_MAX, the 15 s became 4 s, and
# every retry landed inside the block. A pause the budget holds is now waited in
# full (A); one it cannot hold is not waited for at all, and the tool says how
# long the source asked for (B).


def test_a_retry_after_that_fits_is_waited_in_full_not_capped():
    draws = [srv._retry_wait(_state(1, _recorded_429()), remaining=25.0) for _ in range(50)]
    assert min(draws) >= 15.0 > srv.RETRY_WAIT_MAX, sorted(draws)[:3]


def test_the_jitter_does_not_push_a_fitting_hint_past_the_budget():
    # 17.5 s left, 2 s reserve: 15.5 s is the latest the wait may end.
    draws = [srv._retry_wait(_state(1, _recorded_429()), remaining=17.5) for _ in range(50)]
    assert all(15.0 <= d <= 15.5 for d in draws), (min(draws), max(draws))


async def test_a_retry_after_that_fits_is_honoured_then_answered(monkeypatch):
    # Real time, on purpose: the claim is about how long the ladder waited.
    # RETRY_WAIT_MAX at 0.5 s is what a capped hint would have become.
    monkeypatch.setattr(srv, "RETRY_WAIT_MAX", 0.5)
    calls: list[float] = []

    async def _factory():
        calls.append(time.monotonic())
        if len(calls) == 1:
            raise _err(429, "1")
        return {"ok": True}

    assert await srv._retrying_http(_factory) == {"ok": True}
    assert len(calls) == 2
    assert calls[1] - calls[0] >= 1.0, f"came back after {calls[1] - calls[0]:.2f}s"


async def test_a_retry_after_past_the_budget_stops_at_once(monkeypatch):
    # The recorded 429 asks for 15 s; with 10 s of budget it cannot be honoured,
    # and every attempt before then would be refused again.
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 10.0)
    calls: list[int] = []

    async def _factory():
        calls.append(1)
        raise _recorded_429()

    started = time.monotonic()
    with pytest.raises(httpx.HTTPStatusError) as raised:
        await srv._retrying_http(_factory)
    assert raised.value.response.status_code == 429
    assert len(calls) == 1, "an attempt inside the block is refused again"
    assert time.monotonic() - started < 1.0


async def test_after_one_honoured_pause_the_next_that_no_longer_fits_stops(monkeypatch):
    # 3.5 s of budget: the first 1 s pause fits (1 <= 3.5 - 2), the second, from
    # about 1.1 s in, does not. Two calls, then the status error — no third.
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 3.5)
    calls: list[int] = []

    async def _factory():
        calls.append(1)
        raise _err(429, "1")

    started = time.monotonic()
    with pytest.raises(httpx.HTTPStatusError):
        await srv._retrying_http(_factory)
    elapsed = time.monotonic() - started
    assert len(calls) == 2
    assert 1.0 <= elapsed < 2.0, elapsed


# --- What the tool tells the caller ------------------------------------------


@respx.mock
async def test_the_tool_names_the_pause_the_source_asked_for(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 10.0)
    rec = fixture_json("pxweb_429.json")
    throttled = rec["throttled"]
    route = respx.get(f"{srv.BFS_API_BASE}/de/px-x-1504000000_173/px-x-1504000000_173.px").mock(
        return_value=httpx.Response(
            throttled["status"], headers=throttled["headers"], content=throttled["body"]
        )
    )
    srv._metadata_cache.clear()

    result = await srv.bfs_get_table_metadata(
        srv.GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
    )
    data = result.model_dump(exclude_none=True)
    assert data["error"].startswith("Rate-Limit: BFS STAT-TAB"), data
    assert "15 Sekunden" in data["hint"], data
    assert route.call_count == 1


def test_without_a_retry_after_the_tool_keeps_its_own_message():
    assert srv._source_asks_to_wait(_err(429), "X") is None
    assert srv._source_asks_to_wait(_err(500, "15"), "X") is None


def test_a_503_with_retry_after_is_not_called_a_rate_limit():
    got = srv._source_asks_to_wait(_err(503, "30"), "Das Gemeindeverzeichnis (AGVCH)")
    assert got is not None
    assert "Rate-Limit" not in got["error"] and "HTTP 503" in got["error"]
    assert "30 Sekunden" in got["hint"]


def test_retry_after_is_ignored_where_it_means_nothing():
    assert srv._parse_retry_after(_err(500, "120")) is None
    assert srv._parse_retry_after(httpx.ConnectError("no response attached")) is None
    assert srv._parse_retry_after(None) is None


# --- Jitter, and the cap that has to come after it ---------------------------


def test_the_wait_is_spread_not_deterministic():
    draws = {srv._retry_wait(_state(1, None)) for _ in range(50)}
    assert len(draws) > 1, "wait_exponential is identical for every client in an outage"


def test_a_retry_after_wait_is_spread_one_sided():
    draws = [srv._retry_wait(_state(1, _err(429, "2"))) for _ in range(50)]
    assert len(set(draws)) > 1
    assert all(2.0 <= d <= 2.5 for d in draws), sorted(draws)[:3]


def test_a_retry_after_beats_the_curve(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
    hinted = srv._retry_wait(_state(1, _err(503, "30")), remaining=100.0)
    curve = srv._retry_wait(_state(1, httpx.ConnectError("x")))
    assert hinted >= 30.0 > curve


def test_the_cap_is_a_real_bound_not_a_midpoint():
    # Jitter is random — one draw proves nothing. The curve is capped by
    # RETRY_WAIT_MAX; a Retry-After by what is left of the budget.
    for attempt in range(1, 9):
        for _ in range(25):
            assert srv._retry_wait(_state(attempt, None)) <= srv.RETRY_WAIT_MAX
            hinted = srv._retry_wait(_state(attempt, _err(429, "86400")), remaining=10.0)
            assert hinted <= 10.0 - srv.RETRY_AFTER_ATTEMPT_RESERVE


def test_capping_before_the_jitter_would_not_have_been_a_bound():
    """Counter-check for the ordering, so the test above is known to fail."""
    broken = min(srv.RETRY_WAIT_INITIAL * 2**7, srv.RETRY_WAIT_MAX) * 1.5
    assert broken > srv.RETRY_WAIT_MAX


def test_the_module_globals_are_read_at_call_time(monkeypatch):
    """Existing tests lower RETRY_WAIT_INITIAL with monkeypatch.

    A wait bound at import would ignore them and the suite would start sleeping
    for real again.
    """
    monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
    assert srv._retry_wait(_state(1, None)) < 0.01


# --- What is retried (pinning what was already right) ------------------------


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_statuses_are_retryable(status):
    assert srv._is_transient(_err(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retryable(status):
    assert srv._is_transient(_err(status)) is False


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError("refused"),
        httpx.ReadError("cut"),
        httpx.WriteError("cut"),
        httpx.ConnectTimeout("slow"),
    ],
)
def test_network_errors_are_retryable(exc):
    assert srv._is_transient(exc) is True


async def test_a_transient_error_is_actually_retried(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
    calls: list[int] = []

    async def _factory():
        calls.append(1)
        if len(calls) == 1:
            raise _err(503)
        return {"ok": True}

    assert await srv._retrying_http(_factory) == {"ok": True}
    assert len(calls) == 2


async def test_a_client_error_is_surfaced_immediately(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
    calls: list[int] = []

    async def _factory():
        calls.append(1)
        raise _err(404)

    with pytest.raises(httpx.HTTPStatusError):
        await srv._retrying_http(_factory)
    assert len(calls) == 1, "a third attempt does not turn a 404 into a 200"


# --- The budget, measured on the wall clock ----------------------------------


async def test_a_slow_response_is_cut_by_the_wall_clock_deadline(monkeypatch):
    """The assertion a fake clock cannot refute.

    A clock that only advances when something sleeps cannot disprove a claim
    about *real* time: the code that ignores the wall clock never sleeps, so no
    time passes and the broken version stays green. This test sleeps for real —
    deliberately, as do the two that wait a real `Retry-After` above.

    It also shows why `stop_after_delay` would not have been enough: tenacity
    declines to start a *new* attempt past the delay, but cannot cut one that
    is already running, and one slow attempt is exactly this failure.

    The margins are wide on purpose — see `_BUDGET` above for the measurement
    that set them.
    """
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", _BUDGET)

    async def _slow():
        await asyncio.sleep(_SLOW_RESPONSE)
        return {"ok": True}

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await srv._retrying_http(_slow)
    elapsed = time.monotonic() - started

    # Two-sided on purpose. The upper bound is the guarantee: a call that would
    # have taken _SLOW_RESPONSE was cut. The lower bound says the cut came from
    # the budget rather than from something failing straight away — a deadline
    # computed wrong sails through an upper bound alone.
    assert elapsed >= _BUDGET / 2, f"cut too early to be the budget: {elapsed:.3f}s"
    assert elapsed < _CUT_BY, f"HTTP_TIMEOUT is not a budget: {elapsed:.2f}s"


async def test_the_budget_bounds_the_whole_ladder_not_one_attempt(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 0.15)
    monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)

    async def _always_slow():
        await asyncio.sleep(0.08)
        raise _err(503)

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await srv._retrying_http(_always_slow)
    elapsed = time.monotonic() - started
    assert elapsed < 0.4, elapsed
