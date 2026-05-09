/** @type {import('next').NextConfig} */
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

  // Vercel deploys this app from web/ as the project root, so no rewrites
  // or basePath are needed.
};

export default nextConfig;
