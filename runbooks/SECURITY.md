# Security Runbook — Texas Sports Academy Academic Personalization Assistant

This runbook covers incident response and secret rotation for the Phase 7
dashboard at `web/`. The dashboard is a Next.js App Router application
deployed on Vercel that reads JSON snapshots from this same GitHub repo.

It does **not** cover the legacy Flask Slack-poster (`app.py`) or the
GitHub Pages dashboard (`docs/timeback-dashboard.js`); those are
separate systems and out of scope here.

---

## 1. System overview

| Surface | What it holds | Trust boundary |
| --- | --- | --- |
| GitHub repo `data/history/*.json` | Per-day TimeBack snapshots: student names, emails, minutes, accuracy. | Repo is **private**. Only collaborators + the data-collection workflow can read. |
| GitHub Actions workflow | TimeBack PAT used to pull fresh data each morning. | Stored as `TIMEBACK_API_KEY` secret. |
| Vercel project (Next.js dashboard) | At runtime: AUTH_GOOGLE_*, AUTH_SECRET, GITHUB_DATA_READ_PAT. | Server-side only. Never exposed to browsers. |
| Browser session (signed-in coach) | JWT cookie; in-memory roster + snapshots. | HTTPS only; session 8h max; HttpOnly cookie. |
| Coach laptop CSV exports | Downloaded student rows. | Out of our control once downloaded. Coaches are responsible. |

---

## 2. Authoritative contact

**Primary on-call**: Kelvin Childress
**Backup**: _unset — fill in when a second head coach is added._
**Escalation**: Alpha School security lead.

Update this section whenever staffing changes. The runbook is the source
of truth, not Slack DMs.

---

## 3. Secret inventory and rotation cadence

| Secret | Where stored | Used by | Rotate every | Last rotated |
| --- | --- | --- | --- | --- |
| `TIMEBACK_API_KEY` | GitHub Actions secret | Daily snapshot workflow | 180 days | _set when issued_ |
| `AUTH_SECRET` | Vercel env var | Auth.js JWT signing | 365 days | _set when issued_ |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | Vercel env var | Google OAuth login | 365 days, or on suspected exposure | _set when issued_ |
| `GITHUB_DATA_READ_PAT` | Vercel env var | Server-side reads of `data/history/` | 90 days (max GitHub allows for fine-grained PATs) | _set when issued_ |

Calendar reminders for these dates live in the head coach's personal
calendar. Do not commit dates to this file.

### 3.1 Rotation procedure (general)

1. Generate the new value at its source (Google Cloud Console, GitHub PAT
   page, `openssl rand -base64 32`, etc.).
2. Add the **new** value to Vercel/GitHub Secrets **alongside** the old
   one if the platform supports two values; otherwise replace and accept
   one short failure window.
3. Trigger a Vercel redeploy (Deployments → Redeploy latest).
4. Watch the deployment logs and the next 24h of traffic for failures.
5. Once the new value is confirmed working, revoke the old one at its
   source. **Never** leave an unused but still-valid PAT alive.
6. Update the "Last rotated" date in this table.

### 3.2 Rotation procedure (GITHUB_DATA_READ_PAT specifically)

GitHub fine-grained PATs cap at 90 days. Set a calendar reminder 7 days
before expiry. Steps:

1. Go to `github.com/settings/personal-access-tokens` while signed in as
   the owner.
2. Generate a new fine-grained PAT, scoped to **only** this repo, with
   **Contents: Read-only** and nothing else.
3. Paste into Vercel → Settings → Environment Variables →
   `GITHUB_DATA_READ_PAT` (Production + Preview).
4. Redeploy.
5. Once healthy, delete the old PAT from `settings/personal-access-tokens`.

---

## 4. Incident response

### 4.1 Severity levels

| Level | Definition | Response time |
| --- | --- | --- |
| **SEV-1** | PII confirmed leaked off-system, or unauthorized account access confirmed. | Begin within 1 hour. |
| **SEV-2** | Suspected leak; unable to confirm yet. Or: a secret is known-compromised but no abuse seen. | Begin within 4 hours. |
| **SEV-3** | Misconfiguration risk found internally; no evidence of abuse. | Begin same business day. |

### 4.2 First 30 minutes (any severity)

1. **Stop the bleeding.** If a secret is exposed: revoke it at the source
   immediately. Do not wait for a meeting.
2. **Capture evidence.** Screenshot the exposure, save the URL, save any
   logs. Do not edit or delete the source.
3. **Note the timeline.** When did the exposure start? End? How was it
   discovered? Write this down before memory fades.
4. **Notify.** Page the on-call (section 2). For SEV-1, also notify the
   Alpha School security lead.

### 4.3 Containment by exposure type

**Google OAuth client secret leaked**
- Rotate `AUTH_GOOGLE_SECRET` (section 3.1).
- Existing user sessions remain valid (JWT-signed independently). To
  force re-login of all users, also rotate `AUTH_SECRET`.

**`AUTH_SECRET` leaked**
- Rotate `AUTH_SECRET`. All existing sessions become invalid on next
  request — users will see /login. This is the desired behavior.

**`GITHUB_DATA_READ_PAT` leaked**
- Revoke the PAT at `github.com/settings/personal-access-tokens` first.
- Then issue a replacement (section 3.2).
- Even with the PAT, an attacker can only read snapshots already in this
  repo. No write access is possible because the PAT is read-only.

**`TIMEBACK_API_KEY` leaked**
- Contact TimeBack admin to revoke and reissue.
- Audit recent API call volume for anomalies.

**Unauthorized sign-in**
- Capture the email and timestamp from Google Workspace audit log.
- Remove the user from the Google Workspace org if external.
- Confirm `ALLOWED_EMAIL_DOMAINS` in `web/src/auth.ts` did not regress.
- If the user was on an allowed domain but should not have access:
  consider tightening to an explicit allow-list of email **addresses**
  (not just domains).

**A snapshot file in `data/history/` contains data it shouldn't**
- Do not push a deleting commit. The data is in git history.
- Use `git filter-repo` or contact GitHub Support to scrub the blob.
- Force-push is required and breaks every clone. Coordinate.

### 4.4 Post-incident (within 7 days)

- Write a short postmortem in this directory: `runbooks/incidents/YYYY-MM-DD-shortname.md`.
- Sections: timeline, impact, root cause, what stopped it from being
  worse, follow-ups.
- File follow-up issues in the GitHub repo. Tag with `security`.

---

## 5. Hardening checklist (current state)

| Control | Status |
| --- | --- |
| HTTPS only (Vercel-enforced) | ✅ |
| HSTS (`Strict-Transport-Security`) | ✅ (set in `next.config.mjs` Cycle F) |
| Content Security Policy | ✅ (set in `next.config.mjs` Cycle F) |
| `X-Frame-Options: DENY` | ✅ |
| `X-Content-Type-Options: nosniff` | ✅ |
| `Referrer-Policy: strict-origin-when-cross-origin` | ✅ |
| `Permissions-Policy` (camera/mic/geo off) | ✅ |
| Auth domain allow-list enforced server-side | ✅ (`signIn` callback in `auth.ts`) |
| Session max-age 8h | ✅ (Cycle F) |
| HttpOnly + Secure session cookie | ✅ (Auth.js default in production) |
| Secrets only in Vercel/Actions, never in repo | ✅ |
| Server-only env vars marked `server-only` | ✅ (per `lib/githubData.ts`) |
| Dependabot enabled | ⚠️ Toggle in repo Settings → Code security |
| Repo is private | ✅ |
| GitHub Actions logs reviewed before public Slack re-enable | ⏳ See `SLACK-PAUSE-CHECKLIST.md` |

---

## 6. Things this app intentionally does **not** do

These are not bugs. They are choices made to keep the surface small.

- **No password authentication.** Google OAuth only.
- **No third-party analytics.** No Vercel Analytics, no GA, no Sentry.
  If you add one later, update the CSP in `next.config.mjs`.
- **No write APIs.** The app only reads. The only way to change data is
  to commit to this repo.
- **No email notifications.** All notification flow goes through the
  separate Slack-poster (`app.py`), which is paused until lift-time.
- **No "remember me" beyond 8h.** Coaches re-authenticate each work day.
