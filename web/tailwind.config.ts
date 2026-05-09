import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Concern severity colors used across digest_v2-style badges.
        severity: {
          low: "#16a34a",     // green-600
          medium: "#ca8a04",  // yellow-600
          high: "#dc2626",    // red-600
        },
      },
    },
  },
  plugins: [],
};

export default config;
