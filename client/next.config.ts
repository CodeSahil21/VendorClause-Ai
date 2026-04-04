import type { NextConfig } from "next";

const backendApiBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000/api/v1').replace(/\/$/, '');

const nextConfig: NextConfig = {
  reactStrictMode: false,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendApiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
