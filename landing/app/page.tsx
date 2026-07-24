'use client'

import { useState, useEffect, useRef } from 'react'

// ─── Scroll animation hook ────────────────────────────────────────────────────

function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('[data-reveal]')
    // Mark them hidden only after hydration (avoids flash of invisible content)
    els.forEach(el => el.classList.add('animate-ready'))

    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add('is-visible')
            observer.unobserve(e.target)
          }
        })
      },
      { threshold: 0.1, rootMargin: '0px 0px -60px 0px' }
    )
    els.forEach(el => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}

// ─── Static data ──────────────────────────────────────────────────────────────

const PLATFORMS = [
  { name: 'Twitter / X', color: '#1d9bf0', bg: 'rgba(29,155,240,0.08)', border: 'rgba(29,155,240,0.22)' },
  { name: 'Instagram',   color: '#e1306c', bg: 'rgba(225,48,108,0.08)', border: 'rgba(225,48,108,0.22)' },
  { name: 'Facebook',    color: '#1877f2', bg: 'rgba(24,119,242,0.08)', border: 'rgba(24,119,242,0.22)' },
  { name: 'Telegram',    color: '#0088cc', bg: 'rgba(0,136,204,0.08)',  border: 'rgba(0,136,204,0.22)' },
]

const FEATURES = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="22"/>
        <line x1="8" y1="22" x2="16" y2="22"/>
      </svg>
    ),
    title: 'Voice Learning',
    desc: 'Upload 5 to 10 samples of your writing. VoxlyAI maps your vocabulary, sentence structure, tone, and rhythm, building a style profile that sounds uniquely like you.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
    ),
    title: 'Platform-Native',
    desc: "A Twitter thread isn't an Instagram caption. Each output is shaped for the platform's character limits, format conventions, and engagement patterns, not just reformatted.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>
        <path d="M9 18h6"/>
        <path d="M10 22h4"/>
      </svg>
    ),
    title: 'Topic Intelligence',
    desc: 'Feed it a topic name, URL, PDF, DOCX, or raw text. It extracts context and generates content grounded in your source, with current sentiment awareness.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>
        <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>
        <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>
      </svg>
    ),
    title: 'Batch Generation',
    desc: 'One API call, one topic, all four platforms simultaneously. Cross-platform campaigns in seconds instead of hours.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18"/>
        <path d="M18 17V9"/>
        <path d="M13 17V5"/>
        <path d="M8 17v-3"/>
      </svg>
    ),
    title: 'Performance Analysis',
    desc: 'Feed back impressions, likes, retweets. Get concrete green flags, red flags, and the best hook pattern per content mode.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6"/>
        <polyline points="8 6 2 12 8 18"/>
      </svg>
    ),
    title: 'API-First',
    desc: 'Full REST API with Bearer token auth. Keys start with vlx-. Integrate into CI pipelines, Slack bots, n8n, or any automation stack.',
  },
]

type SampleTab = 'twitter' | 'instagram' | 'facebook' | 'telegram'
const SAMPLE_TABS: SampleTab[] = ['twitter', 'instagram', 'facebook', 'telegram']

const SAMPLES: Record<SampleTab, { label: string; badge: string; content: string; meta: string }> = {
  twitter: {
    label: 'Twitter / X', badge: 'Thread · 7 tweets',
    content: `The biggest mistake in AI content isn't bad writing.

It's that it doesn't sound like *you*.

Here's how VoxlyAI learned my voice in 3 uploads, and started writing posts I'd actually publish: 🧵

1/ I fed it my last 30 tweets. Not the viral ones. The ones that felt most like me.

2/ It didn't copy my words. It learned my *structure*. Short punchy opener. Three-line middle. Kicker ending.

3/ First generated post? I almost thought I wrote it.

That's the test.`,
    meta: 'topic: "voice & AI" · platform: twitter · type: thread · 4s',
  },
  instagram: {
    label: 'Instagram', badge: 'Caption + hashtags',
    content: `The AI didn't write this. I did.

(Well. Sort of.)

I trained VoxlyAI on how I actually talk: the rhythm, the words I overuse, the way I end every caption with a question.

Then I asked it to write about building in public.

The draft came back sounding like me on a good day. ✨

The future of content creation isn't AI replacing you.
It's AI amplifying you.

What would you ask it to write? 👇

—
#contentcreator #AItools #buildingInPublic #creatoreconomy`,
    meta: 'topic: "building in public" · platform: instagram · type: idea · 3s',
  },
  facebook: {
    label: 'Facebook', badge: 'Long-form post',
    content: `Something interesting happened today.

I've been testing AI content tools for about six months. Most produce the same generic output regardless of who's using them.

VoxlyAI is different. I uploaded a handful of my old posts as writing samples. Within minutes it was generating content that actually sounds like something I'd write. Not in a "it used my name" way, but in a "this has my rhythm, my quirks, my way of building to a point" way.

I asked it to write about AI in content creation (meta, I know). The output didn't feel like AI. It felt like me after a second coffee.

If you create content professionally, it's worth 10 minutes of your time.`,
    meta: 'topic: "AI & content creation" · platform: facebook · type: long_form · 3s',
  },
  telegram: {
    label: 'Telegram', badge: 'Channel post · Markdown',
    content: `**Quick thought on AI writing tools**

The ones that work don't try to write *for* you. They write *as* you.

VoxlyAI ingests your samples → maps your voice → generates content that matches your actual style across platforms.

Tested across three completely different writing voices. In each case, a reader familiar with the author called the output "indistinguishable."

Worth a look: app.voxlyai.online`,
    meta: 'topic: "AI writing tools" · platform: telegram · type: long_form · 2s',
  },
}

type EndpointTab = 'generate' | 'batch' | 'source' | 'analyze'
type LangTab = 'curl' | 'js' | 'python'

const ENDPOINTS: Record<EndpointTab, { label: string; path: string; desc: string }> = {
  generate: { label: 'Generate',     path: '/generate/',              desc: 'Generate content for one platform and format. Returns up to 3 post variations.' },
  batch:    { label: 'Batch',        path: '/generate/batch',         desc: 'Generate for all four platforms in a single request.' },
  source:   { label: 'From Source',  path: '/generate/from-source',   desc: 'Generate from a URL, file (PDF, DOCX, image), or raw text.' },
  analyze:  { label: 'Performance',  path: '/analyze/performance',    desc: 'Analyze post engagement metrics. Returns green flags, red flags, and the best hook pattern.' },
}

const CODE: Record<EndpointTab, Record<LangTab, string>> = {
  generate: {
    curl: `curl -X POST https://voxly-api.voxlyai.online/generate/ \\
  -H "Authorization: Bearer vlx-your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "topic_name": "AI in healthcare",
    "platform": "twitter",
    "content_type": "idea"
  }'`,
    js: `const res = await fetch(
  'https://voxly-api.voxlyai.online/generate/',
  {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer vlx-your_key_here',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic_name: 'AI in healthcare',
      platform: 'twitter',      // twitter | instagram | facebook | telegram
      content_type: 'idea',     // idea | long_form | thread | article
      // persona_id: 12,        // optional: pin a specific style profile
    }),
  }
)
const data = await res.json()
// data.results → array of generated posts`,
    python: `import httpx

resp = httpx.post(
    "https://voxly-api.voxlyai.online/generate/",
    headers={"Authorization": "Bearer vlx-your_key_here"},
    json={
        "topic_name": "AI in healthcare",
        "platform": "twitter",     # twitter | instagram | facebook | telegram
        "content_type": "idea",    # idea | long_form | thread | article
        # "persona_id": 12,        # optional: pin a specific style profile
    },
)
data = resp.json()
# data["results"] → list of generated posts`,
  },
  batch: {
    curl: `curl -X POST https://voxly-api.voxlyai.online/generate/batch \\
  -H "Authorization: Bearer vlx-your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "topic_name": "AI in healthcare",
    "content_type": "idea"
  }'

# Returns content for all four platforms simultaneously`,
    js: `const res = await fetch(
  'https://voxly-api.voxlyai.online/generate/batch',
  {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer vlx-your_key_here',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic_name: 'AI in healthcare',
      content_type: 'idea',   // idea | long_form | thread | article
    }),
  }
)
const data = await res.json()
// data.results → {
//   twitter: {...}, instagram: {...},
//   facebook: {...}, telegram: {...},
// }`,
    python: `import httpx

resp = httpx.post(
    "https://voxly-api.voxlyai.online/generate/batch",
    headers={"Authorization": "Bearer vlx-your_key_here"},
    json={
        "topic_name": "AI in healthcare",
        "content_type": "idea",   # idea | long_form | thread | article
    },
)
data = resp.json()
# data["results"] → {
#   "twitter": {...}, "instagram": {...},
#   "facebook": {...}, "telegram": {...},
# }`,
  },
  source: {
    curl: `# From a URL
curl -X POST https://voxly-api.voxlyai.online/generate/from-source \\
  -H "Authorization: Bearer vlx-your_key_here" \\
  -F "platform=twitter" \\
  -F "content_type=thread" \\
  -F "url=https://example.com/article"

# From a file (PDF, DOCX, PNG, JPG, WEBP)
curl -X POST https://voxly-api.voxlyai.online/generate/from-source \\
  -H "Authorization: Bearer vlx-your_key_here" \\
  -F "platform=instagram" \\
  -F "content_type=idea" \\
  -F "file=@/path/to/document.pdf"`,
    js: `const form = new FormData()
form.append('platform', 'twitter')
form.append('content_type', 'thread')

// Pick one source:
form.append('url', 'https://example.com/article')
// or: form.append('text', 'Raw text...')
// or: form.append('file', fileInput.files[0])

const res = await fetch(
  'https://voxly-api.voxlyai.online/generate/from-source',
  {
    method: 'POST',
    // Do NOT set Content-Type — let browser set multipart boundary
    headers: { 'Authorization': 'Bearer vlx-your_key_here' },
    body: form,
  }
)`,
    python: `import httpx

# From a URL
resp = httpx.post(
    "https://voxly-api.voxlyai.online/generate/from-source",
    headers={"Authorization": "Bearer vlx-your_key_here"},
    data={"platform": "twitter", "content_type": "thread",
          "url": "https://example.com/article"},
)

# From a file
with open("report.pdf", "rb") as f:
    resp = httpx.post(
        "https://voxly-api.voxlyai.online/generate/from-source",
        headers={"Authorization": "Bearer vlx-your_key_here"},
        data={"platform": "instagram", "content_type": "idea"},
        files={"file": ("report.pdf", f, "application/pdf")},
    )`,
  },
  analyze: {
    curl: `curl -X POST https://voxly-api.voxlyai.online/analyze/performance \\
  -H "Authorization: Bearer vlx-your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "posts": [
      {
        "text": "First post content...",
        "mode": "idea",
        "impressions": 4200,
        "likes": 312,
        "retweets": 48,
        "replies": 21
      },
      {
        "text": "Second post content...",
        "mode": "thread",
        "impressions": 1800,
        "likes": 90,
        "retweets": 12,
        "replies": 5
      }
    ]
  }'

# Minimum 3 posts required`,
    js: `const res = await fetch(
  'https://voxly-api.voxlyai.online/analyze/performance',
  {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer vlx-your_key_here',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      posts: [
        {
          text: 'Post text here...',
          mode: 'idea',           // content_type used to generate it
          impressions: 4200,
          likes: 312,
          retweets: 48,
          replies: 21,
        },
        // minimum 3 posts required
      ],
    }),
  }
)
// Returns: { green_flags, red_flags, insight,
//            best_hook_pattern, mode_performance }`,
    python: `import httpx

resp = httpx.post(
    "https://voxly-api.voxlyai.online/analyze/performance",
    headers={"Authorization": "Bearer vlx-your_key_here"},
    json={
        "posts": [
            {"text": "Post text...", "mode": "idea",
             "impressions": 4200, "likes": 312,
             "retweets": 48, "replies": 21},
            # minimum 3 posts required
        ]
    },
)
# Returns: green_flags, red_flags, insight,
#          best_hook_pattern, mode_performance`,
  },
}

const RESPONSE_EXAMPLE = `{
  "content_type": "idea",
  "results": [
    {
      "id": 1042,
      "platform": "twitter",
      "content_type": "idea",
      "title": "AI in healthcare: 3 angles",
      "content": "The hospital room of 2030 won't have fewer doctors.\\n\\nIt'll have doctors who never miss a diagnosis.\\n\\nHere's what AI actually changes in medicine, and what it doesn't: 🧵",
      "meta": { "angle": "forward-looking", "hook_type": "contrast" },
      "version": 1,
      "created_at": "2026-07-24T10:42:18.000Z"
    }
  ]
}`

// ─── Sub-components ───────────────────────────────────────────────────────────

function WaveIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <rect x="1"    y="8" width="2.5" height="4"  rx="1.25" fill="white" opacity="0.45" />
      <rect x="5"    y="5" width="3"   height="10" rx="1.5"  fill="white" opacity="0.7"  />
      <rect x="9"    y="2" width="3.5" height="16" rx="1.75" fill="white"                />
      <rect x="13.5" y="5" width="3"   height="10" rx="1.5"  fill="white" opacity="0.7"  />
      <rect x="18"   y="8" width="2.5" height="4"  rx="1.25" fill="white" opacity="0.45" />
    </svg>
  )
}

function WaveBars() {
  return (
    <div className="wave-bars justify-center">
      {Array.from({ length: 14 }, (_, i) => (
        <div key={i} className="wave-bar" />
      ))}
    </div>
  )
}

function Divider() {
  return (
    <div className="max-w-5xl mx-auto px-6">
      <div style={{ height: 1, background: 'linear-gradient(90deg, transparent, rgba(99,102,241,0.25), transparent)' }} />
    </div>
  )
}

// ─── Sections ─────────────────────────────────────────────────────────────────

function Nav() {
  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50"
      style={{ background: 'rgba(6,6,15,0.85)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(99,102,241,0.1)' }}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" className="nav-logo-wrap flex items-center gap-2.5 no-underline">
          <div
            className="logo-mark w-8 h-8 flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #818cf8, #4f46e5)', borderRadius: 8 }}
          >
            <WaveIcon size={18} />
          </div>
          <span className="font-bold text-base text-[#f0eeff] tracking-tight">VoxlyAI</span>
        </a>

        <div className="hidden md:flex items-center gap-6 text-sm">
          {['How it works:#how-it-works', 'Features:#features', 'Samples:#samples', 'API:#api'].map(item => {
            const [label, href] = item.split(':')
            return (
              <a key={label} href={href} className="nav-link text-sm">{label}</a>
            )
          })}
        </div>

        <a
          href="https://app.voxlyai.online"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-glow px-4 py-2 text-white text-sm font-semibold rounded-lg"
          style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)' }}
        >
          Get Started
        </a>
      </div>
    </nav>
  )
}

function Hero() {
  return (
    <section className="relative pt-32 pb-24 px-6 overflow-hidden">
      {/* Dot grid */}
      <div className="grid-bg absolute inset-0 pointer-events-none" />

      {/* Drifting orbs */}
      <div className="hero-orb hero-orb-1" />
      <div className="hero-orb hero-orb-2" />
      <div className="hero-orb hero-orb-3" />

      <div className="relative max-w-4xl mx-auto text-center">
        <h1 data-reveal className="text-5xl md:text-[5.5rem] font-black tracking-tight mb-4 leading-[1.02]">
          <span className="text-[#f0eeff]">Your Voice,</span>
          <br />
          <span className="gradient-text">Amplified.</span>
        </h1>

        {/* Voice visualizer */}
        <div data-reveal className="flex justify-center mb-8 opacity-80">
          <WaveBars />
        </div>

        <p data-reveal className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-3 leading-relaxed">
          AI that learns your writing style and generates platform-native posts for Twitter,
          Instagram, Facebook, and Telegram that sound like you wrote them.
        </p>
        <p data-reveal className="text-sm text-slate-500 mb-10">
          Feed it your samples. Get content that doesn&apos;t feel AI-generated. Full REST API included.
        </p>

        <div data-reveal className="flex flex-col sm:flex-row gap-3 justify-center mb-14">
          <a
            href="https://app.voxlyai.online"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-glow cta-btn-pulse px-8 py-3.5 text-white font-bold rounded-xl text-sm"
            style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)' }}
          >
            Get Started Free →
          </a>
          <a
            href="#api"
            className="btn-outline-anim px-8 py-3.5 font-semibold rounded-xl text-sm text-slate-300"
            style={{ border: '1px solid rgba(99,102,241,0.25)', background: 'rgba(99,102,241,0.05)' }}
          >
            View API Docs ↓
          </a>
        </div>

        {/* Platform pills */}
        <div data-reveal className="flex flex-wrap justify-center gap-2">
          {PLATFORMS.map((p, i) => (
            <span
              key={p.name}
              className="pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium"
              style={{
                background: p.bg,
                border: `1px solid ${p.border}`,
                color: p.color,
                animationDelay: `${i * 0.5}s`,
              }}
            >
              {p.name}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  const steps = [
    { n: '01', title: 'Upload your writing', desc: 'Paste 5 to 10 samples of your own posts, articles, or notes. The more they represent your natural voice, the sharper the output.' },
    { n: '02', title: 'Your voice is learned', desc: "VoxlyAI maps your sentence structure, vocabulary, rhythm, and what you tend to emphasize, building a style profile that is uniquely yours." },
    { n: '03', title: 'Generate on demand', desc: 'Request content by topic, platform, and format. Get posts that sound like you wrote them, ready to publish or tweak.' },
  ]

  return (
    <section id="how-it-works" className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14" data-reveal>
          <h2 className="text-3xl font-bold text-[#f0eeff] mb-3">How It Works</h2>
          <p className="text-slate-400 max-w-lg mx-auto">Three steps from first login to content that sounds like yours.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <div
              key={s.n}
              data-reveal
              className={`step-card p-6 rounded-2xl relative animate-delay-${i + 1}`}
              style={{ background: '#0d0d20', border: '1px solid rgba(99,102,241,0.12)' }}
            >
              {i < 2 && (
                <div className="hidden md:block absolute top-8 -right-3 z-10 text-indigo-900/40 text-xl">→</div>
              )}
              <div className="step-num text-4xl font-black text-indigo-900/45 mb-4 font-mono leading-none">{s.n}</div>
              <h3 className="text-[#f0eeff] font-semibold text-base mb-2">{s.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function Features() {
  return (
    <section id="features" className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14" data-reveal>
          <h2 className="text-3xl font-bold text-[#f0eeff] mb-3">Everything You Need</h2>
          <p className="text-slate-400 max-w-lg mx-auto">Built for solo creators, newsletters, agencies, and developer automation workflows.</p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              data-reveal
              className={`card-hover p-5 rounded-xl animate-delay-${i + 1}`}
              style={{ background: '#0d0d20', border: '1px solid rgba(99,102,241,0.1)' }}
            >
              <div
                className="feature-icon mb-4 w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: 'rgba(99,102,241,0.12)', color: '#818cf8' }}
              >
                {f.icon}
              </div>
              <h3 className="text-[#f0eeff] font-semibold text-sm mb-2">{f.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function SampleOutput() {
  const [active, setActive] = useState<SampleTab>('twitter')
  const [tabKey, setTabKey] = useState(0)
  const s = SAMPLES[active]

  const handleTab = (tab: SampleTab) => {
    setActive(tab)
    setTabKey(k => k + 1)
  }

  return (
    <section id="samples" className="py-20 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12" data-reveal>
          <h2 className="text-3xl font-bold text-[#f0eeff] mb-3">See the Output</h2>
          <p className="text-slate-400">Real examples of VoxlyAI-generated content, styled for each platform.</p>
        </div>

        <div data-reveal className="flex gap-2 mb-6 overflow-x-auto pb-1">
          {SAMPLE_TABS.map(tab => (
            <button
              key={tab}
              onClick={() => handleTab(tab)}
              className={`tab-btn px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap border ${active === tab ? 'tab-active' : ''}`}
              style={active === tab ? {} : { background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.07)', color: '#64748b' }}
            >
              {SAMPLES[tab].label}
            </button>
          ))}
        </div>

        <div data-reveal className="panel-hover rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.15)' }}>
          <div className="px-5 py-3 flex items-center justify-between flex-wrap gap-2"
            style={{ background: '#090915', borderBottom: '1px solid rgba(99,102,241,0.1)' }}>
            <span className="text-xs font-medium text-slate-400">{s.badge}</span>
            <code className="text-xs text-slate-600 font-mono">{s.meta}</code>
          </div>
          <div key={tabKey} className="tab-fade p-6" style={{ background: '#0d0d20' }}>
            <pre className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-sans m-0">{s.content}</pre>
          </div>
        </div>

        <p className="text-center text-xs text-slate-600 mt-4">
          Style trained on 8 writing samples · Generated in under 5s
        </p>
      </div>
    </section>
  )
}

function ApiDocs() {
  const [endpoint, setEndpoint] = useState<EndpointTab>('generate')
  const [lang, setLang] = useState<LangTab>('curl')
  const [epKey, setEpKey] = useState(0)
  const [langKey, setLangKey] = useState(0)
  const ep = ENDPOINTS[endpoint]

  const handleEndpoint = (key: EndpointTab) => { setEndpoint(key); setEpKey(k => k + 1); setLangKey(k => k + 1) }
  const handleLang = (key: LangTab) => { setLang(key); setLangKey(k => k + 1) }

  return (
    <section id="api" className="py-20 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12" data-reveal>
          <div
            className="inline-block px-3 py-1 rounded-md text-xs font-mono font-semibold text-indigo-300 mb-4"
            style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)' }}
          >
            REST API
          </div>
          <h2 className="text-3xl font-bold text-[#f0eeff] mb-2">API Reference</h2>
          <p className="text-slate-400 text-sm">
            Base URL:{' '}
            <code className="text-indigo-300">https://voxly-api.voxlyai.online</code>
            {' · '}
            <a href="https://voxly-api.voxlyai.online/docs" target="_blank" rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 transition-colors">
              Interactive docs ↗
            </a>
          </p>
        </div>

        {/* Auth */}
        <div data-reveal className="mb-8 p-5 rounded-xl" style={{ background: '#0d0d20', border: '1px solid rgba(99,102,241,0.12)' }}>
          <h3 className="text-[#f0eeff] font-semibold text-sm mb-3 flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded font-mono font-bold text-amber-300"
              style={{ background: 'rgba(251,191,36,0.1)' }}>AUTH</span>
            Authentication
          </h3>
          <p className="text-slate-400 text-sm mb-4">
            All endpoints require a Bearer token. Keys start with{' '}
            <code className="text-indigo-300">vlx-</code> and are generated at{' '}
            <a href="https://app.voxlyai.online" target="_blank" rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 transition-colors">
              app.voxlyai.online → Settings → API Keys
            </a>.
          </p>
          <div className="px-4 py-3 rounded-lg text-sm font-mono overflow-x-auto"
            style={{ background: '#030308', border: '1px solid rgba(99,102,241,0.12)' }}>
            <span className="text-slate-500">Authorization: </span>
            <span className="text-indigo-300">Bearer </span>
            <span className="text-green-300/80">vlx-your_key_here</span>
          </div>
        </div>

        {/* Endpoint selector */}
        <div data-reveal className="flex flex-wrap gap-2 mb-5">
          {(Object.keys(ENDPOINTS) as EndpointTab[]).map(key => (
            <button
              key={key}
              onClick={() => handleEndpoint(key)}
              className={`tab-btn flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium border ${endpoint === key ? 'tab-active' : ''}`}
              style={endpoint === key ? {} : { background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.07)', color: '#64748b' }}
            >
              <span className="text-xs font-mono font-bold text-emerald-400">POST</span>
              {ENDPOINTS[key].label}
            </button>
          ))}
        </div>

        {/* Code panel */}
        <div data-reveal className="panel-hover rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.15)' }}>
          <div key={`ep-${epKey}`} className="tab-fade px-5 py-4"
            style={{ background: '#090915', borderBottom: '1px solid rgba(99,102,241,0.1)' }}>
            <div className="flex items-center gap-3 mb-1.5 flex-wrap">
              <span className="text-xs font-mono font-bold text-emerald-400 px-2 py-0.5 rounded"
                style={{ background: 'rgba(52,211,153,0.1)' }}>POST</span>
              <code className="text-indigo-300 text-sm font-mono break-all">
                https://voxly-api.voxlyai.online{ep.path}
              </code>
            </div>
            <p className="text-slate-400 text-xs">{ep.desc}</p>
          </div>

          {/* Language tabs */}
          <div className="px-5 pt-4 flex gap-1"
            style={{ background: '#0d0d20', borderBottom: '1px solid rgba(99,102,241,0.08)' }}>
            {(['curl', 'js', 'python'] as LangTab[]).map(l => (
              <button
                key={l}
                onClick={() => handleLang(l)}
                className={`lang-tab-btn px-3 pb-3 pt-0 text-xs font-mono font-semibold border-b-2 ${lang === l ? 'lang-active' : ''}`}
                style={{ background: 'transparent', borderTop: 'none', borderLeft: 'none', borderRight: 'none',
                  borderBottomColor: lang === l ? '#818cf8' : 'transparent' }}
              >
                {l === 'js' ? 'JavaScript' : l === 'curl' ? 'cURL' : 'Python'}
              </button>
            ))}
          </div>

          <div key={`code-${langKey}`} className="tab-fade p-5 code-wrap" style={{ background: '#030308' }}>
            <pre className="text-slate-300 text-xs leading-relaxed m-0 whitespace-pre">
              {CODE[endpoint][lang]}
            </pre>
          </div>
        </div>

        {/* Response example */}
        <div data-reveal className="panel-hover mt-5 rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.12)' }}>
          <div className="px-5 py-3" style={{ background: '#090915', borderBottom: '1px solid rgba(99,102,241,0.1)' }}>
            <span className="text-xs font-medium text-slate-400">
              Example response · <code className="text-green-400">200 OK</code>
            </span>
          </div>
          <div className="p-5 code-wrap" style={{ background: '#030308' }}>
            <pre className="text-slate-300 text-xs leading-relaxed m-0">{RESPONSE_EXAMPLE}</pre>
          </div>
        </div>

        {/* Quick reference chips */}
        <div data-reveal className="mt-6 grid sm:grid-cols-2 gap-4">
          {[
            { title: 'Platforms', chips: ['twitter', 'instagram', 'facebook', 'telegram'] },
            { title: 'Content Types', chips: ['idea', 'long_form', 'thread', 'article'] },
          ].map(group => (
            <div key={group.title} className="p-5 rounded-xl"
              style={{ background: '#0d0d20', border: '1px solid rgba(99,102,241,0.1)' }}>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">{group.title}</h4>
              <div className="flex gap-2">
                {group.chips.map(c => (
                  <code key={c} className="flex-1 text-center text-xs py-2 rounded-lg font-mono text-indigo-300"
                    style={{ background: 'rgba(99,102,241,0.1)' }}>{c}</code>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Live sandbox */}
        <ApiSandbox />

        <p className="text-center mt-8 text-sm">
          <a href="https://app.voxlyai.online" target="_blank" rel="noopener noreferrer"
            className="text-indigo-400 hover:text-indigo-300 transition-colors">
            Get your API key → app.voxlyai.online → Settings → API Keys
          </a>
        </p>
      </div>
    </section>
  )
}

function ApiSandbox() {
  const [apiKey, setApiKey] = useState('')
  const [topic, setTopic] = useState('')
  const [platform, setPlatform] = useState('twitter')
  const [contentType, setContentType] = useState('idea')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<{
    status: number
    body: string
    content?: string
    title?: string
  } | null>(null)
  const [netError, setNetError] = useState<string | null>(null)

  const canRun = apiKey.trim().length > 4 && topic.trim().length > 0 && !loading

  const run = async () => {
    if (!canRun) return
    setLoading(true)
    setResponse(null)
    setNetError(null)
    try {
      const res = await fetch('https://voxly-api.voxlyai.online/generate/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey.trim()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          topic_name: topic.trim(),
          platform,
          content_type: contentType,
        }),
      })
      const data = await res.json()
      const first = data?.results?.[0]
      setResponse({
        status: res.status,
        body: JSON.stringify(data, null, 2),
        content: first?.content,
        title: first?.title,
      })
    } catch (e) {
      setNetError(
        e instanceof Error
          ? `${e.message}. Check that the API is reachable and CORS is configured.`
          : 'Network error — unable to reach the API.'
      )
    } finally {
      setLoading(false)
    }
  }

  const isOk = response !== null && response.status >= 200 && response.status < 300
  const inputBase = { background: '#030308', border: '1px solid rgba(99,102,241,0.18)' }

  return (
    <div data-reveal className="mt-8 rounded-2xl overflow-hidden"
      style={{ border: '1px solid rgba(99,102,241,0.22)' }}>

      {/* Header */}
      <div className="px-5 py-3 flex items-center gap-2.5"
        style={{ background: '#070712', borderBottom: '1px solid rgba(99,102,241,0.12)' }}>
        <span className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ background: '#34d399', boxShadow: '0 0 6px rgba(52,211,153,0.65)' }} />
        <span className="text-sm font-semibold text-slate-200">Sandbox</span>
        <span className="text-xs text-slate-600">live · calls the real API</span>
        <a href="https://app.voxlyai.online" target="_blank" rel="noopener noreferrer"
          className="ml-auto text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
          Get an API key →
        </a>
      </div>

      <div className="p-5 space-y-4" style={{ background: '#09091a' }}>

        {/* API key */}
        <div>
          <label className="text-xs font-mono text-slate-500 mb-1.5 block">Authorization</label>
          <div className="flex items-center rounded-lg overflow-hidden" style={inputBase}>
            <span className="px-3 py-2 text-xs font-mono text-slate-500 flex-shrink-0"
              style={{ borderRight: '1px solid rgba(99,102,241,0.18)' }}>Bearer</span>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="vlx-your_key_here"
              className="flex-1 px-3 py-2 text-sm font-mono text-slate-200 placeholder-slate-700 bg-transparent outline-none"
            />
          </div>
        </div>

        {/* Topic */}
        <div>
          <label className="text-xs font-mono text-slate-500 mb-1.5 block">topic_name</label>
          <input
            type="text"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="e.g. AI in healthcare"
            className="w-full px-3 py-2 rounded-lg text-sm font-mono text-slate-200 placeholder-slate-700 bg-transparent outline-none"
            style={inputBase}
          />
        </div>

        {/* Platform + content_type + Run */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[110px]">
            <label className="text-xs font-mono text-slate-500 mb-1.5 block">platform</label>
            <select
              value={platform}
              onChange={e => setPlatform(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm font-mono text-slate-200 outline-none"
              style={inputBase}
            >
              {['twitter', 'instagram', 'facebook', 'telegram'].map(p => (
                <option key={p} value={p} style={{ background: '#030308' }}>{p}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[110px]">
            <label className="text-xs font-mono text-slate-500 mb-1.5 block">content_type</label>
            <select
              value={contentType}
              onChange={e => setContentType(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm font-mono text-slate-200 outline-none"
              style={inputBase}
            >
              {['idea', 'long_form', 'thread', 'article'].map(c => (
                <option key={c} value={c} style={{ background: '#030308' }}>{c}</option>
              ))}
            </select>
          </div>
          <button
            onClick={run}
            disabled={!canRun}
            className="btn-glow flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold text-white"
            style={{
              background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
              opacity: canRun ? 1 : 0.38,
              cursor: canRun ? 'pointer' : 'not-allowed',
              minWidth: 90,
            }}
          >
            {loading ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                  style={{ animation: 'spin 0.75s linear infinite' }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                Running
              </>
            ) : 'Run →'}
          </button>
        </div>

        {/* Network error */}
        {netError && (
          <div className="px-4 py-3 rounded-lg text-sm text-red-400"
            style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.18)' }}>
            {netError}
          </div>
        )}

        {/* Response */}
        {response && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-500">Response</span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded"
                style={{
                  color: isOk ? '#34d399' : '#f87171',
                  background: isOk ? 'rgba(52,211,153,0.1)' : 'rgba(239,68,68,0.1)',
                }}>
                {response.status} {isOk ? 'OK' : 'Error'}
              </span>
            </div>

            {isOk && response.content && (
              <div className="p-4 rounded-xl"
                style={{ background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.18)' }}>
                {response.title && (
                  <div className="text-xs font-semibold text-indigo-400 mb-2">{response.title}</div>
                )}
                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{response.content}</p>
              </div>
            )}

            <div className="rounded-xl overflow-hidden"
              style={{ border: `1px solid ${isOk ? 'rgba(52,211,153,0.12)' : 'rgba(239,68,68,0.15)'}` }}>
              <div className="px-4 py-2"
                style={{ background: '#030308', borderBottom: `1px solid ${isOk ? 'rgba(52,211,153,0.1)' : 'rgba(239,68,68,0.12)'}` }}>
                <span className="text-xs font-mono text-slate-600">full response</span>
              </div>
              <div className="code-wrap p-4" style={{ background: '#030308', maxHeight: 280, overflowY: 'auto' }}>
                <pre className="text-xs leading-relaxed m-0" style={{ color: isOk ? '#94a3b8' : '#f87171' }}>
                  {response.body}
                </pre>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

function BotSection() {
  const steps = [
    { n: '1', title: 'Find VoxlyAI on OKX.AI', desc: 'Open the OKX.AI marketplace and search for "VoxlyAI". No API key or account required.' },
    { n: '2', title: 'Describe what you need', desc: 'Tell the agent your topic, target platform, and the tone you want. Just speak naturally.' },
    { n: '3', title: 'Receive ready-to-post content', desc: "The agent calls VoxlyAI's API internally and returns formatted content in the chat, ready to copy and publish." },
  ]

  return (
    <section id="bot" className="py-20 px-6">
      <div className="max-w-4xl mx-auto">
        <div data-reveal className="rounded-3xl p-8 md:p-12" style={{ background: '#0d0d20', border: '1px solid rgba(99,102,241,0.15)' }}>
          <div className="flex items-start gap-4 mb-10">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl flex-shrink-0"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.2)' }}>🤖</div>
            <div>
              <div className="text-xs font-semibold text-indigo-400 mb-1 uppercase tracking-wider">OKX.AI Marketplace</div>
              <h2 className="text-2xl font-bold text-[#f0eeff] mb-1">Use VoxlyAI via Chat</h2>
              <p className="text-slate-400 text-sm">No API key needed. Generate content through natural language, available to any OKX.AI user.</p>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-4 mb-10">
            {steps.map((s, i) => (
              <div key={s.n}
                data-reveal
                className={`card-hover p-5 rounded-xl animate-delay-${i + 1}`}
                style={{ background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.1)' }}>
                <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white mb-3"
                  style={{ background: '#6366f1' }}>{s.n}</div>
                <h4 className="text-[#f0eeff] text-sm font-semibold mb-1.5">{s.title}</h4>
                <p className="text-slate-400 text-xs leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>

          {/* Sample chat */}
          <div data-reveal className="rounded-xl overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.12)' }}>
            <div className="px-4 py-2.5 flex items-center gap-2"
              style={{ background: '#090915', borderBottom: '1px solid rgba(99,102,241,0.1)' }}>
              <div className="w-2 h-2 rounded-full bg-indigo-400/50" />
              <span className="text-xs text-slate-400 font-medium">Sample conversation · VoxlyAI on OKX.AI</span>
            </div>
            <div className="p-5 space-y-5" style={{ background: '#060610' }}>
              <div className="bubble-in bubble-in-1 flex gap-3">
                <div className="w-7 h-7 rounded-full bg-slate-700 flex-shrink-0 flex items-center justify-center text-xs text-slate-300 font-semibold">U</div>
                <div className="text-sm text-slate-300 rounded-xl rounded-tl-sm px-4 py-3 max-w-[80%]"
                  style={{ background: 'rgba(255,255,255,0.06)' }}>
                  Write me a Twitter thread about using AI without losing your authentic voice. Make it sound a bit contrarian.
                </div>
              </div>
              <div className="bubble-in bubble-in-2 flex gap-3 flex-row-reverse">
                <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
                  style={{ background: 'linear-gradient(135deg, #818cf8, #4f46e5)' }}>
                  <WaveIcon size={14} />
                </div>
                <div className="rounded-xl rounded-tr-sm px-4 py-3 max-w-[80%]"
                  style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.2)' }}>
                  <div className="text-xs text-indigo-400 mb-2.5 font-medium font-mono">
                    generating · twitter · thread · contrarian angle
                  </div>
                  <div className="text-sm text-slate-200 leading-relaxed">
                    Everyone&apos;s trying to &quot;use AI authentically.&quot; Here&apos;s what that actually means, and why most people get it completely backwards: 🧵<br /><br />
                    1/ The advice you&apos;ll hear: &quot;Edit the output until it sounds like you.&quot;<br />
                    That&apos;s not authentic. That&apos;s polishing something fake until it looks real.<br /><br />
                    2/ The approach that works: train the model on <em>your</em> writing first. Then generate. Now you&apos;re not polishing. You&apos;re drafting.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function CTA() {
  return (
    <section className="py-28 px-6 relative overflow-hidden">
      <div className="hero-orb" style={{ width: 400, height: 400, background: 'radial-gradient(circle, rgba(99,102,241,0.2) 0%, transparent 70%)', top: '-100px', left: '50%', transform: 'translateX(-50%)' }} />
      <div className="relative max-w-2xl mx-auto text-center">
        <h2 data-reveal className="text-4xl md:text-5xl font-black text-[#f0eeff] mb-5 leading-tight">
          Start generating content<br />
          <span className="gradient-text">that sounds like you.</span>
        </h2>
        <p data-reveal className="text-slate-400 mb-10 leading-relaxed max-w-lg mx-auto">
          Upload your writing samples, get your API key, and start publishing content your audience can&apos;t tell wasn&apos;t hand-crafted.
        </p>
        <div data-reveal className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="https://app.voxlyai.online"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-glow cta-btn-pulse px-8 py-4 text-white font-bold rounded-xl text-sm"
            style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)' }}
          >
            Create Your Account →
          </a>
          <a
            href="https://app.voxlyai.online"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-outline-anim px-8 py-4 font-semibold rounded-xl text-sm text-slate-300"
            style={{ border: '1px solid rgba(99,102,241,0.2)', background: 'rgba(99,102,241,0.05)' }}
          >
            Get API Key
          </a>
        </div>
        <p className="text-xs text-slate-600 mt-5">Free to start · API keys generated instantly in Settings → API Keys</p>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="px-6 py-10" style={{ borderTop: '1px solid rgba(99,102,241,0.1)' }}>
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #818cf8, #4f46e5)', borderRadius: 6 }}>
            <WaveIcon size={13} />
          </div>
          <span className="text-sm font-bold text-[#f0eeff]">VoxlyAI</span>
          <span className="text-slate-600 text-sm">© 2026</span>
        </div>
        <div className="flex flex-wrap gap-6 text-sm text-slate-500 justify-center">
          {[
            ['App', 'https://app.voxlyai.online'],
            ['API Docs', 'https://voxly-api.voxlyai.online/docs'],
            ['Quick Start', '#api'],
          ].map(([label, href]) => (
            <a key={label} href={href}
              target={href.startsWith('http') ? '_blank' : undefined}
              rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
              className="hover:text-slate-300 transition-colors">
              {label}
            </a>
          ))}
        </div>
        <p className="text-xs text-slate-600">© 2026 VoxlyAI. All rights reserved.</p>
      </div>
    </footer>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  useScrollReveal()

  return (
    <main style={{ background: '#06060f', minHeight: '100vh' }}>
      <Nav />
      <Hero />
      <Divider />
      <HowItWorks />
      <Divider />
      <Features />
      <Divider />
      <SampleOutput />
      <Divider />
      <ApiDocs />
      <Divider />
      <CTA />
      <Footer />
    </main>
  )
}
