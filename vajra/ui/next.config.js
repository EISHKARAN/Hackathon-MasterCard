/** @type {import('next').NextConfig} */
// The backend base URL. In `docker compose up` the API is at http://api:8000; locally at :8000.
// The demo path reads the committed replay bundle through this backend, so the UI never needs the net.
const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
module.exports = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
