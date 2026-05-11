/**
 * Phase 5 — Report data assembler.
 *
 * Pure function. Given snapshots already fetched and a window already
 * resolved, returns a structured payload the PDF renderer consumes.
 *
 * Per Phase 5 Design Brief (locked):
 *   Q-Phase5-3: two scope buttons — "End of quarter" (current session)
 *               and "End of year" (last 365 days).
 *   Q-Phase5-7: per-subject XP table + concern summary + window-vs-window
 *               delta; NO coach-notes section.
 *
 * The assembler is purely functional so it can be unit-tested without
 * any GitHub fetches. The route handler does the I/O and passes
 * snapshots in.
 */
import "server-only";

import type { Snapshot, SubjectTarget } from "./types";
import {
  aggregateRange,
  type StudentMetrics,
  type ConcernCategory,
} from "./aggregate";
import { rollupSubjectTargets } from "./subjectTargets";

/** Scope buttons exposed on the student page. */
export type ReportScope = "eoq" | "eoy";

/** Human-readable label per scope (used in the PDF cover). */
export const REPORT_SCOPE_LABEL: Record<ReportScope, string> = {
  eoq: "End of quarter",
  eoy: "End of year",
};

/** One row in the per-subject XP table. */
export interface ReportSubjectRow {
  subject: string;
  avgTargetPerDay: number;
  avgActualPerDay: number;
  delta: number;
  daysObserved: number;
}

/** Window-vs-window deficit delta block. */
export interface ReportDeltaBlock {
  currentDeficit: number;
  priorDeficit: number | null;
  delta: number | null;
  currentStart: string;
  currentEnd: string;
  priorStart: string | null;
  priorEnd: string | null;
}

/** Concern category code + the canonical short label shown in the PDF. */
export interface ReportConcernItem {
  code: ConcernCategory;
  label: string;
}

const CONCERN_LABELS: Record<ConcernCategory, string> = {
  behind_multiple_days: "Behind multiple days",
  deep_deficit: "Deep deficit (≥ 100 XP)",
  gap_not_closing: "Gap not closing vs prior window",
  frequent_exceptions: "Frequent coach exceptions",
};

/** Fully structured payload handed to the PDF document. */
export interface ReportPayload {
  /** Identity. */
  studentName: string;
  coachName: string;
  schoolName: string;

  /** Scope + dates. */
  scope: ReportScope;
  scopeLabel: string;
  windowLabel: string;
  generatedDateIso: string;

  /** Cover one-liner. */
  summaryLine: string;

  /** Body sections. */
  subjects: ReportSubjectRow[];
  concerns: ReportConcernItem[];
  delta: ReportDeltaBlock;

  /** Snapshot coverage diagnostics (rendered as a small caption). */
  daysPresent: number;
  daysInCurrentWindow: number;
}

/** Inputs to buildReportPayload. */
export interface BuildReportInput {
  studentName: string;
  schoolName: string;
  scope: ReportScope;
  scopeLabel?: string;
  windowLabel: string;
  generatedDateIso: string;
  currentSnaps: Snapshot[];
  priorSnaps: Snapshot[];
  currentStart: string;
  currentEnd: string;
  priorStart: string | null;
  priorEnd: string | null;
}

/**
 * Compose the report payload from already-fetched snapshots.
 *
 * Returns null if the student does not appear in the current window — the
 * caller should treat that as a 404 ("no data for this student in the
 * selected scope"). We do NOT silently emit an empty PDF, because that
 * would be more confusing than a clear error.
 */
export function buildReportPayload(input: BuildReportInput): ReportPayload | null {
  const allSnaps = [...input.priorSnaps, ...input.currentSnaps];

  // Determine the student's coach from the most-recent appearance in the
  // current window. Falls back to prior window if the student is absent
  // current-window (which should already have been short-circuited; this
  // is a safety net).
  let coachName = "";
  let daysPresent = 0;
  for (const day of input.currentSnaps) {
    const stu = day.students.find((s) => s.name === input.studentName);
    if (stu) {
      coachName = stu.coach;
      daysPresent += 1;
    }
  }
  if (daysPresent === 0) {
    // Try prior window for the coach name only; if still absent, bail.
    for (const day of input.priorSnaps) {
      const stu = day.students.find((s) => s.name === input.studentName);
      if (stu) {
        coachName = stu.coach;
        break;
      }
    }
    if (!coachName) return null;
  }

  // Per-subject rollup uses the CURRENT window only (matches the dashboard
  // student detail page's behavior).
  const subjectTargets: SubjectTarget[] = rollupSubjectTargets(
    input.currentSnaps,
    input.studentName,
  );
  const subjects: ReportSubjectRow[] = subjectTargets.map((s) => ({
    subject: s.subject,
    avgTargetPerDay: s.avgTargetPerDay,
    avgActualPerDay: s.avgActualPerDay,
    delta: s.delta,
    daysObserved: s.daysObserved,
  }));

  // Use aggregateRange against the union of both windows so it can compute
  // the prior-window deficit and concerns identically to the dashboard.
  const aggCurrentDays = Math.max(
    1,
    isoDayDiffInclusive(input.currentStart, input.currentEnd),
  );
  const aggPriorDays =
    input.priorStart && input.priorEnd
      ? Math.max(1, isoDayDiffInclusive(input.priorStart, input.priorEnd))
      : 0;
  const digest = aggregateRange(allSnaps, input.currentEnd, {
    currentDays: aggCurrentDays,
    priorDays: aggPriorDays,
  });
  const metrics: StudentMetrics | undefined = digest.perStudent[input.studentName];

  const concerns: ReportConcernItem[] = (metrics?.concerns ?? []).map((c) => ({
    code: c,
    label: CONCERN_LABELS[c],
  }));

  const delta: ReportDeltaBlock = {
    currentDeficit: metrics?.deficitTotal ?? 0,
    priorDeficit: metrics?.priorDeficitTotal ?? null,
    delta: metrics?.deficitDelta ?? null,
    currentStart: input.currentStart,
    currentEnd: input.currentEnd,
    priorStart: input.priorStart,
    priorEnd: input.priorEnd,
  };

  const summaryLine = composeSummaryLine({
    studentName: input.studentName,
    daysPresent,
    daysInCurrentWindow: aggCurrentDays,
    currentDeficit: delta.currentDeficit,
    deltaValue: delta.delta,
    concernCount: concerns.length,
  });

  return {
    studentName: input.studentName,
    coachName,
    schoolName: input.schoolName,
    scope: input.scope,
    scopeLabel: input.scopeLabel ?? REPORT_SCOPE_LABEL[input.scope],
    windowLabel: input.windowLabel,
    generatedDateIso: input.generatedDateIso,
    summaryLine,
    subjects,
    concerns,
    delta,
    daysPresent,
    daysInCurrentWindow: aggCurrentDays,
  };
}

/** One-line summary printed on the cover. Plain-spoken; no jargon. */
function composeSummaryLine(args: {
  studentName: string;
  daysPresent: number;
  daysInCurrentWindow: number;
  currentDeficit: number;
  deltaValue: number | null;
  concernCount: number;
}): string {
  const firstName = args.studentName.split(/\s+/)[0] ?? args.studentName;
  const present = `${args.daysPresent} of ${args.daysInCurrentWindow} days observed`;
  const deficit =
    args.currentDeficit > 0
      ? `current deficit ${Math.round(args.currentDeficit)} XP`
      : "no current deficit";
  let trend = "";
  if (args.deltaValue !== null) {
    if (args.deltaValue > 0) trend = `, up ${Math.round(args.deltaValue)} XP vs prior`;
    else if (args.deltaValue < 0) trend = `, down ${Math.round(-args.deltaValue)} XP vs prior`;
    else trend = ", unchanged vs prior";
  }
  const concerns =
    args.concernCount === 0
      ? "no active concerns"
      : `${args.concernCount} active concern${args.concernCount === 1 ? "" : "s"}`;
  return `${firstName}: ${present}; ${deficit}${trend}; ${concerns}.`;
}

/** Days between two inclusive ISO dates (YYYY-MM-DD). */
function isoDayDiffInclusive(start: string, end: string): number {
  const ts = Date.UTC(
    parseInt(start.slice(0, 4), 10),
    parseInt(start.slice(5, 7), 10) - 1,
    parseInt(start.slice(8, 10), 10),
  );
  const te = Date.UTC(
    parseInt(end.slice(0, 4), 10),
    parseInt(end.slice(5, 7), 10) - 1,
    parseInt(end.slice(8, 10), 10),
  );
  return Math.floor((te - ts) / 86_400_000) + 1;
}

/** Build the canonical filename per Q-Phase5-8. */
export function reportFilename(
  studentSlug: string,
  scope: ReportScope,
  dateIso: string,
): string {
  return `${studentSlug}_${scope}_${dateIso}.pdf`;
}
