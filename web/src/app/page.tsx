import { auth, signOut } from "@/auth";

/**
 * Placeholder landing page. Phase 7 Part 5 replaces this with the
 * coach-roster routing logic. For now we just confirm auth works and
 * give the user a way to sign out.
 */
export default async function HomePage() {
  const session = await auth();
  const email = session?.user?.email ?? "(unknown)";
  const name = session?.user?.name ?? null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-4 text-2xl font-semibold text-gray-900">
        TSA Academic Dashboard
      </h1>

      <p className="mb-6 text-sm text-gray-700">
        You are signed in as <strong>{name ?? email}</strong>{" "}
        <span className="text-gray-500">({email})</span>.
      </p>

      <p className="mb-8 text-sm text-gray-600">
        Roster pages are coming in Phase 7 Part 5.
      </p>

      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/login" });
        }}
      >
        <button
          type="submit"
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50"
        >
          Sign out
        </button>
      </form>
    </main>
  );
}
