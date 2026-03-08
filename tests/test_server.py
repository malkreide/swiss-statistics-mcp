"""
Tests for swiss-statistics-mcp.

Three tiers:
  - Unit tests (fast, no network)
  - Integration tests (mock HTTP)
  - Live smoke tests (real API, marked separately)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        assert result["total_rows"] == 4
        assert result["returned_rows"] == 4
        assert len(result["rows"]) == 4
        assert result["rows"][0]["Schuljahr"] == "2022/23"
        assert result["rows"][0]["Kanton"] == "Zürich"
        assert result["rows"][0]["Wert"] == 5000

    def test_max_rows_respected(self):
        from swiss_statistics_mcp.server import _format_jsonstat2_as_table
        data = _mock_jsonstat2_response()
        result = _format_jsonstat2_as_table(data, max_rows=2)

        assert result["returned_rows"] == 2
        assert result["total_rows"] == 4
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
        from swiss_statistics_mcp.server import bfs_list_themes, ListThemesInput

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_all_dbs_response(),
        ):
            result = await bfs_list_themes(ListThemesInput(lang="de"))
            data = json.loads(result)

        assert "themes" in data
        assert len(data["themes"]) == 21
        assert data["total_datasets"] == len(_mock_all_dbs_response())

    @pytest.mark.asyncio
    async def test_theme_codes_present(self):
        from swiss_statistics_mcp.server import bfs_list_themes, ListThemesInput

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_all_dbs_response(),
        ):
            result = await bfs_list_themes(ListThemesInput(lang="de"))
            data = json.loads(result)

        codes = [t["code"] for t in data["themes"]]
        assert "15" in codes  # Bildung
        assert "01" in codes  # Bevölkerung
        assert "17" in codes  # Politik


class TestBfsGetTableMetadata:
    @pytest.mark.asyncio
    async def test_returns_variables(self):
        from swiss_statistics_mcp.server import bfs_get_table_metadata, GetTableMetadataInput

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_teacher_metadata(),
        ):
            result = await bfs_get_table_metadata(
                GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
            )
            data = json.loads(result)

        assert "variables" in data
        assert data["n_variables"] == 3
        assert data["variables"][0]["code"] == "Schuljahr"

    @pytest.mark.asyncio
    async def test_theme_info_included(self):
        from swiss_statistics_mcp.server import bfs_get_table_metadata, GetTableMetadataInput

        with patch(
            "swiss_statistics_mcp.server._get",
            new_callable=AsyncMock,
            return_value=_mock_teacher_metadata(),
        ):
            result = await bfs_get_table_metadata(
                GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
            )
            data = json.loads(result)

        assert data["theme_code"] == "15"
        assert "Bildung" in data["theme_name"]

    @pytest.mark.asyncio
    async def test_404_returns_friendly_error(self):
        import httpx
        from swiss_statistics_mcp.server import bfs_get_table_metadata, GetTableMetadataInput

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
            data = json.loads(result)

        assert "error" in data
        assert "hint" in data


class TestBfsGetData:
    @pytest.mark.asyncio
    async def test_returns_table_structure(self):
        from swiss_statistics_mcp.server import bfs_get_data, GetDataInput

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_get_data(
                GetDataInput(table_id="px-x-1504000000_173")
            )
            data = json.loads(result)

        assert "rows" in data
        assert "title" in data
        assert len(data["rows"]) == 4

    @pytest.mark.asyncio
    async def test_filter_passed_to_api(self):
        from swiss_statistics_mcp.server import bfs_get_data, GetDataInput, DimensionFilter

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
        from swiss_statistics_mcp.server import bfs_get_data, GetDataInput

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
            data = json.loads(result)

        assert "warning" in data
        assert data["returned_rows"] == 100
        assert data["total_rows"] == 1000


class TestBfsEducationStats:
    @pytest.mark.asyncio
    async def test_teachers_topic(self):
        from swiss_statistics_mcp.server import bfs_education_stats, GetEducationStatsInput

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_education_stats(
                GetEducationStatsInput(topic="teachers", lang="de")
            )
            data = json.loads(result)

        assert data["topic"] == "teachers"
        assert "rows" in data
        assert "px-x-1504000000_173" in data["table_id"]

    @pytest.mark.asyncio
    async def test_canton_filter_resolved(self):
        from swiss_statistics_mcp.server import bfs_education_stats, GetEducationStatsInput

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
        from swiss_statistics_mcp.server import bfs_education_stats, GetEducationStatsInput

        result = await bfs_education_stats(
            GetEducationStatsInput(topic="teachers", canton="Fantasialand")
        )
        data = json.loads(result)
        assert "error" in data


class TestBfsPopulation:
    @pytest.mark.asyncio
    async def test_total_breakdown(self):
        from swiss_statistics_mcp.server import bfs_population, GetPopulationInput

        with patch(
            "swiss_statistics_mcp.server._post",
            new_callable=AsyncMock,
            return_value=_mock_jsonstat2_response(),
        ):
            result = await bfs_population(GetPopulationInput(region="Zürich"))
            data = json.loads(result)

        assert data["region"] == "Zürich"
        assert "rows" in data

    @pytest.mark.asyncio
    async def test_age_breakdown_filters_0_18(self):
        from swiss_statistics_mcp.server import bfs_population, GetPopulationInput

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
        from swiss_statistics_mcp.server import bfs_compare_cantons, CompareCantonsInput

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
                data = json.loads(result)

        assert "rows" in data
        assert data["cantons_compared"] == ["0", "1", "2"]
        assert data["canton_variable"] == "Kanton"


class TestBfsFeaturedDatasets:
    @pytest.mark.asyncio
    async def test_returns_featured_list(self):
        from swiss_statistics_mcp.server import bfs_featured_datasets, ListThemesInput

        result = await bfs_featured_datasets(ListThemesInput(lang="de"))
        data = json.loads(result)

        assert "featured_datasets" in data
        assert data["total"] >= 10

    @pytest.mark.asyncio
    async def test_schulamt_relevance_present(self):
        from swiss_statistics_mcp.server import bfs_featured_datasets, ListThemesInput

        result = await bfs_featured_datasets(ListThemesInput(lang="de"))
        data = json.loads(result)

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


# ---------------------------------------------------------------------------
# Live smoke tests (require network – run separately)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveAPI:
    """Real API calls. Run with: pytest -m live"""

    @pytest.mark.asyncio
    async def test_live_list_themes(self):
        from swiss_statistics_mcp.server import bfs_list_themes, ListThemesInput
        result = await bfs_list_themes(ListThemesInput(lang="de"))
        data = json.loads(result)
        assert data["total_datasets"] > 600

    @pytest.mark.asyncio
    async def test_live_teacher_metadata(self):
        from swiss_statistics_mcp.server import bfs_get_table_metadata, GetTableMetadataInput
        result = await bfs_get_table_metadata(
            GetTableMetadataInput(table_id="px-x-1504000000_173", lang="de")
        )
        data = json.loads(result)
        assert "Lehrkräfte" in data["title"]
        assert len(data["variables"]) >= 3

    @pytest.mark.asyncio
    async def test_live_education_stats_teachers(self):
        from swiss_statistics_mcp.server import bfs_education_stats, GetEducationStatsInput
        result = await bfs_education_stats(
            GetEducationStatsInput(topic="teachers", canton="Zürich")
        )
        data = json.loads(result)
        assert "rows" in data
        assert len(data["rows"]) > 0

    @pytest.mark.asyncio
    async def test_live_population_zurich(self):
        from swiss_statistics_mcp.server import bfs_population, GetPopulationInput
        result = await bfs_population(
            GetPopulationInput(region="Zürich", year="2024", breakdown="total")
        )
        data = json.loads(result)
        assert "rows" in data
        assert len(data["rows"]) > 0
