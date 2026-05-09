import { describe, expect, it } from "vitest";

import {
  aggregateRange,
  CONCERN_BEHIND_MULTIPLE_DAYS,
  CONCERN_DEEP_DEFICIT,
  CONCERN_FREQUENT_EXCEPTIONS,
  CONCERN_GAP_NOT_CLOSING,
  DEFAULT_COACH_TREND_THRESHOLD,
  DEFAULT_CURRENT_WINDOW_DAYS,
  DEFAULT_PRIOR_WINDOW_DAYS,
} from "./aggregate";
import type { Snapshot, StudentSnap, SubjectSnap } from "./types";

// ---------------------------------------------------------------------------
// Synthetic snapshot helpers (no I/O, no fetch — purely in-memory).
// ---------------------------------------------------------------------------
function subj(
  name: string,
  target: number,
  actual: number,
  status: "on_track" | "behind" = "on_track",
  tier: string = "personalized_base",
): SubjectSnap {
  return { name, target_xp: target, actual_xp: actual, status, tier };
}

function student(
  name: string,
  coach: string,
  subjects: SubjectSnap[],
): StudentSnap {
  return { name, coach, subjects };
}

function snap(date: string, students: StudentSnap[]): Snapshot {
  return { date, students };
}

function fiveDayCurrentWindowEnding(today: string): string[] {
  // Returns [today-4 .. today] as ISO strings.
  const dates: string[] = [];
  const t = Date.UTC(
    parseInt(today.slice(0, 4), 10),
    parseInt(today.slice(5, 7), 10) - 1,
    parseInt(today.slice(8, 10), 10),
  );
  for (let i = 4; i >= 0; i--) {
    const d = new Date(t - i * 86_400_000);
    dates.push(d.toISOString().slice(0, 10));
  }
  return dates;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("aggregateRange — empty inputs", () => {
  it("produces an empty payload when snapshots are empty", () => {
    const out = aggregateRange([], "2026-05-11");
    expect(Object.keys(out.perStudent)).toEqual([]);
    expect(Object.keys(out.perCoach)).toEqual([]);
    expect(out.topConcerns).toEqual([]);
    expect(out.daysInCurrentWindow).toBe(0);
  });
});

describe("aggregateRange — single on-track student", () => {
  it("does not flag a student as a concern", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    const snapshots = dates.map((d) =>
      snap(d, [student("Alice", "Coach Bob", [subj("Math", 30, 30)])]),
    );
    const out = aggregateRange(snapshots, today);
    expect(out.perStudent.Alice.concerns).toEqual([]);
    expect(out.perStudent.Alice.severity).toBe(0);
  });
});

describe("aggregateRange — behind multiple days", () => {
  it("flags behind_multiple_days when status=behind on >= 2 subject-days", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    const snapshots = dates.map((d) =>
      snap(d, [student("Bob", "Coach C", [subj("Math", 30, 5, "behind")])]),
    );
    const out = aggregateRange(snapshots, today);
    expect(out.perStudent.Bob.concerns).toContain(CONCERN_BEHIND_MULTIPLE_DAYS);
    expect(out.perStudent.Bob.severity).toBeGreaterThan(0);
  });
});

describe("aggregateRange — deep deficit", () => {
  it("flags deep_deficit when total deficit >= threshold", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    // 5 days * 30 XP deficit = 150 XP > default 100 threshold.
    const snapshots = dates.map((d) =>
      snap(d, [student("Carlos", "Coach D", [subj("Math", 50, 20, "behind")])]),
    );
    const out = aggregateRange(snapshots, today);
    expect(out.perStudent.Carlos.concerns).toContain(CONCERN_DEEP_DEFICIT);
  });
});

describe("aggregateRange — frequent exceptions", () => {
  it("flags frequent_exceptions when override tier appears >= 3 subject-days", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    const snapshots = dates.map((d) =>
      snap(d, [
        student("Diana", "Coach E", [
          subj("Math", 30, 30, "on_track", "coach_xp_override"),
        ]),
      ]),
    );
    const out = aggregateRange(snapshots, today);
    expect(out.perStudent.Diana.concerns).toContain(CONCERN_FREQUENT_EXCEPTIONS);
  });
});

describe("aggregateRange — gap not closing", () => {
  it("flags gap_not_closing when prior had deficit and current is no better", () => {
    const today = "2026-05-11";
    const allDates: string[] = [];
    const t = Date.UTC(2026, 4, 11);
    for (let i = 9; i >= 0; i--) {
      const d = new Date(t - i * 86_400_000);
      allDates.push(d.toISOString().slice(0, 10));
    }
    // Prior 5 days: deficit 30 each. Current 5 days: deficit 30 each (flat).
    const snapshots = allDates.map((d) =>
      snap(d, [student("Eve", "Coach F", [subj("Math", 50, 20, "behind")])]),
    );
    const out = aggregateRange(snapshots, today);
    expect(out.perStudent.Eve.concerns).toContain(CONCERN_GAP_NOT_CLOSING);
  });
});

describe("aggregateRange — coach trend clusters", () => {
  it("creates a cluster when >= 2 students under one coach share a concern", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    const snapshots = dates.map((d) =>
      snap(d, [
        student("Alpha", "Coach Z", [subj("Math", 30, 5, "behind")]),
        student("Beta", "Coach Z", [subj("Math", 30, 5, "behind")]),
      ]),
    );
    const out = aggregateRange(snapshots, today);
    const coachZ = out.perCoach["Coach Z"];
    expect(coachZ).toBeDefined();
    const hasCluster = Object.values(coachZ.trendClusters).some(
      (names) => names.length >= DEFAULT_COACH_TREND_THRESHOLD,
    );
    expect(hasCluster).toBe(true);
  });
});

describe("aggregateRange — top concerns sorting and cap", () => {
  it("returns at most topConcernsN students, sorted by severity desc", () => {
    const today = "2026-05-11";
    const dates = fiveDayCurrentWindowEnding(today);
    const students = Array.from({ length: 10 }, (_, i) =>
      student(`S${i}`, "Coach X", [subj("Math", 30, 0, "behind")]),
    );
    const snapshots = dates.map((d) => snap(d, students));
    const out = aggregateRange(snapshots, today, { topConcernsN: 3 });
    expect(out.topConcerns.length).toBeLessThanOrEqual(3);
    for (let i = 1; i < out.topConcerns.length; i++) {
      expect(out.topConcerns[i - 1].severity).toBeGreaterThanOrEqual(
        out.topConcerns[i].severity,
      );
    }
  });
});

describe("aggregateRange — window options", () => {
  it("respects custom currentDays / priorDays settings", () => {
    const today = "2026-05-11";
    // Build 30 days of snapshots.
    const allDates: string[] = [];
    const t = Date.UTC(2026, 4, 11);
    for (let i = 29; i >= 0; i--) {
      const d = new Date(t - i * 86_400_000);
      allDates.push(d.toISOString().slice(0, 10));
    }
    const snapshots = allDates.map((d) =>
      snap(d, [student("Frank", "Coach G", [subj("Math", 30, 30)])]),
    );

    const defaultOut = aggregateRange(snapshots, today);
    expect(defaultOut.daysInCurrentWindow).toBe(DEFAULT_CURRENT_WINDOW_DAYS);
    expect(defaultOut.daysInPriorWindow).toBe(DEFAULT_PRIOR_WINDOW_DAYS);

    const wideOut = aggregateRange(snapshots, today, {
      currentDays: 30,
      priorDays: 0,
    });
    expect(wideOut.daysInCurrentWindow).toBe(30);
    expect(wideOut.daysInPriorWindow).toBe(0);
    expect(wideOut.priorWindow).toBeNull();
  });
});

describe("aggregateRange — invalid input", () => {
  it("throws on a malformed today string", () => {
    exp
