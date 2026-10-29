import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Give concurrent development servers separate output directories and locks.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
