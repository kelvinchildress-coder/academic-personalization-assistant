import asyncio
import json
import subprocess
import logging
import os
import math
import requests as http_requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from playwright.async_api import async_playwright

app = Flask(__name__)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data.json"
STUDENTS_FILE = BASE_DIR / "students.json"
STUDENT_IDS_FILE = BASE_DIR / "student_ids.json"
GROUPS_FILE = BASE_DIR / "groups.json"
CACHE_DIR = BASE_DIR / "cache"
CDP_URL = "http://127.0.0.1:9222"
TIMEBACK_BASE = "https://alpha.timeback.com"
TIMEZONE = "America/Los_Angeles"

CACHE_DIR.mkdir(exist_ok=True)

STUDENTS = []
STUDENT_IDS = {}  # name -> sourcedId mapping
GROUPS = []  # list of {"name": "Group Name", "students": ["Name1", "Name2"]}


def load_students():
    global STUDENTS, STUDENT_IDS, GROUPS
    if STUDENTS_FILE.exists():
        STUDENTS = json.loads(STUDENTS_FILE.read_text())
    if STUDENT_IDS_FILE.exists():
        STUDENT_IDS = json.loads(STUDENT_IDS_FILE.read_text())
    if GROUPS_FILE.exists():
        GROUPS = json.loads(GROUPS_FILE.read_text())


def save_students_file():
    STUDENTS_FILE.write_text(json.dumps(STUDENTS))


def save_student_ids():
    STUDENT_IDS_FILE.write_text(json.dumps(STUDENT_IDS, indent=2))


load_students()


def get_cached_day(date_str):
    """Return cached processed student data for a date, or None."""
    cache_file = CACHE_DIR / f"{date_str}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return None


def get_cached_day_complete(date_str, cookies=None):
    """Return cached data for a date, backfilling missing or empty students via API.
    Returns None only if no cache exists at all."""
    cached = get_cached_day(date_str)
    if cached is None:
        return None

    cached_by_name = {s["name"]: s for s in cached}

    # Find students that are missing OR have empty data (possibly stale from old scraper)
    needs_fetch = []
    for name in STUDENTS:
        if name not in cached_by_name:
            needs_fetch.append(name)
        elif not cached_by_name[name].get("subjects"):
            # Empty subjects list — might be stale. Re-verify against the API.
            # Mark with _verified=True after checking so we don't re-check every time.
            if not cached_by_name[name].get("_verified"):
                needs_fetch.append(name)

    if needs_fetch and cookies:
        changed = False
        for name in needs_fetch:
            sid = resolve_student_id(name, cookies)
            if not sid:
                continue
            try:
                metrics = fetch_activity_metrics(sid, date_str, cookies)
                student_data = process_api_metrics(name, metrics, date_str)

                if not student_data["subjects"]:
                    # API confirmed no data — mark as verified so we don't keep re-checking
                    student_data["_verified"] = True

                cached_by_name[name] = student_data
                changed = True
            except Exception as e:
                logger.error(f"Backfill error for {name} on {date_str}: {e}")

        if changed:
            # Rebuild list in STUDENTS order, remove students no longer in list
            cached = [cached_by_name[name] for name in STUDENTS if name in cached_by_name]
            save_cached_day(date_str, cached)
    else:
        # Still filter to current student list and reorder
        cached = [cached_by_name[name] for name in STUDENTS if name in cached_by_name]

    return cached


def save_cached_day(date_str, students_data):
    """Save processed student data for a date."""
    cache_file = CACHE_DIR / f"{date_str}.json"
    cache_file.write_text(json.dumps(students_data, indent=2))


def ensure_chrome_debug():
    """Make sure Chrome is running with remote debugging enabled."""
    try:
        import urllib.request
        urllib.request.urlopen(CDP_URL + "/json/version", timeout=2)
        return True
    except:
        pass

    chrome_data = Path.home() / "Library/Application Support/Google/Chrome"
    wrapper = Path.home() / ".chrome-debug"

    if not wrapper.exists() or not (wrapper / "Local State").exists():
        if wrapper.exists():
            import shutil
            shutil.rmtree(wrapper, ignore_errors=True)
        wrapper.mkdir(parents=True, exist_ok=True)
        for item in chrome_data.iterdir():
            link = wrapper / item.name
            if not link.exists():
                try:
                    os.symlink(item, link)
                except:
                    pass

    subprocess.Popen([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        f"--user-data-dir={wrapper}",
        "--profile-directory=Default",  # Change this if Chrome uses a different profile
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(15):
        import time
        time.sleep(1)
        try:
            import urllib.request
            urllib.request.urlopen(CDP_URL + "/json/version", timeout=2)
            return True
        except:
            pass

    return False


# ─── Direct API (no tabs) ───

def get_auth_cookies():
    """Grab auth cookies from Chrome's running session via CDP — no tabs opened."""
    if not ensure_chrome_debug():
        return None

    async def _get():
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            cookies = await context.cookies()
            await browser.close()
            return cookies

    all_cookies = asyncio.run(_get())
    return {c["name"]: c["value"] for c in all_cookies if "timeback" in c.get("domain", "")}


def make_cookie_header(cookies):
    """Build a Cookie header string from a dict."""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def api_headers(cookies):
    """Standard headers for TimeBack API calls."""
    return {
        "Content-Type": "application/json",
        "Cookie": make_cookie_header(cookies),
        "Origin": TIMEBACK_BASE,
        "Referer": f"{TIMEBACK_BASE}/app/learning-metrics",
    }


def resolve_student_id(name, cookies):
    """Look up a student's sourcedId by name. Caches the result."""
    if name in STUDENT_IDS:
        return STUDENT_IDS[name]

    url = f"{TIMEBACK_BASE}/_serverFn/src_features_learning-metrics_components_fast-student-search_actions_client_ts--fetchUsersByRole_createServerFn_handler?createServerFn"
    payload = {
        "data": {"roles": ["student"], "search": name, "limit": {"$undefined": 0}, "orgSourcedIds": []},
        "context": {},
    }

    resp = http_requests.post(url, json=payload, headers=api_headers(cookies), timeout=15)
    resp.raise_for_status()
    results = resp.json().get("result", [])

    # Find exact match
    for user in results:
        full_name = f"{user.get('givenName', '')} {user.get('familyName', '')}".strip()
        if full_name.lower() == name.lower():
            sid = user["sourcedId"]
            STUDENT_IDS[name] = sid
            save_student_ids()
            logger.info(f"Resolved '{name}' → {sid}")
            return sid

    # Fallback: first result
    if results:
        sid = results[0]["sourcedId"]
        STUDENT_IDS[name] = sid
        save_student_ids()
        logger.info(f"Resolved '{name}' → {sid} (first result)")
        return sid

    logger.error(f"Could not resolve student: {name}")
    return None


def fetch_activity_metrics(student_id, date_str, cookies):
    """Call getActivityMetrics API for a single student and single date."""
    # TimeBack expects UTC times for the timezone-adjusted day
    # For America/Los_Angeles (UTC-7 in PDT): day starts at 07:00 UTC, ends at 06:59:59.999 UTC next day
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # Use 7-hour offset (Pacific Time) — this matches what the frontend sends
    start_utc = dt.strftime("%Y-%m-%dT07:00:00.000Z")
    end_dt = dt + timedelta(days=1)
    end_utc = end_dt.strftime("%Y-%m-%dT06:59:59.999Z")

    url = f"{TIMEBACK_BASE}/_serverFn/src_features_learning-metrics_actions_getActivityMetrics_ts--getActivityMetrics_createServerFn_handler?createServerFn"
    payload = {
        "data": {
            "startDate": start_utc,
            "endDate": end_utc,
            "studentId": student_id,
            "timezone": TIMEZONE,
        },
        "context": {},
    }

    resp = http_requests.post(url, json=payload, headers=api_headers(cookies), timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", {}).get("data", {})


def process_api_metrics(student_name, metrics_data, date_str):
    """Convert raw API metrics into our dashboard format."""
    facts = metrics_data.get("facts", {}).get(date_str, {})

    subjects = []
    total_xp = 0
    total_minutes = 0
    total_correct = 0
    total_questions = 0

    for subject_name, subject_data in facts.items():
        activity = subject_data.get("activityMetrics", {})
        time_data = subject_data.get("timeSpentMetrics", {})

        xp = activity.get("xpEarned", 0)
        correct = activity.get("correctQuestions", 0)
        total_q = activity.get("totalQuestions", 0)
        mastered = activity.get("masteredUnits", 0)
        active_secs = time_data.get("activeSeconds", 0)
        minutes = math.ceil(active_secs / 60) if active_secs else 0
        accuracy = round((correct / total_q) * 100) if total_q > 0 else 0

        total_xp += xp
        total_minutes += minutes
        total_correct += correct
        total_questions += total_q

        subjects.append({
            "name": subject_name,
            "xp": round(xp),
            "accuracy": accuracy,
            "minutes": minutes,
            "mastered": mastered,
            "no_data": xp == 0 and minutes == 0 and accuracy == 0,
        })

    overall_accuracy = round((total_correct / total_questions) * 100) if total_questions > 0 else 0

    return {
        "name": student_name,
        "total_xp": round(total_xp),
        "overall_accuracy": overall_accuracy,
        "total_minutes": total_minutes,
        "subjects": subjects,
        "absent": total_xp == 0 and total_minutes == 0 and len(subjects) == 0,
    }


def fetch_day_via_api(date_str, cookies):
    """Fetch all students' data for a single date using direct API calls."""
    processed = []
    for name in STUDENTS:
        sid = resolve_student_id(name, cookies)
        if not sid:
            continue
        try:
            metrics = fetch_activity_metrics(sid, date_str, cookies)
            student_data = process_api_metrics(name, metrics, date_str)
            processed.append(student_data)
        except Exception as e:
            logger.error(f"API error for {name} on {date_str}: {e}")

    return processed


def scrape_single_api(date_str=None):
    """Fetch one date via direct API — no tabs."""
    if not STUDENTS:
        return {"error": "no_students", "message": "Add students first."}

    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    cookies = get_auth_cookies()

    # Use cache for past dates (backfills new students automatically)
    if date_str != today:
        cached = get_cached_day_complete(date_str, cookies)
        if cached:
            logger.info(f"Cache hit for {date_str}")
            result = {
                "students": cached,
                "date": date_str,
                "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
                "from_cache": True,
            }
            DATA_FILE.write_text(json.dumps(result, indent=2))
            return result

    if not cookies:
        return {"error": "chrome_error", "message": "Could not connect to Chrome to get auth cookies."}

    processed = fetch_day_via_api(date_str, cookies)

    if not processed:
        return {"error": "no_data", "message": "No data returned. Session may have expired — log into TimeBack in Chrome."}

    save_cached_day(date_str, processed)

    result = {
        "students": processed,
        "date": date_str,
        "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
    }

    DATA_FILE.write_text(json.dumps(result, indent=2))
    return result


def scrape_range_api(start_date, end_date, weekdays_only=True):
    """Fetch multiple dates via direct API — no tabs."""
    if not STUDENTS:
        return {"error": "no_students", "message": "Add students first."}

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        if not weekdays_only or current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    if not dates:
        return {"error": "no_dates", "message": "No weekdays in the selected range."}

    cookies = get_auth_cookies()

    # Split into cached vs needs-fetching
    days = []
    dates_to_fetch = []

    for date_str in dates:
        if date_str != today:
            cached = get_cached_day_complete(date_str, cookies)
            if cached:
                logger.info(f"Cache hit for {date_str}")
                days.append({
                    "date": date_str,
                    "day_name": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A"),
                    "students": cached,
                })
                continue
        dates_to_fetch.append(date_str)

    if dates_to_fetch:
        if not cookies:
            if not days:
                return {"error": "chrome_error", "message": "Could not connect to Chrome to get auth cookies."}
        else:
            for date_str in dates_to_fetch:
                processed = fetch_day_via_api(date_str, cookies)
                if processed:
                    save_cached_day(date_str, processed)
                    days.append({
                        "date": date_str,
                        "day_name": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A"),
                        "students": processed,
                    })

    days.sort(key=lambda d: d["date"])

    result = {
        "days": days,
        "start": start_date,
        "end": end_date,
        "cached_count": len(dates) - len(dates_to_fetch),
        "scraped_count": len(dates_to_fetch),
        "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
    }

    DATA_FILE.write_text(json.dumps(result, indent=2))
    return result


# ─── Routes ───

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/refresh", methods=["POST"])
def refresh():
    data = request.get_json() or {}
    date_str = data.get("date")
    start = data.get("start")
    end = data.get("end")
    weekdays = data.get("weekdays_only", True)

    try:
        if start and end and start != end:
            result = scrape_range_api(start, end, weekdays)
        else:
            result = scrape_single_api(date_str or start)
        return jsonify(result)
    except Exception as e:
        logger.exception("Refresh failed")
        return jsonify({"error": "scrape_failed", "message": str(e)}), 500


@app.route("/api/students", methods=["GET"])
def get_students():
    return jsonify({"students": STUDENTS})


@app.route("/api/students", methods=["POST"])
def update_students():
    global STUDENTS
    STUDENTS = request.get_json().get("students", [])
    save_students_file()
    return jsonify({"students": STUDENTS})


@app.route("/api/groups", methods=["GET"])
def get_groups():
    return jsonify({"groups": GROUPS})


@app.route("/api/groups", methods=["POST"])
def update_groups():
    global GROUPS
    GROUPS = request.get_json().get("groups", [])
    GROUPS_FILE.write_text(json.dumps(GROUPS, indent=2))
    return jsonify({"groups": GROUPS})


@app.route("/api/cached", methods=["GET"])
def cached_data():
    if DATA_FILE.exists():
        return jsonify(json.loads(DATA_FILE.read_text()))
    return jsonify(None)


@app.route("/api/search-students", methods=["POST"])
def search_students():
    """Search TimeBack for students by name."""
    query = (request.get_json() or {}).get("query", "").strip()
    if len(query) < 2:
        return jsonify({"results": []})

    cookies = get_auth_cookies()
    if not cookies:
        return jsonify({"results": [], "error": "No auth cookies available"})

    url = f"{TIMEBACK_BASE}/_serverFn/src_features_learning-metrics_components_fast-student-search_actions_client_ts--fetchUsersByRole_createServerFn_handler?createServerFn"
    payload = {
        "data": {"roles": ["student"], "search": query, "limit": {"$undefined": 0}, "orgSourcedIds": []},
        "context": {},
    }

    try:
        resp = http_requests.post(url, json=payload, headers=api_headers(cookies), timeout=15)
        resp.raise_for_status()
        users = resp.json().get("result", [])
        results = []
        for user in users:
            full_name = f"{user.get('givenName', '')} {user.get('familyName', '')}".strip()
            results.append({"name": full_name, "sourcedId": user.get("sourcedId", "")})
        return jsonify({"results": results})
    except Exception as e:
        logger.error(f"Student search failed: {e}")
        return jsonify({"results": [], "error": str(e)})


@app.route("/api/status", methods=["GET"])
def status():
    """Check if Chrome debug is reachable and TimeBack session is active."""
    try:
        import urllib.request
        urllib.request.urlopen(CDP_URL + "/json/version", timeout=2)
        chrome_ok = True
    except:
        chrome_ok = False

    cookies = None
    if chrome_ok:
        try:
            cookies = get_auth_cookies()
        except:
            pass

    return jsonify({
        "chrome": chrome_ok,
        "authenticated": bool(cookies),
    })


@app.route("/api/clear", methods=["POST"])
def clear_data():
    """Clear all cached data and student IDs for a fresh start."""
    global STUDENT_IDS
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(exist_ok=True)
    STUDENT_IDS = {}
    save_student_ids()
    if DATA_FILE.exists():
        DATA_FILE.write_text("{}")
    return jsonify({"success": True})


if __name__ == "__main__":
    ensure_chrome_debug()
    app.run(port=5051, debug=True)
