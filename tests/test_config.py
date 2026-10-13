import pytest

from budget.config import ConfigError, load_config, load_overrides
from tests.conftest import CONFIG_TOML


def write(tmp_path, text, name="config.toml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_example_config_loads():
    from pathlib import Path
    cfg = load_config(Path(__file__).parent.parent / "config.example.toml")
    assert [c.name for c in cfg.budgeted] == [
        "Groceries", "Housing", "Transport", "Restaurants & takeaway", "Shopping & clothes",
        "Subscriptions", "Leisure", "Vacation", "Health", "Children", "Miscellaneous"]
    assert [c.name for c in cfg.non_budgeted] == ["Income", "Transfers"]
    assert cfg.model == "claude-opus-5-5"


def test_model_defaults_to_opus(tmp_path):
    text = CONFIG_TOML.format(reference_date="2026-01-31").replace('model = "claude-haiku-5-5"\n', "")
    assert load_config(write(tmp_path, text)).model == "claude-opus-5-5"


def test_paths_resolve_relative_to_config_file(tmp_path):
    cfg = load_config(write(tmp_path, CONFIG_TOML.format(reference_date="2026-01-31")))
    assert cfg.database == tmp_path / "data" / "budget.db"


def test_reference_date_today(tmp_path):
    import datetime as dt
    cfg = load_config(write(tmp_path, CONFIG_TOML.format(reference_date="today")), today=dt.date(2026, 5, 1))
    assert cfg.reference_date == dt.date(2026, 5, 1)


@pytest.mark.parametrize("broken, message", [
    ('name = "Miscellaneous"', "Miscellaneous"),
    ('yearly_limit = 500', "yearly_limit"),
    ('reference_date = "2026-01-31"', "reference_date"),
])
def test_invalid_config_is_rejected(tmp_path, broken, message):
    text = CONFIG_TOML.format(reference_date="2026-01-31")
    replacement = {'name = "Miscellaneous"': 'name = "Andet"', 'yearly_limit = 500': '',
                   'reference_date = "2026-01-31"': 'reference_date = "yesterday"'}[broken]
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, text.replace(broken, replacement, 1)))


def test_overrides_load_case_insensitively(tmp_path):
    p = write(tmp_path, '[rules]\n"netto" = "Groceries"\n[transactions]\n"A3F9C1D2..." = "Housing"\n', "o.toml")
    o = load_overrides(p, ["Groceries", "Housing"])
    assert o.rules == {"NETTO": "Groceries"}
    assert o.transactions == {"a3f9c1d2": "Housing"}


def test_missing_overrides_file_means_no_overrides(tmp_path):
    o = load_overrides(tmp_path / "nope.toml", ["Housing"])
    assert o.rules == {} and o.transactions == {}


@pytest.mark.parametrize("text", ['[rules]\n"NETTO" = "Food"\n', '[transactions]\n"a3f" = "Housing"\n'])
def test_invalid_overrides_are_rejected(tmp_path, text):
    with pytest.raises(ConfigError):
        load_overrides(write(tmp_path, text, "o.toml"), ["Groceries", "Housing"])
