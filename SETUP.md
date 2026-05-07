# Setup — Academic Personalization Assistant

Step-by-step setup for the daily Slack reporting system. Browser-only steps
work fine on a Chromebook; ingest-host steps depend on which path you chose.

## 1. Slack app (one-time, browser only)

1. Go to <https://api.slack.com/apps> and click **Create New App** → **From
   scratch**. Name it `Academic Personalization Assistant`. Pick the Alpha
   workspace.
2. In the left sidebar, click **OAuth & Permissions**.
3. Under **Bot Token Scopes**, add:
   - `chat:write`
   - `chat:write.public`
   - `users:read`
   - `users:read.email`
   - `channels:read`
4. Scroll up and click **Install to Workspace**. Approve the prompt.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-…`). Treat it like
   a password — never paste it into chat or email.
6. Go to <https://github.com/kelvinchildress-coder/academic-personalization-assistant/settings/secrets/actions>.
7. Click **New repository secret**:
   - Name: `SLACK_BOT_TOKEN`
   - Value: paste the `xoxb-…` token. Click **Add secret**.
8. In Slack, invite the new bot to `#sports`:
   - Open `#sports`, click the channel name → **Integrations** → **Add
     apps** → find `Academic Personalization Assistant` → **Add**.

## 2. GitHub Actions schedules (already configured)

Three workflows are committed in `.github/workflows/`:

- **morning-report.yml** — 8:00 AM CT, Mon–Fri.
- **live-updates.yml** — every 30 min between 9 AM and 3 PM CT, Mon–Fri.
- **eod-summary.yml** — 5:00 PM CT, Mon–Fri.

GitHub Actions cron is in UTC, so each workflow runs at both the
CDT-equivalent and CST-equivalent UTC times. Each script bails out fast
when called outside its real window (not a school day, no fresh data, etc.),
so the duplicate triggers are harmless.

To verify the workflows registered:

> Actions tab → confirm `morning-report`, `live-updates`, `eod-summary`
> all appear in the left sidebar.

## 3. Ingest path

You must pick one of three paths to populate `data/latest.json` each
school day. Pick whichever applies to your situation; only one is needed.

### Path 3 — TimeBack service account / API token (preferred, fully unattended)

Use this if TimeBack grants you an API token.

1. Add the token as a GitHub secret named `TIMEBACK_API_TOKEN`.
2. Add a new file `scripts/scrape_via_api.py` (Claude will generate this
   once the token is provisioned and we know the endpoint shape).
3. Add a new workflow `.github/workflows/scrape.yml` that runs at
   6:30 AM CT and writes `data/latest.json` + `data/<date>.json`.
4. The morning-report workflow runs an hour later (already scheduled at
   8:00 AM CT) and reads what `scrape.yml` committed.

No laptop required. This is the cleanest answer.

### Path 1 — Linux on Chromebook (Crostini)

Use this if Path 3 is not yet available and your Chromebook allows Linux.

1. ChromeOS **Settings** → **Advanced** → **Developers** → **Linux
   development environment** → **Turn on**. Allocate at least 10 GB.
   (If this option is grayed out, your IT admin has it locked; use Path 4.)
2. Open the Linux terminal (Linux Files → terminal icon, or search
   "Terminal" in the launcher).
3. Install dependencies:
```bash
   sudo apt update
   sudo apt install -y python3 python3-pip git chromium python3-venv
```
4. Clone the repo:
```bash
   cd ~
   git clone https://github.com/kelvinchildress-coder/academic-personalization-assistant.git
   cd academic-personalization-assistant
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
```
5. Generate a fine-scoped GitHub Personal Access Token at
   <https://github.com/settings/personal-access-tokens/new>:
   - Resource owner: `kelvinchildress-coder`
   - Repository: only `academic-personalization-assistant`
   - Repository permissions: `Contents` → **Read and write**
   - Expiration: 90 days
   - Click **Generate token** and copy the value.
6. Store the PAT in Linux's secret store (or the simplest secure file):
```bash
   mkdir -p ~/.config/apa
   chmod 700 ~/.config/apa
   # Paste the token at the prompt; this writes it to a file readable
   # only by you.
   read -s -p "Paste GitHub PAT: " TOKEN
   echo "$TOKEN" > ~/.config/apa/github-token
   chmod 600 ~/.config/apa/github-token
   unset TOKEN
```
7. Test once manually:
```bash
   source venv/bin/activate
   python scripts/scrape_and_push.py
```
   (Note: `scripts/scrape_and_push.py` will be generated for Linux once
   you confirm Crostini works. The Mac version was discarded.)
8. Schedule it via cron:
```bash
   crontab -e
```
   Add this line:
```
   30 6 * * 1-5 cd ~/academic-personalization-assistant && ./venv/bin/python scripts/scrape_and_push.py >> ~/.config/apa/cron.log 2>&1
```
   (6:30 AM Linux local time. If your Chromebook timezone is set to
   Central, this is 6:30 CT.)
9. Make sure your Chromebook is **on and logged into TimeBack** weekday
   mornings before 6:30 AM CT.

### Path 4 — Manual bookmarklet (fallback)

Use this only if Paths 3 and 1 are both unavailable.

1. The repo already has `docs/timeback-dashboard.js`, the existing
   bookmarklet client.
2. Each weekday morning, you (or any coach with TimeBack access) opens
   TimeBack in Chrome and clicks the bookmarklet. It captures the day's
   data and posts it to a small intermediary endpoint.
3. The intermediary writes `data/latest.json` to the repo via GitHub's
   Contents API.
4. Slack posts then run from GitHub Actions on the existing morning /
   live / EOD schedule.

This path requires one daily click. We will generate the small
intermediary as a final step if you end up here.

## 4. Holiday calendar

`src/calendar_tsa.py` ships with `HOLIDAYS = frozenset()` (empty). Until
you populate it with TSA Calendar A no-school dates, the system treats
every Mon–Fri as a school day and will post on holidays.

When you provide the calendar document, we'll generate one follow-up
commit that fills `HOLIDAYS` for SY 2025–26.

## 5. Adding / removing students

- **Edit `students.json`** to change the roster the existing scraper
  pulls. Either a list of strings or a list of student objects:
```json
  ["Aaron M", "Brooke S", {"name": "Carla R", "xp_overrides": {"Math": 30}}]
```
- **Edit `config/coaches.json`** to change which coach owns which
  student. Names must match exactly.

## 6. Setting per-student overrides

In `students.json`, replace a string entry with an object:

```json
{
  "name": "Aaron M",
  "xp_overrides": { "Math": 30, "Reading": 20 }
}
```

Override values **replace** the locked base for that student/subject only.

## 7. Setting a "test out of grade by date" goal

In `students.json`:

```json
{
  "name": "Aaron M",
  "test_out_goal": {
    "subject": "Math",
    "target_xp": 1500,
    "target_date": "2026-03-15",
    "starting_xp": 0
  }
}
```

The daily target is back-solved as `(target_xp − starting_xp) /
remaining_school_days` with a sanity cap at 4× the locked base.

## 8. Rotating credentials

- **Slack token:** Generate a new bot token in the Slack app settings,
  update the `SLACK_BOT_TOKEN` GitHub secret.
- **GitHub PAT (Path 1 only):** Generate a new fine-scoped PAT, replace
  `~/.config/apa/github-token` on the Linux container.

## 9. What to do if a workflow fails

- Open the **Actions** tab, click the failing run, expand the failing
  step. Most failures are: missing `SLACK_BOT_TOKEN` secret, the bot
  not invited to `#sports`, or stale `data/latest.json`.
- The morning-report workflow DMs Kelvin Childress automatically when it
  detects stale or missing data. No public post will go out in that case.

## 10. Manual smoke test

From the **Actions** tab:

1. Click **morning-report** → **Run workflow** → Run.
2. Watch the run; expand the "Post morning report" step.
3. Verify in Slack `#sports` that the parent message + 7 coach replies
   + head-coach digest all appeared.

If you don't have real data yet, commit a synthetic `data/latest.json`:

```json
{
  "date": "2026-05-04",
  "timestamp": "May 4, 2026 at 7:00 AM",
  "students": [
    {
      "name": "Aaron M",
      "total_xp": 30,
      "overall_accuracy": 85,
      "total_minutes": 25,
      "subjects": [
        {"name": "Math", "xp": 30, "accuracy": 85, "minutes": 25, "mastered": 1, "no_data": false, "has_test": false}
      ],
      "absent": false
    }
  ]
}
```

then re-run the workflow.
