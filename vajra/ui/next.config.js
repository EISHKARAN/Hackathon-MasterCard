/** @type {import('next').NextConfig} */

// The scorer's base URL. Locally and under compose it is a local service; when deployed it is the
// hosted scorer. Set NEXT_PUBLIC_API_BASE in the deployment's environment.
//
// 127.0.0.1 rather than localhost, deliberately. Node 18+ resolves `localhost` to ::1 first, and the
// scorer binds IPv4, so `localhost` intermittently produced connection failures that looked like the
// service being down.
const API = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

module.exports = {
  reactStrictMode: true,

  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },

  experimental: {
    // CARRIES THE EVIDENCE INTO THE SERVERLESS BUNDLE.
    //
    // The screens read their JSON with a path computed at runtime, so Next's static tracing cannot
    // discover those files: it sees `fs.readFileSync(someVariable)` and has nothing to follow. The
    // build therefore succeeds, deploys, and then every screen renders its absent-artefact fallback,
    // which reads as a broken pipeline rather than a missing include.
    //
    // This directive is the designed escape hatch. The staged directory is produced by the prebuild
    // step; the two mechanisms are useless apart.
    outputFileTracingIncludes: {
      "/**": ["./reports/**"],
    },
  },
};
