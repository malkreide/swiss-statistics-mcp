"""
Tests for swiss-statistics-mcp.

Three tiers:
  - Unit tests (fast, no network)
  - Integration tests (mock HTTP)
  - Live smoke tests (real API, marked separately)
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear module-level caches between tests so cache state from one test
    cannot mask a mock in the next."""
    from swiss_statistics_mcp.server import (
        _catalog_cache,
        _hsso_index_cache,
        _metadata_cache,
        _metadata_timestamps,
        _snapshot_cache,
    )
    _catalog_cache.clear()
    _metadata_cache.clear()
    _metadata_timestamps.clear()
    _snapshot_cache.clear()
    _hsso_index_cache.clear()
    yield
    _catalog_cache.clear()
    _metadata_cache.clear()
    _metadata_timestamps.clear()
    _snapshot_cache.clear()
    _hsso_index_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_all_dbs_response() -> list[dict]:
    """Minimal list of mock BFS databases for testing."""
    return [
        {"dbid": "px-x-1504000000_173", "text": "px-x-1504000000_173"},
        {"dbid": "px-x-0102010000_101", "text": "px-x-0102010000_101"},
        {"dbid": "px-x-1509090000_101", "text": "px-x-1509090000_101"},
        {"dbid": "px-x-1703030000_101", "text": "px-x-1703030000_101"},
        {"dbid": "px-x-0301000000_101", "text": "px-x-0301000000_101"},
    ]


def _mock_teacher_metadata() -> dict:
    return {
        "title": "Lehrkräfte nach Schuljahr, Kanton, Beschäftigungsgrad und Bildungsstufe",
        "source": "BFS",
        "updated": "2024-10-01T00:00:00",
        "variables": [
            {
                "code": "Schuljahr",
                "text": "Schuljahr",
                "values": ["0", "1", "2", "3"],
                "valueTexts": ["2010/11", "2011/12", "2012/13", "2013/14"],
            },
            {
                "code": "Kanton",
                "text": "Kanton",
                "values": ["0", "1", "2"],
                "valueTexts": ["Schweiz", "Zürich", "Bern / Berne"],
            },
            {
                "code": "Beschäftigungsgrad",
                "text": "Beschäftigungsgrad",
                "values": ["0", "1", "2"],
                "valueTexts": ["<50%", "50-89%", ">89%"],
            },
        ],
    }


def _mock_jsonstat2_response() -> dict:
    return {
        "class": "dataset",
        "label": "Lehrkräfte Test",
        "source": "BFS",
        "updated": "2024-10-01T00:00:00",
        "id": ["Schuljahr", "Kanton"],
        "size": [2, 2],
        "dimension": {
            "Schuljahr": {
                "label": "Schuljahr",
                "category": {
                    "index": {"0": 0, "1": 1},
                    "label": {"0": "2022/23", "1": "2023/24"},
                },
            },
            "Kanton": {
                "label": "Kanton",
                "category": {
                    "index": {"0": 0, "1": 1},
                    "label": {"0": "Zürich", "1": "Bern / Berne"},
                },
            },
        },
        "value": [5000, 4200, 5100, 4300],
    }


# ---------------------------------------------------------------------------
# Unit tests: theme helpers
# ---------------------------------------------------------------------------

class TestThemeCodeExtraction:
    def test_education_theme(self):
        from swiss_statistics_mcp.server import _theme_code_from_dbid
        assert _theme_code_from_dbid("px-x-1504000000_173") == "15"

    def test_population_theme(self):
        from swiss_statistics_mcp.server import _theme_code_from_dbid
        assert _theme_code_from_dbid("px-x-0102010000_101") == "01"

    def test_politics_theme(self):
        from swiss_statistics_mcp.server import _theme_code_from_dbid
        assert _theme_code_from_dbid("px-x-1703030000_101") == "17"

    def test_work_theme(self):
        from swiss_statistics_mcp.server import _theme_code_from_dbid
        assert _theme_code_from_dbid("px-x-0301000000_101") == "03"

    def test_sustainability_theme(self):
        from swiss_statistics_mcp.server import _theme_code_from_dbid
        assert _theme_code_from_dbid("px-x-2105000000_101") == "21"


class TestJsonStat2Formatting:
    def test_basic_table(self):
        from swiss_statistics_mcp.server import _format_jsonstat2_as_table
        data = _mock_jsonstat2_response()
        result = _format_jsonstat2_as_table(data)

        assert result["title"] == "Lehrkräfte Test"
        assert result["rows_total"] == 4
        assert result["rows_returned"] == 4
        assert result["truncated"] is False
        assert len(result["rows"]) == 4
        assert result["rows"][0]["Schuljahr"] == "2022/23"
        assert result["rows"][0]["Kanton"] == "Zürich"
        assert result["rows"][0]["Wert"] == 5000

    def test_max_rows_respected(self):
        from swiss_statistics_mcp.server import _format_jsonstat2_as_table
        data = _mock_jsonstat2_response()
        result = _format_jsonstat2_as_table(data, max_rows=2)

        assert result["rows_returned"] == 2
        assert result["rows_total"] == 4
        assert result["truncated"] is True
        assert len(result["rows"]) == 2

    def test_dimensions_included(self):
        from swiss_statistics_mcp.server import _format_jsonstat2_as_table
        data = _mock_jsonstat2_response()
        result = _format_jsonstat2_as_table(data)

        assert len(result["dimensions"]) == 2
        assert result["dimensions"][0]["id"] == "Schuljahr"
        assert result["dimensions"][1]["id"] == "Kanton"


class TestCantonMapping:
    def test_zurich_mapped(self):
        from swiss_statistics_mcp.server import CANTON_NAME_TO_VALUE
        assert CANTON_NAME_TO_VALUE["Zürich"] == "1"

    def test_bern_mapped(self):
        from swiss_statistics_mcp.server import CANTON_NAME_TO_VALUE
        assert CANTON_NAME_TO_VALUE["Bern / Berne"] == "2"

    def test_all_26_cantons_present(self):
        from swiss_statistics_mcp.server import CANTON_NAME_TO_VALUE
        # 26 cantons + Switzerland = 27 entries
        assert len(CANTON_NAME_TO_VALUE) == 27

    def test_schweiz_is_zero(self):
        from swiss_statistics_mcp.server import CANTON_NAME_TO_VALUE
        assert CANTON_NAME_TO_VALUE["Schweiz"] == "0"


class TestFeaturedDatasets:
    def test_featured_tables_defined(self):
        from swiss_statistics_mcp.server import FEATURED_TABLES
        assert len(FEATURED_TABLES) >= 10

    def test_teacher_table_featured(self):
        from swiss_statistics_mcp.server import FEATURED_TABLES
        assert "px-x-1504000000_173" in FEATURED_TABLES

    def test_population_table_featured(self):
        from swiss_statistics_mcp.server import FEATURED_TABLES
        assert "px-x-0102010000_101" in FEATURED_TABLES


# ---------------------------------------------------------------------------
# Integration tests: tool invocations (mocked HTTP)
# ---------------------------------------------------------------------------

class TestBfsListThemes:
    @pytest.mark.asyncio
    async def test_returns_all_themes(self):
        from swiss_statistics_mcp.server import ListThemesInput, bfs_list_themes

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_all_dbs_response(),
        ):
            result = await bfs_list_themes(ListThemesInput(lang="de"))
            data = result.model_dump(exclude_none=True)

        assert "themes" in data
        assert len(data["themes"]) == 21
        assert data["total_datasets"] == len(_mock_all_dbs_response())

    @pytest.mark.asyncio
    async def test_theme_codes_present(self):
        from swiss_statistics_mcp.server import ListThemesInput, bfs_list_themes

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_all_dbs_response(),
        ):
            result = await bfs_list_themes(ListThemesInput(lang="de"))
            data = result.model_dump(exclude_none=True)

        codes = [t["code"] for t in data["themes"]]
        assert "15" in codes  # Bildung
        assert "01" in codes  # Bevölkerung
        assert "17" in codes  # Politik


class TestBfsGetTableMetadata:
    @pytest.mark.asyncio
    async def test_returns_variables(self):
        from swiss_statistics_mcp.server import GetTableMetadataInput, bfs_get_table_metadata

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_teacher_metadata(),
        ):
            result = await bfs_get_table_metadata(
                GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
            )
            data = result.model_dump(exclude_none=True)

        assert "variables" in data
        assert data["n_variables"] == 3
        assert data["variables"][0]["code"] == "Schuljahr"

    @pytest.mark.asyncio
    async def test_theme_info_included(self):
        from swiss_statistics_mcp.server import GetTableMetadataInput, bfs_get_table_metadata

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_teacher_metadata(),
        ):
            result = await bfs_get_table_metadata(
                GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
            )
            data = result.model_dump(exclude_none=True)

        assert data["theme_code"] == "15"
        assert "Bildung" in data["theme_name"]

    @pytest.mark.asyncio
    async def test_404_returns_friendly_error(self):
        import httpx

        from swiss_statistics_mcp.server import GetTableMetadataInput, bfs_get_table_metadata

        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            result = await bfs_get_table_metadata(
                GetTableMetadataInput(table_id="px-x-9999999999_999", lang="de")
            )
            data = result.model_dump(exclude_none=True)

        assert "error" in data
        assert "hint" in data


class TestBfsGetData:
    @pytest.mark.asyncio
    async def test_returns_table_structure(self):
        from swiss_statistics_mcp.server import GetDataInput, bfs_get_data

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_get_data(
                GetDataInput(table_id="px-x-1504000000_173")
            )
            data = result.model_dump(exclude_none=True)

        assert "rows" in data
        assert "title" in data
        assert len(data["rows"]) == 4

    @pytest.mark.asyncio
    async def test_filter_passed_to_api(self):
        from swiss_statistics_mcp.server import DimensionFilter, GetDataInput, bfs_get_data

        posted_body = {}

        async def capture_post(url, body):
            posted_body.update(body)
            return _mock_jsonstat2_response()

        with patch("swiss_statistics_mcp.server._post", side_effect=capture_post):
            await bfs_get_data(
                GetDataInput(
                    table_id="px-x-1504000000_173",
                    filters=[DimensionFilter(code="Kanton", values=["1"])],
                )
            )

        assert len(posted_body["query"]) == 1
        assert posted_body["query"][0]["code"] == "Kanton"
        assert posted_body["query"][0]["selection"]["values"] == ["1"]

    @pytest.mark.asyncio
    async def test_max_rows_warning(self):
        from swiss_statistics_mcp.server import GetDataInput, bfs_get_data

        big_response = _mock_jsonstat2_response()
        big_response["value"] = list(range(1000))
        big_response["size"] = [1000]
        big_response["id"] = ["TestDim"]
        big_response["dimension"] = {
            "TestDim": {
                "label": "Test",
                "category": {
                    "index": {str(i): i for i in range(1000)},
                    "label": {str(i): f"Val {i}" for i in range(1000)},
                },
            }
        }

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=big_response,
        ):
            result = await bfs_get_data(
                GetDataInput(table_id="px-x-1504000000_173", max_rows=100)
            )
            data = result.model_dump(exclude_none=True)

        # ARCH-009: machine-readable truncation signal instead of German prose
        assert data["truncated"] is True
        assert data["rows_returned"] == 100
        assert data["rows_total"] == 1000
        assert "note" in data and "begrenzt" in data["note"]


class TestBfsEducationStats:
    @pytest.mark.asyncio
    async def test_teachers_topic(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput, bfs_education_stats

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_education_stats(
                GetEducationStatsInput(topic="teachers", lang="de")
            )
            data = result.model_dump(exclude_none=True)

        assert data["topic"] == "teachers"
        assert "rows" in data
        assert "px-x-1504000000_173" in data["table_id"]

    @pytest.mark.asyncio
    async def test_canton_filter_resolved(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput, bfs_education_stats

        posted_bodies: list[dict] = []

        async def capture(url, body):
            posted_bodies.append(body)
            return _mock_jsonstat2_response()

        with patch("swiss_statistics_mcp.server._post", side_effect=capture):
            await bfs_education_stats(
                GetEducationStatsInput(topic="teachers", canton="Zürich")
            )

        # Zürich should resolve to value "1"
        assert len(posted_bodies) == 1
        query = posted_bodies[0]["query"]
        assert len(query) == 1
        assert query[0]["selection"]["values"] == ["1"]

    @pytest.mark.asyncio
    async def test_invalid_canton_returns_error(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput, bfs_education_stats

        result = await bfs_education_stats(
            GetEducationStatsInput(topic="teachers", canton="Fantasialand")
        )
        data = result.model_dump(exclude_none=True)
        assert "error" in data


class TestBfsPopulation:
    @pytest.mark.asyncio
    async def test_total_breakdown(self):
        from swiss_statistics_mcp.server import GetPopulationInput, bfs_population

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_population(GetPopulationInput(region="Zürich"))
            data = result.model_dump(exclude_none=True)

        assert data["region"] == "Zürich"
        assert "rows" in data

    @pytest.mark.asyncio
    async def test_age_breakdown_filters_0_18(self):
        from swiss_statistics_mcp.server import GetPopulationInput, bfs_population

        posted: list[dict] = []

        async def capture(url, body):
            posted.append(body)
            return _mock_jsonstat2_response()

        with patch("swiss_statistics_mcp.server._post", side_effect=capture):
            await bfs_population(GetPopulationInput(region="Schweiz", breakdown="age"))

        query = posted[0]["query"]
        alter_filter = next((q for q in query if "Alter" in q["code"]), None)
        assert alter_filter is not None
        # Should include ages 0-18
        assert "0" in alter_filter["selection"]["values"]
        assert "18" in alter_filter["selection"]["values"]


class TestBfsCompareCanstons:
    @pytest.mark.asyncio
    async def test_multiple_cantons(self):
        from swiss_statistics_mcp.server import CompareCantonsInput, bfs_compare_cantons

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_teacher_metadata(),
        ):
            with patch(
                "swiss_statistics_mcp.server._post",
                new_callable=AsyncMock,
                return_value=_mock_jsonstat2_response(),
            ):
                result = await bfs_compare_cantons(
                    CompareCantonsInput(
                        table_id="px-x-1504000000_173",
                        canton_values=["0", "1", "2"],
                    )
                )
                data = result.model_dump(exclude_none=True)

        assert "rows" in data
        assert data["cantons_compared"] == ["0", "1", "2"]
        assert data["canton_variable"] == "Kanton"


class TestBfsFeaturedDatasets:
    @pytest.mark.asyncio
    async def test_returns_featured_list(self):
        from swiss_statistics_mcp.server import ListThemesInput, bfs_featured_datasets

        result = await bfs_featured_datasets(ListThemesInput(lang="de"))
        data = result.model_dump(exclude_none=True)

        assert "featured_datasets" in data
        assert data["total"] >= 10

    @pytest.mark.asyncio
    async def test_schulamt_relevance_present(self):
        from swiss_statistics_mcp.server import ListThemesInput, bfs_featured_datasets

        result = await bfs_featured_datasets(ListThemesInput(lang="de"))
        data = result.model_dump(exclude_none=True)

        teacher_entry = next(
            (d for d in data["featured_datasets"] if d["table_id"] == "px-x-1504000000_173"),
            None,
        )
        assert teacher_entry is not None
        assert "schulamt_relevanz" in teacher_entry
        assert "⭐" in teacher_entry["schulamt_relevanz"]


# ---------------------------------------------------------------------------
# Pydantic input validation tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_invalid_lang_rejected(self):
        from swiss_statistics_mcp.server import ListThemesInput
        with pytest.raises(Exception):
            ListThemesInput(lang="xx")

    def test_invalid_theme_code_rejected(self):
        from swiss_statistics_mcp.server import ListTablesByThemeInput
        with pytest.raises(Exception):
            ListTablesByThemeInput(theme_code="abc")

    def test_short_search_query_rejected(self):
        from swiss_statistics_mcp.server import SearchTablesInput
        with pytest.raises(Exception):
            SearchTablesInput(query="a")

    def test_valid_education_topic(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput
        params = GetEducationStatsInput(topic="teachers")
        assert params.topic == "teachers"

    def test_invalid_education_topic_rejected(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput
        with pytest.raises(Exception):
            GetEducationStatsInput(topic="unicorn")

    def test_invalid_breakdown_rejected(self):
        from swiss_statistics_mcp.server import GetPopulationInput
        with pytest.raises(Exception):
            GetPopulationInput(breakdown="xyz")

    def test_max_rows_capped_at_5000(self):
        from swiss_statistics_mcp.server import GetDataInput
        with pytest.raises(Exception):
            GetDataInput(table_id="px-x-1504000000_173", max_rows=99999)

    def test_canton_values_min_2(self):
        from swiss_statistics_mcp.server import CompareCantonsInput
        with pytest.raises(Exception):
            CompareCantonsInput(table_id="px-x-1504000000_173", canton_values=["1"])

    def test_valid_table_id_accepted(self):
        from swiss_statistics_mcp.server import (
            CompareCantonsInput,
            GetDataInput,
            GetTableMetadataInput,
        )
        for cls in (GetTableMetadataInput, GetDataInput):
            cls(table_id="px-x-1504000000_173", lang="de")
        CompareCantonsInput(
            table_id="px-x-1504000000_173", canton_values=["1", "2"]
        )

    @pytest.mark.parametrize("bad_id", [
        "../etc/passwd",
        "px-x-../foo",
        "px-X-1504000000_173",          # uppercase letter rejected
        "px-x-1504000000_173;rm -rf",   # shell metacharacters
        "px-x-1504000000_173%2F..",     # URL-encoded traversal
        "ftp://example.com/file",
        "px-x-abc_123",                 # non-numeric digits-section
        "",
    ])
    def test_malformed_table_id_rejected(self, bad_id):
        from swiss_statistics_mcp.server import GetTableMetadataInput
        with pytest.raises(Exception):
            GetTableMetadataInput(table_id=bad_id, lang="de")


# ---------------------------------------------------------------------------
# Resilience tests (SEC-018, SCALE-002, SCALE-003, SCALE-004)
# ---------------------------------------------------------------------------

class TestRetry:
    """Outbound BFS calls must retry on transient errors (5xx, network)
    and surface 4xx immediately."""

    @pytest.fixture(autouse=True)
    def _fast_retries(self, monkeypatch):
        # Keep retry attempts but make backoff effectively instant. The
        # constants are read at module import for the decorator config,
        # so we patch the module attributes the runtime uses.
        import swiss_statistics_mcp.server as srv
        monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
        monkeypatch.setattr(srv, "RETRY_WAIT_MAX", 0.002)

    @pytest.mark.asyncio
    async def test_retries_on_503_then_succeeds(self, monkeypatch):
        import httpx

        from swiss_statistics_mcp.server import _get

        success_payload = {"ok": True}
        attempts = {"n": 0}

        async def fake_handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 2:
                return httpx.Response(503, request=request)
            return httpx.Response(200, json=success_payload, request=request)

        transport = httpx.MockTransport(fake_handler)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: real_client(transport=transport, **kw),
        )

        result = await _get("https://example.invalid/path")

        assert result == success_payload
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_on_400(self, monkeypatch):
        import httpx

        from swiss_statistics_mcp.server import _get

        attempts = {"n": 0}

        async def fake_handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(400, json={"error": "bad query"}, request=request)

        transport = httpx.MockTransport(fake_handler)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: real_client(transport=transport, **kw),
        )

        with pytest.raises(httpx.HTTPStatusError):
            await _get("https://example.invalid/path")

        assert attempts["n"] == 1, f"expected exactly one attempt on 4xx, got {attempts['n']}"

    @pytest.mark.asyncio
    async def test_gives_up_after_max_attempts(self, monkeypatch):
        import httpx

        import swiss_statistics_mcp.server as srv
        monkeypatch.setattr(srv, "RETRY_MAX_ATTEMPTS", 3)

        attempts = {"n": 0}

        async def always_503(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(503, request=request)

        transport = httpx.MockTransport(always_503)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: real_client(transport=transport, **kw),
        )

        with pytest.raises(httpx.HTTPStatusError):
            await srv._get("https://example.invalid/path")

        assert attempts["n"] == 3


class TestMetadataCache:
    """Repeated metadata fetches for the same (table, lang) must hit the
    in-memory cache instead of going to the network."""

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        from swiss_statistics_mcp.server import _fetch_metadata_cached

        cached_meta = {"title": "Lehrkräfte", "variables": []}

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=cached_meta,
        ) as mock_get:
            r1 = await _fetch_metadata_cached("px-x-1504000000_173", "de")
            r2 = await _fetch_metadata_cached("px-x-1504000000_173", "de")

        assert r1 == cached_meta == r2
        assert mock_get.call_count == 1, "expected exactly one upstream call"

    @pytest.mark.asyncio
    async def test_different_lang_misses_cache(self):
        from swiss_statistics_mcp.server import _fetch_metadata_cached

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value={"title": "x", "variables": []},
        ) as mock_get:
            await _fetch_metadata_cached("px-x-1504000000_173", "de")
            await _fetch_metadata_cached("px-x-1504000000_173", "fr")

        assert mock_get.call_count == 2


class TestFanoutConcurrency:
    """`bfs_list_tables_by_theme` fans out metadata fetches in parallel
    bounded by FANOUT_CONCURRENCY."""

    @pytest.mark.asyncio
    async def test_parallel_metadata_fetches(self, monkeypatch):
        """5 tables × 50ms each: sequential would be ~250ms,
        parallel (concurrency=5) should be ~50ms. We assert a generous
        upper bound to keep the test stable on slow CI."""
        import asyncio as aio
        import time as time_mod

        from swiss_statistics_mcp.server import (
            ListTablesByThemeInput,
            bfs_list_tables_by_theme,
        )

        async def slow_meta(dbid: str, lang: str) -> dict:
            await aio.sleep(0.05)
            return {
                "title": f"meta-{dbid}",
                "updated": "2024",
                "variables": [{"code": "Kanton"}],
            }

        # The first `_get` call inside `bfs_list_tables_by_theme` fetches
        # the database index; later fan-out goes through the cached helper.
        async def fake_get(url):
            return _mock_all_dbs_response()

        monkeypatch.setattr("swiss_statistics_mcp.server._get", fake_get)
        monkeypatch.setattr(
            "swiss_statistics_mcp.server._fetch_metadata_cached", slow_meta
        )

        t0 = time_mod.monotonic()
        result = await bfs_list_tables_by_theme(
            ListTablesByThemeInput(theme_code="15", limit=5)
        )
        elapsed = time_mod.monotonic() - t0

        data = result.model_dump(exclude_none=True)
        assert isinstance(data.get("tables"), list)
        # 5× 50ms parallel ≈ 50ms; allow generous headroom for CI noise.
        assert elapsed < 0.20, f"expected parallel fan-out, took {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Error sanitization tests (SEC-022, OBS-004)
# ---------------------------------------------------------------------------

class TestErrorSanitization:
    """Generic catch-all errors must log the full trace server-side but
    return only a sanitized message to the client — no library internals,
    no file paths, no raw exception text."""

    @pytest.mark.asyncio
    async def test_unexpected_error_does_not_leak_internals(self, caplog):
        from swiss_statistics_mcp.server import (
            _LOGGER,
            GetTableMetadataInput,
            bfs_get_table_metadata,
        )

        # A non-HTTP error: e.g. our parser crashes on malformed JSON.
        # The raw exception text contains a fictitious internal path that
        # must never reach the client response.
        secret_marker = "/internal/path/to/secret_module.py"
        leaky_error = RuntimeError(
            f"KeyError in {secret_marker} at line 42 — token=ABCDEF"
        )

        _LOGGER.propagate = True
        try:
            with patch(
                "swiss_statistics_mcp.server._get",
                new_callable=AsyncMock,
                side_effect=leaky_error,
            ), caplog.at_level(logging.ERROR, logger="swiss_statistics_mcp"):
                result = await bfs_get_table_metadata(
                    GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
                )
        finally:
            _LOGGER.propagate = False

        data = result.model_dump(exclude_none=True)

        # Client side: sanitized
        assert "error" in data
        assert secret_marker not in result
        assert "RuntimeError" not in result
        assert "token=ABCDEF" not in result
        assert "line 42" not in result

        # Server side: full trace landed in logs
        trace_records = [r for r in caplog.records if r.exc_info]
        assert trace_records, "expected an exc_info record from _LOGGER.exception"
        formatted = "\n".join(r.getMessage() + str(r.exc_info[1]) for r in trace_records)
        assert "RuntimeError" in formatted or "RuntimeError" in str(trace_records[0].exc_info)


# ---------------------------------------------------------------------------
# Transport / host-binding tests (SDK-004)
# ---------------------------------------------------------------------------

class TestTransportBinding:
    """The streamable-http transport must bind to loopback by default and
    only expose externally when the operator opts in explicitly."""

    def test_default_host_is_loopback(self):
        from swiss_statistics_mcp.server import mcp
        assert mcp.settings.host == "127.0.0.1"


# ---------------------------------------------------------------------------
# Logging tests (OBS-001, OBS-002, OBS-003, SEC-014)
# ---------------------------------------------------------------------------

class TestToolLogging:
    """Every tool call must emit a start and an end JSON log on stderr,
    tagged with a correlation id (`rid`) and a `duration_ms`."""

    @pytest.mark.asyncio
    async def test_emits_start_and_end_events(self, caplog):
        from swiss_statistics_mcp.server import (
            _LOGGER,
            ListThemesInput,
            bfs_list_themes,
        )

        with caplog.at_level(logging.INFO, logger="swiss_statistics_mcp"):
            # Ensure our logger propagates to caplog for assertion purposes
            _LOGGER.propagate = True
            try:
                await bfs_list_themes(ListThemesInput())
            finally:
                _LOGGER.propagate = False

        events = [r.msg for r in caplog.records if isinstance(r.msg, dict)]
        starts = [e for e in events if e.get("event") == "tool_start"]
        ends = [e for e in events if e.get("event") == "tool_end"]

        assert len(starts) == 1, f"expected 1 tool_start, got {events}"
        assert len(ends) == 1, f"expected 1 tool_end, got {events}"

        start, end = starts[0], ends[0]
        assert start["tool"] == "bfs_list_themes"
        assert start["rid"] == end["rid"]  # correlation id pairs start/end
        assert len(start["rid"]) == 8
        assert end["status"] == "ok"
        assert isinstance(end["duration_ms"], int)
        assert end["duration_ms"] >= 0

    def test_default_log_level_is_info(self):
        from swiss_statistics_mcp.server import _LOGGER
        assert _LOGGER.level == logging.INFO

    def test_log_level_honors_env(self, monkeypatch):
        monkeypatch.setenv("MCP_LOG_LEVEL", "WARNING")
        from swiss_statistics_mcp.server import _configure_logger
        log = _configure_logger()
        try:
            assert log.level == logging.WARNING
        finally:
            log.setLevel(logging.INFO)

    def test_json_formatter_renders_dict_msg(self):
        from swiss_statistics_mcp.server import _JsonFormatter
        record = logging.LogRecord(
            name="swiss_statistics_mcp", level=logging.INFO, pathname=__file__,
            lineno=1, msg={"event": "tool_end", "tool": "bfs_x", "status": "ok"},
            args=(), exc_info=None,
        )
        out = _JsonFormatter().format(record)
        decoded = json.loads(out)
        assert decoded["event"] == "tool_end"
        assert decoded["tool"] == "bfs_x"
        assert decoded["status"] == "ok"
        assert decoded["level"] == "INFO"


# ---------------------------------------------------------------------------
# Reference layer: AGVCH communes + HSSO historical series
# ---------------------------------------------------------------------------

# Snapshot fixture reproduces the real trap: HistoricalCode 10078 is BOTH
# ZH's 'Bezirk Horgen' (Level 2) and VS's commune 'Vionnaz' (Level 3).
_SNAPSHOT_CSV = (
    "HistoricalCode,BfsCode,ValidFrom,ValidTo,Level,Parent,Name,ShortName,"
    "Inscription,Radiation,Rec_Type_fr,Rec_Type_de\n"
    "1,1,12.09.1848,,1,,Zürich,ZH,,,,\n"
    "10078,201,01.01.1900,,2,1,Bezirk Horgen,Horgen,,,,\n"
    "16123,293,01.01.2019,,3,10078,Wädenswil,Wädenswil,,,,\n"
    "13300,295,01.01.2018,,3,10078,Horgen,Horgen,,,,\n"
    "23,23,12.09.1848,,1,,Valais / Wallis,VS,,,,\n"
    "10013,2308,01.01.1900,,2,23,District de Monthey,Monthey,,,,\n"
    "10078,6158,01.01.1900,,3,10013,Vionnaz,Vionnaz,,,,\n"
)

_CORR_CSV = (
    "InitialHistoricalCode,InitialCode,InitialName,InitialParentHistoricalCode,"
    "InitialParentName,InitialStep,TerminalHistoricalCode,TerminalCode,TerminalName,"
    "TerminalParentHistoricalCode,TerminalParentName,TerminalStep\n"
    "13300,133,Horgen,10078,Bezirk Horgen,24,16999,295,Horgen,10078,Bezirk Horgen,24\n"
)

_MUT_CSV = (
    "MutationNumber,MutationDate,InitialHistoricalCode,InitialCode,InitialName,"
    "InitialParentHistoricalCode,InitialParentName,InitialStep,TerminalHistoricalCode,"
    "TerminalCode,TerminalName,TerminalParentHistoricalCode,TerminalParentName,TerminalStep\n"
    "3582,01.01.2018,13200,132,Hirzel,10078,Bezirk Horgen,26,16999,295,Horgen,10078,Bezirk Horgen,21\n"
    "3582,01.01.2018,13300,133,Horgen,10078,Bezirk Horgen,26,16999,295,Horgen,10078,Bezirk Horgen,21\n"
)

_HSSO_CHAPTER_B = (
    '<html><body>'
    '<a class="explorer-item" href="/de/2012/b/1a">'
    '<div class="explorer-item__title">B.1a</div>'
    '<div class="explorer-item__description">Wohnbevölkerung nach Kantonen</div></a>'
    '<a class="explorer-item" href="/de/2012/b/11b">'
    '<div class="explorer-item__title">B.11b</div>'
    '<div class="explorer-item__description">Erwerbstätige nach Sektoren</div></a>'
    '</body></html>'
)


def _fake_get_text_factory():
    async def fake_get_text(url: str) -> str:
        if "snapshot" in url:
            return _SNAPSHOT_CSV
        if "correspondances" in url:
            return _CORR_CSV
        if "mutations" in url:
            return _MUT_CSV
        if "/de/2012/b" in url:
            return _HSSO_CHAPTER_B
        if "/de/2012/" in url:
            return "<html><body></body></html>"  # other chapters empty
        raise AssertionError(f"unexpected URL: {url}")
    return fake_get_text


class TestAgvchHelpers:
    def test_iso_to_agvch(self):
        from swiss_statistics_mcp.server import _iso_to_agvch
        assert _iso_to_agvch("2025-01-01") == "01-01-2025"

    def test_hsso_xlsx_derivation_zero_pads(self):
        from swiss_statistics_mcp.server import _hsso_xlsx_path
        assert _hsso_xlsx_path("a", "1a") == "/get/A.01a.xlsx"
        assert _hsso_xlsx_path("b", "11b") == "/get/B.11b.xlsx"

    def test_climb_to_canton_disambiguates_shared_historical_code(self):
        """Regression: HistoricalCode 10078 exists at two levels/cantons;
        Wädenswil (Level 3, Parent 10078) must climb to ZH, not VS."""
        import csv
        import io

        from swiss_statistics_mcp.server import _climb_to_canton, _index_by_hist

        rows = list(csv.DictReader(io.StringIO(_SNAPSHOT_CSV)))
        by_hist = _index_by_hist(rows)
        waedenswil = next(r for r in rows if r["BfsCode"] == "293")
        vionnaz = next(r for r in rows if r["BfsCode"] == "6158")

        assert _climb_to_canton(waedenswil, by_hist)["ShortName"] == "ZH"
        assert _climb_to_canton(vionnaz, by_hist)["ShortName"] == "VS"

    def test_parse_hsso_chapter(self):
        from swiss_statistics_mcp.server import _parse_hsso_chapter
        entries = _parse_hsso_chapter(_HSSO_CHAPTER_B)
        assert len(entries) == 2
        assert entries[0].code == "B.1a"
        assert entries[0].title == "Wohnbevölkerung nach Kantonen"
        assert entries[0].xlsx_url == "https://hsso.ch/get/B.01a.xlsx"


class TestLookupCommune:
    @pytest.mark.asyncio
    async def test_lookup_by_name_resolves_canton(self):
        from swiss_statistics_mcp.server import LookupCommuneInput, lookup_commune

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await lookup_commune(
                LookupCommuneInput(name_or_bfs_number="Wädenswil", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 1
        c = data["communes"][0]
        assert c["bfs_number"] == 293
        assert c["canton_abbr"] == "ZH"
        assert c["lindas_uri"] == "https://ld.admin.ch/municipality/293"
        assert data["provenance"] == "live_api"

    @pytest.mark.asyncio
    async def test_lookup_by_number_exact(self):
        from swiss_statistics_mcp.server import LookupCommuneInput, lookup_commune

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await lookup_commune(
                LookupCommuneInput(name_or_bfs_number="295", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 1
        assert data["communes"][0]["name"] == "Horgen"

    @pytest.mark.asyncio
    async def test_lookup_not_found_is_graceful(self):
        from swiss_statistics_mcp.server import LookupCommuneInput, lookup_commune

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await lookup_commune(
                LookupCommuneInput(name_or_bfs_number="Atlantis", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 0
        assert "note" in data
        assert "error" not in data  # empty result is not an error


class TestResolveHistoricalCommune:
    @pytest.mark.asyncio
    async def test_anchor_query_horgen(self):
        """Anchor: old BFS 133 (Horgen) → today's 295 with mutation path."""
        from swiss_statistics_mcp.server import (
            ResolveHistoricalCommuneInput,
            resolve_historical_commune,
        )

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await resolve_historical_commune(
                ResolveHistoricalCommuneInput(
                    bfs_number=133, from_date="2000-01-01", to_date="2025-01-01"
                )
            )
        data = result.model_dump(exclude_none=True)
        assert data["unchanged"] is False
        assert len(data["resolves_to"]) == 1
        assert data["resolves_to"][0]["bfs_number"] == 295
        assert data["resolves_to"][0]["lindas_uri"] == "https://ld.admin.ch/municipality/295"
        # mutation path includes both Hirzel and Horgen merging into 295
        assert len(data["mutation_path"]) == 2

    @pytest.mark.asyncio
    async def test_unknown_number_returns_error(self):
        from swiss_statistics_mcp.server import (
            ResolveHistoricalCommuneInput,
            resolve_historical_commune,
        )

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await resolve_historical_commune(
                ResolveHistoricalCommuneInput(
                    bfs_number=9998, from_date="2000-01-01", to_date="2025-01-01"
                )
            )
        data = result.model_dump(exclude_none=True)
        assert "error" in data and "hint" in data


class TestListCommunes:
    @pytest.mark.asyncio
    async def test_list_zurich(self):
        from swiss_statistics_mcp.server import ListCommunesInput, list_communes

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await list_communes(
                ListCommunesInput(canton="ZH", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert data["canton"] == "Zürich"
        # Only ZH communes (Wädenswil, Horgen) — Vionnaz belongs to VS
        codes = sorted(c["bfs_number"] for c in data["communes"])
        assert codes == [293, 295]

    @pytest.mark.asyncio
    async def test_unknown_canton_error(self):
        from swiss_statistics_mcp.server import ListCommunesInput, list_communes

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await list_communes(
                ListCommunesInput(canton="XX", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert "error" in data


class TestSearchHistoricalSeries:
    @pytest.mark.asyncio
    async def test_search_matches_and_carries_nc_licence(self):
        from swiss_statistics_mcp.server import (
            SearchHistoricalSeriesInput,
            search_historical_series,
        )

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await search_historical_series(
                SearchHistoricalSeriesInput(topic="Wohnbevölkerung")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 1
        assert data["series"][0]["xlsx_url"] == "https://hsso.ch/get/B.01a.xlsx"
        # NonCommercial notice must always be present
        assert "NonCommercial" in data["licence_note"]

    @pytest.mark.asyncio
    async def test_search_no_match_period_hint(self):
        from swiss_statistics_mcp.server import (
            SearchHistoricalSeriesInput,
            search_historical_series,
        )

        with patch(
            "swiss_statistics_mcp.server._get_text",
            side_effect=_fake_get_text_factory(),
        ):
            result = await search_historical_series(
                SearchHistoricalSeriesInput(topic="Nichtsdergleichen", period="1850-1900")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 0
        assert "Periodenfilter" in data["note"]


class TestReferenceLayerResilience:
    @pytest.fixture(autouse=True)
    def _fast_retries(self, monkeypatch):
        import swiss_statistics_mcp.server as srv
        monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
        monkeypatch.setattr(srv, "RETRY_WAIT_MAX", 0.002)

    @pytest.mark.asyncio
    async def test_get_text_retries_on_503(self, monkeypatch):
        import httpx

        from swiss_statistics_mcp.server import _get_text

        attempts = {"n": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 2:
                return httpx.Response(503, request=request)
            return httpx.Response(200, text="ok", request=request)

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
        )

        assert await _get_text("https://example.invalid") == "ok"
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_lookup_network_error_is_graceful(self):
        from swiss_statistics_mcp.server import LookupCommuneInput, lookup_commune

        async def boom(url: str) -> str:
            raise ConnectionError("upstream down")

        with patch("swiss_statistics_mcp.server._get_text", side_effect=boom):
            result = await lookup_commune(
                LookupCommuneInput(name_or_bfs_number="Zürich", valid_at_date="2025-01-01")
            )
        data = result.model_dump(exclude_none=True)
        assert "error" in data and "hint" in data

    @pytest.mark.asyncio
    async def test_hsso_all_chapters_down_is_graceful(self):
        from swiss_statistics_mcp.server import (
            SearchHistoricalSeriesInput,
            search_historical_series,
        )

        async def boom(url: str) -> str:
            raise ConnectionError("hsso down")

        with patch("swiss_statistics_mcp.server._get_text", side_effect=boom):
            result = await search_historical_series(
                SearchHistoricalSeriesInput(topic="Bevölkerung")
            )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] == 0
        assert "error" in data


class TestReferenceLayerValidation:
    def test_bad_date_rejected(self):
        from swiss_statistics_mcp.server import LookupCommuneInput
        with pytest.raises(Exception):
            LookupCommuneInput(name_or_bfs_number="Zürich", valid_at_date="01-01-2025")

    def test_bfs_number_range(self):
        from swiss_statistics_mcp.server import ResolveHistoricalCommuneInput
        with pytest.raises(Exception):
            ResolveHistoricalCommuneInput(bfs_number=0, from_date="2000-01-01")

    def test_short_topic_rejected(self):
        from swiss_statistics_mcp.server import SearchHistoricalSeriesInput
        with pytest.raises(Exception):
            SearchHistoricalSeriesInput(topic="x")

    def test_defaults_to_today(self):
        from swiss_statistics_mcp.server import LookupCommuneInput
        params = LookupCommuneInput(name_or_bfs_number="Zürich")
        assert len(params.valid_at_date) == 10  # YYYY-MM-DD


# ---------------------------------------------------------------------------
# Live smoke tests (require network – run separately)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveAPI:
    """Real API calls. Run with: pytest -m live"""

    @pytest.mark.asyncio
    async def test_live_list_themes(self):
        from swiss_statistics_mcp.server import ListThemesInput, bfs_list_themes
        result = await bfs_list_themes(ListThemesInput(lang="de"))
        data = result.model_dump(exclude_none=True)
        assert data["total_datasets"] > 600

    @pytest.mark.asyncio
    async def test_live_teacher_metadata(self):
        from swiss_statistics_mcp.server import GetTableMetadataInput, bfs_get_table_metadata
        result = await bfs_get_table_metadata(
            GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
        )
        data = result.model_dump(exclude_none=True)
        assert "Lehrkräfte" in data["title"]
        assert len(data["variables"]) >= 3

    @pytest.mark.asyncio
    async def test_live_education_stats_teachers(self):
        from swiss_statistics_mcp.server import GetEducationStatsInput, bfs_education_stats
        result = await bfs_education_stats(
            GetEducationStatsInput(topic="teachers", canton="Zürich")
        )
        data = result.model_dump(exclude_none=True)
        assert "rows" in data
        assert len(data["rows"]) > 0

    @pytest.mark.asyncio
    async def test_live_population_zurich(self):
        from swiss_statistics_mcp.server import GetPopulationInput, bfs_population
        result = await bfs_population(
            GetPopulationInput(region="Zürich", year="2024", breakdown="total")
        )
        data = result.model_dump(exclude_none=True)
        assert "rows" in data
        assert len(data["rows"]) > 0

    @pytest.mark.asyncio
    async def test_live_lookup_commune(self):
        from swiss_statistics_mcp.server import LookupCommuneInput, lookup_commune
        result = await lookup_commune(
            LookupCommuneInput(name_or_bfs_number="Wädenswil", valid_at_date="2025-01-01")
        )
        data = result.model_dump(exclude_none=True)
        assert data["communes"][0]["canton_abbr"] == "ZH"

    @pytest.mark.asyncio
    async def test_live_resolve_anchor(self):
        from swiss_statistics_mcp.server import (
            ResolveHistoricalCommuneInput,
            resolve_historical_commune,
        )
        result = await resolve_historical_commune(
            ResolveHistoricalCommuneInput(
                bfs_number=133, from_date="2000-01-01", to_date="2025-01-01"
            )
        )
        data = result.model_dump(exclude_none=True)
        # Old Horgen (133) re-keys onto today's 295
        assert 295 in [s["bfs_number"] for s in data["resolves_to"]]

    @pytest.mark.asyncio
    async def test_live_search_historical_series(self):
        from swiss_statistics_mcp.server import (
            SearchHistoricalSeriesInput,
            search_historical_series,
        )
        result = await search_historical_series(
            SearchHistoricalSeriesInput(topic="Bevölkerung")
        )
        data = result.model_dump(exclude_none=True)
        assert data["total_matches"] > 0
        assert data["series"][0]["xlsx_url"].endswith(".xlsx")
