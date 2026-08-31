"""Tests for FrostWatchConfig."""


def test_db_path_defaults_under_data_dir(tmp_path, monkeypatch):
    """Regression: Path('') normalizes to '.', which used to skip the fallback."""
    monkeypatch.setenv("FROSTWATCH_DATA_DIR", str(tmp_path))
    from frostwatch.core.config import FrostWatchConfig

    cfg = FrostWatchConfig()
    assert str(cfg.db_path) not in ("", ".")
    assert cfg.db_path == tmp_path / "frostwatch.db"
