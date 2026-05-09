import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/auth";
import { listHistoryDates, readRange } from "@/lib/githubData";
import { aggregateRange, DEFAULT_CURRENT_WINDOW_DAYS } from "@/lib/aggregate";
import { buildCoachIndex, slugifyName } from "@/lib/slug";
import { isHeadCoach } from "@/lib/authz";

export const dynamic = "force-dynamic";
export const revalidate = 0;

/**
 * Phase 7 Part 5 — Per-coach roster page.
 *
 * URL: /coach/[coachId]   where coachId is a display-name slug.
 *
 * Authorization model (Q5-3 = a):
 *   - Head coach can view any roster.
 *   - Non-head viewers can ONLY view their own roster, where "own" is
 *     determined by matching the slug derived from session.user.name to
 *     the URL slug.
 *
 * Why slug-match instead of an email-to-coach-name lookup? The snapshot
 * schema does not (yet) carry coach emails -- only display names. The
 * OAuth session carries email + name. The cleanest bridge today is:
 * slugify(session.user.name) === params.coachId. Phase 8 (data
 * enrichment, future) can replace this with an explicit coach-email
 * mapping if needed.
 */

const ROSTER_WINDOW_DAYS = 30;

interface PageProps {
  params: { coachId: string };
}

export default async function CoachRosterPage({ params }: PageProps) {
  const session = await auth();
  const viewerEmail = session?.user?.email ?? null;
  if (!viewerEmail) {
    redirect("/login");
  }

  const slug = params.coachId.toLowerCase();

  // 1. Load most recent snapshot to resolve slug -> coach name.
  const dates = await listHistoryDates();
  if (dates.length === 0) {
    return <NoDataView reason="no-history" />;
  }
  const today = dates[dates.length - 1];

  const window = await readRange(today, ROSTER_WINDOW_DAYS);
  const latest = window[window.length - 1];
  if (!latest) {
    return <NoDataView reason="empty-latest" />;
  }

  const idx = buildCoachIndex(latest.students);
  const coachName = idx.bySlug.get(slug);
  if (!coachName) {
    notFound();
  }

  // 2. Authorization check.
  const viewerName = session?.user?.name ?? "";
  const viewerSlug = slugifyName(viewerName);
  const isOwnRoster = !!viewerSlug && viewerSlug === slug;
  const allowed = isHeadCoach(viewerEmail) || isOwnRoster;

  if (!allowed) {
    return <ForbiddenView coachName={coachName} />;
  }

  // 3. Restrict snapshot window to this coach's students only.
  const coachWindow = window.map((snap) => ({
    ...snap,
    students: snap.students.filter((s) => s.coach === coachName),
  }));

  // 4. Aggregate.
  const result = aggregateRange(coachWindow, today, {
    currentWindowDays: DEFAULT_CURRENT_WINDOW_DAYS,
  });

  // 5. Render.
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
        <p className="text-sm text
