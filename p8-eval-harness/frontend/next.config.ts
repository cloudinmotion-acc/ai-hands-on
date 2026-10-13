import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    BACKEND_URL: process.env.BACKEND_URL || "http://localhost:8001",
    RESULTS_DIR: process.env.RESULTS_DIR || "../results",
  },
};

export default nextConfig;
