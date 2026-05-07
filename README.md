# Academic Personalization Assistant

Coach-set personalized XP goals on top of TimeBack data, with daily-recalculating targets,
trend tracking, and Slack reports. Built for Texas Sports Academy (TSA), Calendar A,
SY 2025–26.

## Status

> **Last completed checkpoint:** 2 — additive Path B logic shipped:
> `src/` (models, calendar, targets, report builder, slack poster),
> `config/coaches.json` (34 students mapped to 7 coaches + Head Coach),
> `scripts/post_morning_report.py`, `scripts/post_live_updates.py`,
> `scripts/post_eod_summary.py`, full `tests/` suite, three GitHub
> Actions workflows (`morning-report`, `live-updates`, `eod-summary`),
> and `SETUP.md`. Holiday calendar + ingest-side scraper script pending.

If a chat session dies mid-build, a fresh chat can resume by reading this checkpoint
marker, the file tree, and the recent commit messages.

## Architecture (Path B — laptop scraper + GitHub Actions for always-on services)

The upstream Flask + Playwright scraper (`app.py`, `templates/dashboard.html`,
`docs/timeback-dashboard.js`) is preserved unmodified. New logic lives in
`src/` and runs in GitHub Actions, reading `data/latest.json` written by
the ingest path (TimeBack API service account if available; Linux
Chromebook scraper otherwise; manual bookmarklet fallback).

## Slack delivery model

Reports post to the `#sports` channel as a thread:

- **Parent message** — header (e.g. `*Morning Report — Mon May 4*`)
- **Threaded replies** — one per coach, tagging the coach with `<@U…>` and listing
  their students with today's target. Coaches resolved at runtime by the bot via
  `users.list`; no hand-collected user IDs in the repo.
- **Head Coach digest** — one threaded reply at the end tagging Kelvin Childress
  with the campus-wide standout issues and successes.
- **Live updates** — every 30 minutes during school hours, additional threaded
  replies when a student crosses accuracy <60% in any app or exceeds 125% of XP
  target in any app.
- **End-of-day summary** — one threaded reply at 5:00 PM CT listing students who
  did not finish the day Green, grouped by coach.

## Roster

Texas Sports Academy, 34 students, 7 coaches + Head Coach. See
`config/coaches.json` for the authoritative coach → student mapping.

## XP target rules (locked)

| Subject | Daily XP | Notes |
|---|---|---|
| Math | 25 | Base rate |
| Reading | 25 | Base rate |
| Language | 25 | Base rate |
| Writing | 12.5 | Flat (TimeBack averages alt-week 25) |
| Science | 12.5 | Flat (TimeBack averages alt-week 25) |
| Vocabulary | 10 | Base rate |
| FastMath | 10 | Base rate |

- Coaches can override per-app XP per student via `students.json`.
- Coaches can set a "test out of grade by date" goal; daily target back-solves to
  `(remaining_xp / remaining_school_days)` with a 4× base cap.
- Pace status uses TimeBack's literal labels for base-rate students; richer
  PaceReport for personalized goals.
- Accuracy below 60% in any subject auto-flags the student.
- School days only — no weekends, holidays, or TSA breaks (Calendar A).

## Recovery instructions for a future chat

1. Read this README — find the **Last completed checkpoint** line.
2. Read the most recent commits on `main` for trajectory.
3. Resume from the next checkpoint per the build plan.

## Setup

See [`SETUP.md`](./SETUP.md). Browser-only steps (Slack app, GitHub
secrets) work on any device. The ingest path setup depends on whether
TimeBack provided an API token, whether your Chromebook supports
Crostini Linux, or whether you're using the manual bookmarklet fallback.

## Upstream

Forked from [Alpha-School-SB/timeback-dashboard-v2](https://github.com/alpha-school-sb/timeback-dashboard-v2).
The original scraper is kept; this repo extends it with goal logic, Slack reports,
calendar awareness, and TSA-specific config.
