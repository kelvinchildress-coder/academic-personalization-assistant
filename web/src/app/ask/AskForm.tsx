"use client";

/**
 * Phase 6 — Ask palette UI.
 *
 * Client component. Renders:
 *   - A grid of 12 palette tiles (one per AskKind).
 *   - Per-kind param controls (n, student name) for the currently selected kind.
 *   - A "Run" button that pushes /ask?w=...&k=...&... into the URL.
 *
 * URL is the source of truth. The selected palette tile reflects the
 * current `?k=` value. Submitting builds a new URL and routes to it,
 * which re-renders the server page with fresh data.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  DEFAULT_TOP_N,
  MAX_TOP_N,
  paramsToUrl,
} from "@/lib/askKinds";
import {
  ASK_KIND_HELP,
  ASK_KIND_LABEL,
  type AskKind,
  type AskParams,
} from "@/lib/types";

interface Props {
  initialParams: AskParams;
  /** Current window param string (e.g. "30d" or "2026-27-S1"). */
  preserveWindow: string;
}

const ORDERED_KINDS: AskKind[] = [
  "top_xp",
  "bottom_xp",
  "deficit_increase",
  "deficit_decrease",
  "concern_behind_multiple_days",
  "concern_deep_deficit",
  "concern_gap_not_closing",
  "concern_frequent_exceptions",
  "no_activity",
  "student_subject_breakdown",
  "roster_subject_mix",
  "clean_window",
];

const KINDS_WITH_N = new Set<AskKind>([
  "top_xp",
  "bottom_xp",
  "deficit_increase",
  "deficit_decrease",
]);

export function AskForm({ initialParams, preserveWindow }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [kind, setKind] = useState<AskKind>(initialParams.kind);
  const [n, setN] = useState<number>(
    "n" in initialParams && initialParams.n !== undefined
      ? initialParams.n
      : DEFAULT_TOP_N,
  );
  const [studentName, setStudentName] = useState<string>(
    initialParams.kind === "student_subject_breakdown"
      ? initialParams.studentName
      : "",
  );

  function buildParams(): AskParams {
    switch (kind) {
      case "top_xp":
      case "bottom_xp":
      case "deficit_increase":
      case "deficit_decrease":
        return { kind, n };
      case "student_subject_breakdown":
        return { kind, studentName };
      default:
        return { kind };
    }
  }

  function onRun(e: React.FormEvent) {
    e.preventDefault();
    const usp = paramsToUrl(buildParams());
    // Preserve the window param.
    const w = sp.get("w") ?? preserveWindow;
    if (w) usp.set("w", w);
    router.push(`/ask?${usp.toString()}`);
  }

  return (
    <form onSubmit={onRun} className="space-y-4">
      <div>
        <h2 className="text-sm font-medium text-zinc-700">Pick a question</h2>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {ORDERED_KINDS.map((k) => {
            const selected = k === kind;
            return (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={
                  "rounded-md border px-3 py-2 text-left text-sm transition-colors " +
                  (selected
                    ? "border-sky-500 bg-sky-50 text-sky-900"
                    : "border-zinc-200 bg-white text-zinc-800 hover:border-zinc-300 hover:bg-zinc-50")
                }
                aria-pressed={selected}
              >
                <div className="font-medium">{ASK_KIND_LABEL[k]}</div>
                <div className="mt-0.5 text-xs text-zinc-500">
                  {ASK_KIND_HELP[k]}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Per-kind controls */}
      <div className="flex flex-wrap items-end gap-3">
        {KINDS_WITH_N.has(kind) ? (
          <label className="inline-flex flex-col text-sm text-zinc-700">
            <span className="mb-1">How many</span>
            <input
              type="number"
              min={1}
              max={MAX_TOP_N}
              value={n}
              onChange={(e) =>
                setN(Math.max(1, Math.min(MAX_TOP_N, Number(e.target.value) || DEFAULT_TOP_N)))
              }
              className="w-24 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </label>
        ) : null}

        {kind === "student_subject_breakdown" ? (
          <label className="inline-flex flex-col text-sm text-zinc-700">
            <span className="mb-1">Student name</span>
            <input
              type="text"
              value={studentName}
              onChange={(e) => setStudentName(e.target.value)}
              placeholder="e.g. Alice Lopez"
              className="w-64 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </label>
        ) : null}

        <button
          type="submit"
          className="rounded-md bg-sky-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-400"
        >
          Run
        </button>
      </div>
    </form>
  );
}
