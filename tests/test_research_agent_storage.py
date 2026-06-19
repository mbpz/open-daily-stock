"""Tests for ResearchAgent P7-4 storage split (slim steps + separate artifacts)."""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.agents.research_agent import ResearchAgent, ResearchStep, ResearchReport


def _make_report(code="600519", topic="test", large_output_size_kb=5):
    """Build a report with a deliberately large tool_output (search results)."""
    # 5 KB fake "search_news" payload
    big = {
        "results": [
            {"title": f"title-{i}", "url": f"https://example.com/{i}", "snippet": "x" * 200}
            for i in range(20)
        ]
    }
    steps = [
        ResearchStep(
            iteration=1, thinking="search first",
            action="search_news", tool_input={"q": "a"},
            tool_output=big, observation="20 results",
        ),
        ResearchStep(
            iteration=2, thinking="check kline",
            action="get_kline", tool_input={"code": code},
            tool_output={"date": "2024-01-01", "close": 100.0}, observation="kline ok",
        ),
    ]
    return ResearchReport(
        code=code, topic=topic, steps=steps,
        final_report="# report", tool_calls=2,
        duration_seconds=1.5, timestamp="2024-01-01T00:00:00",
    )


@pytest.fixture
def isolated_db():
    """Use a temp DB so we don't pollute the real one."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_research.db"
        with patch("src.storage.get_config") as gc:
            cfg = MagicMock()
            cfg.get_db_url.return_value = f"sqlite:///{db_path}"
            cfg.is_demo_mode.return_value = False
            cfg.debug = False
            cfg.auto_check_update = False
            gc.return_value = cfg
            from src.storage import DatabaseManager
            DatabaseManager.reset_instance()
            db = DatabaseManager(db_url=f"sqlite:///{db_path}")
            yield db
            DatabaseManager.reset_instance()


def test_save_report_creates_artifacts_table(isolated_db):
    agent = ResearchAgent()
    report = _make_report()
    agent._save_report(report)
    # Verify both tables exist
    from sqlalchemy import text
    with isolated_db.get_session() as session:
        rows = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('research_logs', 'research_artifacts')"
        )).fetchall()
        table_names = {r[0] for r in rows}
        assert "research_logs" in table_names
        assert "research_artifacts" in table_names


def test_save_report_strips_tool_output_from_steps_json(isolated_db):
    """The slim steps_json must not contain the heavy tool_output field."""
    from sqlalchemy import text
    agent = ResearchAgent()
    report = _make_report()
    agent._save_report(report)

    with isolated_db.get_session() as session:
        row = session.execute(text("SELECT steps_json FROM research_logs")).fetchone()
        steps_json = row[0]

    # Verify tool_output is NOT in the JSON
    assert "tool_output" not in steps_json, "tool_output leaked into steps_json"
    # But the summary fields ARE there
    parsed = json.loads(steps_json)
    assert len(parsed) == 2
    assert parsed[0]["action"] == "search_news"
    assert parsed[0]["observation"] == "20 results"
    assert parsed[1]["action"] == "get_kline"


def test_save_report_persists_tool_outputs_in_artifacts(isolated_db):
    """Each step's tool_output must be stored in research_artifacts."""
    from sqlalchemy import text
    agent = ResearchAgent()
    report = _make_report()
    agent._save_report(report)

    with isolated_db.get_session() as session:
        rows = session.execute(text(
            "SELECT iteration, tool_name, output_json, output_size_bytes "
            "FROM research_artifacts ORDER BY iteration"
        )).fetchall()

    assert len(rows) == 2
    # First row: search_news with the large payload
    assert rows[0][0] == 1
    assert rows[0][1] == "search_news"
    payload = json.loads(rows[0][2])
    assert len(payload["results"]) == 20
    assert rows[0][3] > 1024  # size in bytes > 1KB

    # Second row: kline
    assert rows[1][1] == "get_kline"
    assert json.loads(rows[1][2])["close"] == 100.0


def test_load_report_rehydrates_tool_outputs(isolated_db):
    """load_report should reattach the full tool_output to each step."""
    from sqlalchemy import text
    agent = ResearchAgent()
    report = _make_report()
    agent._save_report(report)

    # Find the inserted id
    with isolated_db.get_session() as session:
        log_id = session.execute(text("SELECT id FROM research_logs")).fetchone()[0]

    loaded = agent.load_report(log_id)
    assert loaded is not None
    assert loaded.code == "600519"
    assert len(loaded.steps) == 2
    # tool_output must be reattached from artifacts
    assert loaded.steps[0].action == "search_news"
    assert loaded.steps[0].tool_output is not None
    assert len(loaded.steps[0].tool_output["results"]) == 20
    assert loaded.steps[1].tool_output == {"date": "2024-01-01", "close": 100.0}


def test_load_report_returns_none_for_missing_id(isolated_db):
    agent = ResearchAgent()
    assert agent.load_report(99999) is None


def test_steps_json_size_is_substantially_smaller(isolated_db):
    """The whole point: storing artifacts separately keeps research_logs slim."""
    from sqlalchemy import text
    agent = ResearchAgent()
    # 10 KB+ payload
    big = {"results": [{"x": "y" * 500} for _ in range(20)]}
    steps = [ResearchStep(
        iteration=1, thinking="t", action="search_news",
        tool_input={}, tool_output=big, observation="o",
    )] * 3  # 3 large steps
    report = ResearchReport(
        code="x", topic="t", steps=steps,
        final_report="r", tool_calls=3, duration_seconds=1.0,
        timestamp="2024-01-01",
    )
    agent._save_report(report)

    with isolated_db.get_session() as session:
        slim_size = session.execute(text(
            "SELECT LENGTH(steps_json) FROM research_logs"
        )).fetchone()[0]
        artifact_total = session.execute(text(
            "SELECT SUM(output_size_bytes) FROM research_artifacts"
        )).fetchone()[0]

    # slim JSON should be a tiny fraction of the artifacts (~5% or less).
    assert slim_size < artifact_total / 10, (
        f"steps_json ({slim_size} bytes) not slim enough vs artifacts "
        f"({artifact_total} bytes)"
    )
    # And artifacts actually contain the big payload
    assert artifact_total > 10_000
