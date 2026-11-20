from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .checks import run_all

REQUIRED = ("flow", "run_id", "status")


def load_runs(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    runs = json.loads(text) if text.startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
    for i, r in enumerate(runs):
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            raise ValueError(f"record {i}: missing {', '.join(missing)}")
    return runs


def render_markdown(runs, findings):
    lines = ["# Run audit", "", f"Runs read: {len(runs)}. Findings: {len(findings)}.", ""]
    if not findings:
        lines.append("No findings.")
    for f in findings:
        lines.append(f"- **{f.severity.upper()}** `{f.check}` in `{f.flow}` "
                     f"(runs: {', '.join(f.run_ids)}): {f.message}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(prog="flow-run-audit", description=__doc__)
    p.add_argument("runs", help="JSON array or JSONL file of run records")
    p.add_argument("--now", help="ISO time to use as 'now' (default: current UTC)")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--max-minutes", type=int, default=60)
    p.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    a = p.parse_args(argv)
    try:
        runs = load_runs(a.runs)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    now = datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else datetime.now(timezone.utc)
    findings = run_all(runs, now, a.max_attempts, a.max_minutes)
    if a.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        print(render_markdown(runs, findings), end="")
    return 1 if any(f.severity == "high" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
