"""
src.agent
=========

Slack-driven coach onboarding & maintenance agent for the Academic
Personalization Assistant.

High-level flow (driven by scripts/agent_run.py + agent-poll.yml):

  1. gap_finder.find_gaps(...)                  -> list of GoalGap
  2. question_drafter.draft_question(gap)       -> Slack DM text (Anthropic)
  3. slack_io.send_dm(coach, text)              -> records outbound message
  4. slack_io.fetch_recent_replies(coach)       -> raw reply text
  5. reply_parser.parse_reply(text, context)    -> StructuredPatch
  6. config_writer.apply_patch(patch)           -> commits to config/students.json

Phase 1 (active onboarding) runs hourly during school hours weekdays
until every student has a complete goal set. Phase 2 (steady state)
runs once daily and only listens for unsolicited coach updates.
"""

from .gap_finder import GoalGap, find_gaps         # noqa: F401
from .config_writer import (                        # noqa: F401
    StructuredPatch,
    apply_patch,
    validate_patch,
)
