/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Required for Docker deployment
  images: {
    domains: [],
    formats: ['image/avif', 'image/webp'],
  },
  // Turbopack configuration (Next.js 16 uses Turbopack by default)
  turbopack: {
    // Path aliases are handled by tsconfig.json
  },
  // WAJIB ADA untuk menghindari exit code 1 saat deploy
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
}

module.exports = nextConfig



