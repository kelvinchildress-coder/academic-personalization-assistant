/**
 * Phase 6 — Ask answer → table render helpers.
 *
 * Pure functions that translate an AskAnswer variant into a uniform
 * { columns, rows } shape so the UI layer can render every kind with
 * one <table> component instead of twelve. No React imports, no I/O.
 *
 * Column ids are stable strings so the UI can attach Tailwind classes
 * or alignment hints without re-deriving from labels.
 */

import type { AskAnswer } from "./types";

export interface RenderColumn {
  id: string;
  label: string;
  /** Cell alignment hint. UI maps "right" to a right-aligned class. */
  align: "left" | "right";
}

export type RenderCell = string | number;

export interface RenderedTable {
  title: string;
  subtitle: string;
  columns: RenderColumn[];
  rows: RenderCell[][];
  /** Optional notice shown above the table when rows.length === 0. */
  emptyNotice: string;
}

/** One-line description of the scope, for the subtitle. */
function scopeLine(a: AskAnswer): string {
  const s = a.scope;
  const prior =
    s.priorStart && s.priorEnd
      ? ` · prior ${s.priorStart} → ${s.priorEnd}`
      : "";
  const coach = s.coachFilter ? ` · coach ${s.coachFilter}` : " · all coaches";
  return `${s.windowLabel} (${s.currentStart} → ${s.currentEnd}${prior})${coach} · ${s.nStudentsInScope} students in scope`;
}

function num(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString() : "—";
}

function num1(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "—";
  return n.toFixed(1);
}

function signed(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "—";
  const fixed = n.toFixed(1);
  return n > 0 ? `+${fixed}` : fixed;
}

const COL = {
  rank: { id: "rank", label: "#", align: "right" as const },
  student: { id: "student", label: "Student", align: "left" as const },
  coach: { id: "coach", label: "Coach", align: "left" as const },
  actualXp: { id: "actualXp", label: "Actual XP", align: "right" as const },
  targetXp: { id: "targetXp", label: "Target XP", align: "right" as const },
  deficit: { id: "deficit", label: "Deficit", align: "right" as const },
  daysPresent: {
    id: "daysPresent",
    label: "Days present",
    align: "right" as const,
  },
  curDeficit: {
    id: "curDeficit",
    label: "Current deficit",
    align: "right" as const,
  },
  priDeficit: {
    id: "priDeficit",
    label: "Prior deficit",
    align: "right" as const,
  },
  delta: { id: "delta", label: "Δ", align: "right" as const },
  daysBehind: {
    id: "daysBehind",
    label: "Days behind",
    align: "right" as const,
  },
  severity: { id: "severity", label: "Severity", align: "right" as const },
  subject: { id: "subject", label: "Subject", align: "left" as const },
  avgTarget: {
    id: "avgTarget",
    label: "Avg target/day",
    align: "right" as const,
  },
  avgActual: {
    id: "avgActual",
    label: "Avg actual/day",
    align: "right" as const,
  },
  daysObserved: {
    id: "daysObserved",
    label: "Days observed",
    align: "right" as const,
  },
  curAvg: { id: "curAvg", label: "Current avg", align: "right" as const },
  priAvg: { id: "priAvg", label: "Prior avg", align: "right" as const },
  nStudents: { id: "nStudents", label: "Students", align: "right" as const },
};

export function renderAnswer(a: AskAnswer): RenderedTable {
  const subtitle = scopeLine(a);

  switch (a.kind) {
    case "top_xp":
    case "bottom_xp": {
      const title =
        a.kind === "top_xp"
          ? "Top students by actual XP"
          : "Bottom students by actual XP";
      return {
        title,
        subtitle,
        columns: [
          COL.rank,
          COL.student,
          COL.coach,
          COL.actualXp,
          COL.targetXp,
          COL.deficit,
          COL.daysPresent,
        ],
        rows: a.rows.map((r) => [
          r.rank,
          r.studentName,
          r.coach,
          num(r.actualXp),
          num(r.targetXp),
          num(r.deficit),
          r.daysPresent,
        ]),
        emptyNotice: "No students in scope.",
      };
    }
    case "deficit_increase":
    case "deficit_decrease": {
      const title =
        a.kind === "deficit_increase"
          ? "Largest deficit increase vs prior window"
          : "Largest deficit decrease vs prior window";
      return {
        title,
        subtitle,
        columns: [
          COL.rank,
          COL.student,
          COL.coach,
          COL.curDeficit,
          COL.priDeficit,
          COL.delta,
        ],
        rows: a.rows.map((r) => [
          r.rank,
          r.studentName,
          r.coach,
          num(r.currentDeficit),
          num(r.priorDeficit),
          signed(r.delta),
        ]),
        emptyNotice:
          "No students have a comparable prior window (need both windows present).",
      };
    }
    case "concern_behind_multiple_days":
    case "concern_deep_deficit":
    case "concern_gap_not_closing":
    case "concern_frequent_exceptions": {
      const titles = {
        concern_behind_multiple_days: "Students with concern: behind multiple days",
        concern_deep_deficit: "Students with concern: deep deficit",
        concern_gap_not_closing: "Students with concern: gap not closing",
        concern_frequent_exceptions:
          "Students with concern: frequent exceptions",
      } as const;
      return {
        title: titles[a.kind],
        subtitle,
        columns: [
          COL.student,
          COL.coach,
          COL.daysBehind,
          COL.deficit,
          COL.severity,
        ],
        rows: a.rows.map((r) => [
          r.studentName,
          r.coach,
          r.daysBehind,
          num(r.deficit),
          r.severity.toFixed(2),
        ]),
        emptyNotice: "No students match this concern in the current window.",
      };
    }
    case "no_activity":
      return {
        title: "Students with no snapshot in current window",
        subtitle,
        columns: [COL.student, COL.coach, COL.daysPresent],
        rows: a.rows.map((r) => [r.studentName, r.coach, r.daysPresent]),
        emptyNotice: "Every student in scope has at least one snapshot.",
      };
    case "student_subject_breakdown":
      return {
        title: `Subject breakdown — ${a.studentName || "(no student selected)"}`,
        subtitle,
        columns: [
          COL.subject,
          COL.avgTarget,
          COL.avgActual,
          COL.delta,
          COL.daysObserved,
        ],
        rows: a.rows.map((r) => [
          r.subject,
          num1(r.avgTargetPerDay),
          num1(r.avgActualPerDay),
          signed(r.delta),
          r.daysObserved,
        ]),
        emptyNotice: a.studentName
          ? "No subject data for this student in the current window."
          : "Enter a student name to see a subject breakdown.",
      };
    case "roster_subject_mix":
      return {
        title: "Roster-wide subject XP mix (current vs prior)",
        subtitle,
        columns: [
          COL.subject,
          COL.curAvg,
          COL.priAvg,
          COL.delta,
          COL.nStudents,
        ],
        rows: a.rows.map((r) => [
          r.subject,
          num1(r.currentAvgActual),
          num1(r.priorAvgActual),
          signed(r.delta),
          r.nStudents,
        ]),
        emptyNotice: "No subject data in the current window.",
      };
    case "clean_window":
      return {
        title: "Clean window (zero days-behind in current window)",
        subtitle,
        columns: [COL.student, COL.coach, COL.daysPresent, COL.actualXp],
        rows: a.rows.map((r) => [
          r.studentName,
          r.coach,
          r.daysPresent,
          num(r.actualXp),
        ]),
        emptyNotice:
          "No students went the full current window without a 'behind' day.",
      };
  }
}
