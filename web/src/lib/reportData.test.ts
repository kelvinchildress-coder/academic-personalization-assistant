/**
 * Phase 5 — Tests for reportData.ts.
 *
 * Pure assembler tests; no GitHub fetches. Snapshots are constructed
 * in-line.
 */
import { describe, it, expect } from "vitest";
import {
  buildReportPayload,
  reportFilename,
  REPORT_SCOPE_LABEL,
  type ReportPayload,
} from "./reportData";
import type { Snapshot } from "./types";

function makeSnap(
  date: string,
  studentName: string,
  coach: string,
  subjects: Array<{ name: string; target: number; actual: number; status?: string; tier?: string }>,
): Snapshot {
  return {
    date,
    students: [
      {
        name: studentName,
        coach,
        subjects: subjects.map((s) => ({
          name: s.name,
          target_xp: s.target,
          actual_xp: s.actual,
          status: s.status ?? (s.actual >= s.target ? "on_track" : "behind"),
          tier: s.tier ?? "personalized_base",
        })),
      },
    ],
  };
}

describe("reportFilename", () => {
  it("produces slug_scope_date.pdf", () => {
    expect(reportFilename("ella-alexander", "eoq", "2026-05-10")).toBe(
      "ella-alexander_eoq_2026-05-10.pdf",
    );
  });

  it("handles eoy scope", () => {
    expect(reportFilename("lucy-wilkinson", "eoy", "2026-05-10")).toBe(
      "lucy-wilkinson_eoy_2026-05-10.pdf",
    );
  });
});

describe("REPORT_SCOPE_LABEL", () => {
  it("maps eoq", () => {
    expect(REPORT_SCOPE_LABEL.eoq).toBe("End of quarter");
  });
  it("maps eoy", () => {
    expect(REPORT_SCOPE_LABEL.eoy).toBe("End of year");
  });
});

describe("buildReportPayload", () => {
  it("returns null when student is absent from both windows", () => {
    const currentSnaps: Snapshot[] = [
      makeSnap("2026-05-10", "Other Student", "coach@x.school", [
        { name: "Math", target: 100, actual: 80 },
      ]),
    ];
    const result = buildReportPayload({
      studentName: "Missing Student",
      schoolName: "Texas Sports Academy",
      scope: "eoq",
      windowLabel: "SY25-26 Session 5",
      generatedDateIso: "2026-05-10",
      currentSnaps,
      priorSnaps: [],
      currentStart: "2026-05-10",
      currentEnd: "2026-05-10",
      priorStart: null,
      priorEnd: null,
    });
    expect(result).toBeNull();
  });

  it("assembles a clean-window payload (no deficit, no concerns)", () => {
    const currentSnaps: Snapshot[] = [
      makeSnap("2026-05-08", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 100 },
        { name: "Reading", target: 100, actual: 110 },
      ]),
      makeSnap("2026-05-09", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 100 },
        { name: "Reading", target: 100, actual: 110 },
      ]),
    ];
    const result = buildReportPayload({
      studentName: "Ella Alexander",
      schoolName: "Texas Sports Academy",
      scope: "eoq",
      windowLabel: "SY25-26 Session 5",
      generatedDateIso: "2026-05-09",
      currentSnaps,
      priorSnaps: [],
      currentStart: "2026-05-08",
      currentEnd: "2026-05-09",
      priorStart: null,
      priorEnd: null,
    });
    expect(result).not.toBeNull();
    const r = result as ReportPayload;
    expect(r.studentName).toBe("Ella Alexander");
    expect(r.coachName).toBe("coach@x.school");
    expect(r.daysPresent).toBe(2);
    expect(r.scope).toBe("eoq");
    expect(r.scopeLabel).toBe("End of quarter");
    expect(r.subjects).toHaveLength(2);
    expect(r.subjects.map((s) => s.subject).sort()).toEqual(["Math", "Reading"]);
    expect(r.concerns).toHaveLength(0);
    expect(r.delta.currentDeficit).toBe(0);
    expect(r.summaryLine).toContain("no current deficit");
    expect(r.summaryLine).toContain("no active concerns");
  });

  it("detects deep_deficit + behind_multiple_days concerns", () => {
    // 5 days, all behind, total deficit > 100 XP.
    const currentSnaps: Snapshot[] = [
      "2026-05-05",
      "2026-05-06",
      "2026-05-07",
      "2026-05-08",
      "2026-05-09",
    ].map((d) =>
      makeSnap(d, "Lucy Wilkinson", "coach@x.school", [
        { name: "Math", target: 100, actual: 40 },
      ]),
    );
    const result = buildReportPayload({
      studentName: "Lucy Wilkinson",
      schoolName: "Texas Sports Academy",
      scope: "eoq",
      windowLabel: "SY25-26 Session 5",
      generatedDateIso: "2026-05-09",
      currentSnaps,
      priorSnaps: [],
      currentStart: "2026-05-05",
      currentEnd: "2026-05-09",
      priorStart: null,
      priorEnd: null,
    });
    expect(result).not.toBeNull();
    const r = result as ReportPayload;
    const codes = r.concerns.map((c) => c.code).sort();
    expect(codes).toContain("deep_deficit");
    expect(codes).toContain("behind_multiple_days");
    expect(r.delta.currentDeficit).toBeGreaterThanOrEqual(100);
    expect(r.summaryLine).toContain("current deficit");
  });

  it("computes window-vs-window delta when prior snaps provided", () => {
    const currentSnaps: Snapshot[] = [
      makeSnap("2026-05-08", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 50 },
      ]),
      makeSnap("2026-05-09", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 50 },
      ]),
    ];
    const priorSnaps: Snapshot[] = [
      makeSnap("2026-05-06", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 80 },
      ]),
      makeSnap("2026-05-07", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 80 },
      ]),
    ];
    const result = buildReportPayload({
      studentName: "Ella Alexander",
      schoolName: "Texas Sports Academy",
      scope: "eoq",
      windowLabel: "SY25-26 Session 5",
      generatedDateIso: "2026-05-09",
      currentSnaps,
      priorSnaps,
      currentStart: "2026-05-08",
      currentEnd: "2026-05-09",
      priorStart: "2026-05-06",
      priorEnd: "2026-05-07",
    });
    expect(result).not.toBeNull();
    const r = result as ReportPayload;
    expect(r.delta.currentDeficit).toBe(100); // 2 days × 50 XP deficit
    expect(r.delta.priorDeficit).toBe(40); // 2 days × 20 XP deficit
    expect(r.delta.delta).toBe(60); // 100 - 40
    expect(r.summaryLine).toContain("up 60 XP vs prior");
  });

  it("includes subject rows with averaged target/actual per day", () => {
    const currentSnaps: Snapshot[] = [
      makeSnap("2026-05-08", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 80 },
        { name: "Reading", target: 60, actual: 70 },
      ]),
      makeSnap("2026-05-09", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 120, actual: 100 },
        { name: "Reading", target: 60, actual: 70 },
      ]),
    ];
    const result = buildReportPayload({
      studentName: "Ella Alexander",
      schoolName: "Texas Sports Academy",
      scope: "eoq",
      windowLabel: "SY25-26 Session 5",
      generatedDateIso: "2026-05-09",
      currentSnaps,
      priorSnaps: [],
      currentStart: "2026-05-08",
      currentEnd: "2026-05-09",
      priorStart: null,
      priorEnd: null,
    });
    expect(result).not.toBeNull();
    const r = result as ReportPayload;
    const math = r.subjects.find((s) => s.subject === "Math");
    expect(math).toBeDefined();
    expect(math?.avgTargetPerDay).toBe(110); // (100+120)/2
    expect(math?.avgActualPerDay).toBe(90); // (80+100)/2
    expect(math?.delta).toBe(-20);
    expect(math?.daysObserved).toBe(2);
  });

  it("uses scope label EoY when scope=eoy", () => {
    const currentSnaps: Snapshot[] = [
      makeSnap("2026-05-09", "Ella Alexander", "coach@x.school", [
        { name: "Math", target: 100, actual: 100 },
      ]),
    ];
    const result = buildReportPayload({
      studentName: "Ella Alexander",
      schoolName: "Texas Sports Academy",
      scope: "eoy",
      windowLabel: "Last 365 days",
      generatedDateIso: "2026-05-09",
      currentSnaps,
      priorSnaps: [],
      currentStart: "2025-05-10",
      currentEnd: "2026-05-09",
      priorStart: null,
      priorEnd: null,
    });
    expect(result).not.toBeNull();
    expect((result as ReportPayload).scopeLabel).toBe("End of year");
  });
});
