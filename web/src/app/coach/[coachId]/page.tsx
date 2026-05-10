/**
 * Phase 7 Part 8 — Per-coach roster page (rewritten).
 *
 * Changes from Part 6:
 *  - Header import + breadcrumb trail.
 *  - Email-map authz via requireCoachOrRedirect (Q8-6/Q8-7).
 *  - Responsive: dense table on >=640px, stacked cards on <640px (Q8-5 C).
 *  - WindowSelector now takes sessions + currentSessionId props (Q8-9).
 *  - Subject-target hint in each row when daysObserved < 5 is suppressed
 *    here (per-row aggregation lives on the student detail page).
 *
 * Window resolution (?w=...):
 *   "30d"             -> 30 days
 *   "year"            -> 365 days
 *   "<sessionId>"     -> session.startDate..session.endDate
 *   default           -> "30d"
 */

import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Header } from "@/components/Header";
import { WindowSelector } from "@/components/WindowSelector";
import { requireCoachOrRedirect } from "@/lib/authz";
import { aggregate } from "@/lib/aggregate";
import { getSnapshotsForRange } from "@/lib/githubData";
import { getSessions, findCurrentSession, sessionDays } from "@/lib/sessions";
import { resolveWindow } from "@/lib/window";
import type { StudentMetrics } from "@/lib/aggregate";
import type { Session } from "@/lib/types";
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
  const windowResolution = resolveWindow(wParam, sessions, todayIso);

  // Pull snapshots for the resolved current+prior windows.
  const snapshots = await getSnapshotsForRange(
    windowResolution.currentStart,
    windowResolution.currentEnd
  );
  const priorSnapshots = await getSnapshotsForRange(
    windowResolution.priorStart,
    windowResolution.priorEnd
  );

  const result = aggregate(snapshots, priorSnapshots, {
    currentDays: windowResolution.currentDays,
    priorDays: windowResolution.priorDays,
  });

  // Filter to this coach's roster. Head coach sees the requested coach's
  // roster; the requested coachId slug determines which.
  const myStudents: StudentMetrics[] = Object.values(result.perStudent).filter(
    (s) => slugify(s.coach) === params.coachId
  );
  myStudents.sort((a, b) => b.severity - a.severity || a.name.localeCompare(b.name));

  // Display name for breadcrumb. Head coach: derive from any matching
  // student's coach field; Coach: from their own resolved name.
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
          Window: {windowResolution.label} ({windowResolution.currentDays} days
          observed) · {myStudents.length} student
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
                    <th className="px-3 py-2 text-right font-medium">Days behind</th>
                    <th className="px-3 py-2 text-right font-medium">Deficit XP</th>
                    <th className="px-3 py-2 text-right font-medium">Δ vs prior</th>
                    <th className="px-3 py-2 text-left font-medium">Concerns</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {myStudents.map((s) => (
                    <tr key={s.name} className="hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <Link
                          href={`/coach/${params.coachId}/student/${slugify(s.name)}?w=${encodeURIComponent(wParam)}`}
                          className="text-sky-700 hover:underline"
                        >
                          {s.name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{s.daysBehind.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{s.deficitTotal.toFixed(0)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {s.deficitDelta >= 0 ? "+" : ""}
                        {s.deficitDelta.toFixed(0)}
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
                  href={`/coach/${params.coachId}/student/${slugify(s.name)}?w=${encodeURIComponent(wParam)}`}
                  className="block rounded-md border border-zinc-200 bg-white p-3 hover:bg-zinc-50"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-zinc-900">{s.name}</div>
                    <div className="text-xs text-zinc-500">
                      {s.daysBehind.toFixed(1)} days behind
                    </div>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-2 text-xs text-zinc-600">
                    <div>Deficit: <span className="tabular-nums">{s.deficitTotal.toFixed(0)} XP</span></div>
                    <div>Δ: <span className="tabular-nums">{s.deficitDelta >= 0 ? "+" : ""}{s.deficitDelta.toFixed(0)}</span></div>
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
