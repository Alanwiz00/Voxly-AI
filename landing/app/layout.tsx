import type { Metadata } from 'next'
import './globals.css'

const SITE_URL = 'https://voxlyai.online'
const APP_URL  = 'https://app.voxlyai.online'
const OG_IMAGE = `${APP_URL}/og-image.png`

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default:  'VoxlyAI | Your Voice, Amplified',
    template: '%s | VoxlyAI',
  },
  description:
    'VoxlyAI learns your writing style and generates platform-native posts for Twitter, Instagram, Facebook, and Telegram that sound like you wrote them. Full REST API included.',
  keywords: [
    'AI content generator',
    'social media AI',
    'AI writing assistant',
    'Twitter content AI',
    'Instagram caption generator',
    'Facebook post generator',
    'Telegram content AI',
    'AI ghostwriter',
    'voice learning AI',
    'social media automation',
    'content creation tool',
    'VoxlyAI',
  ],
  authors:   [{ name: 'VoxlyAI', url: SITE_URL }],
  creator:   'VoxlyAI',
  publisher: 'VoxlyAI',
  robots: {
    index:     true,
    follow:    true,
    googleBot: { index: true, follow: true },
  },
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    type:        'website',
    siteName:    'VoxlyAI',
    title:       'VoxlyAI | Your Voice, Amplified',
    description: 'AI that learns your writing style and generates platform-native posts that sound like you wrote them. Twitter, Instagram, Facebook, Telegram.',
    url:         SITE_URL,
    images: [
      {
        url:    OG_IMAGE,
        width:  1200,
        height: 630,
        alt:    'VoxlyAI - Your Voice, Amplified',
      },
    ],
  },
  twitter: {
    card:        'summary_large_image',
    title:       'VoxlyAI | Your Voice, Amplified',
    description: 'AI that learns your writing style and generates posts that sound like you, not like a robot.',
    images:      [OG_IMAGE],
    creator:     '@voxlyai',
  },
  icons: {
    icon: [{ url: '/favicon.svg', type: 'image/svg+xml' }],
  },
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  name: 'VoxlyAI',
  url: SITE_URL,
  description:
    'AI content generator that learns your writing style and creates platform-native social media posts for Twitter, Instagram, Facebook, and Telegram.',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'USD',
    description: 'Free to start. API keys generated instantly.',
  },
  creator: {
    '@type': 'Organization',
    name: 'VoxlyAI',
    url: SITE_URL,
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </body>
    </html>
  )
}
