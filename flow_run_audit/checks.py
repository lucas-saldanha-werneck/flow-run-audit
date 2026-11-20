"""Checks over a list of run records (plain dicts).

Run record fields (all optional except flow, run_id, status):
  flow, run_id, trigger_key, status (Succeeded|Failed|Running), attempt,
  started_at (ISO 8601), duration_ms, outputs, log
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "us_phone": re.compile(r"\b\(?\d{3}\)?[ -]\d{3}-\d{4}\b"),
    "dob": re.compile(r"\b(?:dob|date of birth)\s*[:=]\s*\d{4}-\d{2}-\d{2}\b", re.I),
}


@dataclass
class Finding:
    check: str
    severity: str  # high | medium | low
    flow: str
    run_ids: list
    message: str

    def to_dict(self):
        return asdict(self)


def _parse(ts):
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def duplicate_success(runs):
    """Same flow + trigger_key succeeded more than once: the flow is not idempotent."""
    groups = defaultdict(list)
    for r in runs:
        if r.get("trigger_key") and r["status"] == "Succeeded":
            groups[(r["flow"], r["trigger_key"])].append(r["run_id"])
    return [
        Finding("duplicate_success", "high", flow, ids,
                f"trigger '{key}' completed {len(ids)} times; side effects may have run twice")
        for (flow, key), ids in groups.items() if len(ids) > 1
    ]


def silent_failure(runs):
    """Run says Succeeded but produced nothing."""
    out = []
    for r in runs:
        if r["status"] == "Succeeded" and not r.get("outputs"):
            out.append(Finding("silent_failure", "high", r["flow"], [r["run_id"]],
                               "status Succeeded but outputs are empty"))
    return out


def retry_storm(runs, max_attempts=3):
    out = []
    for r in runs:
        if int(r.get("attempt", 1)) > max_attempts:
            out.append(Finding("retry_storm", "medium", r["flow"], [r["run_id"]],
                               f"attempt {r['attempt']} exceeds limit of {max_attempts}"))
    return out


def stuck_runs(runs, now, max_minutes=60):
    out = []
    for r in runs:
        if r["status"] != "Running":
            continue
        start = _parse(r.get("started_at"))
        if start and (now - start).total_seconds() > max_minutes * 60:
            mins = int((now - start).total_seconds() // 60)
            out.append(Finding("stuck_run", "medium", r["flow"], [r["run_id"]],
                               f"still Running after {mins} min (limit {max_minutes})"))
    return out


def pii_in_logs(runs):
    out = []
    for r in runs:
        text = str(r.get("log", ""))
        hits = sorted(n for n, p in PII_PATTERNS.items() if p.search(text))
        if hits:
            out.append(Finding("pii_in_logs", "high", r["flow"], [r["run_id"]],
                               "log text matches PII pattern(s): " + ", ".join(hits)))
    return out


def run_all(runs, now=None, max_attempts=3, max_minutes=60):
    now = now or datetime.now(timezone.utc)
    findings = (duplicate_success(runs) + silent_failure(runs)
                + retry_storm(runs, max_attempts) + stuck_runs(runs, now, max_minutes)
                + pii_in_logs(runs))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.check, f.flow))
