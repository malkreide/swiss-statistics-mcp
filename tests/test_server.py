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

import httpx
import pytest
import respx

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
        _price_index_cache,
        _snapshot_cache,
    )
    _catalog_cache.clear()
    _metadata_cache.clear()
    _metadata_timestamps.clear()
    _snapshot_cache.clear()
    _hsso_index_cache.clear()
    _price_index_cache.clear()
    yield
    _catalog_cache.clear()
    _metadata_cache.clear()
    _metadata_timestamps.clear()
    _snapshot_cache.clear()
    _hsso_index_cache.clear()
    _price_index_cache.clear()


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
        # Depending on the pytest version, caplog may capture a propagated
        # record more than once (its handler and the root capture handler
        # both see it). The server emits each line exactly once — the single
        # copy in "Captured stderr" confirms that — so we assert on distinct
        # logical events, keyed by (event, correlation-id), not raw record
        # count.
        unique = {(e.get("event"), e.get("rid")): e for e in events}
        starts = [e for e in unique.values() if e.get("event") == "tool_start"]
        ends = [e for e in unique.values() if e.get("event") == "tool_end"]

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
# Construction & real-estate tools (STAT-TAB theme 09)
# ---------------------------------------------------------------------------

_BFS_BASE = "https://www.pxweb.bfs.admin.ch/api/v1/de"
_URL_106 = f"{_BFS_BASE}/px-x-0904030000_106/px-x-0904030000_106.px"
_URL_105 = f"{_BFS_BASE}/px-x-0904030000_105/px-x-0904030000_105.px"
_URL_205 = f"{_BFS_BASE}/px-x-0904010000_205/px-x-0904010000_205.px"

_GEO_VAR = "Grossregion (<<) / Kanton (-) / Gemeinde (......)"

# _106 exposes the BFS number AS the value code ('0261').
_META_106 = {
    "title": "Neu erstellte Gebäude mit Wohnungen nach ...",
    "source": "BFS",
    "variables": [
        {
            "code": _GEO_VAR,
            "text": _GEO_VAR,
            "values": ["CH", "ZH", "0261", "0002"],
            "valueTexts": [
                "Schweiz",
                "- Kanton Zürich",
                "......0261 Zürich",
                "......0002 Affoltern am Albis",
            ],
        },
        {
            "code": "Gebäudetyp",
            "text": "Gebäudetyp",
            "values": ["0", "1", "2"],
            "valueTexts": ["Gebäude mit Wohnungen - Total", "Einfamilienhaus", "Mehrfamilienhaus"],
        },
        {
            "code": "Jahr",
            "text": "Jahr",
            "values": ["2013", "2014", "2015"],
            "valueTexts": ["2013", "2014", "2015"],
            "time": True,
        },
    ],
}

# _105 uses an OPAQUE sequential value code ('160'); the BFS number lives only
# in the label ('......0261 Zürich'). This is the real cross-cube quirk.
_META_105 = {
    "title": "Neu erstellte Wohnungen nach ... Anzahl Zimmer ...",
    "source": "BFS",
    "variables": [
        {
            "code": _GEO_VAR,
            "text": _GEO_VAR,
            "values": ["0", "4", "160", "9"],
            "valueTexts": [
                "Schweiz",
                "<< Zürich",
                "......0261 Zürich",
                "......0001 Aeugst am Albis",
            ],
        },
        {
            "code": "Anzahl Zimmer",
            "text": "Anzahl Zimmer",
            "values": ["0", "1", "2", "3", "4", "5", "6"],
            "valueTexts": [
                "Wohnungen - Total",
                "1-Zimmer-Wohnung",
                "2-Zimmer-Wohnung",
                "3-Zimmer-Wohnung",
                "4-Zimmer-Wohnung",
                "5-Zimmer-Wohnung",
                "6-Zimmer-Wohnung oder grösser",
            ],
        },
        {
            "code": "Jahr",
            "text": "Jahr",
            "values": ["2013", "2014", "2015"],
            "valueTexts": ["2013", "2014", "2015"],
            "time": True,
        },
    ],
}

_META_205 = {
    "title": "Bauinvestitionen und Arbeitsvorrat nach ...",
    "source": "BFS",
    "variables": [
        {
            "code": _GEO_VAR,
            "text": _GEO_VAR,
            "values": ["CH", "R1", "ZH", "0261"],
            "valueTexts": [
                "Schweiz",
                "<< Genferseeregion",
                "- Kanton Zürich",
                "......0261 Zürich",
            ],
        },
        {
            "code": "Art der Arbeiten",
            "text": "Art der Arbeiten",
            "values": ["0", "1", "2"],
            "valueTexts": ["Art der Arbeiten - Total", "Neubau", "Umbau"],
        },
        {
            "code": "Kategorie der Bauwerke",
            "text": "Kategorie der Bauwerke",
            "values": ["0", "900"],
            "valueTexts": ["Kategorie der Bauwerke - Total", "Wohnen"],
        },
        {
            "code": "Beobachtungseinheit",
            "text": "Beobachtungseinheit",
            "values": ["kost_j", "var_kost_j", "arbv_k", "var_arbv_k"],
            "valueTexts": [
                "Laufendes Jahr - Absolute Werte",
                "Laufendes Jahr - Veränderungsraten",
                "Folgejahr (Arbeitsvorrat) - Absolute Werte",
                "Folgejahr (Arbeitsvorrat) - Veränderungsraten",
            ],
        },
        {
            "code": "Jahr",
            "text": "Jahr",
            "values": ["2014", "2015", "2016"],
            "valueTexts": ["2014", "2015", "2016"],
            "time": True,
        },
    ],
}


def _jsonstat2(ids, categories, values):
    """Build a minimal json-stat2 payload from (dim, {code: label}) pairs."""
    dimension = {}
    size = []
    for dim, cat in categories:
        codes = list(cat.keys())
        dimension[dim] = {
            "label": dim,
            "category": {
                "index": {c: i for i, c in enumerate(codes)},
                "label": dict(cat),
            },
        }
        size.append(len(codes))
    return {
        "class": "dataset",
        "label": "test",
        "source": "BFS",
        "updated": "2025-01-01",
        "id": ids,
        "size": size,
        "dimension": dimension,
        "value": values,
    }


def _resp_106():
    return _jsonstat2(
        [_GEO_VAR, "Gebäudetyp", "Jahr"],
        [
            (_GEO_VAR, {"0261": "......0261 Zürich"}),
            ("Gebäudetyp", {"0": "Gebäude mit Wohnungen - Total"}),
            ("Jahr", {"2013": "2013", "2014": "2014", "2015": "2015"}),
        ],
        [195, 153, 250],
    )


def _resp_105():
    # room dim (7) × year dim (3): room-outer, year-inner.
    rooms = {
        "0": "Wohnungen - Total",
        "1": "1-Zimmer-Wohnung",
        "2": "2-Zimmer-Wohnung",
        "3": "3-Zimmer-Wohnung",
        "4": "4-Zimmer-Wohnung",
        "5": "5-Zimmer-Wohnung",
        "6": "6-Zimmer-Wohnung oder grösser",
    }
    values = (
        [500, 520, 540]  # total
        + [50, 55, 60]  # 1-room
        + [80, 80, 80]  # 2-room
        + [100, 110, 120]  # 3-room
        + [120, 125, 130]  # 4-room
        + [30, 25, 20]  # 5-room
        + [20, 30, 30]  # 6+-room
    )
    return _jsonstat2(
        [_GEO_VAR, "Anzahl Zimmer", "Jahr"],
        [
            (_GEO_VAR, {"160": "......0261 Zürich"}),
            ("Anzahl Zimmer", rooms),
            ("Jahr", {"2013": "2013", "2014": "2014", "2015": "2015"}),
        ],
        values,
    )


def _resp_205():
    # Beobachtungseinheit (2) × Jahr (3): unit-outer, year-inner.
    return _jsonstat2(
        [_GEO_VAR, "Art der Arbeiten", "Kategorie der Bauwerke", "Beobachtungseinheit", "Jahr"],
        [
            (_GEO_VAR, {"ZH": "- Kanton Zürich"}),
            ("Art der Arbeiten", {"0": "Art der Arbeiten - Total"}),
            ("Kategorie der Bauwerke", {"0": "Kategorie der Bauwerke - Total"}),
            (
                "Beobachtungseinheit",
                {
                    "kost_j": "Laufendes Jahr - Absolute Werte",
                    "arbv_k": "Folgejahr (Arbeitsvorrat) - Absolute Werte",
                },
            ),
            ("Jahr", {"2014": "2014", "2015": "2015", "2016": "2016"}),
        ],
        [1000, 1100, 1200, 2000, 2100, 2200],
    )


class TestConstructionGeoResolver:
    """The geo resolver must handle both cube coding schemes (BFS-as-code and
    opaque-code-with-BFS-in-label) — the core PxWeb Gemeindecode quirk."""

    def test_bfs_number_as_value_code(self):
        from swiss_statistics_mcp.server import _resolve_municipality_geo

        code, name = _resolve_municipality_geo(_META_106, _GEO_VAR, 261)
        assert code == "0261"
        assert name == "Zürich"

    def test_opaque_code_with_bfs_in_label(self):
        """Regression: _105 codes Zürich as '160'; the BFS number 261 appears
        only in the label. Matching on the code would silently pick the wrong
        commune."""
        from swiss_statistics_mcp.server import _resolve_municipality_geo

        code, name = _resolve_municipality_geo(_META_105, _GEO_VAR, 261)
        assert code == "160"
        assert name == "Zürich"

    def test_unknown_bfs_returns_none(self):
        from swiss_statistics_mcp.server import _resolve_municipality_geo

        assert _resolve_municipality_geo(_META_106, _GEO_VAR, 9998) == (None, None)

    def test_investment_geo_by_level(self):
        from swiss_statistics_mcp.server import _resolve_investment_geo

        assert _resolve_investment_geo(_META_205, "kanton", "ZH") == ("ZH", "Kanton Zürich")
        assert _resolve_investment_geo(_META_205, "gemeinde", "261") == ("0261", "Zürich")
        assert _resolve_investment_geo(_META_205, "grossregion", "R1") == (
            "R1",
            "Genferseeregion",
        )

    def test_investment_geo_name_substring_fallback(self):
        from swiss_statistics_mcp.server import _resolve_investment_geo

        code, name = _resolve_investment_geo(_META_205, "grossregion", "Genfersee")
        assert code == "R1"


class TestConstructionActivity:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path_series_with_rooms(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )

        respx.get(_URL_106).mock(return_value=httpx.Response(200, json=_META_106))
        respx.post(_URL_106).mock(return_value=httpx.Response(200, json=_resp_106()))
        respx.get(_URL_105).mock(return_value=httpx.Response(200, json=_META_105))
        respx.post(_URL_105).mock(return_value=httpx.Response(200, json=_resp_105()))

        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=261, since_year=2013)
        )
        data = result.model_dump(exclude_none=True)

        assert data["municipality_name"] == "Zürich"
        assert data["table_ids"] == ["px-x-0904030000_106", "px-x-0904030000_105"]
        assert len(data["years"]) == 3
        y0 = data["years"][0]
        assert y0["year"] == 2013
        assert y0["new_buildings"] == 195
        assert y0["new_dwellings"] == 500
        assert y0["dwellings_by_rooms"]["1-Zimmer-Wohnung"] == 50
        assert "Wohnungen - Total" not in y0["dwellings_by_rooms"]  # total excluded
        assert data["provenance"] == "live_api"

    @respx.mock
    @pytest.mark.asyncio
    async def test_since_year_filters_earlier_years(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )

        respx.get(_URL_106).mock(return_value=httpx.Response(200, json=_META_106))
        respx.post(_URL_106).mock(return_value=httpx.Response(200, json=_resp_106()))
        respx.get(_URL_105).mock(return_value=httpx.Response(200, json=_META_105))
        respx.post(_URL_105).mock(return_value=httpx.Response(200, json=_resp_105()))

        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=261, since_year=2015)
        )
        data = result.model_dump(exclude_none=True)
        assert [y["year"] for y in data["years"]] == [2015]

    @respx.mock
    @pytest.mark.asyncio
    async def test_unknown_commune_graceful(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )

        respx.get(_URL_106).mock(return_value=httpx.Response(200, json=_META_106))

        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=9998, since_year=2013)
        )
        data = result.model_dump(exclude_none=True)
        assert "error" in data and "hint" in data

    @respx.mock
    @pytest.mark.asyncio
    async def test_bad_query_400_is_sanitized(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )

        respx.get(_URL_106).mock(return_value=httpx.Response(200, json=_META_106))
        respx.post(_URL_106).mock(return_value=httpx.Response(400, text="Bad Request"))

        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=261, since_year=2013)
        )
        data = result.model_dump(exclude_none=True)
        assert "400" in data["error"]
        assert "hint" in data


class TestConstructionInvestment:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path_investment_and_arbeitsvorrat(self):
        from swiss_statistics_mcp.server import (
            ConstructionInvestmentInput,
            bfs_construction_investment,
        )

        respx.get(_URL_205).mock(return_value=httpx.Response(200, json=_META_205))
        respx.post(_URL_205).mock(return_value=httpx.Response(200, json=_resp_205()))

        result = await bfs_construction_investment(
            ConstructionInvestmentInput(level="kanton", code="ZH", since_year=2014)
        )
        data = result.model_dump(exclude_none=True)

        assert data["region_name"] == "Kanton Zürich"
        assert data["unit"] == "1000 CHF"
        assert len(data["years"]) == 3
        y0 = data["years"][0]
        assert y0["year"] == 2014
        assert y0["investment"] == 1000
        assert y0["work_on_hand"] == 2000  # Arbeitsvorrat, the leading indicator

    @respx.mock
    @pytest.mark.asyncio
    async def test_unknown_code_graceful(self):
        from swiss_statistics_mcp.server import (
            ConstructionInvestmentInput,
            bfs_construction_investment,
        )

        respx.get(_URL_205).mock(return_value=httpx.Response(200, json=_META_205))

        result = await bfs_construction_investment(
            ConstructionInvestmentInput(level="kanton", code="XX")
        )
        data = result.model_dump(exclude_none=True)
        assert "error" in data and "hint" in data


class TestConstructionRetry:
    """The construction tools inherit the shared transient-error retry."""

    @pytest.fixture(autouse=True)
    def _fast_retries(self, monkeypatch):
        import swiss_statistics_mcp.server as srv

        monkeypatch.setattr(srv, "RETRY_WAIT_INITIAL", 0.001)
        monkeypatch.setattr(srv, "RETRY_WAIT_MAX", 0.002)

    @respx.mock
    @pytest.mark.asyncio
    async def test_503_on_data_post_then_succeeds(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )

        respx.get(_URL_106).mock(return_value=httpx.Response(200, json=_META_106))
        respx.get(_URL_105).mock(return_value=httpx.Response(200, json=_META_105))
        respx.post(_URL_105).mock(return_value=httpx.Response(200, json=_resp_105()))
        post_106 = respx.post(_URL_106).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=_resp_106()),
            ]
        )

        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=261, since_year=2013)
        )
        data = result.model_dump(exclude_none=True)
        assert data.get("error") is None
        assert len(data["years"]) == 3
        assert post_106.call_count == 2  # retried once after the 503


class TestConstructionValidation:
    def test_bad_level_rejected(self):
        from swiss_statistics_mcp.server import ConstructionInvestmentInput

        with pytest.raises(Exception):
            ConstructionInvestmentInput(level="planet", code="ZH")

    def test_municipality_bfs_range(self):
        from swiss_statistics_mcp.server import ConstructionActivityInput

        with pytest.raises(Exception):
            ConstructionActivityInput(municipality_bfs=0)

    def test_since_year_lower_bound(self):
        from swiss_statistics_mcp.server import ConstructionActivityInput

        with pytest.raises(Exception):
            ConstructionActivityInput(municipality_bfs=261, since_year=2010)

    def test_defaults(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            ConstructionInvestmentInput,
        )

        assert ConstructionActivityInput(municipality_bfs=261).since_year == 2015
        assert ConstructionInvestmentInput(level="gemeinde", code="261").since_year == 2015


# ---------------------------------------------------------------------------
# Price indices — IMPI & Baupreisindex (CKAN + DAM)
# ---------------------------------------------------------------------------

_CKAN_SEARCH_PREFIX = "https://ckan.opendata.swiss/api/3/action/package_search"
_DAM_PDF_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/111/master"
_DAM_XLSX_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/222/master"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _make_bpi_xlsx_bytes():
    """Build a minimal Baupreisindex workbook matching the real structure:
    a year-named base sheet with month/year header rows and REG/OBJ code rows."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2025"
    ws.append(["<BASE_2025>", "Basis Oktober 2025 = 100"])
    ws.append([None, None, "Gewicht in %", "Oktober", "April", "Oktober"])
    ws.append([None, None, None, 2024, 2025, 2025])
    ws.append(["<REG_01>", "Schweiz"])
    ws.append(["<OBJ_02>", "Baugewerbe\xa0: Total", 100, 99.1, 99.7, 100.0])
    ws.append(["<REG_02>", "Genferseeregion"])
    # This second REG_01-less block must NOT be picked for the national series.
    ws.append(["<OBJ_02>", "Baugewerbe\xa0: Total", 100, 50.0, 51.0, 52.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _ckan_bpi_result():
    return {
        "result": {
            "count": 1,
            "results": [
                {
                    "name": "schweizerischer-baupreisindex-multibasen",
                    "title": {"de": "Schweizerischer Baupreisindex (Multibasen)"},
                    "resources": [
                        {"format": "PDF", "url": _DAM_PDF_URL},
                        {"format": "XLSX", "url": _DAM_XLSX_URL},
                    ],
                }
            ],
        }
    }


def _ckan_impi_result():
    return {
        "result": {
            "count": 1,
            "results": [
                {
                    "name": "schweizerischer-wohnimmobilienpreisindex-impi",
                    "title": {"de": "Schweizerischer Wohnimmobilienpreisindex (IMPI)"},
                    "resources": [
                        {"format": "PDF", "url": _DAM_PDF_URL},
                        {"format": "HTML", "url": "https://www.bfs.admin.ch/asset/de/2071-2003"},
                    ],
                }
            ],
        }
    }


class TestPriceIndexParser:
    def test_parses_national_baugewerbe_total(self):
        from swiss_statistics_mcp.server import _parse_baupreisindex_xlsx

        parsed = _parse_baupreisindex_xlsx(_make_bpi_xlsx_bytes())
        assert parsed is not None
        base, base_label, obj_label, series = parsed
        assert base == "2025"
        assert base_label == "Basis Oktober 2025 = 100"
        assert obj_label == "Baugewerbe : Total"  # nbsp normalized
        assert series == [("2024-10", 99.1), ("2025-04", 99.7), ("2025-10", 100.0)]
        # The Genferseeregion block (50/51/52) must not leak into the national row.

    def test_returns_none_on_unexpected_structure(self):
        import io

        import openpyxl

        from swiss_statistics_mcp.server import _parse_baupreisindex_xlsx

        wb = openpyxl.Workbook()
        wb.active.title = "Info"  # no year-named base sheet
        buf = io.BytesIO()
        wb.save(buf)
        assert _parse_baupreisindex_xlsx(buf.getvalue()) is None


class TestPriceIndexBaupreisindex:
    @respx.mock
    @pytest.mark.asyncio
    async def test_happy_path_parses_series_and_skips_pdf(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(200, json=_ckan_bpi_result())
        )
        # First candidate is a PDF and must be skipped by content-type.
        respx.get(_DAM_PDF_URL).mock(
            return_value=httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})
        )
        respx.get(_DAM_XLSX_URL).mock(
            return_value=httpx.Response(
                200, content=_make_bpi_xlsx_bytes(), headers={"content-type": _XLSX_MIME}
            )
        )

        result = await bfs_price_index(PriceIndexInput(index="baupreisindex"))
        data = result.model_dump(exclude_none=True)
        assert data.get("error") is None
        assert data["base"] == "Basis Oktober 2025 = 100"
        assert "Baugewerbe" in data["coverage"]
        assert data["series"][0] == {"period": "2024-10", "value": 99.1}
        assert data["provenance"] == "live_api"

    @respx.mock
    @pytest.mark.asyncio
    async def test_since_year_filters_series(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(200, json=_ckan_bpi_result())
        )
        respx.get(_DAM_PDF_URL).mock(
            return_value=httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        )
        respx.get(_DAM_XLSX_URL).mock(
            return_value=httpx.Response(
                200, content=_make_bpi_xlsx_bytes(), headers={"content-type": _XLSX_MIME}
            )
        )

        result = await bfs_price_index(
            PriceIndexInput(index="baupreisindex", since_year=2025)
        )
        periods = [p["period"] for p in result.model_dump()["series"]]
        assert periods == ["2025-04", "2025-10"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_second_call_is_cached(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        ckan = respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(200, json=_ckan_bpi_result())
        )
        respx.get(_DAM_PDF_URL).mock(
            return_value=httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        )
        respx.get(_DAM_XLSX_URL).mock(
            return_value=httpx.Response(
                200, content=_make_bpi_xlsx_bytes(), headers={"content-type": _XLSX_MIME}
            )
        )

        await bfs_price_index(PriceIndexInput(index="baupreisindex"))
        r2 = await bfs_price_index(PriceIndexInput(index="baupreisindex"))
        assert r2.provenance == "cached"
        assert ckan.call_count == 1  # network hit only once


class TestPriceIndexImpi:
    @respx.mock
    @pytest.mark.asyncio
    async def test_impi_returns_links_and_limitation(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(200, json=_ckan_impi_result())
        )

        result = await bfs_price_index(PriceIndexInput(index="impi"))
        data = result.model_dump(exclude_none=True)
        assert data.get("error") is None
        assert "series" not in data  # IMPI has no machine-readable series
        assert data["source_links"]
        assert "PDF" in data["note"]


class TestPriceIndexUserAgent:
    """Regression for the CKAN 403-without-User-Agent quirk: every CKAN call
    MUST carry a custom User-Agent header."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_ckan_request_sends_custom_user_agent(self):
        from swiss_statistics_mcp.server import (
            CKAN_USER_AGENT,
            PriceIndexInput,
            bfs_price_index,
        )

        route = respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(200, json=_ckan_impi_result())
        )
        await bfs_price_index(PriceIndexInput(index="impi"))
        sent_ua = route.calls.last.request.headers.get("user-agent")
        assert sent_ua == CKAN_USER_AGENT
        assert sent_ua.startswith("swiss-statistics-mcp/")

    @respx.mock
    @pytest.mark.asyncio
    async def test_ckan_403_is_graceful(self):
        """If CKAN rejects the request (the 403 quirk), the tool degrades
        cleanly instead of leaking a stacktrace."""
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        respx.get(url__startswith=_CKAN_SEARCH_PREFIX).mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = await bfs_price_index(PriceIndexInput(index="baupreisindex"))
        data = result.model_dump(exclude_none=True)
        assert "error" in data and "hint" in data


class TestPriceIndexValidation:
    def test_bad_index_rejected(self):
        from swiss_statistics_mcp.server import PriceIndexInput

        with pytest.raises(Exception):
            PriceIndexInput(index="hauspreise")

    def test_since_year_optional(self):
        from swiss_statistics_mcp.server import PriceIndexInput

        assert PriceIndexInput(index="impi").since_year is None


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

    @pytest.mark.asyncio
    async def test_live_construction_activity_zurich(self):
        from swiss_statistics_mcp.server import (
            ConstructionActivityInput,
            bfs_construction_activity,
        )
        result = await bfs_construction_activity(
            ConstructionActivityInput(municipality_bfs=261, since_year=2015)
        )
        data = result.model_dump(exclude_none=True)
        assert data["municipality_name"] == "Zürich"
        assert len(data["years"]) > 0
        # room-count breakdown must resolve despite _105's opaque geo codes
        assert data["years"][0]["dwellings_by_rooms"]

    @pytest.mark.asyncio
    async def test_live_construction_investment_canton_zh(self):
        from swiss_statistics_mcp.server import (
            ConstructionInvestmentInput,
            bfs_construction_investment,
        )
        result = await bfs_construction_investment(
            ConstructionInvestmentInput(level="kanton", code="ZH", since_year=2015)
        )
        data = result.model_dump(exclude_none=True)
        assert len(data["years"]) > 0
        assert data["years"][0]["work_on_hand"] is not None

    @pytest.mark.asyncio
    async def test_live_price_index_baupreisindex(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        result = await bfs_price_index(
            PriceIndexInput(index="baupreisindex", since_year=2015)
        )
        data = result.model_dump(exclude_none=True)
        assert data.get("error") is None
        assert len(data["series"]) > 0
        assert data["series"][-1]["value"] > 0

    @pytest.mark.asyncio
    async def test_live_price_index_impi_links(self):
        from swiss_statistics_mcp.server import PriceIndexInput, bfs_price_index

        result = await bfs_price_index(PriceIndexInput(index="impi"))
        data = result.model_dump(exclude_none=True)
        assert data.get("error") is None
        assert data["source_links"]  # PDF/HTML links, no parsed series
