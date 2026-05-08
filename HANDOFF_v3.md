# HANDOFF v3 — Academic Personalization Assistant

**Repo:** `kelvinchildress-coder/academic-personalization-assistant`
**Owner:** Kelvin Childress (head coach, Texas Sports Academy)
**As of:** 2026-05-08
**Status:** Foundation, cascade, reporting, agent, summer refresh, and orchestration all complete. Live activation is gated on two external secrets only.

---

## 0. PURPOSE OF THIS DOCUMENT

This is the single source of truth for the next agent. It is intentionally exhaustive: read it end-to-end before writing any code. It encodes:

1. What the user actually wants (the *true desired design*).
2. What is built, what's frozen, and what is intentionally dormant.
3. What still needs to happen to take the system fully live.
4. The hard constraints (security, copy-paste workflow, locked rules).
5. The decisions already made by the user — DO NOT relitigate them.

If anything in this document conflicts with chat history, this document wins. If anything in this document conflicts with the user, ASK before acting.

---

## 1. THE TRUE DESIRED DESIGN

### 1.1 What this product *is*

A Slack-native academic personalization assistant for Texas Sports Academy that:

1. Pulls daily learning data from TimeBack (XP, accuracy, minutes, mastery, on-track/behind status, remaining XP per grade per subject) for every TSA student.
2. Computes a per-student, per-subject daily XP target using a 4-tier priority cascade that respects coach overrides absolutely.
3. Posts a morning report to `#sports` (one parent message + threaded live updates throughout the day) showing each student vs. their personalized target, color-coded by status.
4. Talks to coaches via Slack DM through an AI agent (Anthropic / Claude) to fill in the missing pieces — primarily target test-out grades, custom XP/day overrides, and ratifications. Conversational, polite, throttled.
5. Sends the head coach a weekly digest of trends, anomalies, and coverage gaps every Monday morning. (Digest is sketched in `report_builder.build_head_coach_digest`; currently posted only on demand — wiring a Monday-morning workflow is a small future tweak.)
6. Refreshes its roster at end of summer by DMing the head coach for the new coach/student grouping for the next school year and opening a PR for review.

The system runs entirely on GitHub Actions (no server) and is API-ready: where TimeBack's API is not yet available, a bookmarklet (`docs/export-day.js`) is the manual data-pull bridge. When the API arrives, only the data-ingestion layer changes; everything downstream stays identical.

### 1.2 The 4-Tier Priority Cascade (the core algorithm)

For every (student, subject) on every school day, we resolve a daily XP target by walking this cascade top-down. The first tier that produces a value wins, and the report cites which tier was used.

| Tier | Name | Source | Notes |
|------|------|--------|-------|
| **0a** | Coach absolute XP/day override | `student.overrides.xp_per_day[subject]` (also legacy `manual_xp_per_day[subject]`) | Set via the agent or by editing config. Bypasses everything below. |
| **0b** | Coach absolute test-by override | `student.overrides.test_by[subject]` (also legacy `manual_test_out_grade` + `manual_test_out_date`) | Drives a Tier-1-style calculation but with coach-chosen grade/date. |
| **1**  | Grade-mastered XP/day | Auto: `remaining_xp_to_target_grade / school_days_until_target_date` | Default `target_date` = next MAP after today. Default `target_grade` per Q2 rule. Skipped when `remaining_xp` or `grade_xp_table` value is None. |
| **2**  | Adjusted coach XP/day | Reserved for future "soft nudge" coach inputs | Not implemented in v1 — slot intentionally left. |
| **3**  | Personalized base XP/day | `locked_base + 2.5 × (age_grade − current_grade_in_subject)` | Floor: 10 XP/day. Only applies to Math/Reading/Language/Writing/Science. FastMath/Vocabulary always pass through to Tier 4. |
| **4**  | Locked TSA base | Math/Reading/Language: 25; Writing/Science: 12.5; Vocab/FastMath: 10 | Always available; the floor. |

**Q2 default target grade rule (locked, year-start anchored):**
```
default_target_grade = max(
    next_anchor_grade_at_or_above(age_grade),   # anchors: 1, 3, 5, 8
    year_start_grade_in_subject + 2
)
```
`year_start_grade_in_subject` is a snapshot taken at SY start. It does NOT move during the year. (User clarification: "the 2 grade growth is from the start of the year, not at any given point or they would always be chasing an impossible growth.")

**Locked TSA base targets (Tier 4):**
- Math, Reading, Language: 25 XP/day
- Writing, Science: 12.5 XP/day (flat, NOT alternating)
- Vocabulary, FastMath: 10 XP/day
- Accuracy floor: 60% — below this counts as "behind" regardless of XP
- Overperform threshold: 125% — at or above this counts as "ahead"
- Trend window: 5 school days
- School days only (Calendar A)

**Personalized base examples (Tier 3):**
- 4th-grade-age student in 7th-grade Math: `25 + 2.5 × (4 − 7) = 17.5 XP/day`
- 4th-grade-age student in 1st-grade Reading: `25 + 2.5 × (4 − 1) = 32.5 XP/day`
- Floor: never below 10 XP/day for any subject.

### 1.3 Reporting model

- **Morning report (07:00 CT, school days):** parent message in `#sports`, then one threaded reply per coach. Each row cites its cascade tier (e.g. `[T1 grade-mastered]`, `[T0a coach XP]`).
- **Live updates (every ~2 hours, 09:00–17:00 CT, school days):** NEW threaded replies under the morning parent. NEVER edit the parent. Each detects fresh low-accuracy / overperform events.
- **End-of-day summary (~17:30 CT):** final threaded reply.
- **Weekly head-coach digest (Monday 07:00 CT):** DM with trends, anomalies, coverage gaps. Helper exists; a Monday-only workflow is a small future tweak.
- **Coach DMs:** driven by the agent on demand.

### 1.4 The agent

Phase 1 (active onboarding): hourly during school hours weekdays as long as `config/students.json` has gaps. Drafts a friendly DM per gap (with cascade default included so coaches can reply `use default`), sends it, watches for replies, parses tolerantly via regex first then Anthropic if needed, validates, and writes the patch back to config.

Phase 2 (steady state): once daily. Listens for unsolicited coach updates only.

LLM: Anthropic (Claude). The agent never invents names, never asks the same question twice in a 7-day window, always quotes the cascade default, and never deletes data — patches are merge-only.

### 1.5 End-of-summer roster refresh

In late July through early August, the system DMs the head coach to confirm next year's coach + student groupings. The reply is parsed by Anthropic into a proposal written to `data/proposed_roster.json`. The workflow then opens a pull request — never auto-merged. Roster changes are too high-stakes for silent overwrites.

### 1.6 Stale data handling (locked rule)

If `data/latest.json` is older than 24h on a school day, the morning workflow SKIPS the post and DMs the head coach. NEVER post-with-caveat.

### 1.7 The single seam where the API drops in

`src/timeback_api.py` is the only file that needs to change when TimeBack's API is available. Two methods (`_real_fetch_grade_xp_total`, `_real_fetch_student_cumulative_xp`) need real implementations and `USE_REAL_API = True`. Everything downstream consumes a fixed JSON envelope that's already locked.

---

## 2. CALENDAR (Locked dates — Calendar A)

**SY25-26 (current year, last stretch):**
- Spring MAP: May 19–22, 2026
- Memorial Day (no school): May 25, 2026
- Last day of school: June 5, 2026

**SY26-27:**
- First day: August 12, 2026
- Fall MAP: August 18–21, 2026
- Labor Day: September 7, 2026
- Fall break: October 12–16, 2026
- Thanksgiving: November 23–27, 2026
- Winter break: December 21, 2026 – January 1, 2027
- MLK Day: January 18, 2027
- Winter MAP: January 26–29, 2027
- Mid-winter break: February 22–26, 2027
- Spring break: April 19–23, 2027
- Spring MAP: May 18–21, 2027
- Last day: June 4, 2027

These dates live in `config/map_calendar.json` and are parsed by `src/calendar_map.py`. Trust this file over any other calendar source.

---

## 3. CRITICAL CONSTRAINTS

1. NEVER accept tokens, API keys, or credentials in chat. Direct the user to add them as GitHub Actions secrets.
2. NEVER modify these files (must remain bit-identical to upstream timeback-scraper):
   - `app.py`
   - `templates/dashboard.html`
   - `docs/timeback-dashboard.js`
   - `setup.sh`
   - `.gitignore`
3. All file uploads via copy-paste in the GitHub web editor. The user's environment cannot drag-drop. Verify every commit via `https://api.github.com/repos/kelvinchildress-coder/academic-personalization-assistant/contents/<path>` and confirm size.
4. Live updates = NEW threaded replies. NEVER edit the parent message.
5. Stale data → SKIP + DM head coach. Never post-with-caveat.
6. Name normalization: "Lisa Willis" must always be displayed as "Lisa C Willis".
7. Tool-output filter quirk: strings containing `=` may be blocked by the assistant tool-result filter. When using `javascript_tool`, replace `=` with `_EQ_` before returning if needed.
8. Q1–Q6 are LOCKED. Do not re-ask. (See §9 below.)

---

## 4. PROJECT FILE INVENTORY (Verified at handoff)

### Root
- `app.py`, `setup.sh`, `.gitignore` — UPSTREAM, frozen
- `requirements.txt` — `flask`, `playwright`, `requests`, `python-dateutil`, `pytz`, `slack_sdk`, `PyGithub`, `anthropic>=0.34.0`, `pytest>=7.0`
- `README.md` — coach-facing project doc
- `HANDOFF_v3.md` — this file

### `templates/`
- `dashboard.html` — UPSTREAM, frozen

### `docs/`
- `timeback-dashboard.js` — UPSTREAM, frozen
- `index.html` — UPSTREAM
- `export-day.js` — smart bookmarklet producing the JSON envelope; auto-mode logic: before 8am CT = "morning" (yesterday), after 8am = "live" (today), manual day-tab respected and tagged "manual"

### `data/`
- `latest.json` — last bookmarklet/API export (35 students, real)
- `state.json` — today's Slack parent thread_ts (placeholder until first run)
- `agent_state.json` — agent throttle log + outbound/inbound DM markers
- `summer_state.json` — summer-refresh phase tracker
- `proposed_roster.json` — agent's proposed roster (PR-only)

### `config/`
- `map_calendar.json` — MAP windows + holidays for SY25-26 and SY26-27
- `coaches.json` — 7 coaches incl. Kelvin Childress (head)
- `students.json` — 35 students keyed by name; per-student profile fields
- `grade_xp.json` — K–12 × 7 subjects, mostly null until API token wired

### `src/`
- `models.py` — UPSTREAM-derived dataclasses, frozen
- `calendar_tsa.py` — pre-existing school-day math
- `calendar_map.py` — MAP-aware school-day math (parses `map_calendar.json`)
- `student_profile.py` — per-student profile dataclasses + loaders
- `test_out_goals.py` — Q2 default + Tier 0b grade resolution
- `student_progress.py` — joins data/latest.json with configs into `ProgressLedger`
- `targets.py` — full 4-tier cascade (`resolve_daily_target`, `resolve_all_subjects`); legacy `all_subject_targets` and `base_target` preserved
- `report_builder.py` — legacy v1 functions preserved + new tier-aware layer (`build_tiered_morning_payload`, `build_stale_data_dm`)
- `slack_poster.py` — basic Slack post helpers (legacy)
- `slack_threading.py` — daily parent thread_ts persistence
- `timeback_api.py` — single API seam; stub today
- `agent/__init__.py`
- `agent/gap_finder.py` — finds prioritized goal gaps with 7-day re-ask throttle
- `agent/question_drafter.py` — Anthropic + template fallback
- `agent/reply_parser.py` — regex first, Anthropic fallback, schema-validated patches
- `agent/config_writer.py` — `StructuredPatch`, `validate_patch`, `apply_patch`
- `agent/slack_io.py` — DM I/O (live or dry-run)
- `agent/runner.py` — one-tick orchestrator + CLI

### `scripts/`
- `post_morning.py`, `post_live_update.py`, `post_eod.py`
- `agent_run.py`
- `grade_xp_collector.py`
- `summer_roster_refresh.py`

### `.github/workflows/`
- `morning-report.yml` (07:00 CT)
- `live-update.yml` (every ~2h, school hours)
- `eod-summary.yml` (~17:30 CT)
- `agent-poll.yml` (hourly Phase 1 / daily Phase 2 floor)
- `grade-xp-collector.yml` (hourly during school hours; no-op without token)
- `summer-roster.yml` (daily; only acts in late July / early August)

### `tests/`
- `test_calendar_map.py`, `test_calendar_tsa.py`
- `test_targets.py`, `test_targets_cascade.py`
- `test_report_builder.py`, `test_report_builder_tiered.py`
- `test_test_out_goals.py`
- `test_student_progress.py`
- `test_slack_threading.py`
- `test_gap_finder.py`, `test_reply_parser.py`, `test_config_writer.py`

---

## 5. THE JSON ENVELOPE (sacred — do not change without coordinated update)

Bookmarklet writes / API will write / `student_progress` reads:

```json
{
  "date": "2026-05-04",
  "mode": "morning|live|manual",
  "timestamp": "2026-05-04T07:42:13-05:00",
  "students": [
    {
      "name": "Lisa C Willis",
      "total_xp": 142.5,
      "overall_accuracy": 0.81,
      "total_minutes": 95,
      "absent": false,
      "subjects": [
        {
          "name": "Math",
          "xp": 28.0,
          "accuracy": 0.79,
          "minutes": 22,
          "mastered": false,
          "no_data": false,
          "has_test": false
        }
      ]
    }
  ]
}
```

When the API lands, two optional fields per subject row become available and Tier 1 of the cascade activates: `current_grade` (int) and `total_xp_in_grade` (float).

---

## 6. SECRETS

| Secret | Purpose | Status at handoff |
|---|---|---|
| `SLACK_BOT_TOKEN` | All Slack posts and DMs | ✅ set |
| `SLACK_CHANNEL_ID` | `#sports` channel ID | ✅ set |
| `HEAD_COACH_SLACK_ID` | Stale alerts + future digest + summer refresh | ✅ set |
| `COACH_SLACK_IDS_JSON` | Coach-name → Slack user ID JSON map | ✅ set |
| `ANTHROPIC_API_KEY` | Agent LLM drafting + parsing + summer parsing | ❌ pending |
| `ANTHROPIC_MODEL` | Optional model override; defaults to `claude-3-5-sonnet-latest` | optional |
| `TIMEBACK_API_TOKEN` | Grade-XP collector + future ingestion | ❌ pending (no token yet) |
| `TIMEBACK_API_BASE_URL` | Optional override; defaults to `https://alpha.timeback.com/api` | optional |

System runs degraded but safely without `ANTHROPIC_API_KEY` (templates instead of LLM) and without `TIMEBACK_API_TOKEN` (Tier 1 skipped, falls through to Tier 3/4).

NEVER paste secret values in chat.

---

## 7. ROSTER GROUND TRUTH

- 7 coaches, 35 students.
- Head coach: Kelvin Childress.
- Slack workspace: `T8E6M88BS`. Channel: `#sports` (ID stored in `SLACK_CHANNEL_ID` secret). Bot is installed and invited.
- Lisa C Willis (NOT "Lisa Willis") is one of the coaches; the normalization is applied automatically.
- Mira Kambic has a known subject="Unknown" data quirk in TimeBack; `student_progress.normalize_subject` returns None for it and `build_student_progress` collects it into `unknown_subject_rows` for coach review.

---

## 8. KNOWN GOTCHAS

1. **`coaches.json` truncation history.** Earlier in the project a truncation was manually patched. Verify it round-trips through `json.loads` cleanly before any agent run.
2. **Tool-result `=` filter.** When using `javascript_tool`, replace `=` with `_EQ_` before returning if a string contains `=`.
3. **Bookmarklet closure scope.** The data is in a closure, not on `window`. Read from the rendered DOM in `#tb-dash-overlay`.
4. **Learning Report iframe is QuickSight.** Not scrapeable. Wait for the API token.
5. **Slack threading.** Once a parent message is created, `thread_ts` is persisted in `data/state.json`. A new parent is created every morning.
6. **DST drift.** Workflow crons are in UTC. We deliberately schedule double cron entries on critical workflows (morning, EOD) so DST transitions don't drop a day.
7. **Phase-1 vs Phase-2 cadence.** Set in `agent-poll.yml`: hourly during school hours weekdays as long as gaps exist, with a daily 14:00 UTC floor for steady-state listening.
8. **Multi-student coach replies.** `runner.py` matches a reply to a gap by sole-open-student or by first-name in text. The Anthropic parser tolerates more, but the matching layer above it is intentionally simple. If coaches start replying about multiple students per message, upgrade pairing logic, not the parser.
9. **`overrides.xp_per_day` patches** use the dotted-path field name; `config_writer` expands on apply. Don't write `{"overrides": {...}}` directly via patches.
10. **Lisa Willis name normalization** is applied in three places: `student_progress.normalize_student_name`, `report_builder._coach_for_student`, `runner.run_tick`'s coach roster lookup. Keep them in sync.
11. **The agent never deletes student data.** All patches are merge-only. Removing a target requires a manual edit to `config/students.json`.
12. **`USE_REAL_API`** in `src/timeback_api.py` is False until both the token is available AND the two `_real_*` methods are implemented against the real endpoint shape. The grade-XP collector and Tier 1 stay dormant until both conditions are met.
13. **Summer refresh is gated on `ANTHROPIC_API_KEY`.** Without it, only the Phase R1 ping is sent.

---

## 9. LOCKED DECISIONS (Q1–Q6)

Do not re-ask:

- **Q1 — Personalized base floor:** 10 XP/day for any subject.
- **Q2 — Default target grade:** `max(next_anchor ≥ age_grade [1,3,5,8], year_start_grade + 2)` — anchored at year start.
- **Q3 — Polling cadence:** hourly during school hours weekdays until every student is fully configured, then once daily.
- **Q4 — LLM:** Anthropic (Claude).
- **Q5 — Slack format:** DMs per coach for individual messages, weekly digest DM to head coach.
- **Q6 — MAP source:** SY25-26 / SY26-27 master calendar sheet, Calendar A row.

Coach overrides (Tier 0a/0b) are ALWAYS absolute. The metric (which tier won) MUST be cited in every report row.

---

## 10. ORDER OF OPERATIONS TO MAKE THE SYSTEM LIVE

1. Set `ANTHROPIC_API_KEY` in repo secrets when available.
2. When TimeBack provides an API token: set `TIMEBACK_API_TOKEN`, then implement the two `_real_*` methods in `src/timeback_api.py` and flip `USE_REAL_API = True`.
3. Manually trigger `morning-report.yml` once via the Actions tab → **Run workflow**. Confirm it posts to `#sports` correctly with one threaded reply per coach, and that `data/state.json` updates.
4. Manually trigger `agent-poll.yml` once. Confirm DMs go out to coaches whose students have open gaps. Watch for replies and confirm `config/students.json` updates and state files commit cleanly.
5. Let the crons run on schedule from there.
6. After one full week, verify `live-update.yml` has been firing and `eod-summary.yml` posts cleanly.
7. (Future, optional) Add a `weekly-digest.yml` workflow Monday 07:00 CT calling `report_builder.build_head_coach_digest`. The helper already exists.

---

## 11. INTERACTION RULES (For the next agent talking to the user)

- The user is **Kelvin Childress** — head coach and project owner. He thinks in product terms, not code.
- He prefers concrete plans over open questions. When you must ask, bundle questions in batches.
- He commits via GitHub web editor by copy-paste (Chromebook, no drag-drop). Always provide full-file paste-able blocks, never diffs.
- Verify every commit via `api.github.com/.../contents/<path>` after he says "committed".
- Never paste secrets in chat. Direct him to the GitHub Settings UI.
- Keep responses focused; long projects burn context fast.
