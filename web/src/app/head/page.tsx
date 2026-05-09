import { redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/auth";
import { listHistoryDates, readRange } from "@/lib/githubData";
import { aggregateRange } from "@/lib/aggregate";
import { buildCoachIndex, slugifyName } from "@/lib/slug";
import { isHeadCoach } from "@/lib/authz";
import { parseWindowParam } from "@/lib/window";
import WindowSelector from "@/components/WindowSelector";

export const dynamic = "force-dynamic";
export const revalidate = 0;

interface PageProps {
  searchParams: { window?: string | string[] };
}

/**
 * Phase 7 Part 6 — Head-coach overview.
 *
 * URL: /head[?window=30d|session|year]
 *
 * Authorization: head coach only. Non-head viewers are redirected to their
 * own coach roster (or to /login if there's no derivable own-slug).
 *
 * Layout (Q6-2 = b): flat all-students table across every coach, sorted by
 * severity desc. Each row has click-through to per-student detail and to
 * the owning coach's roster.
 */
export default async function HeadOverviewPage({ searchParams }: PageProps) {
  const session = await auth();
  const viewerEmail = session?.user?.email ?? null;
  if (!viewerEmail) {
    redirect("/login");
  }

  if (!isHeadCoach(viewerEmail)) {
    const ownSlug = slugifyName(session?.user?.name ?? "");
    redirect(ownSlug ? `/coach/${ownSlug}` : "/");
  }

  const window = parseWindowParam(searchParams?.window);

  const dates = await listHistoryDates();
  if (dates.length === 0) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="mb-2 text-xl font-semibold text-gray-900">No data yet</h1>
        <p className="text-sm text-gray-700">
          The history store has no usable snapshots. Once the daily snapshot
          job runs, the overview will appear here.
        </p>
      </main>
    );
  }

  const today = dates[dates.length - 1];
  const snaps = await readRange(today, window.days);
  const latest = snaps[snaps.length - 1];

  const result = aggregateRange(snaps, today, {
    currentDays: window.days,
  });

  const coachIndex = latest ? buildCoachIndex(latest.students) : null;
  const allStudents = Object.values(result.perStudent)
    .slice()
    .sort((a, b) => b.severity - a.severity);

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Head-coach overview
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {window.label} through {today}. {allStudents.length} students
            across {Object.keys(result.perCoach).length} coaches.
          </p>
        </div>
        <WindowSelector />
      </header>

      {allStudents.length === 0 ? (
        <p className="text-sm text-gray-700">
          No students in the latest snapshot.
        </p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left text-xs uppercase tracking-wide text-gray-600">
              <th className="px-3 py-2 font-medium">Student</th>
              <th className="px-3 py-2 font-medium">Coach</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Top concern</th>
              <th className="px-3 py-2 font-medium text-right">Severity</th>
              <th className="px-3 py-2 font-medium text-right">XP days behind</th>
            </tr>
          </thead>
          <tbody>
            {allStudents.map((row) => {
              const coachSlug =
                coachIndex?.byName.get(row.coach) ?? slugifyName(row.coach);
              const studentSlug = slugifyName(row.name);
              const topConcern = row.concerns[0] ?? "—";
              return (
                <tr
                  key={`${row.coach}::${row.name}`}
                  className="border-b border-gray-200 hover:bg-gray-50"
                >
                  <td className="px-3 py-2">
                    <Link
                      href={`/coach/${coachSlug}/student/${studentSlug}`}
                      className="text-blue-700 hover:underline"
                    >
                      {row.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/coach/${coachSlug}`}
                      className="text-blue-700 hover:underline"
                    >
                      {row.coach}
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
                    {row.daysBehind}
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
