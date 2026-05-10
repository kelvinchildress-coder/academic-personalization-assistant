"use client";

/**
 * Phase 7 Part 8 — WindowSelector (rewritten).
 *
 * Q6-3: window dropdown is URL-persisted via the `?w=...` query param.
 * Q8-9 (A): the "session" option is now a dynamic list of session IDs
 * read from data/sessions.json and supplied by the parent server
 * component as the `sessions` prop. URL persists session id directly.
 *
 * Window options:
 *   - "30d"          last 30 days from today
 *   - "year"         last 365 days from today
 *   - "<sessionId>"  one entry per session (e.g. "2025-26-S5")
 *
 * The current selection is read by the parent page (server side) from
 * searchParams.w and passed in as `value`. On change, we route to the
 * same path with an updated `?w=...`.
 */

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { Session } from "@/lib/types";

interface Props {
  value: string;
  sessions: Session[];
  /** When true, indicates currentSessionId for the leading "Current session" entry. */
  currentSessionId?: string | null;
}

export function WindowSelector({ value, sessions, currentSessionId }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    const usp = new URLSearchParams(params.toString());
    usp.set("w", next);
    startTransition(() => {
      router.push(`${pathname}?${usp.toString()}`);
    });
  }

  // Sessions are sorted ascending by startDate; we display newest-first.
  const sessionsDesc = [...sessions].sort((a, b) =>
    b.startDate.localeCompare(a.startDate)
  );

  return (
    <label className="inline-flex items-center gap-2 text-sm text-zinc-700">
      <span className="text-zinc-500">Window:</span>
      <select
        value={value}
        onChange={onChange}
        disabled={pending}
        aria-label="Select time window"
        className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-50"
      >
        <option value="30d">Last 30 days</option>
        <option value="year">Last 365 days</option>
        {currentSessionId ? (
          <optgroup label="Current">
            {sessionsDesc
              .filter((s) => s.id === currentSessionId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.startDate} → {s.endDate})
                </option>
              ))}
          </optgroup>
        ) : null}
        <optgroup label="All sessions">
          {sessionsDesc
            .filter((s) => s.id !== currentSessionId)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.startDate} → {s.endDate})
              </option>
            ))}
        </optgroup>
      </select>
    </label>
  );
}
