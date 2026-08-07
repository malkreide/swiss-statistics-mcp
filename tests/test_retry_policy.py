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

import swiss_statistics_mcp.server as srv

URL = "https://example.test/x"


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
    monkeypatch.setattr(srv, "RETRY_WAIT_MAX", 100.0)
    hinted = srv._retry_wait(_state(1, _err(503, "30")))
    curve = srv._retry_wait(_state(1, httpx.ConnectError("x")))
    assert hinted >= 30.0 > curve


def test_the_cap_is_a_real_bound_not_a_midpoint():
    # Jitter is random — one draw proves nothing.
    for attempt in range(1, 9):
        for _ in range(25):
            assert srv._retry_wait(_state(attempt, None)) <= srv.RETRY_WAIT_MAX
            assert srv._retry_wait(_state(attempt, _err(429, "86400"))) <= srv.RETRY_WAIT_MAX


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
    deliberately, and it is the only one here that does.

    It also shows why `stop_after_delay` would not have been enough: tenacity
    declines to start a *new* attempt past the delay, but cannot cut one that
    is already running, and one slow attempt is exactly this failure.
    """
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 0.05)

    async def _slow():
        await asyncio.sleep(0.30)
        return {"ok": True}

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await srv._retrying_http(_slow)
    assert time.monotonic() - started < 0.25, "HTTP_TIMEOUT is not a budget"


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
