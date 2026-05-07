/**
 * docs/export-day.js
 * Academic Personalization Assistant — TimeBack day exporter
 *
 * Companion bookmarklet to docs/timeback-dashboard.js (LOCKED, do not modify).
 * Reads the rendered TimeBack Dashboard overlay and exports a single day's
 * results as a clipboard-ready JSON envelope matching data/latest.json schema.
 *
 * Usage:
 *   1. Click the existing TimeBack Dashboard bookmarklet first (loads/renders data).
 *   2. Wait for the day-tabs to populate with real numbers.
 *   3. Click the EXPORT DAY bookmarklet (this file, minified).
 *   4. Paste clipboard contents into data/latest.json on GitHub.
 *
 * Mode auto-selection (Central Time):
 *   - Before 08:00 CT on a school day  -> "morning"  -> exports MOST RECENT COMPLETED school day
 *   - 08:00 CT or later on a school day -> "live"    -> exports TODAY (in-progress)
 *   - Weekend or known holiday          -> "morning" -> exports MOST RECENT COMPLETED school day
 *   - User has manually clicked a day-tab BEFORE running the bookmarklet
 *     (i.e., active day != heuristic day) -> respect the manual choice ("manual" mode).
 *
 * Output envelope:
 *   {
 *     "date":      "YYYY-MM-DD",
 *     "mode":      "morning" | "live" | "manual",
 *     "students":  [ {name,total_xp,overall_accuracy,total_minutes,absent,subjects:[...]}, ... ],
 *     "timestamp": "ISO 8601",
 *     "source":    "bookmarklet:export-day.js@v1"
 *   }
 *
 * Each subject row:
 *   { name, xp, accuracy, minutes, mastered, no_data, has_test }
 *
 * Schema is a drop-in for src/report_builder.py:to_daily_results().
 *
 * IMPORTANT: This file is bookmarklet source. The actual one-line bookmarklet
 * payload is at the BOTTOM of this file (search for "BOOKMARKLET PAYLOAD").
 */

(function exportDayMain() {
  'use strict';

  // ---------- Calendar A holiday & no-school table (kept small; full source in src/calendar_tsa.py) ----------
  // Used only by the bookmarklet's "morning vs. live" heuristic.
  // Format: ISO date strings (YYYY-MM-DD) for non-school days.
  // Source of truth lives server-side; this is a redundant client copy.
  var NO_SCHOOL_DAYS = [
    // SY25-26 remaining
    '2026-05-25', // Memorial Day
    // After 2026-06-05 the school year ends; everything until 2026-08-12 is summer break.
    // SY26-27
    '2026-09-07',                                         // Labor Day
    '2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16', // Fall break
    '2026-11-23','2026-11-24','2026-11-25','2026-11-26','2026-11-27', // Thanksgiving
    '2026-12-21','2026-12-22','2026-12-23','2026-12-24','2026-12-25',
    '2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01', // Winter break
    '2027-01-18',                                         // MLK
    '2027-02-22','2027-02-23','2027-02-24','2027-02-25','2027-02-26', // Mid-winter break
    '2027-04-19','2027-04-20','2027-04-21','2027-04-22','2027-04-23'  // Spring break
  ];
  var SY_LAST_DAY = '2026-06-05';     // last instructional day of SY25-26
  var SY_NEXT_FIRST_DAY = '2026-08-12'; // first day of SY26-27

  // ---------- Time helpers (Central Time) ----------
  function nowCT() {
    // Convert the user's local clock to America/Chicago. Bookmarklet runs in the
    // browser, so we use Intl to fetch parts in Chicago tz.
    var fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Chicago',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    });
    var parts = {};
    fmt.formatToParts(new Date()).forEach(function (p) { parts[p.type] = p.value; });
    return {
      iso: parts.year + '-' + parts.month + '-' + parts.day,
      hour: parseInt(parts.hour, 10),
      // Day of week: 0 = Sunday ... 6 = Saturday. Compute from the iso date safely.
      dow: (function () {
        var d = new Date(parts.year + '-' + parts.month + '-' + parts.day + 'T12:00:00Z');
        return d.getUTCDay();
      })()
    };
  }

  function isoAddDays(iso, n) {
    var d = new Date(iso + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.getUTCFullYear() + '-' +
      String(d.getUTCMonth() + 1).padStart(2, '0') + '-' +
      String(d.getUTCDate()).padStart(2, '0');
  }

  function isSchoolDay(iso) {
    var d = new Date(iso + 'T12:00:00Z');
    var dow = d.getUTCDay();
    if (dow === 0 || dow === 6) return false;            // Sat/Sun
    if (NO_SCHOOL_DAYS.indexOf(iso) !== -1) return false; // listed holiday
    // Summer-break window between SY25-26 last day and SY26-27 first day.
    if (iso > SY_LAST_DAY && iso < SY_NEXT_FIRST_DAY) return false;
    return true;
  }

  function lastCompletedSchoolDay(fromIso) {
    var probe = isoAddDays(fromIso, -1);
    for (var i = 0; i < 30; i++) {
      if (isSchoolDay(probe)) return probe;
      probe = isoAddDays(probe, -1);
    }
    return fromIso; // fallback (should never happen)
  }

  function pickHeuristicDate() {
    var t = nowCT();
    var todayIsSchool = isSchoolDay(t.iso);
    if (todayIsSchool && t.hour >= 8) return { date: t.iso, mode: 'live' };
    return { date: lastCompletedSchoolDay(t.iso), mode: 'morning' };
  }

  // ---------- DOM helpers ----------
  function num(s) {
    if (s === null || s === undefined) return 0;
    var m = String(s).replace(/,/g, '').match(/-?[0-9]+(\.[0-9]+)?/);
    return m ? parseFloat(m[0]) : 0;
  }

  function shortDateToIso(text) {
    // Expects strings like "May 4, 2026" or "May 4, 2026 at 11:09 AM".
    if (!text) return null;
    var m = text.match(/([A-Za-z]+)\s+([0-9]{1,2}),\s*([0-9]{4})/);
    if (!m) return null;
    var months = { Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12 };
    var k = m[1].slice(0, 3);
    var mo = months[k];
    if (!mo) return null;
    return m[3] + '-' + String(mo).padStart(2, '0') + '-' + String(parseInt(m[2], 10)).padStart(2, '0');
  }

  function findDayTabByDate(targetIso) {
    var tabs = Array.from(document.querySelectorAll('#tb-dash-overlay .day-tab'));
    if (!tabs.length) return null;
    // The day-tabs do not carry explicit dates; we infer them from the
    // section-header date range ("May 4, 2026 – May 10, 2026") + tab order
    // (Mon..Sun). The active tab tells us which day is currently rendered;
    // we map that anchor into a Mon-of-week and offset by tab index.
    var hdr = document.querySelector('#tb-dash-overlay .section-header .section-date');
    var hdrText = hdr ? hdr.textContent : '';
    var rangeMatch = hdrText.match(/([A-Za-z]+\s+[0-9]{1,2},\s*[0-9]{4})/g);
    if (!rangeMatch || !rangeMatch.length) return null;
    var weekStart = shortDateToIso(rangeMatch[0]); // Monday of displayed week
    if (!weekStart) return null;
    for (var i = 0; i < tabs.length; i++) {
      var tabDate = isoAddDays(weekStart, i);
      if (tabDate === targetIso) return { tab: tabs[i], iso: tabDate, index: i };
    }
    return null;
  }

  function activeDayIso() {
    var tabs = Array.from(document.querySelectorAll('#tb-dash-overlay .day-tab'));
    if (!tabs.length) return null;
    var activeIdx = tabs.findIndex(function (t) { return t.classList.contains('active'); });
    if (activeIdx < 0) return null;
    var hdr = document.querySelector('#tb-dash-overlay .section-header .section-date');
    var rangeMatch = hdr && hdr.textContent ? hdr.textContent.match(/([A-Za-z]+\s+[0-9]{1,2},\s*[0-9]{4})/g) : null;
    if (!rangeMatch || !rangeMatch.length) return null;
    var weekStart = shortDateToIso(rangeMatch[0]);
    return weekStart ? isoAddDays(weekStart, activeIdx) : null;
  }

  function clickDayTab(tab) {
    // The bookmarklet attaches an inline onclick="switchDay(N)"; calling .click()
    // routes through that handler and re-renders the student cards.
    if (tab && typeof tab.click === 'function') tab.click();
  }

  // ---------- Per-day extractor ----------
  function extractStudents() {
    var mc = document.getElementById('mainContent');
    if (!mc) return { date: null, students: [] };
    var dateText = '';
    var hdrs = mc.querySelectorAll('.section-header');
    for (var h = 0; h < hdrs.length; h++) {
      if (/Student Breakdown/i.test(hdrs[h].textContent)) {
        var sd = hdrs[h].querySelector('.section-date');
        if (sd) dateText = sd.textContent.trim();
        break;
      }
    }
    var iso = shortDateToIso(dateText);
    var cards = Array.from(mc.querySelectorAll('.student-card'));
    var students = cards.map(function (card) {
      var name = ((card.querySelector('.student-name') || {}).textContent || '').trim();
      var absent = card.classList.contains('flag-absent');
      var badges = Array.from(card.querySelectorAll('.student-badges .badge'));
      var total_xp = 0, overall_accuracy = 0, total_minutes = 0;
      badges.forEach(function (b) {
        var t = b.textContent.trim();
        if (/XP/i.test(t)) total_xp = num(t);
        else if (t.indexOf('min') !== -1) total_minutes = num(t);
        else if (t.indexOf('%') !== -1) overall_accuracy = num(t);
      });
      var subjects = Array.from(card.querySelectorAll('.subject-row')).map(function (r) {
        var sname = ((r.querySelector('.subject-name') || {}).textContent || '').trim();
        var metrics = Array.from(r.querySelectorAll('.metric'));
        var xp = 0, acc = 0, minutes = 0;
        metrics.forEach(function (m) {
          var unitEl = m.querySelector('.metric-unit');
          var unit = unitEl ? unitEl.textContent.trim() : '';
          var valEl = m.querySelector('.metric-value');
          var v = valEl ? num(valEl.textContent) : 0;
          var valTxt = valEl ? valEl.textContent : '';
          if (unit === 'XP') xp = v;
          else if (unit === 'min') minutes = v;
          else if (valTxt.indexOf('%') !== -1) acc = v;
        });
        var rowText = r.textContent;
        var masteredMatch = rowText.match(/([0-9]+)\s*mastered/i);
        return {
          name: sname,
          xp: xp,
          accuracy: acc,
          minutes: minutes,
          mastered: masteredMatch ? parseInt(masteredMatch[1], 10) : 0,
          no_data: (xp === 0 && acc === 0 && minutes === 0),
          has_test: /test/i.test(rowText)
        };
      });
      return {
        name: name,
        total_xp: total_xp,
        overall_accuracy: overall_accuracy,
        total_minutes: total_minutes,
        absent: absent,
        subjects: subjects
      };
    });
    return { date: iso, students: students };
  }

  // ---------- Toast ----------
  function toast(msg, isErr) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = [
      'position:fixed','z-index:2147483647','left:50%','top:24px',
      'transform:translateX(-50%)','padding:12px 18px',
      'border-radius:8px','font:600 13px/1.4 -apple-system,Segoe UI,sans-serif',
      'color:#fff','box-shadow:0 8px 24px rgba(0,0,0,.25)',
      'background:' + (isErr ? '#c0392b' : '#2241c0')
    ].join(';');
    document.body.appendChild(t);
    setTimeout(function () { try { t.remove(); } catch (e) {} }, 4000);
  }

  // ---------- Clipboard ----------
  function writeClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      }
    } catch (e) { /* fall through */ }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) {}
      ta.remove();
      ok ? resolve() : reject(new Error('execCommand failed'));
    });
  }

  // ---------- Main flow ----------
  function ensureOverlayOpen() {
    var o = document.getElementById('tb-dash-overlay');
    if (!o) return false;
    // Some upstream versions hide the overlay until the original bookmarklet
    // is clicked. If functions exist on window we can re-trigger the open path.
    return true;
  }

  function pickTargetDate() {
    var heuristic = pickHeuristicDate();
    var active = activeDayIso();
    if (active && active !== heuristic.date) {
      // User has chosen a specific day already — respect it.
      return { date: active, mode: 'manual' };
    }
    return heuristic;
  }

  async function run() {
    if (!ensureOverlayOpen()) {
      toast('TimeBack Dashboard not loaded. Click the TB bookmarklet first.', true);
      return;
    }
    if (typeof window.pullData !== 'function') {
      toast('TimeBack Dashboard scripts not detected on this tab.', true);
      return;
    }

    var target = pickTargetDate();
    var match = findDayTabByDate(target.date);
    if (!match) {
      toast('Day tab for ' + target.date + ' not found in current week. Click "Pull Data" first.', true);
      return;
    }

    // Switch to the right day tab if needed, then wait a tick for re-render.
    if (!match.tab.classList.contains('active')) {
      clickDayTab(match.tab);
      await new Promise(function (r) { setTimeout(r, 350); });
    }

    var snap = extractStudents();
    if (!snap.date || !snap.students.length) {
      toast('No student data extracted. Has the dashboard finished loading?', true);
      return;
    }
    if (snap.date !== target.date) {
      // Defensive: the section header date didn't match what we asked for.
      // Still ship what was rendered, but note the discrepancy in the mode.
      target.mode = target.mode + ':date-mismatch';
    }

    var envelope = {
      date: snap.date,
      mode: target.mode,
      students: snap.students,
      timestamp: new Date().toISOString(),
      source: 'bookmarklet:export-day.js@v1'
    };

    var sumXP = snap.students.reduce(function (a, s) { return a + (s.total_xp || 0); }, 0);
    var absentN = snap.students.filter(function (s) { return s.absent; }).length;

    var json = JSON.stringify(envelope, null, 2);
    writeClipboard(json).then(function () {
      toast('Exported ' + snap.date + ' (' + target.mode + ') · ' +
        snap.students.length + ' students · ' + sumXP + ' XP · ' +
        absentN + ' absent · copied to clipboard');
    }).catch(function (e) {
      toast('Copy failed: ' + e.message + ' — JSON in console.', true);
      console.log('--- BEGIN export-day.js JSON ---');
      console.log(json);
      console.log('--- END export-day.js JSON ---');
    });
  }

  // Expose for test injection / debugging.
  window.__tsaExportDay = run;

  // Auto-run on bookmarklet click.
  run();
})();

/* =========================================================================
 * BOOKMARKLET PAYLOAD (one-line, paste this as a Chrome bookmark URL)
 * Save the URL below as a bookmark named "Export TimeBack Day". When clicked,
 * it loads this file from raw.githubusercontent.com and executes immediately.
 *
 * javascript:(function(){var s=document.createElement('script');s.src='https://raw.githubusercontent.com/kelvinchildress-coder/academic-personalization-assistant/main/docs/export-day.js?_t='+Date.now();document.head.appendChild(s);})();
 *
 * Note: GitHub raw URLs serve JS as text/plain by default. Most browsers still
 * execute it. If your browser refuses, use jsDelivr instead:
 *
 * javascript:(function(){var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/gh/kelvinchildress-coder/academic-personalization-assistant@main/docs/export-day.js?_t='+Date.now();document.head.appendChild(s);})();
 * ========================================================================= */
