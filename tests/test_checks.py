import json
from datetime import datetime, timezone

import pytest

from flow_run_audit import checks
from flow_run_audit.cli import load_runs, main

NOW = datetime(2026, 11, 19, 16, 0, tzinfo=timezone.utc)


def run(**kw):
    base = dict(flow="f", run_id="r", status="Succeeded", outputs={"x": 1}, log="")
    base.update(kw)
    return base


def test_duplicate_success_found():
    f = checks.duplicate_success([run(run_id="a", trigger_key="k"), run(run_id="b", trigger_key="k")])
    assert len(f) == 1 and f[0].run_ids == ["a", "b"]


def test_duplicate_ignores_failed_and_other_keys():
    runs = [run(run_id="a", trigger_key="k"), run(run_id="b", trigger_key="k", status="Failed"),
            run(run_id="c", trigger_key="z")]
    assert checks.duplicate_success(runs) == []


def test_silent_failure():
    assert len(checks.silent_failure([run(outputs={})])) == 1
    assert checks.silent_failure([run(outputs={"a": 1})]) == []
    assert checks.silent_failure([run(status="Failed", outputs=None)]) == []


def test_retry_storm_threshold():
    assert checks.retry_storm([run(attempt=3)]) == []
    assert len(checks.retry_storm([run(attempt=4)])) == 1
    assert len(checks.retry_storm([run(attempt=2)], max_attempts=1)) == 1


def test_stuck_runs():
    old = run(status="Running", started_at="2026-11-19T09:00:00Z")
    new = run(status="Running", started_at="2026-11-19T15:45:00Z")
    assert len(checks.stuck_runs([old, new], NOW)) == 1


@pytest.mark.parametrize("text,kind", [
    ("SSN 000-12-3456", "ssn"),
    ("mail a.b@example.com", "email"),
    ("call (555) 123-4567", "us_phone"),
    ("dob: 1980-01-02", "dob"),
])
def test_pii_patterns(text, kind):
    f = checks.pii_in_logs([run(log=text)])
    assert len(f) == 1 and kind in f[0].message


def test_pii_clean_log():
    assert checks.pii_in_logs([run(log="checked case-1001 ok")]) == []


def test_run_all_sorted_high_first():
    f = checks.run_all([run(run_id="a", attempt=9), run(run_id="b", outputs={})], NOW)
    assert [x.severity for x in f] == ["high", "medium"]


def test_load_jsonl_and_json_array(tmp_path):
    rec = run()
    (tmp_path / "a.jsonl").write_text(json.dumps(rec) + "\n")
    (tmp_path / "b.json").write_text(json.dumps([rec]))
    assert load_runs(tmp_path / "a.jsonl") == load_runs(tmp_path / "b.json")


def test_load_rejects_missing_field(tmp_path):
    (tmp_path / "a.jsonl").write_text('{"flow":"f"}\n')
    with pytest.raises(ValueError):
        load_runs(tmp_path / "a.jsonl")


def test_cli_sample_exit_code_and_output(capsys):
    code = main(["examples/sample_runs.jsonl", "--now", "2026-11-19T16:00:00Z"])
    out = capsys.readouterr().out
    assert code == 1
    assert "duplicate_success" in out and "silent_failure" in out
    assert "retry_storm" in out and "stuck_run" in out and "pii_in_logs" in out


def test_cli_sample_counts(capsys):
    main(["examples/sample_runs.jsonl", "--now", "2026-11-19T16:00:00Z", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert sorted(d["check"] for d in data) == [
        "duplicate_success", "pii_in_logs", "retry_storm", "silent_failure", "stuck_run"]


def test_cli_missing_file():
    assert main(["nope.jsonl"]) == 2


def test_cli_clean_file_exit_zero(tmp_path, capsys):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps(run(trigger_key="k")) + "\n")
    assert main([str(p)]) == 0
    assert "No findings" in capsys.readouterr().out
