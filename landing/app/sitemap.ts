import type { MetadataRoute } from 'next'

// Emitted to out/sitemap.xml at build time (static, works with output: 'export').
const SITE_URL = 'https://voxlyai.online'

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date()
  return [
    { url: `${SITE_URL}/`,          lastModified, changeFrequency: 'weekly',  priority: 1 },
    { url: `${SITE_URL}/api-docs/`, lastModified, changeFrequency: 'monthly', priority: 0.8 },
  ]
}
