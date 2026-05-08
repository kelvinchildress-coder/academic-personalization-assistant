"""
scripts/agent_run.py
====================

Thin CLI wrapper that runs ONE agent tick and exits. The actual logic
lives in src.agent.runner.run_tick.

Phase 1 (active onboarding): the workflow runs this hourly during school
hours on weekdays. As long as gaps exist, the runner will draft + send
DMs and parse replies.

Phase 2 (steady state): the workflow runs this once daily. The runner
finds no gaps and only listens for unsolicited coach replies.

Env (read by src.agent.* modules):
  SLACK_BOT_TOKEN          required for live DMs
  COACH_SLACK_IDS_JSON     required (maps coach name -> Slack user ID)
  ANTHROPIC_API_KEY        optional; enables LLM drafting + parsing
  ANTHROPIC_MODEL          optional; defaults to claude-3-5-sonnet-latest
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.agent.runner import run_tick   # noqa: E402
from src.agent.slack_io import SlackIO  # noqa: E402


def _load_coach_slack_ids() -> dict[str, str]:
    raw = os.environ.get("COACH_SLACK_IDS_JSON", "").strip()
    if not raw:
        return {}
    try:
        return dict(json.loads(raw))
    except json.JSONDecodeError:
        print("WARN: COACH_SLACK_IDS_JSON is not valid JSON; ignoring.", file=sys.stderr)
        return {}


def main() -> int:
    coach_ids = _load_coach_slack_ids()
    if not coach_ids:
        print(
            "NOOP: COACH_SLACK_IDS_JSON is empty; the agent has no one to "
            "DM. Add coach Slack IDs as a repo secret to enable."
        )
        return 0

    slack = SlackIO()
    if not slack.is_live:
        print(
            "NOTE: SlackIO running in DRY-RUN mode (no SLACK_BOT_TOKEN or "
            "slack_sdk missing). DMs will be logged, not sent."
        )

    result = run_tick(
        repo_root=REPO_ROOT,
        coach_slack_ids=coach_ids,
        slack=slack,
    )
    print(
        f"OK: phase={result.phase}  dms_sent={result.dms_sent}  "
        f"replies_parsed={result.replies_parsed}  "
        f"patches_applied={result.patches_applied}  "
        f"parse_failures={result.parse_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
