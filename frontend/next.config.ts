import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.VERCEL === "1") return [{ source: "/api/v1/:path*", destination: "/api/" }];
    const backend = (process.env.BACKEND_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  /* config options here */
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
