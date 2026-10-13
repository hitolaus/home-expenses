import json
import subprocess
from types import SimpleNamespace

import pytest

from budget import db
from budget.categorizer import (
    ApiUnavailable, BadResponse, ClaudeClassifier, categorize, reset_claude_results,
)
from budget.config import Overrides
from budget.dedupe import fingerprint_all
from budget.parser import parse_pdf
from tests.conftest import SAMPLE_PDF

GUESSES = {
    "NETTO": "Groceries", "Caffeine": "Restaurant & takeaway", "JOE": "Restaurant & takeaway",
    "Realkredit": "Housing", "Magasin": "Miscellaneous", "Rejsekort": "Transport", "Løn": "Income",
}


class FakeClaude:
    def __init__(self, confidence=0.95, fail=None, respond=None):
        self.calls = []
        self.confidence = confidence
        self.fail = fail
        self.respond = respond

    def __call__(self, items):
        self.calls.append(items)
        if self.fail:
            raise self.fail
        if self.respond:
            return self.respond(items)
        return [{"id": i["id"], "category": next(c for k, c in GUESSES.items() if k in i["description"]),
                 "confidence": self.confidence} for i in items]


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    txs = parse_pdf(SAMPLE_PDF).transactions
    db.insert_transactions(c, txs, fingerprint_all(txs))
    return c


def categories(conn):
    return {t.description: (t.category, t.source) for t in db.all_transactions(conn)}


def test_every_transaction_gets_a_configured_category(conn, config):
    stats = categorize(conn, config, Overrides(), FakeClaude())

    txs = db.all_transactions(conn)
    assert all(t.category in config.category_names for t in txs)
    assert stats.uncategorized == 0
    assert stats.from_claude == len(txs)


def test_recurring_merchant_is_sent_to_claude_once(conn, config):
    fake = FakeClaude()
    categorize(conn, config, Overrides(), fake)

    sent = [i["description"] for batch in fake.calls for i in batch]
    assert sent.count("Rejsekort") == 1
    assert len(sent) == len(set(sent))
    rejsekort = [t for t in db.all_transactions(conn) if t.description == "Rejsekort"]
    assert len(rejsekort) == 60 and {t.category for t in rejsekort} == {"Transport"}


def test_second_run_without_new_transactions_makes_no_api_calls(conn, config):
    categorize(conn, config, Overrides(), FakeClaude())
    fake = FakeClaude()
    stats = categorize(conn, config, Overrides(), fake)
    assert fake.calls == [] and stats.api_calls == 0


def test_merchant_cache_serves_new_transactions_without_api_call(conn, config):
    categorize(conn, config, Overrides(), FakeClaude(confidence=0.9))
    reset = [t.id for t in db.all_transactions(conn) if t.description == "Rejsekort"]
    conn.execute(f"DELETE FROM categorizations WHERE transaction_id IN ({','.join(map(str, reset))})")

    fake = FakeClaude()
    stats = categorize(conn, config, Overrides(), fake)
    assert fake.calls == []
    assert stats.from_cache == 60
    assert categories(conn)["Rejsekort"] == ("Transport", "cache")


def test_low_confidence_results_are_not_cached(conn, config):
    categorize(conn, config, Overrides(), FakeClaude(confidence=0.7))
    assert db.merchant_cache(conn) == {}


def test_unknown_category_becomes_diverse_with_zero_confidence(conn, config):
    fake = FakeClaude(respond=lambda items: [{"id": i["id"], "category": "Made up", "confidence": 0.99}
                                             for i in items])
    categorize(conn, config, Overrides(), fake)
    txs = db.all_transactions(conn)
    assert {(t.category, t.confidence) for t in txs} == {("Miscellaneous", 0.0)}
    assert db.merchant_cache(conn) == {}


def test_results_for_unknown_ids_are_ignored_and_missing_ids_stay_uncategorized(conn, config):
    def respond(items):
        return [{"id": 999999, "category": "Housing", "confidence": 1}] + [
            {"id": i["id"], "category": "Miscellaneous", "confidence": 1} for i in items[1:]]
    stats = categorize(conn, config, Overrides(), FakeClaude(respond=respond))
    assert stats.uncategorized >= 1
    assert all(t.category != "Housing" for t in db.all_transactions(conn))


def test_rule_override_wins_and_needs_no_api_call(conn, config):
    categorize(conn, config, Overrides(), FakeClaude())
    fake = FakeClaude()
    categorize(conn, config, Overrides(rules={"REJSEKORT": "Miscellaneous"}), fake)

    assert fake.calls == []
    assert categories(conn)["Rejsekort"] == ("Miscellaneous", "rule")


def test_pinned_fingerprint_beats_rule(conn, config):
    target = next(t for t in db.all_transactions(conn) if t.description == "Realkredit Danmark")
    overrides = Overrides(rules={"REALKREDIT": "Miscellaneous"},
                          transactions={target.fingerprint[:12]: "Transfers"})
    categorize(conn, config, overrides, FakeClaude())
    assert categories(conn)["Realkredit Danmark"] == ("Transfers", "override")


def test_removing_an_override_reverts_the_transaction(conn, config):
    categorize(conn, config, Overrides(rules={"REALKREDIT": "Miscellaneous"}), FakeClaude())
    categorize(conn, config, Overrides(), FakeClaude())
    assert categories(conn)["Realkredit Danmark"] == ("Housing", "claude")


def test_api_failure_leaves_transactions_uncategorized_and_stops(conn, config):
    fake = FakeClaude(fail=ApiUnavailable("down"))
    stats = categorize(conn, config, Overrides(), fake)
    assert len(fake.calls) == 1
    assert stats.uncategorized == len(db.all_transactions(conn))


def test_bad_batch_response_does_not_stop_other_batches(conn, config, monkeypatch):
    monkeypatch.setattr("budget.categorizer.BATCH_SIZE", 2)
    good = FakeClaude()
    calls = []

    def flaky(items):
        calls.append(items)
        if len(calls) == 1:
            raise BadResponse("garbage")
        return good(items)

    stats = categorize(conn, config, Overrides(), flaky)
    assert len(calls) > 1
    assert 0 < stats.uncategorized < len(db.all_transactions(conn))


def test_no_client_leaves_pending_uncategorized(conn, config):
    stats = categorize(conn, config, Overrides(), None)
    assert stats.uncategorized == len(db.all_transactions(conn))


def test_account_like_numbers_are_masked_before_sending(config):
    c = db.connect(":memory:")
    from tests.test_dedupe import tx
    t = tx(desc="Overført til: 4380567695")
    db.insert_transactions(c, [t], fingerprint_all([t]))
    fake = FakeClaude(respond=lambda items: [])
    categorize(c, config, Overrides(), fake)
    assert fake.calls[0][0]["description"] == "Overført til: ######"


def test_recategorize_all_keeps_overrides(conn, config):
    overrides = Overrides(rules={"REJSEKORT": "Miscellaneous"})
    categorize(conn, config, overrides, FakeClaude())
    reset_claude_results(conn)
    assert db.merchant_cache(conn) == {}
    fake = FakeClaude()
    categorize(conn, config, overrides, fake)
    assert fake.calls
    assert categories(conn)["Rejsekort"] == ("Miscellaneous", "rule")


# --- ClaudeClassifier against a fake `claude` CLI ------------------------------------------------

class FakeRun:
    """Stands in for subprocess.run; records the call and returns a canned CLI result."""

    def __init__(self, stdout="", returncode=0, error=None):
        self.stdout, self.returncode, self.error = stdout, returncode, error
        self.argv = self.kwargs = None

    def __call__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr="")

    def flag(self, name):
        return self.argv[self.argv.index(name) + 1]


def classifier(config, **kw):
    run = FakeRun(**kw)
    return ClaudeClassifier(config, run=run, executable="claude"), run


def cli_result(structured_output=None, is_error=False, result=""):
    out = {"type": "result", "subtype": "success", "is_error": is_error, "result": result}
    if structured_output is not None:
        out["structured_output"] = structured_output
    return json.dumps(out)


def test_classifier_sends_items_to_cli_with_schema_constrained_to_configured_categories(config):
    items = [{"id": 1, "date": "2026-01-01", "description": "Netto", "amount": "-1"}]
    clf, run = classifier(config, stdout=cli_result({"results": [{"id": 1, "category": "Housing", "confidence": 0.9}]}))

    assert clf(items) == [{"id": 1, "category": "Housing", "confidence": 0.9}]
    assert run.argv[0] == "claude" and "-p" in run.argv
    assert run.flag("--model") == "claude-haiku-5-5"
    assert run.flag("--output-format") == "json"
    schema = json.loads(run.flag("--json-schema"))
    assert schema["properties"]["results"]["items"]["properties"]["category"]["enum"] == config.category_names
    assert json.loads(run.kwargs["input"]) == items


def test_classifier_uses_subscription_login_not_api_keys(config, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    clf, run = classifier(config, stdout=cli_result({"results": []}))
    clf([{"id": 1}])
    env = run.kwargs["env"]
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
    assert "PATH" in env


def test_classifier_without_claude_cli_is_unavailable(config, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(ApiUnavailable):
        ClaudeClassifier(config)


@pytest.mark.parametrize("kw", [
    {"stdout": cli_result(is_error=True, result="Not logged in"), "returncode": 1},
    {"stdout": "", "returncode": 1},
    {"error": subprocess.TimeoutExpired(cmd="claude", timeout=1)},
    {"error": FileNotFoundError("claude")},
])
def test_classifier_maps_cli_failures_to_api_unavailable(config, kw):
    clf, _ = classifier(config, **kw)
    with pytest.raises(ApiUnavailable):
        clf([{"id": 1}])


@pytest.mark.parametrize("stdout", ["not json", cli_result(), cli_result({}), cli_result({"results": "x"})])
def test_classifier_rejects_unusable_responses(config, stdout):
    clf, _ = classifier(config, stdout=stdout)
    with pytest.raises(BadResponse):
        clf([{"id": 1}])
