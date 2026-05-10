"use client";

/**
 * Phase 7 Part 8 — Head page client widget: search + CSV export.
 *
 * Lives in /app/head/ as a co-located client component. The parent
 * (head/page.tsx) is a server component and passes the already-filtered
 * rows in for CSV export.
 *
 * Search:
 *   - Submits a form that updates the URL ?q=... param (and preserves ?w=...).
 *   - Server re-renders with the filtered list (Q8-11 C: name + coach + concerns).
 *   - Clearing the input and submitting removes the q param.
 *
 * CSV export:
 *   - Pure client-side Blob + download. Uses the rows already supplied
 *     by the server (the currently filtered + windowed list).
 *   - Columns (Q8-12 A): name, coach, daysPresent, targetTotal, actualTotal,
 *     deficitTotal, daysBehind, severity, concerns (semicolon-joined).
 */

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import type { StudentMetrics } from "@/lib/aggregate";

interface Props {
  rows: StudentMetrics[];
  initialQuery: string;
  wParam: string;
}

const CSV_HEADERS = [
  "name",
  "coach",
  "daysPresent",
  "targetTotal",
  "actualTotal",
  "deficitTotal",
  "daysBehind",
  "severity",
  "concerns",
] as const;

function csvEscape(s: string): string {
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function rowsToCsv(rows: StudentMetrics[]): string {
  const lines: string[] = [CSV_HEADERS.join(",")];
  for (const r of rows) {
    const cells = [
      csvEscape(r.name),
      csvEscape(r.coach),
      String(r.daysPresent),
      r.targetTotal.toFixed(0),
      r.actualTotal.toFixed(0),
      r.deficitTotal.toFixed(0),
      r.daysBehind.toFixed(2),
      r.severity.toFixed(2),
      csvEscape(r.concerns.join("; ")),
    ];
    lines.push(cells.join(","));
  }
  return lines.join("\n");
}

function downloadCsv(filename: string, body: string) {
  const blob = new Blob([body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function HeadSearchAndExport({ rows, initialQuery, wParam }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [query, setQuery] = useState(initialQuery);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const usp = new URLSearchParams(params.toString());
    const trimmed = query.trim();
    if (trimmed) usp.set("q", trimmed);
    else usp.delete("q");
    if (!usp.has("w") && wParam) usp.set("w", wParam);
    startTransition(() => {
      router.push(`${pathname}?${usp.toString()}`);
    });
  }

  function onClear() {
    setQuery("");
    const usp = new URLSearchParams(params.toString());
    usp.delete("q");
    startTransition(() => {
      router.push(`${pathname}?${usp.toString()}`);
    });
  }

  function onExport() {
    const today = new Date().toISOString().slice(0, 10);
    const filename = `tsa-head-overview_${today}_w-${wParam}${
      initialQuery ? `_q-${initialQuery.replace(/[^a-z0-9]/gi, "-")}` : ""
    }.csv`;
    downloadCsv(filename, rowsToCsv(rows));
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <form onSubmit={onSubmit} className="flex flex-1 min-w-[220px] items-center gap-2">
        <label className="sr-only" htmlFor="head-search">
          Search students, coaches, concerns
        </label>
        <input
          id="head-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, coach, or concern…"
          className="flex-1 min-w-[180px] rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
        />
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          Search
        </button>
        {initialQuery && (
          <button
            type="button"
            onClick={onClear}
            disabled={pending}
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            Clear
          </button>
        )}
      </form>
      <button
        type="button"
        onClick={onExport}
        disabled={rows.length === 0}
        className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
        title="Export currently filtered view as CSV"
      >
        Export CSV
      </button>
    </div>
  );
}
