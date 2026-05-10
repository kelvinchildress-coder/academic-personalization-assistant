/**
 * Phase 6 — askKinds unit tests.
 *
 * Pure-function tests. No fetch, no React, no I/O. We build small
 * Snapshot fixtures and assert the dispatch + compute layer returns
 * the expected AskAnswer shape and ordering.
 */

import { describe, expect, it } from "vitest";
import type { Snapshot } from "./types";
import {
  paramsFromUrl,
  paramsToUrl,
  runAsk,
  type RunAskInput,
} from "./askKinds";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function snap(
  date: string,
  students: Array<{
    name: string;
    coach: string;
    subjects: Array<{
      name: string;
      target_xp: number;
      actual_xp: number;
      status?: string;
      tier?: string;
    }>;
  }>,
): Snapshot {
  return {
    date,
    students: students.map((s) => ({
      name: s.name,
      coach: s.coach,
      subjects: s.subjects.map((sub) => ({
        name: sub.name,
        target_xp: sub.target_xp,
        actual_xp: sub.actual_xp,
        status:
          sub.status ?? (sub.actual_xp < sub.target_xp ? "behind" : "on_track"),
        tier: sub.tier ?? "personalized_base",
      })),
    })),
  };
}

const C1 = "coach1@sportsacademy.school";
const C2 = "coach2@sportsacademy.school";

const roster = new Map<string, string>([
  ["Alice", C1],
  ["Bob", C1],
  ["Cara", C2],
  ["Dan", C2],
]);

const currentSnaps: Snapshot[] = [
  snap("2026-05-08", [
    {
      name: "Alice",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 60 }],
    },
    {
      name: "Bob",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 0 }],
    },
    {
      name: "Cara",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 30 }],
    },
  ]),
  snap("2026-05-09", [
    {
      name: "Alice",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 70 }],
    },
    {
      name: "Bob",
      coach: C1,
      subjects: [
        { name: "Math", target_xp: 50, actual_xp: 10, tier: "coach_xp_override" },
      ],
    },
    {
      name: "Cara",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 25 }],
    },
  ]),
  snap("2026-05-10", [
    {
      name: "Alice",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 55 }],
    },
    {
      name: "Bob",
      coach: C1,
      subjects: [
        { name: "Math", target_xp: 50, actual_xp: 0, tier: "coach_xp_override" },
      ],
    },
    {
      name: "Cara",
      coach: C2,
      subjects: [
        { name: "Math", target_xp: 50, actual_xp: 20, tier: "coach_test_by" },
      ],
    },
  ]),
];

const priorSnaps: Snapshot[] = [
  snap("2026-05-06", [
    {
      name: "Alice",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 60 }],
    },
    {
      name: "Bob",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 40 }],
    },
    {
      name: "Cara",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 45 }],
    },
    {
      name: "Dan",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 30 }],
    },
  ]),
  snap("2026-05-07", [
    {
      name: "Alice",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 65 }],
    },
    {
      name: "Bob",
      coach: C1,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 45 }],
    },
    {
      name: "Cara",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 50 }],
    },
    {
      name: "Dan",
      coach: C2,
      subjects: [{ name: "Math", target_xp: 50, actual_xp: 35 }],
    },
  ]),
];

function baseInput(overrides: Partial<RunAskInput> = {}): RunAskInput {
  return {
    params: { kind: "top_xp" },
    currentSnaps,
    priorSnaps,
    today: "2026-05-10",
    currentStart: "2026-05-08",
    currentEnd: "2026-05-10",
    priorStart: "2026-05-06",
    priorEnd: "2026-05-07",
    windowLabel: "Last 3 days",
    coachFilter: null,
    studentNameToCoachEmail: roster,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Dispatcher: every kind returns the matching kind on the answer
// ---------------------------------------------------------------------------

describe("runAsk dispatcher", () => {
  it("returns top_xp answer for top_xp params", () => {
    const a = runAsk(baseInput({ params: { kind: "top_xp" } }));
    expect(a.kind).toBe("top_xp");
  });

  it("returns each concern kind correctly", () => {
    const kinds = [
      "concern_behind_multiple_days",
      "concern_deep_deficit",
      "concern_gap_not_closing",
      "concern_frequent_exceptions",
    ] as const;
    for (const k of kinds) {
      const a = runAsk(baseInput({ params: { kind: k } }));
      expect(a.kind).toBe(k);
    }
  });

  it("returns roster_subject_mix with current and prior in scope", () => {
    const a = runAsk(baseInput({ params: { kind: "roster_subject_mix" } }));
    expect(a.kind).toBe("roster_subject_mix");
    if (a.kind === "roster_subject_mix") {
      expect(a.rows.length).toBeGreaterThan(0);
      expect(a.rows[0].subject).toBe("Math");
      expect(a.rows[0].priorAvgActual).not.toBeNull();
    }
  });
});

// ---------------------------------------------------------------------------
// top_xp / bottom_xp ordering and clamping
// ---------------------------------------------------------------------------

describe("top_xp / bottom_xp", () => {
  it("top_xp sorts by actualTotal desc", () => {
    const a = runAsk(baseInput({ params: { kind: "top_xp", n: 4 } }));
    if (a.kind !== "top_xp") throw new Error("wrong kind");
    expect(a.rows[0].studentName).toBe("Alice");
    expect(a.rows[0].rank).toBe(1);
    for (let i = 1; i < a.rows.length; i++) {
      expect(a.rows[i - 1].actualXp).toBeGreaterThanOrEqual(a.rows[i].actualXp);
    }
  });

  it("bottom_xp excludes daysPresent=0 students and sorts asc", () => {
    const a = runAsk(baseInput({ params: { kind: "bottom_xp", n: 10 } }));
    if (a.kind !== "bottom_xp") throw new Error("wrong kind");
    for (const r of a.rows) {
      expect(r.daysPresent).toBeGreaterThan(0);
    }
    for (let i = 1; i < a.rows.length; i++) {
      expect(a.rows[i - 1].actualXp).toBeLessThanOrEqual(a.rows[i].actualXp);
    }
  });

  it("clamps n to MAX_TOP_N", () => {
    const a = runAsk(baseInput({ params: { kind: "top_xp", n: 9999 } }));
    if (a.kind !== "top_xp") throw new Error("wrong kind");
    expect(a.rows.length).toBeLessThanOrEqual(50);
  });

  it("clamps n to at least 1", () => {
    const a = runAsk(baseInput({ params: { kind: "top_xp", n: 0 } }));
    if (a.kind !== "top_xp") throw new Error("wrong kind");
    expect(a.rows.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// deficit_increase / deficit_decrease direction
// ---------------------------------------------------------------------------

describe("deficit_increase / deficit_decrease", () => {
  it("deficit_increase puts largest positive delta first", () => {
    const a = runAsk(baseInput({ params: { kind: "deficit_increase", n: 5 } }));
    if (a.kind !== "deficit_increase") throw new Error("wrong kind");
    expect(a.rows.length).toBeGreaterThan(0);
    for (let i = 1; i < a.rows.length; i++) {
      expect(a.rows[i - 1].delta).toBeGreaterThanOrEqual(a.rows[i].delta);
    }
  });

  it("deficit_decrease puts most negative delta first", () => {
    const a = runAsk(baseInput({ params: { kind: "deficit_decrease", n: 5 } }));
    if (a.kind !== "deficit_decrease") throw new Error("wrong kind");
    for (let i = 1; i < a.rows.length; i++) {
      expect(a.rows[i - 1].delta).toBeLessThanOrEqual(a.rows[i].delta);
    }
  });
});

// ---------------------------------------------------------------------------
// no_activity isolates students absent from current window
// ---------------------------------------------------------------------------

describe("no_activity", () => {
  it("includes Dan (no current snapshot) and excludes others", () => {
    const a = runAsk(baseInput({ params: { kind: "no_activity" } }));
    if (a.kind !== "no_activity") throw new Error("wrong kind");
    const names = a.rows.map((r) => r.studentName);
    expect(names).toContain("Dan");
    expect(names).not.toContain("Alice");
    expect(names).not.toContain("Bob");
    expect(names).not.toContain("Cara");
  });
});

// ---------------------------------------------------------------------------
// Concern filters surface the right students
// ---------------------------------------------------------------------------

describe("concern filters", () => {
  it("concern_behind_multiple_days surfaces Bob", () => {
    const a = runAsk(
      baseInput({ params: { kind: "concern_behind_multiple_days" } }),
    );
    if (a.kind !== "concern_behind_multiple_days") throw new Error("wrong kind");
    const names = a.rows.map((r) => r.studentName);
    expect(names).toContain("Bob");
  });

  it("concern_deep_deficit surfaces Bob (≥100 XP deficit across 3 days)", () => {
    const a = runAsk(baseInput({ params: { kind: "concern_deep_deficit" } }));
    if (a.kind !== "concern_deep_deficit") throw new Error("wrong kind");
    const names = a.rows.map((r) => r.studentName);
    expect(names).toContain("Bob");
  });

  it("concern_frequent_exceptions surfaces students with ≥3 override subject-days", () => {
    const a = runAsk(
      baseInput({ params: { kind: "concern_frequent_exceptions" } }),
    );
    if (a.kind !== "concern_frequent_exceptions") throw new Error("wrong kind");
    // Bob has 2 override days in current; Cara has 1. Neither hits the
    // default threshold of 3, so we expect an empty list here. This
    // confirms the threshold logic is wired (not a false positive).
    expect(a.rows.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// student_subject_breakdown and roster_subject_mix
// ---------------------------------------------------------------------------

describe("student_subject_breakdown", () => {
  it("returns subject rows for an in-scope student", () => {
    const a = runAsk(
      baseInput({
        params: { kind: "student_subject_breakdown", studentName: "Alice" },
      }),
    );
    if (a.kind !== "student_subject_breakdown") throw new Error("wrong kind");
    expect(a.studentName).toBe("Alice");
    expect(a.rows.length).toBe(1);
    expect(a.rows[0].subject).toBe("Math");
    expect(a.rows[0].daysObserved).toBe(3);
  });

  it("returns empty rows for an out-of-scope student under coach filter", () => {
    const a = runAsk(
      baseInput({
        coachFilter: C2,
        params: { kind: "student_subject_breakdown", studentName: "Alice" },
      }),
    );
    if (a.kind !== "student_subject_breakdown") throw new Error("wrong kind");
    expect(a.rows.length).toBe(0);
  });
});

describe("roster_subject_mix", () => {
  it("computes current and prior averages per subject", () => {
    const a = runAsk(baseInput({ params: { kind: "roster_subject_mix" } }));
    if (a.kind !== "roster_subject_mix") throw new Error("wrong kind");
    const math = a.rows.find((r) => r.subject === "Math");
    expect(math).toBeDefined();
    expect(math!.currentAvgActual).toBeGreaterThan(0);
    expect(math!.priorAvgActual).not.toBeNull();
    expect(math!.delta).not.toBeNull();
    expect(math!.nStudents).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// clean_window highlights students who never went behind
// ---------------------------------------------------------------------------

describe("clean_window", () => {
  it("includes Alice and excludes Bob and Cara", () => {
    const a = runAsk(baseInput({ params: { kind: "clean_window" } }));
    if (a.kind !== "clean_window") throw new Error("wrong kind");
    const names = a.rows.map((r) => r.studentName);
    expect(names).toContain("Alice");
    expect(names).not.toContain("Bob");
    expect(names).not.toContain("Cara");
  });
});

// ---------------------------------------------------------------------------
// Coach filter restricts results
// ---------------------------------------------------------------------------

describe("coach filter", () => {
  it("top_xp under coachFilter=C1 includes only Alice and Bob", () => {
    const a = runAsk(
      baseInput({ coachFilter: C1, params: { kind: "top_xp", n: 10 } }),
    );
    if (a.kind !== "top_xp") throw new Error("wrong kind");
    const names = new Set(a.rows.map((r) => r.studentName));
    expect(names.has("Alice")).toBe(true);
    expect(names.has("Bob")).toBe(true);
    expect(names.has("Cara")).toBe(false);
    expect(names.has("Dan")).toBe(false);
  });

  it("scope.coachFilter is mirrored in the answer", () => {
    const a = runAsk(
      baseInput({ coachFilter: C2, params: { kind: "top_xp" } }),
    );
    expect(a.scope.coachFilter).toBe(C2);
  });

  it("unmapped students are excluded under any coachFilter", () => {
    const unmappedRoster = new Map<string, string>([
      ["Alice", C1],
      // Bob, Cara, Dan intentionally unmapped
    ]);
    const a = runAsk(
      baseInput({
        coachFilter: C1,
        studentNameToCoachEmail: unmappedRoster,
        params: { kind: "top_xp", n: 10 },
      }),
    );
    if (a.kind !== "top_xp") throw new Error("wrong kind");
    const names = new Set(a.rows.map((r) => r.studentName));
    expect(names.has("Alice")).toBe(true);
    expect(names.size).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// URL <-> params round-trip
// ---------------------------------------------------------------------------

describe("paramsFromUrl / paramsToUrl", () => {
  it("defaults to top_xp when k is missing", () => {
    const p = paramsFromUrl(new URLSearchParams(""));
    expect(p.kind).toBe("top_xp");
  });

  it("falls back to top_xp on unknown kind", () => {
    const p = paramsFromUrl(new URLSearchParams("k=not_a_real_kind"));
    expect(p.kind).toBe("top_xp");
  });

  it("parses n for top_xp", () => {
    const p = paramsFromUrl(new URLSearchParams("k=top_xp&n=25"));
    expect(p.kind).toBe("top_xp");
    if (p.kind === "top_xp") expect(p.n).toBe(25);
  });

  it("parses studentName for student_subject_breakdown", () => {
    const p = paramsFromUrl(
      new URLSearchParams("k=student_subject_breakdown&student=Alice%20B"),
    );
    expect(p.kind).toBe("student_subject_breakdown");
    if (p.kind === "student_subject_breakdown") {
      expect(p.studentName).toBe("Alice B");
    }
  });

  it("omits n when it equals the default", () => {
    const usp = paramsToUrl({ kind: "top_xp", n: 10 });
    expect(usp.get("n")).toBeNull();
    expect(usp.get("k")).toBe("top_xp");
  });

  it("emits n when it differs from the default", () => {
    const usp = paramsToUrl({ kind: "top_xp", n: 25 });
    expect(usp.get("n")).toBe("25");
  });

  it("emits student for student_subject_breakdown", () => {
    const usp = paramsToUrl({
      kind: "student_subject_breakdown",
      studentName: "Alice",
    });
    expect(usp.get("student")).toBe("Alice");
  });

  it("round-trips a concern kind unchanged", () => {
    const original = paramsToUrl({ kind: "concern_deep_deficit" });
    const parsed = paramsFromUrl(new URLSearchParams(original.toString()));
    expect(parsed.kind).toBe("concern_deep_deficit");
  });
});
