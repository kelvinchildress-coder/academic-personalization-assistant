/**
 * Phase 6 — Ask palette compute layer.
 *
 * Pure functions. No I/O, no fetch, no React. Caller (the /ask page)
 * resolves the window, fetches snapshots via readRange, then calls
 * runAsk(...) here with the result.
 *
 * Every function honors `coachFilter`: when provided, only students
 * whose StudentSnap.coach matches are included in computation and in
 * the returned scope's nStudentsInScope. Head coach passes null to see
 * all students.
 *
 * The palette is locked at 12 kinds. Adding a 13th means: extend AskKind
 * + AskParams + AskAnswer in types.ts, add a compute<Kind> function
 * below, and add it to the runAsk switch.
 */

import type {
  AskAnswer,
  AskKind,
  AskParams,
  AskRowConcern,
  AskRowDeficitChange,
  AskRowNoActivity,
  AskRowStudentXp,
  AskRowSubjectRoster,
  AskRowSubjectStudent,
  AskRowCleanWindow,
  AskScope,
  Snapshot,
} from "./types";
import {
  aggregateRange,
  CONCERN_BEHIND_MULTIPLE_DAYS,
  CONCERN_DEEP_DEFICIT,
  CONCERN_FREQUENT_EXCEPTIONS,
  CONCERN_GAP_NOT_CLOSING,
  type ConcernCategory,
  type StudentMetrics,
} from "./aggregate";
import { rollupSubjectTargets } from "./subjectTargets";

const DEFAULT_TOP_N = 10;
const MAX_TOP_N = 50;

export interface RunAskInput {
  params: AskParams;
  currentSnaps: Snapshot[];
  priorSnaps: Snapshot[];
  today: string; // ISO; right edge of current window
  currentStart: string; // ISO; left edge of current window
  currentEnd: string; // = today
  priorStart: string | null;
  priorEnd: string | null;
  windowLabel: string;
  /** When non-null, restrict computation to students with this coach email. */
  coachFilter: string | null;
  /**
   * Roster lookup so we can map student display name → coach email.
   * Used only when coachFilter is non-null. Keys are student names as
   * they appear in StudentSnap.name; values are the coach's email.
   * If a student is in snapshots but not in this map, they are
   * excluded from coach-scoped views (defensive default).
   */
  studentNameToCoachEmail: Map<string, string>;
}

/** Single entry point. Dispatches to per-kind compute. */
export function runAsk(input: RunAskInput): AskAnswer {
  switch (input.params.kind) {
    case "top_xp":
      return computeTopXp(input, input.params.n);
    case "bottom_xp":
      return computeBottomXp(input, input.params.n);
    case "deficit_increase":
      return computeDeficitChange(input, "increase", input.params.n);
    case "deficit_decrease":
      return computeDeficitChange(input, "decrease", input.params.n);
    case "concern_behind_multiple_days":
      return computeConcern(input, CONCERN_BEHIND_MULTIPLE_DAYS);
    case "concern_deep_deficit":
      return computeConcern(input, CONCERN_DEEP_DEFICIT);
    case "concern_gap_not_closing":
      return computeConcern(input, CONCERN_GAP_NOT_CLOSING);
    case "concern_frequent_exceptions":
      return computeConcern(input, CONCERN_FREQUENT_EXCEPTIONS);
    case "no_activity":
      return computeNoActivity(input);
    case "student_subject_breakdown":
      return computeStudentSubject(input, input.params.studentName);
    case "roster_subject_mix":
      return computeRosterSubjectMix(input);
    case "clean_window":
      return computeCleanWindow(input);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clampN(n: number | undefined): number {
  const v = n ?? DEFAULT_TOP_N;
  if (!Number.isFinite(v)) return DEFAULT_TOP_N;
  return Math.max(1, Math.min(MAX_TOP_N, Math.floor(v)));
}

function scopeFor(input: RunAskInput, nInScope: number): AskScope {
  return {
    windowLabel: input.windowLabel,
    currentStart: input.currentStart,
    currentEnd: input.currentEnd,
    priorStart: input.priorStart,
    priorEnd: input.priorEnd,
    coachFilter: input.coachFilter,
    nStudentsInScope: nInScope,
  };
}

/** Decide whether a student is in scope for the current coach filter. */
function inScope(
  studentName: string,
  _studentCoachInSnapshot: string,
  input: RunAskInput,
): boolean {
  if (input.coachFilter === null) return true;
  // Prefer canonical roster mapping; fall back to no-match if unmapped.
  const mappedEmail = input.studentNameToCoachEmail.get(studentName);
  if (mappedEmail !== undefined) {
    return mappedEmail === input.coachFilter;
  }
  // No mapping → exclude (defensive; coach views must not leak unmapped students).
  return false;
}

function buildPerStudentScoped(input: RunAskInput): Record<string, StudentMetrics> {
  // Run aggregateRange across the combined snapshot list to get prior deltas.
  const allSnaps = [...input.priorSnaps, ...input.currentSnaps];
  const digest = aggregateRange(allSnaps, input.today, {
    currentDays: input.currentSnaps.length || 1,
    priorDays: input.priorSnaps.length || 0,
  });
  const out: Record<string, StudentMetrics> = {};
  for (const m of Object.values(digest.perStudent)) {
    if (!inScope(m.name, m.coach, input)) continue;
    out[m.name] = m;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Compute functions
// ---------------------------------------------------------------------------

function computeTopXp(input: RunAskInput, n: number | undefined): AskAnswer {
  const per = buildPerStudentScoped(input);
  const rows: AskRowStudentXp[] = Object.values(per)
    .sort((a, b) => b.actualTotal - a.actualTotal || a.name.localeCompare(b.name))
    .slice(0, clampN(n))
    .map((m, i) => ({
      rank: i + 1,
      studentName: m.name,
      coach: m.coach,
      actualXp: m.actualTotal,
      targetXp: m.targetTotal,
      deficit: m.deficitTotal,
      daysPresent: m.daysPresent,
    }));
  return { kind: "top_xp", scope: scopeFor(input, Object.keys(per).length), rows };
}

function computeBottomXp(input: RunAskInput, n: number | undefined): AskAnswer {
  const per = buildPerStudentScoped(input);
  const rows: AskRowStudentXp[] = Object.values(per)
    .filter((m) => m.daysPresent > 0)
    .sort((a, b) => a.actualTotal - b.actualTotal || a.name.localeCompare(b.name))
    .slice(0, clampN(n))
    .map((m, i) => ({
      rank: i + 1,
      studentName: m.name,
      coach: m.coach,
      actualXp: m.actualTotal,
      targetXp: m.targetTotal,
      deficit: m.deficitTotal,
      daysPresent: m.daysPresent,
    }));
  return { kind: "bottom_xp", scope: scopeFor(input, Object.keys(per).length), rows };
}

function computeDeficitChange(
  input: RunAskInput,
  direction: "increase" | "decrease",
  n: number | undefined,
): AskAnswer {
  const per = buildPerStudentScoped(input);
  const eligible = Object.values(per).filter((m) => m.deficitDelta !== null);
  const sorted =
    direction === "increase"
      ? eligible.sort(
          (a, b) =>
            (b.deficitDelta ?? 0) - (a.deficitDelta ?? 0) ||
            a.name.localeCompare(b.name),
        )
      : eligible.sort(
          (a, b) =>
            (a.deficitDelta ?? 0) - (b.deficitDelta ?? 0) ||
            a.name.localeCompare(b.name),
        );
  const rows: AskRowDeficitChange[] = sorted.slice(0, clampN(n)).map((m, i) => ({
    rank: i + 1,
    studentName: m.name,
    coach: m.coach,
    currentDeficit: m.deficitTotal,
    priorDeficit: m.priorDeficitTotal ?? 0,
    delta: m.deficitDelta ?? 0,
  }));
  return {
    kind: direction === "increase" ? "deficit_increase" : "deficit_decrease",
    scope: scopeFor(input, Object.keys(per).length),
    rows,
  };
}

function computeConcern(
  input: RunAskInput,
  concern: ConcernCategory,
): AskAnswer {
  const per = buildPerStudentScoped(input);
  const rows: AskRowConcern[] = Object.values(per)
    .filter((m) => m.concerns.includes(concern))
    .sort((a, b) => b.severity - a.severity || a.name.localeCompare(b.name))
    .map((m) => ({
      studentName: m.name,
      coach: m.coach,
      daysBehind: m.daysBehind,
      deficit: m.deficitTotal,
      severity: m.severity,
    }));
const kindMap: Record<
    ConcernCategory,
    | "concern_behind_multiple_days"
    | "concern_deep_deficit"
    | "concern_gap_not_closing"
    | "concern_frequent_exceptions"
  > = {
    behind_multiple_days: "concern_behind_multiple_days",
    deep_deficit: "concern_deep_deficit",
    gap_not_closing: "concern_gap_not_closing",
    frequent_exceptions: "concern_frequent_exceptions",
  };
  return {
    kind: kindMap[concern],
    scope: scopeFor(input, Object.keys(per).length),
    rows,
  };
}

function computeNoActivity(input: RunAskInput): AskAnswer {
  const per = buildPerStudentScoped(input);
  const rows: AskRowNoActivity[] = Object.values(per)
    .filter((m) => m.daysPresent === 0)
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((m) => ({
      studentName: m.name,
      coach: m.coach,
      daysPresent: m.daysPresent,
    }));
  return {
    kind: "no_activity",
    scope: scopeFor(input, Object.keys(per).length),
    rows,
  };
}

function computeStudentSubject(
  input: RunAskInput,
  studentName: string,
): AskAnswer {
  // Confirm student is in scope before exposing subject-level data.
  let coach = "";
  let found = false;
  for (const day of input.currentSnaps) {
    const s = day.students.find((x) => x.name === studentName);
    if (s) {
      coach = s.coach;
      found = true;
      break;
    }
  }
  if (!found || !inScope(studentName, coach, input)) {
    return {
      kind: "student_subject_breakdown",
      scope: scopeFor(input, 0),
      studentName,
      rows: [],
    };
  }
  const subj = rollupSubjectTargets(input.currentSnaps, studentName);
  const rows: AskRowSubjectStudent[] = subj.map((s) => ({
    subject: s.subject,
    avgTargetPerDay: s.avgTargetPerDay,
    avgActualPerDay: s.avgActualPerDay,
    delta: s.delta,
    daysObserved: s.daysObserved,
  }));
  return {
    kind: "student_subject_breakdown",
    scope: scopeFor(input, 1),
    studentName,
    rows,
  };
}

function computeRosterSubjectMix(input: RunAskInput): AskAnswer {
  const scopedStudents = collectScopedStudents(input);

  const acc = new Map<
    string,
    {
      curActualSum: number;
      curDays: number;
      priActualSum: number;
      priDays: number;
      studentSet: Set<string>;
    }
  >();

  function accumulate(snaps: Snapshot[], side: "cur" | "pri"): void {
    for (const day of snaps) {
      for (const stu of day.students) {
        if (!scopedStudents.has(stu.name)) continue;
        for (const subj of stu.subjects) {
          const prev = acc.get(subj.name) ?? {
            curActualSum: 0,
            curDays: 0,
            priActualSum: 0,
            priDays: 0,
            studentSet: new Set<string>(),
          };
          if (side === "cur") {
            prev.curActualSum += subj.actual_xp;
            prev.curDays += 1;
          } else {
            prev.priActualSum += subj.actual_xp;
            prev.priDays += 1;
          }
          prev.studentSet.add(stu.name);
          acc.set(subj.name, prev);
        }
      }
    }
  }

  accumulate(input.currentSnaps, "cur");
  accumulate(input.priorSnaps, "pri");

  const rows: AskRowSubjectRoster[] = [];
  for (const [subject, a] of acc) {
    const curAvg = a.curDays > 0 ? a.curActualSum / a.curDays : 0;
    const priAvg = a.priDays > 0 ? a.priActualSum / a.priDays : null;
    rows.push({
      subject,
      currentAvgActual: round1(curAvg),
      priorAvgActual: priAvg === null ? null : round1(priAvg),
      delta: priAvg === null ? null : round1(curAvg - priAvg),
      nStudents: a.studentSet.size,
    });
  }
  rows.sort((a, b) => a.subject.localeCompare(b.subject));

  return {
    kind: "roster_subject_mix",
    scope: scopeFor(input, scopedStudents.size),
    rows,
  };
}

function computeCleanWindow(input: RunAskInput): AskAnswer {
  const per = buildPerStudentScoped(input);
  const rows: AskRowCleanWindow[] = Object.values(per)
    .filter((m) => m.daysPresent > 0 && m.daysBehind === 0)
    .sort(
      (a, b) => b.actualTotal - a.actualTotal || a.name.localeCompare(b.name),
    )
    .map((m) => ({
      studentName: m.name,
      coach: m.coach,
      daysPresent: m.daysPresent,
      actualXp: m.actualTotal,
    }));
  return {
    kind: "clean_window",
    scope: scopeFor(input, Object.keys(per).length),
    rows,
  };
}

function collectScopedStudents(input: RunAskInput): Set<string> {
  const all = new Set<string>();
  for (const day of [...input.currentSnaps, ...input.priorSnaps]) {
    for (const stu of day.students) {
      if (inScope(stu.name, stu.coach, input)) all.add(stu.name);
    }
  }
  return all;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

// ---------------------------------------------------------------------------
// URL <-> AskParams (used by both the page and AskForm)
// ---------------------------------------------------------------------------

/**
 * Parse URL search params into AskParams. Defensive: unknown kinds
 * fall back to `top_xp`. This is the single source of truth for what
 * a permalink looks like.
 *
 * Recognized keys:
 *   k       — AskKind discriminator (required for non-default)
 *   n       — top/bottom count (top_xp, bottom_xp, deficit_*)
 *   student — student display name (student_subject_breakdown)
 */
export function paramsFromUrl(sp: URLSearchParams): AskParams {
  const kind = (sp.get("k") ?? "top_xp") as AskKind;
  switch (kind) {
    case "top_xp":
    case "bottom_xp":
    case "deficit_increase":
    case "deficit_decrease": {
      const nRaw = sp.get("n");
      const n = nRaw === null ? undefined : parseInt(nRaw, 10);
      return { kind, n: Number.isFinite(n as number) ? n : undefined };
    }
    case "concern_behind_multiple_days":
    case "concern_deep_deficit":
    case "concern_gap_not_closing":
    case "concern_frequent_exceptions":
    case "no_activity":
    case "roster_subject_mix":
    case "clean_window":
      return { kind };
    case "student_subject_breakdown":
      return {
        kind,
        studentName: sp.get("student") ?? "",
      };
    default:
      return { kind: "top_xp" };
  }
}

/**
 * Build the URL search-param representation of an AskParams. Empty
 * values and defaults are omitted to keep permalinks short. The `w`
 * window param is owned by the page (not by AskParams) and must be
 * merged in by the caller.
 */
export function paramsToUrl(p: AskParams): URLSearchParams {
  const out = new URLSearchParams();
  out.set("k", p.kind);
  switch (p.kind) {
    case "top_xp":
    case "bottom_xp":
    case "deficit_increase":
    case "deficit_decrease":
      if (p.n !== undefined && p.n !== DEFAULT_TOP_N) {
        out.set("n", String(p.n));
      }
      break;
    case "student_subject_breakdown":
      if (p.studentName) out.set("student", p.studentName);
      break;
    default:
      break;
  }
  return out;
}

/** Re-exported defaults for the UI layer. */
export { DEFAULT_TOP_N, MAX_TOP_N };
