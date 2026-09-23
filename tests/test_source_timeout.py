"""A source that answers too slowly is reported as a timeout, not as a defect.

Live run of 21.9.2026: `bfs_population` ran out of `RETRY_TOTAL_BUDGET` on a
cold STAT-TAB query and answered «Interner Fehler beim Abruf der
Bevölkerungsdaten». Measured against the source two days later, the same query
took 21.3s cold and 0.9s warm — nothing internal had failed. The model reads
«interner Fehler» as a bug in this server; the weekly issue read it the same
way.

Why the per-attempt timeout was NOT lowered is recorded next to
`HTTP_TIMEOUT`: an aborted request does not reliably warm the source's cache.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

import swiss_statistics_mcp.server as srv
from swiss_statistics_mcp.server import (
    BrowseCatalogInput,
    CompareCantonsInput,
    ConstructionActivityInput,
    ConstructionInvestmentInput,
    GetDataInput,
    GetEducationStatsInput,
    GetPopulationInput,
    GetTableMetadataInput,
    ListCommunesInput,
    LookupCommuneInput,
    PriceIndexInput,
    ResolveHistoricalCommuneInput,
    SearchTablesInput,
)

STAT_TAB = "BFS STAT-TAB"
AGVCH = "Gemeindeverzeichnis (AGVCH)"
CKAN = "opendata.swiss / BFS DAM"

# Every tool whose top-level handler can see a timeout, with the source it
# must name. `search_historical_series` is absent on purpose: its index build
# swallows every chapter failure and reports «HSSO-Katalog aktuell nicht
# erreichbar» before a timeout could reach the handler.
CASES = [
    (srv.bfs_browse_catalog, BrowseCatalogInput(), STAT_TAB),
    (srv.bfs_browse_catalog, BrowseCatalogInput(theme_code="15", limit=3), STAT_TAB),
    (srv.bfs_search_tables, SearchTablesInput(query="Schule"), STAT_TAB),
    (srv.bfs_get_table_metadata, GetTableMetadataInput(table_id="px-x-1504000000_173"), STAT_TAB),
    (srv.bfs_get_data, GetDataInput(table_id="px-x-1504000000_173"), STAT_TAB),
    (srv.bfs_education_stats, GetEducationStatsInput(topic="teachers"), STAT_TAB),
    (srv.bfs_population, GetPopulationInput(region="Zürich"), STAT_TAB),
    (
        srv.bfs_compare_cantons,
        CompareCantonsInput(table_id="px-x-1504000000_173", canton_values=["1", "2"]),
        STAT_TAB,
    ),
    (srv.bfs_construction_activity, ConstructionActivityInput(municipality_bfs=261), STAT_TAB),
    (
        srv.bfs_construction_investment,
        ConstructionInvestmentInput(level="kanton", code="ZH"),
        STAT_TAB,
    ),
    (
        srv.lookup_commune,
        LookupCommuneInput(name_or_bfs_number="295", valid_at_date="2025-01-01"),
        AGVCH,
    ),
    (
        srv.resolve_historical_commune,
        ResolveHistoricalCommuneInput(bfs_number=133, from_date="2000-01-01", to_date="2025-01-01"),
        AGVCH,
    ),
    (srv.list_communes, ListCommunesInput(canton="ZH", valid_at_date="2025-01-01"), AGVCH),
    (srv.bfs_price_index, PriceIndexInput(index="baupreisindex"), CKAN),
]
IDS = [f"{fn.__name__}-{i}" for i, (fn, _, _) in enumerate(CASES)]


@pytest.fixture(autouse=True)
def _clear_caches():
    """A cached answer never reaches the network, so it could never time out."""
    for cache in (
        srv._catalog_cache,
        srv._metadata_cache,
        srv._metadata_timestamps,
        srv._snapshot_cache,
        srv._hsso_index_cache,
        srv._price_index_cache,
    ):
        cache.clear()


def _raising(exc: BaseException):
    async def fake(_factory):
        raise exc

    return fake


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "params", "source"), CASES, ids=IDS)
async def test_every_tool_reports_the_budget_as_a_timeout(monkeypatch, tool, params, source):
    # The budget raises the builtin TimeoutError from `asyncio.timeout`.
    monkeypatch.setattr(srv, "_retrying_http", _raising(TimeoutError()))
    data = (await tool(params)).model_dump(exclude_none=True)
    assert data["error"].startswith("Zeitüberschreitung: ")
    assert source in data["error"]
    assert "Interner Fehler" not in data["error"]
    assert "erneuter Aufruf" in data["hint"]
    # The cold-cache explanation belongs to STAT-TAB, where it was measured.
    assert ("Cache" in data["hint"]) == (source == STAT_TAB)


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "params", "source"), CASES, ids=IDS)
async def test_httpx_own_timeout_is_a_timeout_too(monkeypatch, tool, params, source):
    monkeypatch.setattr(srv, "_retrying_http", _raising(httpx.ReadTimeout("slow")))
    data = (await tool(params)).model_dump(exclude_none=True)
    assert data["error"].startswith("Zeitüberschreitung: ")


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "params", "source"), CASES, ids=IDS)
async def test_anything_else_is_still_an_internal_error(monkeypatch, tool, params, source):
    # Counter-check: the new branch must not swallow real defects.
    monkeypatch.setattr(srv, "_retrying_http", _raising(ValueError("bug")))
    data = (await tool(params)).model_dump(exclude_none=True)
    assert not data["error"].startswith("Zeitüberschreitung")


@pytest.mark.asyncio
async def test_the_real_budget_ends_in_a_timeout_report(monkeypatch):
    """End to end through the real `_retrying_http`, as on 21.9.2026."""
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 0.2)

    async def slow_post(_url, _body):
        async def cold_query():
            await asyncio.sleep(8.0)  # far past the budget: the source is still computing

        return await srv._retrying_http(cold_query)

    monkeypatch.setattr(srv, "_post", slow_post)
    data = (await srv.bfs_population(GetPopulationInput(region="Zürich", year="2024"))).model_dump(
        exclude_none=True
    )
    assert data["error"].startswith("Zeitüberschreitung: BFS STAT-TAB")
    assert "rows" not in data
    # The cold-cache explanation belongs to STAT-TAB, where it was measured.
    assert "Cache" in data["hint"]


def test_the_message_names_the_budget_actually_in_force(monkeypatch):
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 40.0)
    assert "40 Sekunden" in srv._source_timeout("X")["error"]
