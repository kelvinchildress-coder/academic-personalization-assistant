/**
 * Phase 7 Part 4 — Aggregation layer (pure-functional).
 *
 * TypeScript port of src/digest_v2.py. Takes raw history snapshots and
 * produces per-student metrics, per-coach roll-ups, top-concern lists,
 * and trend clusters.
 *
 * This module is pure: no I/O, no fetch, no imports from githubData.
 * Pages call readRange(...) (Part 3) first, then pass the resulting
 * Snapshot[] into aggregateRange(...) here.
 *
 * Behavioral parity contract with src/digest_v2.py:
 *   - Same four concern categories (behind_multiple_days, deep_deficit,
 *     gap_not_closing, frequent_exceptions).
 *   - Same severity formula: recurrence_count * magnitude_z.
 *   - Same coach trend cluster threshold (N >= 2).
 *
 * The Python version is hardcoded to 5+5 day windows and N=5 top
 * concerns. This TS version takes those as options so the dashboard's
 * window selector can request larger ranges (Q7-6 default 30 days).
 *
 * TODO(future): cross-student magnitude_z normalization. Today
 * magnitude_z is computed within a student's own historical baseline
 * (z-score against that student's own median deficit). A coach-cohort
 * or roster-wide z-score would let us flag students who are unusually
 * behind RELATIVE to peers, not just relative to themselves.
 */

import type { Snapshot, StudentSnap } from "./types";

// ---------------------------------------------------------------------------
// Concern category constants. Match src/digest_v2.py exactly.
// ---------------------------------------------------------------------------
export const CONCERN_BEHIND_MULTIPLE_DAYS = "behind_multiple_days";
export const CONCERN_DEEP_DEFICIT = "deep_deficit";
export const CONCERN_GAP_NOT_CLOSING = "gap_not_closing";
export const CONCERN_FREQUENT_EXCEPTIONS = "frequent_exceptions";

export type ConcernCategory =
  | typeof CONCERN_BEHIND_MULTIPLE_DAYS
  | typeof CONCERN_DEEP_DEFICIT
  | typeof CONCERN_GAP_NOT_CLOSING
  | typeof CONCERN_FREQUENT_EXCEPTIONS;

// ---------------------------------------------------------------------------
// Default tuning. All overridable via AggregateOptions.
// ---------------------------------------------------------------------------
export const DEFAULT_CURRENT_WINDOW_DAYS = 5;
export const DEFAULT_PRIOR_WINDOW_DAYS = 5;
export const DEFAULT_TOP_CONCERNS_N = 5;
export const DEFAULT_COACH_TREND_THRESHOLD = 2;

/** Detection thresholds. Tuned to match digest_v2.py's behavior. */
export const DEFAULT_DETECTION = {
  /** behind_multiple_days: >= this many "behind" subject-days. */
  behindMultipleDaysMin: 2,
  /** deep_deficit: deficit_total >= this many XP. */
  deepDeficitMinXp: 100,
  /** frequent_exceptions: >= this many subject-days with a coach override. */
  frequentExceptionsMin: 3,
};

export interface AggregateOptions {
  currentDays?: number;
  priorDays?: number;
  topConcernsN?: number;
  coachTrendThreshold?: number;
  detection?: Partial<typeof DEFAULT_DETECTION>;
}

// ---------------------------------------------------------------------------
// Output types. Match the digest_v2 dataclasses field-for-field.
// ---------------------------------------------------------------------------
export interface StudentMetrics {
  name: string;
  coach: string;
  daysPresent: number;
  targetTotal: number;
  actualTotal: number;
  deficitTotal: number;
  daysBehind: number;
  exceptionsActive: number;
  priorDeficitTotal: number | null;
  deficitDelta: number | null;
  concerns: ConcernCategory[];
  /** severity = recurrence_count * magnitude_z; 0 if no concerns. */
  severity: number;
}

export interface CoachRollup {
  name: string;
  nStudents: number;
  studentsBehind: number;
  avgDeficitPerStudent: number;
  /** category -> [student names]. Only entries with >= threshold are kept. */
  trendClusters: Record<string, string[]>;
}

export interface DigestPayload {
  today: string; // ISO YYYY-MM-DD
  currentWindow: [string, string]; // [startIso, endIso] inclusive
  priorWindow: [string, string] | null;
  perStudent: Record<string, StudentMetrics>;
  perCoach: Record<string, CoachRollup>;
  topConcerns: StudentMetrics[];
  coachTrendClusters: Array<[string, string, string[]]>; // [coach, category, students]
  daysInCurrentWindow: number;
  daysInPriorWindow: number;
}

// ---------------------------------------------------------------------------
// ISO date arithmetic. String-only; no Date object, no timezones.
// ---------------------------------------------------------------------------
const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;

function assertIso(d: string): void {
  if (!ISO_RE.test(d)) {
    throw new Error(`Invalid ISO date: ${d}`);
  }
}

/** Subtract `n` days from an ISO date string. Pure string arithmetic via Date. */
function isoMinusDays(iso: string, n: number): string {
  assertIso(iso);
  // We use Date here only as a calendar calculator; no timezone reliance
  // because we always go through UTC and serialize back to YYYY-MM-DD.
  const t = Date.UTC(
    parseInt(iso.slice(0, 4), 10),
    parseInt(iso.slice(5, 7), 10) - 1,
    parseInt(iso.slice(8, 10), 10),
  );
  const d = new Date(t - n * 86_400_000);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

// ---------------------------------------------------------------------------
// Statistics helpers (no external deps).
// ---------------------------------------------------------------------------
function median(xs: number[]): number {
  if (xs.length === 0) return 0;
  const sorted = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function stdev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  const variance =
    xs.reduce((acc, v) => acc + (v - m) ** 2, 0) / (xs.length - 1);
  return Math.sqrt(variance);
}

// ---------------------------------------------------------------------------
// Per-student window aggregation
// ---------------------------------------------------------------------------
const COACH_OVERRIDE_TIERS = new Set(["coach_xp_override", "coach_test_by"]);

interface DailyAgg {
  daysPresent: number;
  targetTotal: number;
  actualTotal: number;
  deficitTotal: number;
  daysBehind: number;
  exceptionsActive: number;
  /** Per-day deficit values (used for magnitude_z calculation). */
  dailyDeficits: number[];
}

function emptyAgg(): DailyAgg {
  return {
    daysPresent: 0,
    targetTotal: 0,
    actualTotal: 0,
    deficitTotal: 0,
    daysBehind: 0,
    exceptionsActive: 0,
    dailyDeficits: [],
  };
}

function aggForStudentInWindow(
  studentName: string,
  snapshots: Snapshot[],
): DailyAgg {
  const agg = emptyAgg();
  for (const snap of snapshots) {
    const stu = snap.students.find((s) => s.name === studentName);
    if (!stu) continue;
    agg.daysPresent += 1;
    let dayDeficit = 0;
    for (const subj of stu.subjects) {
      agg.targetTotal += subj.target_xp;
      agg.actualTotal += subj.actual_xp;
      const subjDeficit = Math.max(subj.target_xp - subj.actual_xp, 0);
      agg.deficitTotal += subjDeficit;
      dayDeficit += subjDeficit;
      if (subj.status === "behind") agg.daysBehind += 1;
      if (COACH_OVERRIDE_TIERS.has(subj.tier)) agg.exceptionsActive += 1;
    }
    agg.dailyDeficits.push(dayDeficit);
  }
  return agg;
}

// ---------------------------------------------------------------------------
// Concern detection
// ---------------------------------------------------------------------------
function detectConcerns(
  current: DailyAgg,
  prior: DailyAgg | null,
  detection: typeof DEFAULT_DETECTION,
): ConcernCategory[] {
  const out: ConcernCategory[] = [];

  if (current.daysBehind >= detection.behindMultipleDaysMin) {
    out.push(CONCERN_BEHIND_MULTIPLE_DAYS);
  }
  if (current.deficitTotal >= detection.deepDeficitMinXp) {
    out.push(CONCERN_DEEP_DEFICIT);
  }
  if (
    prior !== null &&
    prior.deficitTotal > 0 &&
    current.deficitTotal - prior.deficitTotal >= 0
  ) {
    out.push(CONCERN_GAP_NOT_CLOSING);
  }
  if (current.exceptionsActive >= detection.frequentExceptionsMin) {
    out.push(CONCERN_FREQUENT_EXCEPTIONS);
  }

  return out;
}

/**
 * Severity = recurrence_count * magnitude_z.
 *
 * recurrence_count: number of subject-days with status="behind" in
 *   the current window (uses daysBehind from DailyAgg).
 *
 * magnitude_z: z-score of current deficit_total against the student's
 *   own daily deficits. Floors at 0.5 so we never multiply by zero
 *   when the student's deficit is exactly at their median (avoids
 *   making severity collapse to 0 when the concern category itself
 *   says they're in trouble).
 */
function severityFor(current: DailyAgg, concerns: ConcernCategory[]): number {
  if (concerns.length === 0) return 0;
  if (current.dailyDeficits.length === 0) return 0;
  const med = median(current.dailyDeficits);
  const sd = stdev(current.dailyDeficits);
  let z: number;
  if (sd === 0) {
    z = 1.0; // flat: can't compute, but concern exists; default to 1.
  } else {
    z = (current.deficitTotal / current.dailyDeficits.length - med) / sd;
  }
  const magnitude = Math.max(z, 0.5);
  const recurrence = current.daysBehind;
  return recurrence * magnitude;
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------
/**
 * Build a DigestPayload from a date-ordered list of snapshots.
 *
 * `today` defines the right edge of the current window. The current
 * window is [today - currentDays + 1, today]. The prior window is
 * [today - currentDays - priorDays + 1, today - currentDays].
 *
 * Snapshots outside both windows are ignored.
 */
export function aggregateRange(
  snapshots: Snapshot[],
  today: string,
  options: AggregateOptions = {},
): DigestPayload {
  assertIso(today);

  const currentDays = options.currentDays ?? DEFAULT_CURRENT_WINDOW_DAYS;
  const priorDays = options.priorDays ?? DEFAULT_PRIOR_WINDOW_DAYS;
  const topN = options.topConcernsN ?? DEFAULT_TOP_CONCERNS_N;
  const trendThreshold =
    options.coachTrendThreshold ?? DEFAULT_COACH_TREND_THRESHOLD;
  const detection = { ...DEFAULT_DETECTION, ...(options.detection ?? {}) };

  const currentEnd = today;
  const currentStart = isoMinusDays(today, currentDays - 1);
  const priorEnd = isoMinusDays(today, currentDays);
  const priorStart = isoMinusDays(today, currentDays + priorDays - 1);

  const currentSnaps = snapshots.filter(
    (s) => s.date >= currentStart && s.date <= currentEnd,
  );
  const priorSnaps = snapshots.filter(
    (s) => s.date >= priorStart && s.date <= priorEnd,
  );

  // Collect all student/coach pairs we've ever seen in either window.
  const studentCoach = new Map<string, string>();
  const allSnaps = [...currentSnaps, ...priorSnaps];
  for (const snap of allSnaps) {
    for (const stu of snap.students) {
      if (!studentCoach.has(stu.name)) {
        studentCoach.set(stu.name, stu.coach);
      }
    }
  }

  // Per-student metrics.
  const perStudent: Record<string, StudentMetrics> = {};
  for (const [name, coach] of studentCoach.entries()) {
    const cur = aggForStudentInWindow(name, currentSnaps);
    const pri =
      priorSnaps.length > 0 ? aggForStudentInWindow(name, priorSnaps) : null;
    const concerns = detectConcerns(cur, pri, detection);
    const severity = severityFor(cur, concerns);
    perStudent[name] = {
      name,
      coach,
      daysPresent: cur.daysPresent,
      targetTotal: cur.targetTotal,
      actualTotal: cur.actualTotal,
      deficitTotal: cur.deficitTotal,
      daysBehind: cur.daysBehind,
      exceptionsActive: cur.exceptionsActive,
      priorDeficitTotal: pri ? pri.deficitTotal : null,
      deficitDelta: pri ? cur.deficitTotal - pri.deficitTotal : null,
      concerns,
      severity,
    };
  }

  // Per-coach roll-up.
  const perCoach: Record<string, CoachRollup> = {};
  for (const s of Object.values(perStudent)) {
    const coach = (perCoach[s.coach] ??= {
      name: s.coach,
      nStudents: 0,
      studentsBehind: 0,
      avgDeficitPerStudent: 0,
      trendClusters: {},
    });
    coach.nStudents += 1;
    if (s.daysBehind > 0) coach.studentsBehind += 1;
  }
  for (const coach of Object.values(perCoach)) {
    const coachStudents = Object.values(perStudent).filter(
      (x) => x.coach === coach.name,
    );
    const totalDeficit = coachStudents.reduce(
      (acc, x) => acc + x.deficitTotal,
      0,
    );
    coach.avgDeficitPerStudent =
      coach.nStudents > 0 ? totalDeficit / coach.nStudents : 0;

    // Trend clusters: any concern shared by >= threshold students under this coach.
    const buckets: Record<string, string[]> = {};
    for (const s of coachStudents) {
      for (const c of s.concerns) {
        (buckets[c] ??= []).push(s.name);
      }
    }
    for (const [cat, names] of Object.entries(buckets)) {
      if (names.length >= trendThreshold) {
        coach.trendClusters[cat] = names.sort();
      }
    }
  }

  // Top concerns: students with at least one concern, sorted by severity desc.
  const topConcerns = Object.values(perStudent)
    .filter((s) => s.concerns.length > 0)
    .sort((a, b) => b.severity - a.severity || a.name.localeCompare(b.name))
    .slice(0, topN);

  // Coach trend cluster flat list, sorted for stable rendering.
  const coachTrendClusters: Array<[string, string, string[]]> = [];
  for (const coach of Object.values(perCoach)) {
    for (const [cat, names] of Object.entries(coach.trendClusters)) {
      coachTrendClusters.push([coach.name, cat, names]);
    }
  }
  coachTrendClusters.sort((a, b) =>
    a[0] === b[0] ? a[1].localeCompare(b[1]) : a[0].localeCompare(b[0]),
  );

  return {
    today,
    currentWindow: [currentStart, currentEnd],
    priorWindow: priorSnaps.length > 0 ? [priorStart, priorEnd] : null,
    perStudent,
    perCoach,
    topConcerns,
    coachTrendClusters,
    daysInCurrentWindow: currentSnaps.length,
    daysInPriorWindow: priorSnaps.length,
  };
}
