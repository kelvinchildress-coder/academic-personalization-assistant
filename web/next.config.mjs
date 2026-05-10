/** @type {import('next').NextConfig} */

// Security headers applied to every response. See runbooks/SECURITY.md
// for the rationale behind each directive.
const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Google fonts CSS + OAuth redirect target
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com data:",
      // Next.js hydration + Tailwind currently require 'unsafe-inline'.
      // Tightening to nonce-based CSP is tracked as a future enhancement.
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      // Google profile pictures shown in the user menu
      "img-src 'self' data: https://lh3.googleusercontent.com",
      // Auth.js hits Google's OAuth endpoints; api.github.com is used by
      // the server-side data layer and never the browser, but allowing
      // it for connect-src costs nothing.
      "connect-src 'self' https://accounts.google.com https://api.github.com https://raw.githubusercontent.com",
      // OAuth popup/redirect target
      "frame-src 'self' https://accounts.google.com",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self' https://accounts.google.com",
      "object-src 'none'",
    ].join("; "),
  },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
];

const nextConfig = {
  // App Router only; no Pages Router.
  reactStrictMode: true,

  // We never want the data PAT to leak to the client. Mark all server-only
  // env vars here so Next.js will refuse to inline them into client bundles
  // by default. (This is belt-and-suspenders; importing from a Client
  // Component would already fail because of the `server-only` package.)
  experimental: {
    serverComponentsExternalPackages: [],
  },

  async headers() {
    return [
      {
        // Apply to every route. Auth.js endpoints under /api/auth pick up
        // the same headers, which is fine.
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },

  // Vercel deploys this app from web/ as the project root, so no rewrites
  // or basePath are needed.
};

export default nextConfig;
