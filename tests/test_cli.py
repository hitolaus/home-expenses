import shutil

from budget import __main__ as cli
from tests.conftest import SAMPLE_PDF
from tests.test_categorizer import FakeClaude


def test_run_twice_imports_once_and_calls_claude_only_on_first_run(tmp_path, config_path, monkeypatch, capsys):
    cfg = config_path("2026-01-31")
    shutil.copy(SAMPLE_PDF, tmp_path / "statements")
    fake = FakeClaude()
    monkeypatch.setattr(cli, "make_classifier", lambda config: fake)
    overrides = tmp_path / "overrides.toml"

    assert cli.main(["--config", str(cfg), "--overrides", str(overrides), "run"]) == 0
    first = capsys.readouterr().out
    calls_after_first = len(fake.calls)
    assert cli.main(["--config", str(cfg), "--overrides", str(overrides)]) == 0
    second = capsys.readouterr().out

    assert "new: 67" in first and calls_after_first > 0
    assert "new: 0" in second and "duplicates skipped: 67" in second and "Claude calls: 0" in second
    assert len(fake.calls) == calls_after_first
    assert (tmp_path / "output" / "report.html").exists()


def test_override_applies_on_next_run_without_api_call(tmp_path, config_path, monkeypatch, capsys):
    cfg = config_path("2026-01-31")
    shutil.copy(SAMPLE_PDF, tmp_path / "statements")
    fake = FakeClaude()
    monkeypatch.setattr(cli, "make_classifier", lambda config: fake)
    overrides = tmp_path / "overrides.toml"
    cli.main(["--config", str(cfg), "--overrides", str(overrides)])
    calls = len(fake.calls)

    overrides.write_text('[rules]\n"rejsekort" = "Miscellaneous"\n', encoding="utf-8")
    cli.main(["--config", str(cfg), "--overrides", str(overrides)])

    assert len(fake.calls) == calls
    from budget import db
    conn = db.connect(tmp_path / "data" / "budget.db")
    assert {t.category for t in db.all_transactions(conn) if t.description == "Rejsekort"} == {"Miscellaneous"}


def test_bad_config_exits_with_error(tmp_path, capsys):
    (tmp_path / "config.toml").write_text('window_months = 0\n', encoding="utf-8")
    assert cli.main(["--config", str(tmp_path / "config.toml"), "report"]) == 2


def test_run_without_claude_cli_still_writes_report(tmp_path, config_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")  # no `claude` executable
    monkeypatch.chdir(tmp_path)
    cfg = config_path("2026-01-31")
    shutil.copy(SAMPLE_PDF, tmp_path / "statements")

    assert cli.main(["--config", str(cfg), "--overrides", str(tmp_path / "overrides.toml")]) == 0

    out = capsys.readouterr().out
    assert "uncategorized: 67" in out and "Claude calls: 0" in out
    assert (tmp_path / "output" / "report.html").exists()
