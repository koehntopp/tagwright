import type { NextConfig } from 'next'

// Static export served by app.py under /static/ui ([ADR 0029](../docs/adr/0029-nextjs-frontend-static-export.md)).
const dev = process.env.NODE_ENV === 'development'
const nextConfig: NextConfig = {
	output: 'export',
	assetPrefix: dev ? undefined : '/static/ui',
	images: { unoptimized: true },
	turbopack: {
		rules: { '*.css': { loaders: ['@tailwindcss/turbopack'], as: '*.css' } },
	},
	// development only: proxy the API of a (scratch) Tagwright instance
	...(dev && {
		async rewrites() {
			return [{ source: '/api/:path*', destination: `${process.env.TAGWRIGHT_API || 'http://localhost:8080'}/api/:path*` }]
		},
	}),
}

export default nextConfig
