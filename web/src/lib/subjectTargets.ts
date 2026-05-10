/**
 * Phase 7 Part 8 — Per-subject XP target/actual rollup.
 *
 * Pure aggregator that takes a series of daily snapshots for ONE student
 * and returns a SubjectTarget per subject — averaging target_xp and
 * actual_xp per day across the days observed.
 *
 * Q8-1 (final): Use SubjectSnap.target_xp directly from snapshots. The
 * Python 4-tier cascade has already produced the right per-subject target
 * by the time the snapshot is written, so the dashboard does not re-derive.
 *
 * Q8-1-caption: callers display "(based on N days)" when daysObserved < 5.
 */

import type { Snapshot, StudentSnap, SubjectTarget } from "./types";

/**
 * Extract a single student's per-day subject snapshots from a series of
 * daily Snapshots. Returns one StudentSnap per day where the student
 * appears. Snapshots are matched by exact name (no slug fuzzing here —
 * caller should pass a canonical display name).
 */
export function studentSnapsAcrossWindow(
  snapshots: Snapshot[],
  studentName: string
): { date: string; snap: StudentSnap }[] {
  const out: { date: string; snap: StudentSnap }[] = [];
  for (const day of snapshots) {
    const found = day.students.find((s) => s.name === studentName);
    if (found) out.push({ date: day.date, snap: found });
  }
  return out;
}

/**
 * Compute SubjectTarget rollup for one student across a window of daily
 * snapshots. Subjects are unioned across all days the student appears
 * — if a subject is present on day 1 but not day 2, it counts as 1
 * day observed for that subject.
 */
export function rollupSubjectTargets(
  snapshots: Snapshot[],
  studentName: string
): SubjectTarget[] {
  const days = studentSnapsAcrossWindow(snapshots, studentName);
  if (days.length === 0) return [];

  const bySubject = new Map<
    string,
    { targetSum: number; actualSum: number; days: number }
  >();

  for (const { snap } of days) {
    for (const subj of snap.subjects) {
      const prev = bySubject.get(subj.name) ?? {
        targetSum: 0,
        actualSum: 0,
        days: 0,
      };
      prev.targetSum += subj.target_xp;
      prev.actualSum += subj.actual_xp;
      prev.days += 1;
      bySubject.set(subj.name, prev);
    }
  }

  const out: SubjectTarget[] = [];
  for (const [subject, agg] of bySubject) {
    const avgTarget = agg.targetSum / agg.days;
    const avgActual = agg.actualSum / agg.days;
    out.push({
      subject,
      avgTargetPerDay: round1(avgTarget),
      avgActualPerDay: round1(avgActual),
      delta: round1(avgActual - avgTarget),
      daysObserved: agg.days,
    });
  }

  // Stable order: alphabetical by subject name.
  out.sort((a, b) => a.subject.localeCompare(b.subject));
  return out;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}
