# flow-run-audit

Independent demo, not affiliated with Jobgether (cliente não diz).

A small Python tool that reads an exported log of automation runs and lists the problems that usually hide in them. It was written as a sample for a Senior AI Automation Engineer role (agents and workflows, health-insurance domain), where "test, monitor, troubleshoot and maintain deployed automations" and "comply with data protection standards" are part of the job.

It has no dependencies beyond the Python standard library.

## What it checks

| Check | Severity | What it flags |
|---|---|---|
| `duplicate_success` | high | The same flow and trigger key succeeded more than once, so side effects may have run twice |
| `silent_failure` | high | Status is Succeeded but the outputs are empty |
| `pii_in_logs` | high | Log text matches an SSN, email, US phone number or date-of-birth pattern |
| `retry_storm` | medium | A run's attempt count is above a limit (default 3) |
| `stuck_run` | medium | A run has been Running longer than a limit (default 60 minutes) |

## Input format

JSON array or JSONL. Each record needs `flow`, `run_id` and `status` (`Succeeded`, `Failed` or `Running`). Optional: `trigger_key`, `attempt`, `started_at` (ISO 8601), `outputs`, `log`.

This is a plain format I chose. It is not the export format of any specific product, so a real export needs a small conversion step first.

## Run it

```
uv sync
uv run flow-run-audit examples/sample_runs.jsonl --now 2026-11-19T16:00:00Z
uv run flow-run-audit examples/sample_runs.jsonl --json
uv run pytest -q
```

Exit code: 1 if any high-severity finding exists, 0 if not, 2 for an unreadable file.

`examples/sample_runs.jsonl` is invented example data. The names, the email and the SSN in it are fake.

## What was tested

- 17 offline tests (`pytest`) covering each check, its threshold edges, the loader for JSON and JSONL, and the CLI exit codes.
- The sample file produces exactly one finding of each of the five kinds.
- The tests run in GitHub Actions on every push.

## What was not tested

- Real exports from Power Automate, Copilot Studio or any other product. I did not map their schemas.
- Large files. The code loads the whole file into memory.
- Time zones other than UTC and ISO timestamps without an offset (treated as UTC).
- The PII patterns are simple regular expressions. They will miss formats such as Medicare IDs, and they can match things that are not personal data. Treat them as a first filter, not a compliance control.
- It only reads logs. It does not stop, retry or fix any run.
