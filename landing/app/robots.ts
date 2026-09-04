import type { MetadataRoute } from 'next'

// Emitted to out/robots.txt at build time (static, works with output: 'export').
const SITE_URL = 'https://voxlyai.online'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
