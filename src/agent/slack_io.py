"""
slack_io.py
===========

Slack DM I/O for the agent. All Slack calls are isolated here so the
runner stays testable. Two modes:

  * Live mode: SLACK_BOT_TOKEN is set. Uses slack_sdk.WebClient.
  * Dry-run:   No token; methods log what *would* happen and return
               deterministic fakes so tests/dev work offline.

Conversation context for parsing:
  fetch_recent_dm_thread(coach_user_id, since_iso_dt) returns a list of
  {ts, user, text, is_bot} dicts so reply_parser can see what the coach
  said in response to our last question.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DmMessage:
    ts: str
    user: str
    text: str
    is_bot: bool


class SlackIO:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        self._client = None
        if self.token:
            try:
                from slack_sdk import WebClient  # type: ignore
                self._client = WebClient(token=self.token)
            except ImportError:
                # We'll log and fall back to dry-run for any call that needs it.
                self._client = None

    # ------------------------------------------------------------------ #

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def open_dm(self, user_id: str) -> Optional[str]:
        """Returns the IM channel id for `user_id`, or None in dry-run."""
        if not self.is_live or not user_id:
            print(f"[slack_io DRY] open_dm({user_id})")
            return None
        resp = self._client.conversations_open(users=user_id)
        return (resp.get("channel") or {}).get("id")

    def send_dm(self, user_id: str, text: str) -> Optional[str]:
        """Send a DM. Returns the message ts, or None in dry-run."""
        if not self.is_live or not user_id:
            print(f"[slack_io DRY] send_dm({user_id}):\n---\n{text}\n---")
            return None
        ch = self.open_dm(user_id)
        if not ch:
            return None
        resp = self._client.chat_postMessage(channel=ch, text=text, unfurl_links=False)
        return resp.get("ts")

    def fetch_recent_dm_thread(
        self,
        user_id: str,
        *,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[DmMessage]:
        """Returns the most recent messages in the DM with `user_id`,
        oldest first. Filters to messages newer than `since` if provided."""
        if not self.is_live or not user_id:
            print(f"[slack_io DRY] fetch_recent_dm_thread({user_id}, since={since})")
            return []
        ch = self.open_dm(user_id)
        if not ch:
            return []
        kwargs: Dict[str, Any] = {"channel": ch, "limit": int(limit)}
        if since:
            kwargs["oldest"] = str(since.replace(tzinfo=since.tzinfo or timezone.utc).timestamp())
        resp = self._client.conversations_history(**kwargs)
        msgs = resp.get("messages") or []
        out: List[DmMessage] = []
        for m in msgs:
            out.append(DmMessage(
                ts=str(m.get("ts", "")),
                user=str(m.get("user", "")),
                text=str(m.get("text", "")),
                is_bot=bool(m.get("bot_id")),
            ))
        out.reverse()  # API returns newest-first; flip to oldest-first.
        return out
