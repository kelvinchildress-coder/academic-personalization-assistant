# Texas Sports Academy — Academic Personalization Dashboard (Phase 7)

Next.js 14 (App Router) static dashboard for visualizing per-coach roster
status, per-student detail, and head-coach overview. Reads daily history
snapshots from `data/history/*.json` in the parent repo via the GitHub
Contents API at request time.

## Tech stack

- Next.js 14 (App Router) + TypeScript + Tailwind CSS
- Auth.js v5 (next-auth) with Google SSO + email-domain allow-list
- Server-runtime data reads via fine-grained GitHub PAT
- Vitest for unit tests

## Allowed login domains

- `sportsacademy.school`
- `alpha.school`
- `2hourlearning.com`

Login attempts from any other email domain are rejected.

## Local development

```bash
cd web
npm install
cp .env.local.example .env.local
# Fill in AUTH_SECRET, AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET, NEXTAUTH_URL,
# GITHUB_DATA_READ_PAT in .env.local. See DEPLOY.md (Part 7) for how to
# obtain each value.
npm run dev
```

The dev server runs on `http://localhost:3000`.

## Production deploy (Vercel)

See `DEPLOY.md` (delivered in Phase 7 Part 7) for step-by-step Vercel
project setup. **Do NOT deploy until DEPLOY.md is in place** — env-var
configuration is critical for both auth and the GitHub data read path.

## Required environment variables

| Name | Where it lives | Purpose |
|---|---|---|
| `AUTH_SECRET` | Vercel + `.env.local` | Auth.js JWT signing key (random 32+ bytes) |
| `AUTH_GOOGLE_ID` | Vercel + `.env.local` | Google OAuth client ID |
| `AUTH_GOOGLE_SECRET` | Vercel + `.env.local` | Google OAuth client secret |
| `NEXTAUTH_URL` | Vercel + `.env.local` | Public app URL |
| `GITHUB_DATA_READ_PAT` | Vercel + `.env.local` | Fine-grained PAT (Contents: Read-only on this repo) |

**Never commit `.env.local` or any of these values.** The repo's
`.gitignore` (and `web/.gitignore`) already exclude them.

## Project structure

```
web/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── .gitignore
├── .env.local.example
├── README.md
└── src/
    └── app/
        └── globals.css
```

Subsequent Phase 7 parts add:

- Part 2 — `src/auth.ts`, `src/middleware.ts`, `src/app/login/page.tsx`,
  `src/app/layout.tsx` (Auth.js + Google SSO + domain allow-list)
- Part 3 — `src/lib/githubData.ts` (server-only data layer)
- Part 4 — `src/lib/aggregate.ts` + tests (digest_v2 metrics in TS)
- Part 5 — `src/app/page.tsx` + `src/app/coach/[coachName]/page.tsx`
- Part 6 — `src/app/student/[studentName]/page.tsx` +
  `src/app/head-coach/page.tsx`
- Part 7 — `DEPLOY.md`
- Part 8 — Closeout addendum
