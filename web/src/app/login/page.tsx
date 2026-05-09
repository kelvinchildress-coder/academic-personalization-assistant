import { signIn } from "@/auth";

type LoginPageProps = {
  searchParams: Promise<{ error?: string; from?: string }>;
};

/**
 * Login page. Server Component — submits a server action to /api/auth/...
 * via Auth.js's signIn().
 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const errorCode = params?.error;
  const fromPath = params?.from ?? "/";

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-2xl font-semibold text-gray-900">
          TSA Academic Dashboard
        </h1>
        <p className="mb-6 text-sm text-gray-600">
          Sign in with your school Google account.
        </p>

        {errorCode ? (
          <div
            role="alert"
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            {errorMessageFor(errorCode)}
          </div>
        ) : null}

        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: fromPath });
          }}
        >
          <button
            type="submit"
            className="w-full rounded-md bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
          >
            Sign in with Google
          </button>
        </form>

        <p className="mt-6 text-xs text-gray-500">
          Access is restricted to <code>sportsacademy.school</code>,{" "}
          <code>alpha.school</code>, and <code>2hourlearning.com</code>{" "}
          email addresses.
        </p>
      </div>
    </main>
  );
}

function errorMessageFor(code: string): string {
  switch (code) {
    case "AccessDenied":
      return "That email address is not on an approved domain. Please sign in with your school Google account.";
    case "Configuration":
      return "Authentication is not configured. Please contact the dashboard administrator.";
    default:
      return "Sign-in failed. Please try again.";
  }
}
