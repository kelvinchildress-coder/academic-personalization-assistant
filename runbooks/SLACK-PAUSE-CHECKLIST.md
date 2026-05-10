# Slack-Pause Lift Checklist

The Slack-poster (`app.py` + GitHub Actions workflow that triggers it)
is **paused** until every item below is ✅. Do not lift the pause until
the entire list passes a single review session.

This list is the gate. Anything not on this list is not blocking.

---

## A. Code and config (this repo)

| ID | Item | Status | Where |
| --- | --- | --- | --- |
| I-1 | Sign-in domain allow-list enforced server-side | ✅ | `web/src/auth.ts` `signIn` callback |
| I-3 | Session max-age limited to 8h (down from 30 days) | ✅ | `web/src/auth.ts` `session.maxAge` |
| T-1 | Security headers (CSP, HSTS, frame-deny, etc.) | ✅ | `web/next.config.mjs` `headers()` |
| L-1 | `GitHubDataError` does not include response body in message | ✅ | Verified in `web/src/lib/githubData.ts` |
| L-2 | Workflow logs audited for any historical leakage of student names | ⏳ | Manual review of GitHub Actions logs older than 90 days will roll off; spot-check most recent runs |
| L-3 | Workflow log lines that print roster sizes do not also print individual identifiers | ⏳ | Same review pass as L-2 |

---

## B. External coordination

| ID | Item | Status | Owner |
| --- | --- | --- | --- |
| S-3 | TimeBack API key scope confirmed read-only and limited to this org | ⏳ | Head coach + TimeBack admin |
| OAuth | Google OAuth client is set to "Internal" (not "External") in Google Cloud Console | ⏳ | Head coach |
| Slack-app | The Slack app posting to `#sports` posts only via webhook to the one channel; no other scopes | ⏳ | Head coach to verify in Slack admin |

---

## C. Operational readiness

| ID | Item | Status | Where |
| --- | --- | --- | --- |
| IR-1 | Incident response runbook exists | ✅ | `runbooks/SECURITY.md` |
| R-1 | PII retention policy documented | ✅ | `runbooks/PII-RETENTION.md` |
| R-2 | PII deletion procedure documented | ✅ | `runbooks/PII-RETENTION.md` § 4 |
| Backup-coach | Backup head-coach contact filled in | ⏳ | `runbooks/SECURITY.md` § 2 |
| Calendar | Secret rotation calendar reminders set | ⏳ | Head coach personal calendar |

---

## D. Smoke test (only at lift time)

When everything above is ✅, run **once**:

1. Trigger the Slack workflow manually with `dry_run=true` (if the
   workflow supports it) or against a private test channel first.
2. Confirm the message format matches the design.
3. Confirm no student names appear in any field where they shouldn't.
4. Confirm the workflow log itself does not print the message body
   verbatim if the body contains student names.
5. Only then re-enable the production trigger.

After the first real run, watch `#sports` for 24h. If any anomaly,
re-pause immediately and root-cause before the next scheduled run.

---

## E. How to actually lift the pause

When this entire list is ✅:

1. Open this file in a PR alongside the workflow re-enablement commit.
2. Reviewer checks each ⏳ has flipped to ✅ with a link to the
   evidence (commit hash, screenshot, ticket).
3. Merge. The workflow's `on:` trigger is now live.
4. Note the lift date in `runbooks/incidents/YYYY-MM-DD-slack-pause-lifted.md`
   (yes, even though it's not an incident — same audit trail).

---

## F. How to re-pause if something goes wrong

1. Edit the workflow YAML and set `on: workflow_dispatch:` only (remove
   the schedule / push triggers).
2. Commit with message `slack: re-pause until <reason>`.
3. File a follow-up issue with the root-cause findings.
4. Update this file: flip the relevant row back to ⏳ and add a note.
