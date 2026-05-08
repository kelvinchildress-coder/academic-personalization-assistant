# Academic Personalization Assistant

Slack-native daily learning report + AI coach assistant for Texas Sports Academy.

The assistant pulls daily TimeBack data, computes a personalized XP target for every (student, subject) using a 4-tier priority cascade that respects coach overrides, posts a morning report to `#sports`, and chats with coaches via Slack DM to fill in goal details. It runs entirely on GitHub Actions — no server.

---

## What you'll see in Slack each day

**Around 7:00 AM CT, in `#sports`:**
- A parent message titled "Morning Report — Mon May 8".
- One threaded reply per coach, listing each of their students with per-subject targets, today's XP/accuracy, and the cascade tier that produced the target (e.g. `[T1 grade-mastered]`, `[T3 personalized]`, `[T0a coach XP]`).
- Status emojis on each row: ✅ on track, ⚠️ behind, 🚀 ahead (over 125% of target), 🔴 stale data.

**Throughout the school day (every ~2 hours):**
- New threaded replies under the morning parent flagging fresh events — for example, a student dropping below 60% accuracy or hitting 125% of target. The parent message is never edited.

**Around 5:30 PM CT:**
- A final EOD summary as a threaded reply showing how the day finished.

**Coach DMs:**
- The agent will DM you when it needs a piece of information — usually a student's current grade, their year-start grade, or a target test-out grade. Each DM includes the cascade default so you can reply with `use default` to accept it. You can also override with phrasing like `Math 6`, `Math by 2027-01-29 to 7`, or `Math 30/day`.

**Mondays at 7:00 AM CT (head coach only):**
- A weekly digest summarizing trends, students sliding off track for 5+ days, and any coverage gaps in the goal config.

---

## How the daily target is decided (the cascade)

For every (student, subject) on every school day, the system walks this priority list top-down. The first tier that produces a value wins, and the report cites which tier was used.

1. **Tier 0a — Coach absolute XP/day override.** If a coach has set an exact daily XP for a student in a subject, that wins absolutely.
2. **Tier 0b — Coach test-by override.** If a coach has set "test out at grade X by date Y," the daily XP is back-solved from that.
3. **Tier 1 — Grade-mastered.** Auto-calculated from XP remaining to the default target grade divided by school days remaining to the next MAP testing window. Requires the TimeBack API to be wired in.
4. **Tier 2 — Reserved.** Not used in v1.
5. **Tier 3 — Personalized base.** Adjusts the locked TSA base by 2.5 XP/day for every grade the student is below or above their age grade in that subject. Floor: 10 XP/day. Applies to Math/Reading/Language/Writing/Science only; Vocabulary and FastMath always pass through to Tier 4.
6. **Tier 4 — Locked TSA base.** Math/Reading/Language: 25; Writing/Science: 12.5; Vocabulary/FastMath: 10.

The default target test-out grade is the larger of: the next anchor grade at or above the student's age grade (anchors are 1, 3, 5, 8), and their year-start grade plus 2. The year-start grade is a snapshot taken at the start of the school year and does NOT move during the year.

---

## How coaches talk to the assistant

The agent will DM you in Slack only when it needs information. Reply naturally — the parser is tolerant.

**Examples it understands:**
- `4` (when asked for an age grade)
- `K` (kindergarten)
- `Math 6` (current grade, year-start grade, or target — depending on what was asked)
- `Lang 5` (aliases: lang/language, read/reading, sci/science, vocab/vocabulary, fastmath/fast math)
- `use default` (accept the cascade default)
- `Math 30/day` (set an exact daily XP for that student in that subject)
- `Math by 2027-01-29 to 7` (test out at grade 7 by January 29, 2027)

If your reply is ambiguous, the agent will re-ask with more context. The same gap will not be re-asked within 7 days, so don't worry about being temporarily unable to answer.

---

## How the daily TimeBack data gets in

There are two ingestion paths. Today only the bookmarklet path is live.

**Bookmarklet path (live today):**
- Each morning, an authorized user clicks an "Export TimeBack Day" bookmarklet in their browser while on the TimeBack dashboard. The bookmarklet writes a JSON snapshot to `data/latest.json` in this repo via the GitHub web editor.
- See `docs/export-day.js` for the bookmarklet source and the README under that file for installation.

**API path (dormant, ready):**
- When TimeBack provides an API token, set it as `TIMEBACK_API_TOKEN` and flip `USE_REAL_API = True` in `src/timeback_api.py` after implementing the two `_real_*` methods. The hourly grade-XP collector workflow will then start populating `config/grade_xp.json` automatically, and Tier 1 of the cascade comes online.

If the latest export is older than 24 hours on a school day, the assistant **skips** the morning post and DMs the head coach. It will never post stale data with a caveat.

---

## Repo layout

```
config/
  coaches.json          7 coaches + head coach + roster
  students.json         per-student profile (age grade, current/year-start
                        grades per subject, coach overrides, ratifications)
  grade_xp.json         total XP required at each (grade, subject) — populated
                        by the API collector when wired
  map_calendar.json     MAP testing windows + holidays for SY25-26 and SY26-27

data/
  latest.json           today's TimeBack export (from bookmarklet or API)
  state.json            today's Slack parent thread_ts (for live updates)
  agent_state.json      agent's outbound/inbound DM state and ask-throttle log
  summer_state.json     end-of-summer roster refresh phase tracker
  proposed_roster.json  the agent's proposed roster update (PR-only)

src/
  calendar_map.py       MAP-aware school-day math
  calendar_tsa.py       legacy school-day math (preserved)
  models.py             upstream-derived dataclasses (frozen)
  student_profile.py    per-student profile dataclasses
  test_out_goals.py     Q2 default target grade + Tier 0b resolution
  student_progress.py   ledger that joins data/latest.json + configs
  targets.py            4-tier cascade
  report_builder.py     Slack-ready text (legacy + tiered layer)
  slack_poster.py       basic Slack post helpers (legacy)
  slack_threading.py    daily parent thread_ts persistence
  timeback_api.py       single seam for the TimeBack API (currently stubbed)
  agent/
    __init__.py
    gap_finder.py       finds prioritized goal gaps
    question_drafter.py drafts coach DMs (Anthropic + template fallback)
    reply_parser.py     parses coach replies (regex + Anthropic fallback)
    config_writer.py    schema-validated patches to students.json
    slack_io.py         Slack DM I/O (live or dry-run)
    runner.py           one-tick agent orchestrator

scripts/
  post_morning.py
  post_live_update.py
  post_eod.py
  agent_run.py
  grade_xp_collector.py
  summer_roster_refresh.py

.github/workflows/
  morning-report.yml      daily 07:00 CT
  live-update.yml         every ~2h, school hours
  eod-summary.yml         daily ~17:30 CT
  agent-poll.yml          hourly Phase 1 / daily Phase 2
  grade-xp-collector.yml  hourly during school hours (no-ops without token)
  summer-roster.yml       daily; only acts during late July / early August

tests/
  test_calendar_map.py
  test_calendar_tsa.py
  test_targets.py
  test_targets_cascade.py
  test_report_builder.py
  test_report_builder_tiered.py
  test_test_out_goals.py
  test_student_progress.py
  test_slack_threading.py
  test_gap_finder.py
  test_reply_parser.py
  test_config_writer.py
```

---

## Required GitHub Actions secrets

| Secret | Purpose |
|---|---|
| `SLACK_BOT_TOKEN` | All Slack posts and DMs |
| `SLACK_CHANNEL_ID` | The `#sports` channel ID (starts with `C`) |
| `HEAD_COACH_SLACK_ID` | The head coach's user ID (starts with `U`) — for stale alerts and the weekly digest |
| `COACH_SLACK_IDS_JSON` | JSON map of coach name → Slack user ID |
| `ANTHROPIC_API_KEY` | Optional. Enables LLM drafting and reply parsing for the agent. |
| `TIMEBACK_API_TOKEN` | Optional. Enables the hourly grade-XP collector and Tier 1 cascade. |
| `TIMEBACK_API_BASE_URL` | Optional. Defaults to `https://alpha.timeback.com/api`. |

The system runs degraded but safely without `ANTHROPIC_API_KEY` (templates instead of LLM) and without `TIMEBACK_API_TOKEN` (Tier 1 skipped, falls through to Tier 3/4).

Never paste secret values in chat. Add them in the repo's Settings → Secrets and variables → Actions.

---

## Running tests locally

```
pip install -r requirements.txt
pytest
```

All tests are designed to run offline — no Slack, TimeBack, or Anthropic calls are made.

---

## Locked rules (don't change without coordinated update)

- The JSON envelope in `data/latest.json` is the single seam between the data layer and everything else. Keep its shape stable.
- Live updates are NEW threaded replies, never edits to the parent message.
- Stale data ⇒ SKIP the post and DM the head coach. Never post-with-caveat.
- "Lisa Willis" is normalized to "Lisa C Willis" everywhere.
- Coach overrides (Tier 0a / 0b) are absolute. The metric used for every target is cited in every report row.
- The 2-grade growth target is anchored at year-start, not rolling.

---

## Project status

Foundation, cascade, reporting, agent, and orchestration are all built. Remaining work to take the system fully live is limited to:
1. Setting `ANTHROPIC_API_KEY` (for LLM-quality coach DMs).
2. Setting `TIMEBACK_API_TOKEN` and implementing the two `_real_*` methods in `src/timeback_api.py` once TimeBack publishes API docs.
3. Manually triggering each workflow once via the Actions tab to confirm end-to-end behavior before relying on the cron schedule.

For full design context and decisions, see `HANDOFF_v3.md` at the repo root.
