/**
 * Phase 7 Part 8 — Head overview page (rewritten, complete).
 *
 * Cycle D fix: imports use the real exports.
 *  - aggregate            -> aggregateRange
 *  - getSnapshotsForRange -> readRange
 *  - resolveWindow        -> now exported by ./lib/window
 *
 * aggregateRange takes a single Snapshot[] + today + {currentDays, priorDays}
 * and splits the current/prior windows internally. So we fetch ONE
 * range that spans both halves, then hand it off.
 *
 * Header import + breadcrumb. Search box (Q8-10/Q8-11) and CSV (Q8-12)
 * are inside HeadSearchAndExport. Stale-banner (Q8-8 Mechanism A).
 * WindowSelector takes sessions + currentSessionId props (Q8-9).
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Header } from "@/components/Header";
import { WindowSelector } from "@/components/WindowSelector";
import { isHeadCoach } from "@/lib/authz";
import { aggregateRange } from "@/lib/aggregate";
import { readRange } from "@/lib/githubData";
import {
  getSessions,
  findCurrentSession,
  isCalendarStale,
} from "@/lib/sessions";
import { resolveWindow } from "@/lib/window";
import { slugify } from "@/lib/slug";
import Link from "next/link";
import { HeadSearchAndExport } from "./HeadSearchAndExport";
import type { StudentMetrics } from "@/lib/aggregate";

export const dynamic = "force-dynamic";

const SESSIONS_EDITOR_URL =
  "https://github.com/kelvinchildress-coder/academic-personalization-assistant/edit/main/data/sessions.json";

interface Props {
  searchParams: { w?: string; q?: string };
}

export default async function HeadOverviewPage({ searchParams }: Props) {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");
  if (!isHeadCoach(session.user.email)) redirect("/");

  const sessions = await getSessions();
  const todayIso = new Date().toISOString().slice(0, 10);
  const currentSession = findCurrentSession(sessions, todayIso);
  const stale = isCalendarStale(sessions, todayIso);

  const wParam = searchParams.w ?? "30d";
  const qParam = (searchParams.q ?? "").trim();

  const win = resolveWindow(wParam, sessions, todayIso);

  // Fetch one continuous range that spans prior+current; aggregateRange
  // splits internally based on currentDays/priorDays.
  const allSnaps = await readRange(win.priorStart, win.currentEnd);

  const result = aggregateRange(allSnaps, win.currentEnd, {
    currentDays: win.currentDays,
    priorDays: win.priorDays,
  });

  const allStudents: StudentMetrics[] = Object.values(result.perStudent);

  // Q8-11 C: search across name, coach, concerns
  const qLower = qParam.toLowerCase();
  const filtered = qLower
    ? allStudents.filter((s) => {
        if (s.name.toLowerCase().includes(qLower)) return true;
        if (s.coach.toLowerCase().includes(qLower)) return true;
        if (s.concerns.some((c) => c.toLowerCase().includes(qLower))) return true;
        return false;
      })
    : allStudents;

  filtered.sort(
    (a, b) => b.severity - a.severity || a.name.localeCompare(b.name),
  );

  return (
    <>
      <Header
        trail={[
          { label: "Home", href: "/" },
          { label: "Head overview" },
        ]}
      />
      <main className="mx-auto max-w-7xl px-3 sm:px-6 py-4 sm:py-6">
        {stale && (
          <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm">
            <p className="font-semibold text-amber-900">
              Session calendar is out of date
            </p>
            <p className="mt-1 text-amber-900/90">
              No current session covers today and no future sessions are on
              file. Update{" "}
              <a
                href={SESSIONS_EDITOR_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-sky-700 hover:underline"
              >
                data/sessions.json
              </a>{" "}
              to add upcoming sessions for the next school year.
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900">
            Head overview — all students
          </h1>
          <WindowSelector
            value={wParam}
            sessions={sessions}
            currentSessionId={currentSession?.id ?? null}
          />
        </div>

        <p className="text-sm text-zinc-500 mb-3">
          Window: {win.label} ({win.currentDays} days) · {filtered.length} of{" "}
          {allStudents.length} student{allStudents.length === 1 ? "" : "s"}
          {qParam ? (
            <>
              {" · "}filter: <span className="font-mono">{qParam}</span>
            </>
          ) : null}
        </p>

        <HeadSearchAndExport
          rows={filtered}
          initialQuery={qParam}
          wParam={wParam}
        />

        {filtered.length === 0 ? (
          <div className="rounded-md border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
            No students match the current filter and window.
          </div>
        ) : (
          <>
            {/* Tablet+ table */}
            <div className="hidden sm:block overflow-x-auto rounded-md border border-zinc-200 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 text-zinc-600">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Student</th>
                    <th className="px-3 py-2 text-left font-medium">Coach</th>
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
                  {filtered.map((s) => (
                    <tr key={s.name} className="hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <Link
                          href={`/coach/${slugify(s.coach)}/student/${slugify(
                            s.name,
                          )}?w=${encodeURIComponent(wParam)}`}
                          className="text-sky-700 hover:underline"
                        >
                          {s.name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-zinc-700">
                        <Link
                          href={`/coach/${slugify(s.coach)}?w=${encodeURIComponent(
                            wParam,
                          )}`}
                          className="hover:underline"
                        >
                          {s.coach}
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
              {filtered.map((s) => (
                <Link
                  key={s.name}
                  href={`/coach/${slugify(s.coach)}/student/${slugify(
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
                  <div className="mt-1 text-xs text-zinc-500">{s.coach}</div>
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
