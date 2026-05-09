# TSA Academic Dashboard — Deployment Guide

This document walks through deploying the `web/` Next.js dashboard to
Vercel with Google SSO and read-only access to the snapshot history in
this GitHub repository.

> **Scope.** This guide is for the **dashboard webapp** under `web/` only.
> The Python automation (head-coach digest, nudges, snapshot writer) lives
> elsewhere in this repo and has its own deploy story.

> **Who runs these steps.** You do. Claude (the AI assistant that wrote
> this code) intentionally does **not** create Vercel projects, mint
> tokens, or set environment variables on your behalf. Every step below
> is a human action.

> **Slack pause.** The head-coach digest workflow remains paused until
> the operator explicitly lifts the pause. Deploying the dashboard does
> **not** affect that pause. The dashboard is read-only and never posts
> to Slack.

---

## 0. Prerequisites

You will need:

- **GitHub** access to `kelvinchildress-coder/academic-personalization-assistant` with permission to create fine-grained personal access tokens (PATs) on your account.
- **Vercel** account with permission to create a new project and link a GitHub repository. A free Hobby plan is sufficient for an internal tool of this size.
- **Google Cloud Console** access with permission to create OAuth 2.0 client credentials in a project of your choosing. The OAuth consent screen does not need to be public; an "Internal" app type is appropriate.
- A terminal with `openssl` available for generating one secret.

You should set aside about 30 minutes for first-time setup. Subsequent deploys are automatic on push to `main`.

---

## 1. Create the Vercel project

1. Go to <https://vercel.com/new>.
2. Click **Import Git Repository** and select `kelvinchildress-coder/academic-personalization-assistant`.
3. On the **Configure Project** screen, set:
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** `web` *(critical — the dashboard is not at the repo root)*
   - **Build Command:** leave default (`next build`)
   - **Output Directory:** leave default (`.next`)
   - **Install Command:** leave default (`npm install`)
   - **Node.js Version:** 20.x or later
4. **Do not click Deploy yet.** First add the environment variables in section 4 below; otherwise the first build will succeed but the running app will fail to authenticate.

---

## 2. Configure Google OAuth

1. Open <https://console.cloud.google.com/>. Select or create a project.
2. Navigate to **APIs & Services → OAuth consent screen**.
   - User type: **Internal** (recommended) if your TSA Google Workspace allows it; otherwise **External** and add the three allowed domains as test users.
   - App name: `TSA Academic Dashboard`
   - User support email: your email
   - Authorized domains: `vercel.app` (and your custom domain if any)
   - Save.
3. Navigate to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Web application**
   - Name: `TSA Academic Dashboard — production`
   - Authorized JavaScript origins: `https://<your-vercel-domain>` (e.g., `https://tsa-dashboard.vercel.app`)
   - Authorized redirect URIs: `https://<your-vercel-domain>/api/auth/callback/google`
   - Click **Create**.
4. Copy the **Client ID** and **Client secret** into a secure password manager. You will paste them into Vercel in section 4.

> **Local development.** If you also want to run the dashboard locally, create a second OAuth client (or add a second redirect URI to the existing one) for `http://localhost:3000/api/auth/callback/google`.

---

## 3. Mint the GitHub data PAT

The dashboard reads snapshot JSON files from `data/history/` in this repo at request time using a server-side fine-grained PAT. The token never leaves Vercel's runtime; it is not exposed to the browser.

1. Go to <https://github.com/settings/personal-access-tokens/new>.
2. Configure the token:
   - **Token name:** `tsa-dashboard-data-read`
   - **Expiration:** `90 days` (rotate per the runbook in section 7)
   - **Resource owner:** `kelvinchildress-coder`
   - **Repository access:** **Only select repositories** → `academic-personalization-assistant`
   - **Repository permissions:** under **Contents**, set to **Read-only**. Leave everything else at **No access**.
3. Click **Generate token**. Copy the token starting with `github_pat_...` immediately; GitHub shows it only once.
4. Save the token in your password manager. You will paste it into Vercel in section 4.

> **Why fine-grained and not classic?** Classic PATs grant `repo` scope (read+write to all your repos). The fine-grained variant restricts to one repository and to **Contents: Read** only, which is exactly what the dashboard needs.

---

## 4. Set environment variables in Vercel

Open the Vercel project → **Settings → Environment Variables**. Add the following five variables, scoped to **Production** (and **Preview** if you want preview deployments to work):

| Variable | Value | Source |
| --- | --- | --- |
| `AUTH_SECRET` | (paste output of `openssl rand -base64 32`) | Generated locally; this is the JWT signing secret |
| `AUTH_GOOGLE_ID` | (paste OAuth Client ID) | Section 2 step 4 |
| `AUTH_GOOGLE_SECRET` | (paste OAuth Client secret) | Section 2 step 4 |
| `NEXTAUTH_URL` | `https://<your-vercel-domain>` | Final production URL |
| `GITHUB_DATA_READ_PAT` | (paste `github_pat_...` token) | Section 3 step 3 |

To generate `AUTH_SECRET`:

```sh
openssl rand -base64 32
```

Mark all five variables as **Sensitive** in the Vercel UI so they are not displayed once saved.

> **What is `NEXTAUTH_URL` for?** Auth.js uses it to construct OAuth callback URLs and to validate state. It must exactly match the host the browser sees (no trailing slash).

---

## 5. First deploy

1. From the Vercel project dashboard, click **Deployments → Redeploy** (or push any commit to `main`).
2. The build runs `npm install` then `next build`. Expected duration: 1–3 minutes.
3. On success, Vercel shows the production URL. Confirm it matches the `NEXTAUTH_URL` you set; if not, update the env var and redeploy.

If the build fails, the most common causes are:

- Missing environment variable → the Auth.js initializer throws at build time. Re-check section 4.
- Root directory not set to `web` → Vercel can't find `package.json`. Re-check section 1 step 3.
- TypeScript error → see Vercel logs; the `web/src/lib/*.test.ts` files are Vitest tests and should be excluded from the production build by `tsconfig.json`'s default `next-env.d.ts` setup, not by manual exclusion.

---

## 6. Verify

After the first deploy succeeds:

1. **Sign in as the head coach** (`kelvin.childress@sportsacademy.school`).
   - Navigate to the production URL.
   - Click **Sign in with Google**.
   - You should land on `/head` (head-coach overview, flat all-students table).
2. **Sign in as a regular coach** (any allowed-domain Google account whose display name matches a `coach` field in the snapshot data).
   - You should land on `/coach/<your-name-slug>`.
3. **Try a cross-coach URL** (as the regular coach, manually edit the URL to another coach's slug).
   - You should see the "Not authorized" page.
4. **Try the window dropdown** (on `/head`, on a coach roster, on a student detail page).
   - URL should update to `?window=session` or `?window=year`.
   - Counts and metrics should change accordingly.
5. **Check that data is live**, not cached: the dashboard uses `revalidate = 0` and 60-second in-process caching in `githubData.ts`. New snapshots committed to `data/history/` should appear within ~1 minute.

---

## 7. Rotation runbook

Three secrets rotate on different cadences:

| Secret | Cadence | Procedure |
| --- | --- | --- |
| `GITHUB_DATA_READ_PAT` | **Every 90 days** | Mint a new fine-grained PAT (section 3), update the Vercel env var, redeploy. The old token can be revoked immediately on GitHub. |
| `AUTH_GOOGLE_SECRET` | When suspected leaked, or yearly | Reset secret in Google Cloud Console → Credentials, update the Vercel env var, redeploy. |
| `AUTH_SECRET` | When suspected leaked | Generate a new value with `openssl rand -base64 32`, update the Vercel env var, redeploy. **All active sessions will be invalidated** (users must sign in again). |

A calendar reminder for the 90-day PAT rotation is recommended; GitHub will email you 7 days before expiry.

---

## 8. What to change in code (not in this doc)

If you need to:

- **Add or remove a head coach** → edit `HEAD_COACH_EMAILS` in `web/src/lib/authz.ts`, commit, redeploy.
- **Change the allowed sign-in domains** → edit `ALLOWED_EMAIL_DOMAINS` in `web/src/auth.ts`, commit, redeploy.
- **Change the default time window** → edit `DEFAULT_WINDOW` in `web/src/lib/window.ts`.
- **Change the cache TTL** → edit the `CACHE_TTL_MS` constant in `web/src/lib/githubData.ts`.

These are all intentionally code-level (not env var) changes, because they represent architectural constraints that should go through code review rather than a Vercel UI edit.

---

## 9. Things this guide does not cover

- **Deleting the production deployment** — out of scope; do this through the Vercel UI directly if needed.
- **Custom domain setup** — straightforward in Vercel UI; remember to update `NEXTAUTH_URL` and the OAuth redirect URI when you do.
- **Preview deployments for pull requests** — works automatically once env vars are scoped to **Preview**, but each preview URL needs to be added as an authorized OAuth redirect URI in Google Cloud, which is fiddly. Recommended: keep the dashboard production-only.
- **Rolling back a bad deploy** — Vercel keeps prior deployments; click **Promote to Production** on a known-good deployment.
- **Lifting the Slack pause on the head-coach digest** — that is a separate runbook in the Python repo's docs.
