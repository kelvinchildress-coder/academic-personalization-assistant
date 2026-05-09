import { auth } from "@/auth";
import { NextResponse } from "next/server";

/**
 * Route gate. Every request that isn't auth or login redirects to /login
 * if the user is not signed in.
 *
 * Note: the /api/auth/* paths and Next.js internals are excluded by the
 * matcher below, so they never enter this function.
 */
export default auth((req) => {
  const isAuthed = !!req.auth;
  const url = req.nextUrl;

  // Anyone may visit /login.
  if (url.pathname.startsWith("/login")) {
    // If already signed in, bounce to home.
    if (isAuthed) return NextResponse.redirect(new URL("/", url));
    return NextResponse.next();
  }

  if (!isAuthed) {
    const loginUrl = new URL("/login", url);
    loginUrl.searchParams.set("from", url.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    // Run on every path except: Next internals (_next), Auth.js routes
    // (api/auth), and static assets in /public (favicon, images).
    "/((?!_next/static|_next/image|favicon.ico|api/auth).*)",
  ],
};
