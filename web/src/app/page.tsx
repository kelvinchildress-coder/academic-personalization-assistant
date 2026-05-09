import { redirect } from "next/navigation";
import Link from "next/link";
import { auth, signOut } from "@/auth";
import { slugifyName } from "@/lib/slug";
import { isHeadCoach } from "@/lib/authz";

/**
 * Phase 7 Part 5 — Home page (post-login landing).
 *
 * Redirect logic (Q7-5 = B with click-through):
 *   - Head coach   -> /head            (Phase 7 Part 6 will create)
 *   - Other viewer -> /coach/[ownSlug] (own roster, derived from name)
 *
 * If the viewer is signed in but has no usable display name to derive a
 * slug from, we render a friendly fallback rather than redirect-looping.
 *
 * Middleware enforces auth on this route, but we re-check defensively.
 */
export default async function HomePage() {
  const session = await auth();
  const email = session?.user?.email ?? null;
  if (!email) {
    redirect("/login");
  }

  if (isHeadCoach(email)) {
    redirect("/head");
  }

  const name = session?.user?.name ?? "";
  const ownSlug = slugifyName(name);
  if (ownSlug) {
    redirect(`/coach/${ownSlug}`);
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-semibold text-gray-900">
        TSA Academic Dashboard
      </h1>
      <p className="mb-4 text-sm text-gray-700">
        Signed in as <strong>{email}</strong>, but we couldn&apos;t derive a
        coach roster URL from your profile name. Ask the administrator to
        confirm your account&apos;s display name matches your coach name in
        the snapshot data.
      </p>
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/login" });
        }}
      >
        <button
          type="submit"
          className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-50"
        >
          Sign out
        </button>
      </form>
      <p className="mt-6 text-xs text-gray-500">
        <Link href="/login" className="underline hover:text-gray-700">
          Back to login
        </Link>
      </p>
    </main>
  );
}
