import { notFound, redirect } from "next/navigation";
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
  params: { coachId: string };
  searchParams: { window?: string | string[] };
}

/**
 * Phase 7 Part 6 — Per-coach roster page (rev 2).
 *
 * URL: /coach/[coachId][?window=30d|session|year]
 *
 * Authz (Q5-3 = a): head coach OR own roster (slug match).
 *
 * Changes from Phase 7 Part 5 rev 1:
 *   - Bug fix: result.perStudent (was result.students)
 *   - Bug fix: row.name (was row.studentName)
 *   - Bug fix: AggregateOptions key currentDays (was currentWindowDays)
 *   - Window dropdown integration (Q6-3 = c)
 */
export default async function CoachRosterPage({
  params,
  searchParams,
}: PageProps) {
  const session = await auth();
  const viewerEmail = session?.user?.email ?? null;
  if (!viewerEmail) redirect("/login");

  const slug = params.coachId.toLowerCase();
  const window = parseWindowParam(searchParams?.window);

  const dates = await listHistoryDates();
  if (dates.length === 0) return <Shell title="No data yet" />;
  const today = dates[dates.length - 1];

  const snaps = await readRange(today, window.days);
  const latest = snaps[snaps.length - 1];
  if (!latest) return <Shell title="No data yet" />;

  const idx = buildCoachIndex(latest.students);
  const coachName = idx.bySlug.get(slug);
  if (!coachName) notFound();

  const viewerSlug = slugifyName(session?.user?.name ?? "");
  const isOwnRoster = !!viewerSlug && viewerSlug === slug;
  const allowed = isHeadCoach(viewerEmail) || isOwnRoster;
  if (!allowed) {
    return (
      <Shell title="Not authorized">
        You don&apos;t have access to {coachName}&apos;s roster. Coaches can
        only view their own students.
      </Shell>
    );
  }

  const coachSnaps = snaps.map((snap) => ({
    ...snap,
    students: snap.students.filter((s) => s.coach === coachName),
  }));
  const result = aggregateRange(coachSnaps, today, {
    currentDays: window.days,
  });

  const studentRows = Object.values(result.perStudent)
    .slice()
    .sort((a, b) => b.severity - a.severity);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Roster — {coachName}
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            {window.label} through {today}. {studentRows.length} students.
          </p>
          {isHeadCoach(viewerEmail) && (
            <p className="mt-2 text-xs text-gray-500">
              Viewing as head coach.{" "}
              <Link href="/head" className="underline hover:text-gray-900">
                All-coach overview
              </Link>
            </p>
          )}
        </div>
        <WindowSelector />
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
              const studentSlug = slugifyName(row.name);
              const topConcern = row.concerns[0] ?? "—";
              return (
                <tr
                  key={row.name}
                  className="border-b border-gray-200 hover:bg-gray-50"
                >
                  <td className="px-3 py-2">
                    <Link
                      href={`/coach/${slug}/student/${studentSlug}`}
                      className="text-blue-700 hover:underline"
                    >
                      {row.name}
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

function Shell({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-xl font-semibold text-gray-900">{title}</h1>
      {children && <p className="text-sm text-gray-700">{children}</p>}
    </main>
  );
}
