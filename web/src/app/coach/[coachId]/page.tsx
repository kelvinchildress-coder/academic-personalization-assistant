import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/auth";
import { listHistoryDates, readRange } from "@/lib/githubData";
import { aggregateRange, DEFAULT_CURRENT_WINDOW_DAYS } from "@/lib/aggregate";
import { buildCoachIndex, slugifyName } from "@/lib/slug";
import { isHeadCoach } from "@/lib/authz";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const ROSTER_WINDOW_DAYS = 30;

interface PageProps {
  params: { coachId: string };
}

/**
 * Phase 7 Part 5 — Per-coach roster page.
 *
 * URL: /coach/[coachId]   where coachId is a display-name slug.
 *
 * Authorization (Q5-3 = a):
 *   - Head coach can view any roster.
 *   - Non-head viewers can only view their own roster, where ownership
 *     is determined by slugify(session.user.name) === params.coachId.
 *
 * The snapshot schema does not carry coach emails, only display names,
 * so name-slug match is the bridge between session identity and roster
 * ownership. A future schema extension can replace this with an explicit
 * coach-email mapping if needed.
 */
export default async function CoachRosterPage({ params }: PageProps) {
  const session = await auth();
  const viewerEmail = session?.user?.email ?? null;
  if (!viewerEmail) {
    redirect("/login");
  }

  const slug = params.coachId.toLowerCase();

  const dates = await listHistoryDates();
  if (dates.length === 0) {
    return (
      <Shell title="No data yet">
        <p className="text-sm text-gray-700">
          The history store has no usable snapshots. Once the daily snapshot
          job runs, the roster will appear here.
        </p>
      </Shell>
    );
  }

  const today = dates[dates.length - 1];
  const window = await readRange(today, ROSTER_WINDOW_DAYS);
  const latest = window[window.length - 1];
  if (!latest) {
    return (
      <Shell title="No data yet">
        <p className="text-sm text-gray-700">
          The latest snapshot is empty. Once the daily snapshot job runs again,
          the roster will appear here.
        </p>
      </Shell>
    );
  }

  const idx = buildCoachIndex(latest.students);
  const coachName = idx.bySlug.get(slug);
  if (!coachName) {
    notFound();
  }

  const viewerName = session?.user?.name ?? "";
  const viewerSlug = slugifyName(viewerName);
  const isOwnRoster = !!viewerSlug && viewerSlug === slug;
  const allowed = isHeadCoach(viewerEmail) || isOwnRoster;

  if (!allowed) {
    return (
      <Shell title="Not authorized">
        <p className="text-sm text-gray-700">
          You don&apos;t have access to {coachName}&apos;s roster. Coaches can
          only view their own students.
        </p>
      </Shell>
    );
  }

  const coachWindow = window.map((snap) => ({
    ...snap,
    students: snap.students.filter((s) => s.coach === coachName),
  }));

  const result = aggregateRange(coachWindow, today, {
    currentWindowDays: DEFAULT_CURRENT_WINDOW_DAYS,
  });

  const studentRows = result.students
    .slice()
    .sort((a, b) => b.severity - a.severity);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Roster — {coachName}
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Window: last {ROSTER_WINDOW_DAYS} days through {today}.{" "}
          {studentRows.length} students.
        </p>
        {isHeadCoach(viewerEmail) && (
          <p className="mt-2 text-xs text-gray-500">
            Viewing as head coach.{" "}
            <Link href="/head" className="underline hover:text-gray-900">
              All-coach overview
            </Link>
          </p>
        )}
      </header>

      {studentRows.length === 0 ? (
        <p className="text-sm text-gray-700">
          No students assigned to this coach in the latest snapshot.
        </p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left text-xs uppercase tracking-wide text-gray-600">
              <th className="px-3 py-2 font-medium">Student</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Top concern</th>
              <th className="px-3 py-2 font-medium text-right">Severity</th>
              <th className="px-3 py-2 font-medium text-right">XP days behind</th>
            </tr>
          </thead>
          <tbody>
            {studentRows.map((row) => {
              const studentSlug = slugifyName(row.studentName);
              const topConcern = row.concerns[0]?.category ?? "—";
              return (
                <tr
                  key={row.studentName}
                  className="border-b border-gray-200 hover:bg-gray-50"
                >
                  <td className="px-3 py-2">
                    <Link
                      href={`/coach/${slug}/student/${studentSlug}`}
                      className="text-blue-700 hover:underline"
                    >
                      {row.studentName}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    {row.concerns.length === 0 ? (
                      <span className="text-green-700">on track</span>
                    ) : (
                      <span className="text-amber-700">
                        {row.concerns.length} concern
                        {row.concerns.length === 1 ? "" : "s"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-700">{topConcern}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-gray-900">
                    {row.severity.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-gray-700">
                    {row.daysBehind ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-xl font-semibold text-gray-900">{title}</h1>
      {children}
    </main>
  );
}
