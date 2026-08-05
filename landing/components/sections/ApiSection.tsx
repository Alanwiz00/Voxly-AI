'use client'
import { useState } from 'react'

const APP = 'https://app.voxlyai.online'

const CODE_SNIPPETS: Record<string, string> = {
  curl: `curl -X POST https://app.voxlyai.online/api/generate \\
  -H "Authorization: Bearer vlx-your-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "topic": "Why decentralized AI matters in 2025",
    "platform": "twitter",
    "persona_id": "your-persona-id"
  }'`,
  js: `const res = await fetch('https://app.voxlyai.online/api/generate', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer vlx-your-key',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    topic: 'Why decentralized AI matters in 2025',
    platform: 'twitter',
    persona_id: 'your-persona-id',
  }),
})
const { content } = await res.json()`,
  python: `import httpx

response = httpx.post(
    "https://app.voxlyai.online/api/generate",
    headers={"Authorization": "Bearer vlx-your-key"},
    json={
        "topic": "Why decentralized AI matters in 2025",
        "platform": "twitter",
        "persona_id": "your-persona-id",
    },
)
content = response.json()["content"]`,
}

const TABS = ['curl', 'js', 'python'] as const

export default function ApiSection() {
  const [active, setActive] = useState<typeof TABS[number]>('curl')

  return (
    <section id="api" style={{ background: 'var(--color-warm)' }}>
      <div className="container-v section-py">

        {/* Top: heading + code block side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-start mb-8">
          <div>
            <p className="eyebrow mb-4">Developer API</p>
            <h2 className="display-md mb-5">
              Every feature.<br />One clean API.
            </h2>
            <p className="text-base leading-relaxed" style={{ color: 'var(--color-ink-2)' }}>
              Generate content, manage personas, and adapt posts across platforms via REST. API keys are prefixed with{' '}
              <code className="text-sm px-1.5 py-0.5 rounded" style={{ background: 'var(--color-border)', color: 'var(--color-ink)' }}>vlx-</code>
              {' '}and are created instantly from your dashboard.
            </p>
          </div>

          <div className="rounded-lg overflow-hidden" style={{ border: '1.5px solid #2a2a2a', background: '#0a0a0a' }}>
            <div className="flex items-center" style={{ borderBottom: '1.5px solid #1f1f1f', background: '#111' }}>
              {TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActive(tab)}
                  className="px-4 py-3 text-xs font-medium transition-colors uppercase"
                  style={{
                    color: active === tab ? '#fff' : '#555',
                    background: 'none',
                    border: 'none',
                    borderBottom: active === tab ? '2px solid #fff' : '2px solid transparent',
                    cursor: 'pointer',
                  }}
                >
                  {tab === 'js' ? 'JavaScript' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
            <pre
              className="p-5 text-xs leading-relaxed overflow-x-auto"
              style={{ color: '#ccc', margin: 0, fontFamily: 'ui-monospace, "Cascadia Code", monospace' }}
            >
              <code>{CODE_SNIPPETS[active]}</code>
            </pre>
          </div>
        </div>

        {/* Full-width endpoint cards */}
        <div className="endpoint-strip">
          {API_FEATURES.map((f) => (
            <div key={f.title} className="endpoint-cell">
              <div
                className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'var(--color-border)' }}
              >
                {f.icon}
              </div>
              <div>
                <p className="text-xs font-semibold mb-1" style={{ color: 'var(--color-ink)', fontFamily: 'ui-monospace, monospace' }}>
                  {f.title}
                </p>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--color-ink-3)' }}>{f.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Button below */}
        <div className="mt-6">
          <a href={`${APP}/api-keys`} className="btn-primary">
            Get your API key
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 7.5h9M8.5 3l4.5 4.5-4.5 4.5" />
            </svg>
          </a>
        </div>

      </div>
    </section>
  )
}

const API_FEATURES = [
  {
    title: 'POST /generate',
    desc: 'Generate platform-native content from a topic or URL',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--color-ink-3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M7 1v12M1 7h12" /></svg>,
  },
  {
    title: 'POST /generate/batch',
    desc: 'Generate for all platforms in one request',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--color-ink-3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="1" width="5" height="5" rx="1" /><rect x="8" y="1" width="5" height="5" rx="1" /><rect x="1" y="8" width="5" height="5" rx="1" /><rect x="8" y="8" width="5" height="5" rx="1" /></svg>,
  },
  {
    title: 'POST /content/:id/adapt',
    desc: 'Reformat an existing post for a different platform',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--color-ink-3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 7h10M7 2l5 5-5 5" /></svg>,
  },
]
