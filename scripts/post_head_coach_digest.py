"""Phase 4 Part 3 — Head-coach digest v2 poster.

Builds the v2 digest for `today` (CT) and posts a single Slack DM to the
head coach. NO public-channel posting; head coach DM only (Q4-5 says
nudges go to coach DM only — but the digest itself is the head-coach's
weekly summary, posted to head coach DM per prior phase locks).

DRY-RUN MODE
------------
Set env var DIGEST_V2_DRY_RUN=1 to print the rendered text to stdout
instead of posting. This lets us verify the pipeline without violating
the Slack pause.

REQUIRED ENV (live mode only)
-----------------------------
- SLACK_BOT_TOKEN          xoxb-... bot token
- HEAD_COACH_SLACK_ID      U-prefixed Slack user ID for the head coach

OPTIONAL ENV
------------
- DIGEST_V2_TODAY          ISO date (YYYY-MM-DD) to override "today";
                           defaults to current date in America/Chicago.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path so `src.*` imports work when this script
# is run as `python scripts/post_head_coach_digest.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.digest_v2 import build_digest_v2  # noqa: E402
from src.digest_v2_renderer import render_digest_v2  # noqa: E402


# ---------------------------------------------------------------------------
# Date resolution (America/Chicago without bringing in pytz/zoneinfo deps).
# ---------------------------------------------------------------------------
def _today_ct() -> date:
    """Return today's date in America/Chicago.

    Uses zoneinfo (stdlib >=3.9). Falls back to UTC date if zoneinfo
    unavailable (defensive — repo targets 3.11).
    """
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Chicago")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _resolve_today() -> date:
    override = os.environ.get("DIGEST_V2_TODAY", "").strip()
    if override:
        return date.fromisoformat(override)
    return _today_ct()


# ---------------------------------------------------------------------------
# Slack posting (live mode).
# ---------------------------------------------------------------------------
def _post_to_slack(text: str, user_id: str, token: str) -> dict:
    """Post a DM to a Slack user. Returns the parsed Slack API response.

    Uses urllib (stdlib) so we don't require the slack_sdk package. We
    still use chat.postMessage with `channel=<user_id>` which Slack
    auto-routes to the user's DM channel.
    """
    import urllib.request

    payload = json.dumps(
        {
            "channel": user_id,
            "text": text,
            "mrkdwn": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url="https://slack.com/api/chat.postMessage",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    today = _resolve_today()
    payload = build_digest_v2(today)
    text = render_digest_v2(payload)

    dry_run = os.environ.get("DIGEST_V2_DRY_RUN", "").strip() == "1"
    if dry_run:
        print(f"[DRY RUN] Head-coach digest for {today.isoformat()}:")
        print("-" * 60)
        print(text)
        print("-" * 60)
        return 0

    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    user_id = os.environ.get("HEAD_COACH_SLACK_ID", "").strip()
    if not token or not user_id:
        print(
            "ERROR: SLACK_BOT_TOKEN and HEAD_COACH_SLACK_ID must be set "
            "(or use DIGEST_V2_DRY_RUN=1).",
            file=sys.stderr,
        )
        return 2

    resp = _post_to_slack(text, user_id, token)
    if not resp.get("ok"):
        print(f"ERROR: Slack API returned not-ok: {resp}", file=sys.stderr)
        return 3

    ts = resp.get("ts", "")
    print(f"Posted head-coach digest for {today.isoformat()} (ts={ts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
