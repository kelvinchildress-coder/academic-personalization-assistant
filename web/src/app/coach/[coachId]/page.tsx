/**
 * Phase 7 Part 8 — Per-coach roster page (Cycle D build-fix).
 *
 * Calls real exports: aggregateRange (not aggregate), readRange (not
 * getSnapshotsForRange), resolveWindow (now in window.ts).
 */

import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Header } from "@/components/Header";
import { WindowSelector } from "@/components/WindowSelector";
import { requireCoachOrRedirect } from "@/lib/authz";
import { aggregateRange } from "@/lib/aggregate";
import { readRange } from "@/lib/githubData";
import { getSessions, findCurrentSession } from "@/lib/sessions";
import { resolveWindow } from "@/lib/window";
import type { StudentMetrics } from "@/lib/aggregate";
import Link from "next/link";
import { slugify } from "@/lib/slug";

export const dynamic = "force-dynamic";

interface Props {
  params: { coachId: string };
  searchParams: { w?: string };
}

export default async function CoachRosterPage({ params, searchParams }: Props) {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");

  const guard = await requireCoachOrRedirect(session, params.coachId);
  if (!guard.ok) redirect(guard.redirect);

  const sessions = await getSessions();
  const todayIso = new Date().toISOString().slice(0, 10);
  const currentSession = findCurrentSession(sessions, todayIso);
  const wParam = searchParams.w ?? "30d";
  const win = resolveWindow(wParam, sessions, todayIso);

  // Read the union of current + prior so aggregateRange can split internally.
  const snapshots = await readRange(win.priorStart, win.currentEnd);

  const result = aggregateRange(snapshots, win.currentEnd, {
    currentDays: win.currentDays,
    priorDays: win.priorDays,
  });

  const myStudents: StudentMetrics[] = Object.values(result.perStudent).filter(
    (s) => slugify(s.coach) === params.coachId,
  );
  myStudents.sort(
    (a, b) => b.severity - a.severity || a.name.localeCompare(b.name),
  );

  const coachDisplayName =
    guard.coachName || myStudents[0]?.coach || params.coachId;

  return (
    <>
      <Header
        trail={[
          { label: "Home", href: "/" },
          ...(guard.coachName === ""
            ? [{ label: "Head overview", href: "/head" }]
            : []),
          { label: coachDisplayName },
        ]}
      />
      <main className="mx-auto max-w-6xl px-3 sm:px-6 py-4 sm:py-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900">
            {coachDisplayName} — Roster
          </h1>
          <WindowSelector
            value={wParam}
            sessions={sessions}
            currentSessionId={currentSession?.id ?? null}
          />
        </div>

        <p className="text-sm text-zinc-500 mb-4">
          Window: {win.label} ({win.currentDays} days) ·{" "}
          {myStudents.length} student
          {myStudents.length === 1 ? "" : "s"}
        </p>

        {myStudents.length === 0 ? (
          <div className="rounded-md border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
            No students found for this coach in the selected window.
          </div>
        ) : (
          <>
            {/* Tablet+ table */}
            <div className="hidden sm:block overflow-x-auto rounded-md border border-zinc-200 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 text-zinc-600">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Student</th>
                    <th className="px-3 py-2 text-right font-medium">
                      Days behind
                    </th>
                    <th className="px-3 py-2 text-right font-medium">
                      Deficit XP
                    </th>
                    <th className="px-3 py-2 text-right font-medium">
                      Δ vs prior
                    </th>
                    <th className="px-3 py-2 text-left font-medium">
                      Concerns
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {myStudents.map((s) => (
                    <tr key={s.name} className="hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <Link
                          href={`/coach/${params.coachId}/student/${slugify(
                            s.name,
                          )}?w=${encodeURIComponent(wParam)}`}
                          className="text-sky-700 hover:underline"
                        >
                          {s.name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {s.daysBehind.toFixed(1)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {s.deficitTotal.toFixed(0)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {s.deficitDelta === null
                          ? "—"
                          : `${s.deficitDelta >= 0 ? "+" : ""}${s.deficitDelta.toFixed(0)}`}
                      </td>
                      <td className="px-3 py-2 text-zinc-600">
                        {s.concerns.length === 0 ? (
                          <span className="text-zinc-400">—</span>
                        ) : (
                          s.concerns.join(", ")
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Phone cards */}
            <div className="sm:hidden space-y-2">
              {myStudents.map((s) => (
                <Link
                  key={s.name}
                  href={`/coach/${params.coachId}/student/${slugify(
                    s.name,
                  )}?w=${encodeURIComponent(wParam)}`}
                  className="block rounded-md border border-zinc-200 bg-white p-3 hover:bg-zinc-50"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-zinc-900">{s.name}</div>
                    <div className="text-xs text-zinc-500">
                      {s.daysBehind.toFixed(1)} days behind
                    </div>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-2 text-xs text-zinc-600">
                    <div>
                      Deficit:{" "}
                      <span className="tabular-nums">
                        {s.deficitTotal.toFixed(0)} XP
                      </span>
                    </div>
                    <div>
                      Δ:{" "}
                      <span className="tabular-nums">
                        {s.deficitDelta === null
                          ? "—"
                          : `${s.deficitDelta >= 0 ? "+" : ""}${s.deficitDelta.toFixed(0)}`}
                      </span>
                    </div>
                  </div>
                  {s.concerns.length > 0 && (
                    <div className="mt-1 text-xs text-zinc-500">
                      {s.concerns.join(", ")}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          </>
        )}
      </main>
    </>
  );
}
