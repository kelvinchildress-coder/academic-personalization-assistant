import NextAuth, { type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

/**
 * Texas Sports Academy — Phase 7 dashboard auth config.
 *
 * Single source of truth for who can sign in. The domain allow-list is
 * intentionally hardcoded here (not env-driven) because it represents an
 * architectural constraint on the application, not a per-deployment knob.
 * Changing the allowed domains requires a code commit + deploy.
 */

const ALLOWED_EMAIL_DOMAINS = [
  "sportsacademy.school",
  "alpha.school",
  "2hourlearning.com",
] as const;

function isAllowedEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  const at = email.lastIndexOf("@");
  if (at < 0) return false;
  const domain = email.slice(at + 1).toLowerCase();
  return (ALLOWED_EMAIL_DOMAINS as readonly string[]).includes(domain);
}

export const authConfig: NextAuthConfig = {
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  ],

  // JWT-only session strategy — no database. Default max age is 30 days.
  session: { strategy: "jwt" },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  callbacks: {
    /**
     * Reject any sign-in whose email is not on an allowed domain. Auth.js
     * surfaces this rejection on the /login page via ?error=AccessDenied.
     */
    async signIn({ user }) {
      return isAllowedEmail(user?.email);
    },

    /**
     * Mirror the user's email and name onto the JWT so server components
     * can read them without re-hitting the provider.
     */
    async jwt({ token, user }) {
      if (user) {
        token.email = user.email ?? token.email;
        token.name = user.name ?? token.name;
      }
      return token;
    },

    /**
     * Project the JWT into the session object that Server / Client
     * Components see via auth() / useSession().
     */
    async session({ session, token }) {
      if (session.user) {
        session.user.email = (token.email as string | undefined) ?? session.user.email;
        session.user.name = (token.name as string | undefined) ?? session.user.name;
      }
      return session;
    },
  },

  trustHost: true,
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);

// Re-exported for tests and any future server-side code that needs to
// validate domains independently.
export { ALLOWED_EMAIL_DOMAINS, isAllowedEmail };
