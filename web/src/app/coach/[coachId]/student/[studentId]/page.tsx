/**
 * Phase 7 Part 8 — Student detail page (Cycle I — add report download).
 *
 * Calls aggregateRange, readRange, resolveWindow.
 *
 * Phase 5 addition: two download links to /api/report/<studentId> for
 * end-of-quarter (eoq) and end-of-year (eoy) PDF reports. Plain anchor
 * tags with `download` attribute — no client JS required.
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
import { rollupSubjectTargets } from "@/lib/subjectTargets";
import { slugify } from "@/lib/slug";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface Props {
  params: { coachId: string; studentId: string };
  searchParams: { w?: string };
}

export default async function StudentDetailPage({ params, searchParams }: Props) {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");

  const guard = await requireCoachOrRedirect(session, params.coachId);
  if (!guard.ok) redirect(guard.redirect);

  const sessions = await getSessions();
  const todayIso = new Date().toISOString().slice(0, 10);
  const currentSession = findCurrentSession(sessions, todayIso);

  const wParam = searchParams.w ?? "30d";
  const win = resolveWindow(wParam, sessions, todayIso);

  const allSnaps = await readRange(win.priorStart, win.currentEnd);
  // Snapshots restricted to the current window only — used for per-subject rollup.
  const currentSnaps = allSnaps.filter(
    (s) => s.date >= win.currentStart && s.date <= win.currentEnd,
  );
  const result = aggregateRange(allSnaps, win.currentEnd, {
    currentDays: win.currentDays,
    priorDays: win.priorDays,
  });

  const studentEntry = Object.values(result.perStudent).find(
    (s) => slugify(s.name) === params.studentId,
  );
  const coachDisplayName = studentEntry?.coach ?? guard.coachName ?? params.coachId;

  if (!studentEntry || slugify(studentEntry.coach) !== params.coachId) {
    return (
      <>
        <Header
          trail={[
            { label: "Home", href: "/" },
            {
              label: coachDisplayName,
              href: `/coach/${params.coachId}?w=${encodeURIComponent(wParam)}`,
            },
            { label: "Not found" },
          ]}
        />
        <main className="mx-auto max-w-3xl px-3 sm:px-6 py-6">
          <div className="rounded-md border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
            Student not found in this coach&apos;s roster for the selected window.
          </div>
        </main>
      </>
    );
  }

  // Per-subject rollup uses ONLY the current window snapshots.
  const subjectTargets = rollupSubjectTargets(currentSnaps, studentEntry.name);

  // Phase 5: report download URLs. Plain anchors with `download` attribute.
  const reportBase = `/api/report/${params.studentId}`;
  const reportEoqHref = `${reportBase}?scope=eoq`;
  const reportEoyHref = `${reportBase}?scope=eoy`;

  return (
    <>
      <Header
        trail={[
          { label: "Home", href: "/" },
          ...(guard.coachName === ""
            ? [{ label: "Head overview", href: "/head" }]
            : []),
          {
            label: coachDisplayName,
            href: `/coach/${params.coachId}?w=${encodeURIComponent(wParam)}`,
          },
          { label: studentEntry.name },
        ]}
      />
      <main className="mx-auto max-w-4xl px-3 sm:px-6 py-4 sm:py-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900">
            {studentEntry.name}
          </h1>
          <WindowSelector
            value={wParam}
            sessions={sessions}
            currentSessionId={currentSession?.id ?? null}
          />
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          Coach: {studentEntry.coach} · Window: {win.label} ({win.currentDays}{" "}
          days)
        </p>

        {/* Headline metrics card */}
        <div className="rounded-md border border-zinc-200 bg-white p-4 sm:p-5 mb-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Days behind" value={studentEntry.daysBehind.toFixed(1)} />
          <Stat label="Deficit XP" value={studentEntry.deficitTotal.toFixed(0)} />
          <Stat
            label="Δ vs prior"
            value={
              studentEntry.deficitDelta === null
                ? "—"
                : `${studentEntry.deficitDelta >= 0 ? "+" : ""}${studentEntry.deficitDelta.toFixed(0)}`
            }
          />
          <Stat label="Severity" value={studentEntry.severity.toFixed(2)} />
        </div>

        {/* Subject Targets card (Q8-1 / Q8-2) */}
        <div className="rounded-md border border-zinc-200 bg-white p-4 sm:p-5 mb-4">
          <h2 className="text-sm font-semibold text-zinc-700 mb-3">
            Subject targets
          </h2>
          {subjectTargets.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No per-subject snapshots available in this window.
            </p>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {subjectTargets.map((t) => {
                const lowSample = t.daysObserved < 5;
                const onTrack = t.delta >= 0;
                return (
                  <li
                    key={t.subject}
                    className="py-2 flex flex-wrap items-center justify-between gap-2"
                  >
                    <div>
                      <div className="font-medium text-zinc-900">
                        {t.subject}
                      </div>
                      <div className="text-xs text-zinc-500">
                        target {t.avgTargetPerDay} XP/day · hitting{" "}
                        {t.avgActualPerDay} XP/day
                        {lowSample && (
                          <span className="ml-1 text-amber-700">
                            (based on {t.daysObserved} day
                            {t.daysObserved === 1 ? "" : "s"})
                          </span>
                        )}
                      </div>
                    </div>
                    <div
                      className={`text-sm font-medium tabular-nums ${
                        onTrack ? "text-emerald-700" : "text-rose-700"
                      }`}
                    >
                      {onTrack ? "+" : ""}
                      {t.delta} XP/day
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {studentEntry.concerns.length > 0 && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 sm:p-5 mb-4">
            <h2 className="text-sm font-semibold text-amber-900 mb-2">
              Active concerns
            </h2>
            <ul className="list-disc pl-5 text-sm text-amber-900/90 space-y-1">
              {studentEntry.concerns.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Phase 5: report download card */}
        <div className="rounded-md border border-sky-200 bg-sky-50 p-4 sm:p-5 mb-4">
          <h2 className="text-sm font-semibold text-sky-900 mb-2">
            Download report
          </h2>
          <p className="text-xs text-sky-900/80 mb-3">
            Generates a PDF summary of {studentEntry.name}&apos;s current
            standing. Confidential — for school and family use only.
          </p>
          <div className="flex flex-wrap gap-2">
            <a
              href={reportEoqHref}
              download
              className="inline-flex items-center rounded-md border border-sky-600 bg-white px-3 py-1.5 text-sm font-medium text-sky-700 hover:bg-sky-50"
            >
              End of quarter
            </a>
            <a
              href={reportEoyHref}
              download
              className="inline-flex items-center rounded-md border border-sky-600 bg-white px-3 py-1.5 text-sm font-medium text-sky-700 hover:bg-sky-50"
            >
              End of year
            </a>
          </div>
        </div>

        <div className="text-xs text-zinc-500">
          <Link
            href={`/coach/${params.coachId}?w=${encodeURIComponent(wParam)}`}
            className="text-sky-700 hover:underline"
          >
            ← Back to roster
          </Link>
        </div>
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-lg sm:text-xl font-semibold text-zinc-900 tabular-nums">
        {value}
      </div>
    </div>
  );
}
