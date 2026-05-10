/**
 * Phase 7 Part 8 — Tests for per-subject XP target rollup.
 */

import { describe, it, expect } from "vitest";
import {
  studentSnapsAcrossWindow,
  rollupSubjectTargets,
} from "./subjectTargets";
import type { Snapshot } from "./types";

const FIXTURE: Snapshot[] = [
  {
    date: "2026-05-08",
    students: [
      {
        name: "Ada Lovelace",
        coach: "Ella Alexander",
        subjects: [
          { name: "Math", target_xp: 30, actual_xp: 18, status: "behind", tier: "personalized_base" },
          { name: "Reading", target_xp: 25, actual_xp: 25, status: "on_track", tier: "personalized_base" },
        ],
      },
      {
        name: "Other Student",
        coach: "Ella Alexander",
        subjects: [{ name: "Math", target_xp: 30, actual_xp: 30, status: "on_track", tier: "personalized_base" }],
      },
    ],
  },
  {
    date: "2026-05-09",
    students: [
      {
        name: "Ada Lovelace",
        coach: "Ella Alexander",
        subjects: [
          { name: "Math", target_xp: 30, actual_xp: 22, status: "behind", tier: "personalized_base" },
          { name: "Reading", target_xp: 25, actual_xp: 27, status: "on_track", tier: "personalized_base" },
          { name: "Science", target_xp: 20, actual_xp: 10, status: "behind", tier: "personalized_base" },
        ],
      },
    ],
  },
];

describe("studentSnapsAcrossWindow", () => {
  it("filters to one student across days", () => {
    const out = studentSnapsAcrossWindow(FIXTURE, "Ada Lovelace");
    expect(out.length).toBe(2);
    expect(out[0].date).toBe("2026-05-08");
    expect(out[1].date).toBe("2026-05-09");
  });

  it("returns empty for unknown student", () => {
    expect(studentSnapsAcrossWindow(FIXTURE, "Nobody")).toEqual([]);
  });
});

describe("rollupSubjectTargets", () => {
  it("averages target/actual per subject across days observed", () => {
    const out = rollupSubjectTargets(FIXTURE, "Ada Lovelace");
    const math = out.find((s) => s.subject === "Math");
    const reading = out.find((s) => s.subject === "Reading");
    const science = out.find((s) => s.subject === "Science");

    expect(math?.avgTargetPerDay).toBe(30);
    expect(math?.avgActualPerDay).toBe(20); // (18+22)/2
    expect(math?.delta).toBe(-10);
    expect(math?.daysObserved).toBe(2);

    expect(reading?.avgActualPerDay).toBe(26); // (25+27)/2
    expect(reading?.daysObserved).toBe(2);

    // Science only present on day 2.
    expect(science?.daysObserved).toBe(1);
    expect(science?.avgActualPerDay).toBe(10);
  });

  it("returns sorted alphabetically by subject", () => {
    const out = rollupSubjectTargets(FIXTURE, "Ada Lovelace");
    expect(out.map((s) => s.subject)).toEqual(["Math", "Reading", "Science"]);
  });

  it("returns empty for unknown student", () => {
    expect(rollupSubjectTargets(FIXTURE, "Nobody")).toEqual([]);
  });
});
