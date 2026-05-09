import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/auth";
import { listHistoryDates, readRange } from "@/lib/githubData";
import { aggregateRange } from "@/lib/aggregate";
import { buildCoachIndex, slugifyName } from "@/lib/slug";
import { isHeadCoach } from "@/lib/authz";
import { parseWindowParam } from "@/lib/window";
import WindowSelector from "@/components/WindowSelector";
import type { Snapshot, SubjectSnap } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

interface PageProps {
  params: { coachId: string; studentId: string };
  searchParams: { window?: string | string[] };
}

interface ExceptionEvent {
  date: string;
  subject: string;
  fromTier: string;
  toTier: string;
}

/**
 * Phase 7 Part 6 — Per-student detail page.
 *
 * URL: /coach/[coachId]/student/[studentId][?window=30d|session|year]
 *
 * Authorization: head coach OR the student's own coach (slug match between
 * params.coachId and slugify(session.user.name)).
 *
 * Sections (Q6-1 = b):
 *   1. Subject table (today's snapshot per subject).
 *   2. Active concerns (from aggregateRange.perStudent[name].concerns).
 *   3. Recent exception log (tier transitions across the window).
 *   4. Per-subject sparklines (target vs actual over the window).
 */
export default async function StudentDetailPage({
  params,
  searchParams,
}: PageProps) {
  const session = await auth();
  const viewerEmail = session?.user?.email ?? null;
  if (!viewerEmail) redirect("/login");

  const coachSlug = params.coachId.toLowerCase();
  const studentSlug = params.studentId.toLowerCase();
  const window = parseWindowParam(searchParams?.window);

  const dates = await listHistoryDates();
  if (dates.length === 0) return <Empty title="No data yet" />;
  const today = dates[dates.length - 1];

  const snaps = await readRange(today, window.days);
  const latest = snaps[snaps.length - 1];
  if (!latest) return <Empty title="No data yet" />;

  const idx = buildCoachIndex(latest.students);
  const coachName = idx.bySlug.get(coachSlug);
  if (!coachName) notFound();

  // Authz.
  const viewerSlug = slugifyName(session?.user?.name ?? "");
  const isOwnRoster = !!viewerSlug && viewerSlug === coachSlug;
  if (!isHeadCoach(viewerEmail) && !isOwnRoster) {
    return (
      <Empty title="Not authorized">
        You don&apos;t have access to {coachName}&apos;s students.
      </Empty>
    );
  }

  // Find student in latest snapshot.
  const student = latest.students.find(
    (s) => s.coach === coachName && slugifyName(s.name) === studentSlug,
  );
  if (!student) notFound();

  // Per-student aggregate (window restricted to this one student).
  const studentSnaps: Snapshot[] = snaps.map((s) => ({
    ...s,
    students: s.students.filter(
      (st) => st.coach === coachName && st.name === student.name,
    ),
  }));
  const result = aggregateRange(studentSnaps, today, {
    currentDays: window.days,
  });
  const metrics = result.perStudent[student.name];

  // Build exception log: walk back through snapshots and emit a row each
  // time a subject's tier transitions between consecutive days.
  const events: ExceptionEvent[] = [];
  for (let i = 1; i < studentSnaps.length; i++) {
    const prev = studentSnaps[i - 1].students[0];
    const curr = studentSnaps[i].students[0];
    if (!prev || !curr) continue;
    const prevBy = new Map(prev.subjects.map((s) => [s.name, s.tier]));
    for (const subj of curr.subjects) {
      const prevTier = prevBy.get(subj.name);
      if (prevTier && prevTier !== subj.tier) {
        events.push({
          date: studentSnaps[i].date,
          subject: subj.name,
          fromTier: prevTier,
          toTier: subj.tier,
        });
      }
    }
  }
  events.reverse(); // most-recent first

  // Build per-subject sparkline data.
  const subjectNames = student.subjects.map((s) => s.name);
  const sparklineData: Record<string, Array<{ target: number; actual: number }>> = {};
  for (const name of subjectNames) {
    sparklineData[name] = studentSnaps.map((s) => {
      const subj: SubjectSnap | undefined = s.students[0]?.subjects.find(
        (x) => x.name === name,
      );
      return {
        target: subj?.target_xp ?? 0,
        actual: subj?.actual_xp ?? 0,
      };
    });
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs text-gray-500">
            <Link
              href={`/coach/${coachSlug}`}
              className="underline hover:text-gray-700"
            >
              ← {coachName}&apos;s roster
            </Link>
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">
            {student.name}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {window.label} through {today}.
          </p>
        </div>
        <WindowSelector />
      </header>

      <section className="mb-8">
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-600">
          Subjects (today)
        </h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left text-xs uppercase text-gray-600">
              <th className="px-3 py-2 font-medium">Subject</th>
              <th className="px-3 py-2 font-medium text-right">Target XP</th>
              <th className="px-3 py-2 font-medium text-right">Actual XP</th>
              <th className="px-3 py-2 font-medium text-right">Deficit</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Tier</th>
            </tr>
          </thead>
          <tbody>
            {student.subjects.map((subj) => {
              const deficit = Math.max(0, subj.target_xp - subj.actual_xp);
              return (
                <tr
                  key={subj.name}
                  className="border-b border-gray-200"
                >
                  <td className="px-3 py-2">{subj.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{subj.target_xp}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{subj.actual_xp}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-amber-700">
                    {deficit || "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        subj.status === "on_track"
                          ? "text-green-700"
                          : "text-amber-700"
                      }
                    >
                      {subj.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-600">{subj.tier}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="mb-8">
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-600">
          Active concerns
        </h2>
        {!metrics || metrics.concerns.length === 0 ? (
          <p className="text-sm text-green-700">On track. No active concerns.</p>
        ) : (
          <ul className="text-sm">
            {metrics.concerns.map((c) => (
              <li key={c} className="border-b border-gray-200 px-3 py-2">
                <span className="text-amber-700">{c}</span>
                <span className="ml-3 text-xs text-gray-500">
                  severity {metrics.severity.toFixed(2)} · {metrics.daysBehind} XP-days behind
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-600">
          Recent tier changes
        </h2>
        {events.length === 0 ? (
          <p className="text-sm text-gray-700">
            No tier transitions in the {window.label.toLowerCase()}.
          </p>
        ) : (
          <ul className="text-sm">
            {events.slice(0, 20).map((e, i) => (
              <li key={i} className="border-b border-gray-200 px-3 py-2">
                <span className="text-xs text-gray-500">{e.date}</span>
                <span className="ml-3">{e.subject}:</span>
                <span className="ml-2 text-gray-600">
                  {e.fromTier} → <span className="font-medium">{e.toTier}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-600">
          Target vs actual (per subject)
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {subjectNames.map((name) => (
            <Sparkline key={name} subject={name} data={sparklineData[name]} />
          ))}
        </div>
      </section>
    </main>
  );
}

function Sparkline({
  subject,
  data,
}: {
  subject: string;
  data: Array<{ target: number; actual: number }>;
}) {
  const w = 280;
  const h = 60;
  const max = Math.max(1, ...data.flatMap((d) => [d.target, d.actual]));
  const x = (i: number) => (data.length <= 1 ? 0 : (i / (data.length - 1)) * w);
  const y = (v: number) => h - (v / max) * h;
  const path = (key: "target" | "actual") =>
    data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join(" ");
  return (
    <div className="rounded border border-gray-200 p-3">
      <p className="mb-1 text-xs font-medium text-gray-700">{subject}</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-16 w-full">
        <path d={path("target")} fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeDasharray="3 3" />
        <path d={path("actual")} fill="none" stroke="#1d4ed8" strokeWidth="1.5" />
      </svg>
      <p className="mt-1 text-[10px] uppercase tracking-wide text-gray-500">
        — actual · - - target
      </p>
    </div>
  );
}

function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-xl font-semibold text-gray-900">{title}</h1>
      {children && <p className="text-sm text-gray-700">{children}</p>}
    </main>
  );
}
