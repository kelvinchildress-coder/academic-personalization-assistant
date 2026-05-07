"""Slack thin client. We avoid hard dependencies on slack_sdk's surface
beyond the methods we actually call, so this file is easy to read.

All credentials come from the env var SLACK_BOT_TOKEN. This module never
prints, logs, or persists the token.
"""
from __future__ import annotations

import os
from typing import Optional

import requests


SLACK_API = "https://slack.com/api"


class SlackError(RuntimeError):
    pass


class SlackPoster:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.environ.get("SLACK_BOT_TOKEN", "")
        if not self.token:
            raise SlackError("SLACK_BOT_TOKEN not set")
        self._user_index: dict[str, str] | None = None
        self._channel_id_cache: dict[str, str] = {}

    # ---- low-level ----

    def _post(self, method: str, payload: dict) -> dict:
        r = requests.post(
            f"{SLACK_API}/{method}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise SlackError(f"{method} failed: {data.get('error')}")
        return data

    def _get(self, method: str, params: dict | None = None) -> dict:
        r = requests.get(
            f"{SLACK_API}/{method}",
            headers={"Authorization": f"Bearer {self.token}"},
            params=params or {},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise SlackError(f"{method} failed: {data.get('error')}")
        return data

    # ---- channel resolution ----

    def channel_id(self, name_or_id: str) -> str:
        """Accepts a channel ID (starts with C/G) or a #name / name string."""
        n = name_or_id.lstrip("#")
        if n.startswith("C") or n.startswith("G"):
            return n
        if n in self._channel_id_cache:
            return self._channel_id_cache[n]
        cursor = ""
        while True:
            data = self._get("conversations.list", {
                "types": "public_channel,private_channel",
                "limit": 1000,
                "cursor": cursor,
            })
            for c in data.get("channels", []):
                if c.get("name") == n:
                    self._channel_id_cache[n] = c["id"]
                    return c["id"]
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
        raise SlackError(f"Channel not found: #{n}")

    # ---- user resolution ----

    def _build_user_index(self) -> dict[str, str]:
        """display_name → user_id, falling back to real_name when display
        is empty. Built once per process."""
        idx: dict[str, str] = {}
        cursor = ""
        while True:
            data = self._get("users.list", {
                "limit": 200,
                "cursor": cursor,
            })
            for m in data.get("members", []):
                if m.get("deleted") or m.get("is_bot"):
                    continue
                profile = m.get("profile", {}) or {}
                dn = (profile.get("display_name") or "").strip()
                rn = (profile.get("real_name") or m.get("real_name") or "").strip()
                key = dn or rn
                if key:
                    idx.setdefault(key, m["id"])
                # Also key by real_name so display-name mismatches still resolve.
                if rn:
                    idx.setdefault(rn, m["id"])
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
        return idx

    def resolve_user(self, name: str) -> Optional[str]:
        if self._user_index is None:
            self._user_index = self._build_user_index()
        return self._user_index.get(name)

    def resolve_users(self, names: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for n in names:
            uid = self.resolve_user(n)
            if uid:
                out[n] = uid
        return out

    # ---- posting ----

    def post(self, channel: str, text: str, thread_ts: str | None = None) -> dict:
        payload = {"channel": self.channel_id(channel), "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return self._post("chat.postMessage", payload)

    def dm(self, user_id: str, text: str) -> dict:
        # opens an IM channel and posts to it
        opened = self._post("conversations.open", {"users": user_id})
        ch = opened["channel"]["id"]
        return self._post("chat.postMessage", {"channel": ch, "text": text})
