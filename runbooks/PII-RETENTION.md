# PII Retention and Deletion Runbook

Companion to `runbooks/SECURITY.md`. This file covers what student data
the system holds, how long, and how to delete it on request.

---

## 1. What counts as PII here

In this system, PII is limited to:

- Student **full name** (first + last)
- Student **email address** (in some snapshots)
- Per-student **TimeBack performance metrics** (minutes, accuracy)
- Coach **email address** and **display name** (from Google profile)
- Coach **roster assignments** (`config/coach_emails.json`)

We do **not** collect:

- Birthdates, addresses, phone numbers, government IDs
- Parent/guardian names or contact info
- Medical, IEP, or behavioral records
- Financial or payment data
- Photographs or biometrics

If anyone proposes adding anything from the "do not collect" list,
that's a design conversation, not a data conversation. Push back.

---

## 2. Where PII lives

| Location | What's there | Owner | Default retention |
| --- | --- | --- | --- |
| `data/history/YYYY-MM-DD.json` | Student names, optional emails, daily metrics | This repo | Indefinite (academic year archive) |
| `data/sessions.json` | Session calendar (no PII) | This repo | Indefinite |
| `config/coach_emails.json` | Coach roster: email + assigned student emails | This repo | Indefinite |
| Vercel build/runtime logs | Request paths, timing, errors. **No** snapshot bodies are logged. | Vercel | 30 days (free tier) |
| GitHub Actions workflow logs | Snapshot fetch outcome. May contain student counts but not names if `console.log` discipline holds. | GitHub | 90 days |
| Browser session cookie | Coach JWT (email, name) | User's browser | 8 hours |
| CSV exports | Whatever the coach exported | Coach laptop | Coach's responsibility |

---

## 3. Retention policy

### 3.1 Snapshots (`data/history/`)

- **Active academic year**: keep all snapshots.
- **End of academic year (June)**: archive previous year's snapshots
  to a separate private branch (`archive/sy25-26`), then optionally
  delete from `main` to reduce clone size. Record the archival commit
  hash here:
  - SY25-26 archive hash: _to fill in June 2026_
  - SY26-27 archive hash: _to fill in June 2027_

### 3.2 Coach roster (`config/coach_emails.json`)

- When a coach leaves: remove their entry in the next commit. Their
  past snapshots remain (they're attached to students, not coaches).

### 3.3 Vercel and GitHub logs

- We don't manage retention for either platform's logs directly. Trust
  their defaults (30 days / 90 days respectively). If a longer audit
  trail is ever required, we'll need to ship logs to a separate
  retention store — out of scope today.

---

## 4. Deletion on request

If a parent, student, or school asks for data to be deleted:

### 4.1 Verify the request is legitimate

1. Confirm the requester's identity through a school-side channel
   (email + at least one secondary verification — admin attestation,
   parent contact on file, etc.).
2. Note the request in writing: who asked, what they asked for, when,
   and who verified.

### 4.2 Determine scope

- **One student, one day**: rare. We almost always delete by student
  across all days.
- **One student, all days**: the common case.
- **Whole class**: handled the same way at scale.
- **Coach account**: just remove from `config/coach_emails.json`.

### 4.3 Execute deletion

For a single student across all snapshots:

1. Identify the student's stable identifier. Names can collide, so
   prefer email if present; otherwise use first+last + the smallest
   coach roster the student appears in.
2. For each file in `data/history/*.json`, remove the student's
   record. Do this in a single commit so the audit trail is clean.
3. Commit message: `data: remove student per deletion request <ticket-id>`.
   Do not include the student's name in the commit message.
4. **Important**: the data is still in git history. For most school
   contexts a normal commit is sufficient. If the requester explicitly
   demands removal from history (rare, usually only under a court
   order), use `git filter-repo` and force-push. This breaks every
   clone of the repo. Coordinate with all collaborators first.

### 4.4 Confirm and record

- Verify the latest snapshot served by the dashboard no longer shows
  the student. Sign in, navigate to head/coach views, search.
- Reply to the requester confirming completion. Cite the commit hash.
- Append to `runbooks/deletions/YYYY-MM-DD.md`: ticket ID, scope,
  commit hash, who executed. Do **not** include the student's name in
  this audit file — use the ticket ID as the link.

---

## 5. Right-to-access requests

Less common than deletions but follow the same verification flow.

1. Identify the student's records across `data/history/`.
2. Export to a CSV (or JSON) and deliver via a school-approved channel
   (school email, secure file transfer). **Do not** attach to a public
   ticket or post in Slack.
3. Record the export in `runbooks/access-requests/YYYY-MM-DD.md` (no
   student name, just the ticket ID and what was sent).

---

## 6. What to do if PII is in a place it shouldn't be

| Discovered location | Action |
| --- | --- |
| In a public Slack message | Delete the message. Notify the channel owner. Treat as SEV-2 per `SECURITY.md`. |
| In a Vercel/GitHub log | Identify the log line. If it's recurring code, fix the code first; logs will roll off in 30/90 days. |
| In a CSV uploaded somewhere off-system | Out of our scope. Notify the coach who exported it; remind them of the export-handling expectations. |
| In a screenshot in a doc | Coordinate doc owner to redact. |
| In an email | Treat as a SEV-2 disclosure. Ask the recipient to delete; document. |

---

## 7. Annual review

The head coach reviews this file every August before school starts.
Update:
- The retention table dates
- The archive hash for the prior year
- Any new collection surface added during the past year
- Contact list in `SECURITY.md` § 2
