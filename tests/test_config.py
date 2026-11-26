import pytest

from campaign_perf.config import load_config


def test_config_loads_and_has_core_assumptions():
    cfg = load_config()
    assert cfg["economics"]["gross_margin"] == 0.40
    assert cfg["retention"]["windows_days"] == [30, 60, 90]
    assert cfg["channels"]["Paid Search"]["cost_per_session"] == 1.50
    assert cfg["channels"]["Direct"]["rank"] is False


def test_unknown_spend_model_rejected(tmp_path):
    bad = tmp_path / "a.yaml"
    bad.write_text("channels:\n  X:\n    model: magic\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown spend model"):
        load_config(bad)
