'use client'
import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'

const BASE = 'https://app.voxlyai.online/api'

// ─── Shared code block component ──────────────────────────────────────────────
function CodeBlock({ tabs }: { tabs: { label: string; code: string }[] }) {
  const [active, setActive] = useState(0)
  return (
    <div className="rounded-md overflow-hidden" style={{ border: '1.5px solid #2a2a2a', background: '#0a0a0a', marginTop: '1rem' }}>
      {tabs.length > 1 && (
        <div className="flex" style={{ borderBottom: '1.5px solid #1f1f1f', background: '#111' }}>
          {tabs.map((t, i) => (
            <button
              key={t.label}
              onClick={() => setActive(i)}
              style={{
                padding: '0.6rem 1rem', fontSize: '0.72rem', fontWeight: 500,
                background: 'none', border: 'none', cursor: 'pointer',
                color: active === i ? '#fff' : '#555',
                borderBottom: active === i ? '2px solid #fff' : '2px solid transparent',
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      <pre style={{ padding: '1.25rem', fontSize: '0.78rem', lineHeight: 1.7, color: '#ccc', margin: 0, overflowX: 'auto', fontFamily: 'ui-monospace, "Cascadia Code", "Fira Code", monospace' }}>
        <code>{tabs[active].code}</code>
      </pre>
    </div>
  )
}

// ─── Response block ────────────────────────────────────────────────────────────
function ResponseBlock({ code }: { code: string }) {
  return (
    <div className="rounded-md overflow-hidden" style={{ border: '1.5px solid var(--color-border)', background: 'var(--color-warm)', marginTop: '0.75rem' }}>
      <div style={{ padding: '0.4rem 1rem', borderBottom: '1.5px solid var(--color-border)', fontSize: '0.65rem', fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-ink-3)' }}>
        Response
      </div>
      <pre style={{ padding: '1rem 1.25rem', fontSize: '0.78rem', lineHeight: 1.7, color: 'var(--color-ink-2)', margin: 0, overflowX: 'auto', fontFamily: 'ui-monospace, "Cascadia Code", "Fira Code", monospace' }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

// ─── Parameter table ──────────────────────────────────────────────────────────
function ParamTable({ params }: { params: { name: string; type: string; required?: boolean; desc: string }[] }) {
  return (
    <div style={{ border: '1.5px solid var(--color-border)', borderRadius: '0.375rem', overflow: 'hidden', marginTop: '1rem' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
        <thead>
          <tr style={{ background: 'var(--color-warm)' }}>
            {['Parameter', 'Type', 'Required', 'Description'].map((h) => (
              <th key={h} style={{ padding: '0.6rem 1rem', textAlign: 'left', fontWeight: 500, color: 'var(--color-ink-3)', fontSize: '0.7rem', letterSpacing: '0.05em', textTransform: 'uppercase', borderBottom: '1.5px solid var(--color-border)' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {params.map((p, i) => (
            <tr key={p.name} style={{ borderTop: i > 0 ? '1px solid var(--color-border)' : 'none' }}>
              <td style={{ padding: '0.65rem 1rem', fontFamily: 'ui-monospace, monospace', fontSize: '0.75rem', color: 'var(--color-ink)', whiteSpace: 'nowrap' }}>{p.name}</td>
              <td style={{ padding: '0.65rem 1rem', color: 'var(--color-ink-3)', fontSize: '0.75rem', fontFamily: 'ui-monospace, monospace' }}>{p.type}</td>
              <td style={{ padding: '0.65rem 1rem' }}>
                <span style={{
                  fontSize: '0.65rem', fontWeight: 500, padding: '0.15rem 0.5rem', borderRadius: '9999px',
                  background: p.required ? '#0d0d0d' : 'var(--color-warm)',
                  color: p.required ? '#fff' : 'var(--color-ink-3)',
                  border: p.required ? 'none' : '1px solid var(--color-border)',
                }}>
                  {p.required ? 'required' : 'optional'}
                </span>
              </td>
              <td style={{ padding: '0.65rem 1rem', color: 'var(--color-ink-2)' }}>{p.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Method badge ──────────────────────────────────────────────────────────────
function Method({ verb, path }: { verb: string; path: string }) {
  const colors: Record<string, string> = { POST: '#16a34a', GET: '#2563eb', DELETE: '#dc2626' }
  return (
    <div className="flex items-center gap-3 mb-4" style={{ padding: '0.75rem 1rem', background: 'var(--color-warm)', border: '1.5px solid var(--color-border)', borderRadius: '0.375rem' }}>
      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: colors[verb] || '#555', fontFamily: 'ui-monospace, monospace', letterSpacing: '0.04em' }}>{verb}</span>
      <span style={{ fontSize: '0.85rem', color: 'var(--color-ink)', fontFamily: 'ui-monospace, monospace' }}>{BASE}{path}</span>
    </div>
  )
}

// ─── Section anchor heading ───────────────────────────────────────────────────
function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)', fontSize: 'clamp(1.4rem, 2.5vw, 1.9rem)', fontWeight: 400, letterSpacing: '-0.015em', color: 'var(--color-ink)', marginBottom: '1.5rem', paddingTop: '2rem', scrollMarginTop: '5rem' }}>
      {children}
    </h2>
  )
}

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-ink)', marginBottom: '0.5rem', marginTop: '2rem', letterSpacing: '-0.01em' }}>
      {children}
    </h3>
  )
}

function Divider() {
  return <div style={{ height: '1.5px', background: 'var(--color-border)', margin: '3rem 0' }} />
}

// ─── Nav sidebar links ────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { label: 'Overview',         href: '#overview' },
  { label: 'Authentication',   href: '#auth' },
  { label: 'Rate limits',      href: '#limits' },
  { label: 'POST /generate',   href: '#generate' },
  { label: 'POST /generate/from-source', href: '#from-source' },
  { label: 'POST /generate/batch', href: '#batch' },
  { label: 'GET /content',     href: '#list-content' },
  { label: 'GET /content/:id', href: '#get-content' },
  { label: 'POST /content/:id/re-edit',  href: '#re-edit' },
  { label: 'POST /content/:id/adapt',    href: '#adapt' },
  { label: 'POST /content/:id/rate',     href: '#rate' },
  { label: 'DELETE /content/:id',        href: '#delete' },
  { label: 'Error codes',      href: '#errors' },
]

export default function ApiDocsClient() {
  return (
    <>
      {/* Top bar */}
      <header style={{ position: 'fixed', inset: '0 0 auto 0', zIndex: 100, background: 'rgba(255,255,255,0.93)', borderBottom: '1.5px solid var(--color-border)', backdropFilter: 'blur(12px)', height: '56px', display: 'flex', alignItems: 'center' }}>
        <div className="container-v" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', color: 'var(--color-ink)' }}>
              <Image src="/logo.svg" alt="VoxlyAI" width={24} height={24} />
              <span style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)', fontSize: '1.2rem', fontWeight: 400, letterSpacing: '-0.025em' }}>
                Voxly<span style={{ color: 'var(--color-ink-3)' }}>AI</span>
              </span>
            </Link>
            <span style={{ color: 'var(--color-border)', fontSize: '1rem' }}>/</span>
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--color-ink-2)' }}>API Reference</span>
          </div>
          <a href="https://app.voxlyai.online/api-keys" className="btn-primary" style={{ fontSize: '0.8rem', padding: '0.5rem 1.25rem' }}>
            Get API key
          </a>
        </div>
      </header>

      <div style={{ paddingTop: '56px', display: 'flex', maxWidth: '1280px', margin: '0 auto', minHeight: '100vh' }}>
        {/* Sidebar */}
        <aside style={{ width: '220px', flexShrink: 0, position: 'sticky', top: '56px', height: 'calc(100vh - 56px)', overflowY: 'auto', padding: '2rem 1.5rem 2rem 0', borderRight: '1.5px solid var(--color-border)' }}>
          <nav>
            <p style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-ink-3)', marginBottom: '0.875rem' }}>Reference</p>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
              {NAV_ITEMS.map((item) => {
                const isEndpoint = item.label.startsWith('POST') || item.label.startsWith('GET') || item.label.startsWith('DELETE')
                return (
                  <li key={item.href}>
                    <a
                      href={item.href}
                      style={{
                        display: 'block', padding: '0.35rem 0.5rem',
                        color: 'var(--color-ink-2)', textDecoration: 'none', borderRadius: '0.25rem',
                        fontFamily: isEndpoint ? 'ui-monospace, monospace' : 'inherit',
                        fontSize: isEndpoint ? '0.72rem' : '0.8rem',
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.color = 'var(--color-ink)')}
                      onMouseOut={(e) => (e.currentTarget.style.color = 'var(--color-ink-2)')}
                    >
                      {item.label}
                    </a>
                  </li>
                )
              })}
            </ul>
          </nav>
        </aside>

        {/* Main content */}
        <main style={{ flex: 1, padding: '2.5rem 0 6rem 3.5rem', maxWidth: '820px' }}>

          {/* Overview */}
          <H2 id="overview">API Reference</H2>
          <p style={{ fontSize: '1rem', lineHeight: 1.75, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            VoxlyAI exposes a REST API that mirrors everything available in the dashboard. Use it to generate platform-native content, manage your writing personas, re-edit drafts, and adapt posts across platforms from your own pipelines.
          </p>
          <p style={{ fontSize: '1rem', lineHeight: 1.75, color: 'var(--color-ink-2)' }}>
            Base URL: <code style={{ fontSize: '0.85rem', padding: '0.15rem 0.5rem', background: 'var(--color-warm)', border: '1px solid var(--color-border)', borderRadius: '0.25rem' }}>{BASE}</code>
          </p>

          <Divider />

          {/* Auth */}
          <H2 id="auth">Authentication</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.75, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            All requests require a bearer token passed in the <code style={codeStyle}>Authorization</code> header. API keys are prefixed with <code style={codeStyle}>vlx-</code> and are generated from your dashboard.
          </p>
          <CodeBlock tabs={[{
            label: 'cURL',
            code: `curl https://app.voxlyai.online/api/generate \\
  -H "Authorization: Bearer vlx-xxxxxxxxxxxxxxxx"`,
          }]} />

          <Divider />

          {/* Limits */}
          <H2 id="limits">Rate limits</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.75, color: 'var(--color-ink-2)', marginBottom: '0.75rem' }}>
            Usage is tracked in tokens per calendar month, not requests per second. The free plan includes 100,000 tokens per month. When the budget is exhausted, generation endpoints return <code style={codeStyle}>403</code> until the next billing cycle.
          </p>
          <div style={{ border: '1.5px solid var(--color-border)', borderRadius: '0.375rem', overflow: 'hidden', marginTop: '1rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'var(--color-warm)' }}>
                  <th style={thStyle}>Plan</th>
                  <th style={thStyle}>Monthly tokens</th>
                  <th style={thStyle}>Notes</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={tdStyle}>Free</td>
                  <td style={tdStyle}>100,000</td>
                  <td style={tdStyle}>Resets on the 1st of each month</td>
                </tr>
              </tbody>
            </table>
          </div>

          <Divider />

          {/* POST /generate */}
          <H2 id="generate">Generate content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Generate platform-native content from a topic name or a saved topic ID. The system selects the best matching persona automatically unless you specify one.
          </p>
          <Method verb="POST" path="/generate" />
          <H3>Request body</H3>
          <ParamTable params={[
            { name: 'topic_name', type: 'string', required: true,  desc: 'Free-form topic or headline to generate content about' },
            { name: 'platform',   type: 'string', required: true,  desc: 'One of: twitter, instagram, facebook, telegram' },
            { name: 'content_type', type: 'string', required: true, desc: 'One of: idea, long_form, thread, article' },
            { name: 'topic_id',   type: 'integer', desc: 'ID of a saved topic. Unlocks sentiment context if available' },
            { name: 'persona_id', type: 'integer', desc: 'Force a specific persona; omit to auto-select' },
          ]} />
          <H3>Example</H3>
          <CodeBlock tabs={[
            {
              label: 'cURL',
              code: `curl -X POST ${BASE}/generate \\
  -H "Authorization: Bearer vlx-xxxxxxxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "topic_name": "Why decentralized AI matters in 2025",
    "platform": "twitter",
    "content_type": "thread"
  }'`,
            },
            {
              label: 'JavaScript',
              code: `const res = await fetch('${BASE}/generate', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer vlx-xxxxxxxxxxxxxxxx',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    topic_name: 'Why decentralized AI matters in 2025',
    platform: 'twitter',
    content_type: 'thread',
  }),
})
const data = await res.json()`,
            },
            {
              label: 'Python',
              code: `import httpx

data = httpx.post(
    "${BASE}/generate",
    headers={"Authorization": "Bearer vlx-xxxxxxxxxxxxxxxx"},
    json={
        "topic_name": "Why decentralized AI matters in 2025",
        "platform": "twitter",
        "content_type": "thread",
    },
).json()`,
            },
          ]} />
          <ResponseBlock code={`{
  "content_type": "thread",
  "results": [
    {
      "id": 142,
      "platform": "twitter",
      "content_type": "thread",
      "title": "Why decentralized AI matters in 2025",
      "content": "Decentralized AI isn't a buzzword...",
      "meta": { "word_count": 87, "hook": "..." },
      "version": 1,
      "parent_id": null,
      "rating": null,
      "created_at": "2025-08-05T09:21:44Z"
    }
  ]
}`} />

          <Divider />

          {/* POST /generate/from-source */}
          <H2 id="from-source">Generate from source</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Generate content from an existing source: a URL, raw text, a PDF, a DOCX, or an image. Sent as <code style={codeStyle}>multipart/form-data</code>.
          </p>
          <Method verb="POST" path="/generate/from-source" />
          <H3>Form fields</H3>
          <ParamTable params={[
            { name: 'platform',     type: 'string', required: true,  desc: 'One of: twitter, instagram, facebook, telegram' },
            { name: 'content_type', type: 'string', required: true,  desc: 'One of: idea, long_form, thread, article' },
            { name: 'url',         type: 'string',  desc: 'URL to fetch and extract content from' },
            { name: 'text',        type: 'string',  desc: 'Raw text to use as the source' },
            { name: 'file',        type: 'file',    desc: 'PDF, DOCX, or image file (.jpg, .png, .webp)' },
            { name: 'persona_id',  type: 'integer', desc: 'Force a specific persona; omit to auto-select' },
          ]} />
          <H3>Example (URL)</H3>
          <CodeBlock tabs={[{
            label: 'cURL',
            code: `curl -X POST ${BASE}/generate/from-source \\
  -H "Authorization: Bearer vlx-xxxxxxxxxxxxxxxx" \\
  -F "platform=instagram" \\
  -F "content_type=idea" \\
  -F "url=https://example.com/article"`,
          }]} />

          <Divider />

          {/* POST /generate/batch */}
          <H2 id="batch">Batch generate</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Generate content for a specific platform in a single call. Useful for automating multi-platform campaigns one platform at a time.
          </p>
          <Method verb="POST" path="/generate/batch" />
          <H3>Request body</H3>
          <ParamTable params={[
            { name: 'platform',     type: 'string', required: true, desc: 'One of: twitter, instagram, facebook, telegram' },
            { name: 'content_type', type: 'string', required: true, desc: 'One of: idea, long_form, thread, article' },
            { name: 'topic_name',   type: 'string', desc: 'Free-form topic' },
            { name: 'topic_id',     type: 'integer', desc: 'ID of a saved topic' },
          ]} />

          <Divider />

          {/* GET /content */}
          <H2 id="list-content">List content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Returns the authenticated user's generated content, newest first. Only top-level items are returned (not re-edit children).
          </p>
          <Method verb="GET" path="/content" />
          <H3>Query parameters</H3>
          <ParamTable params={[
            { name: 'platform',     type: 'string',  desc: 'Filter by platform' },
            { name: 'content_type', type: 'string',  desc: 'Filter by content type' },
            { name: 'limit',        type: 'integer', desc: 'Max results (default 20, max 100)' },
            { name: 'offset',       type: 'integer', desc: 'Pagination offset (default 0)' },
          ]} />

          <Divider />

          {/* GET /content/:id */}
          <H2 id="get-content">Get content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Returns a single content record including its full version history.
          </p>
          <Method verb="GET" path="/content/{id}" />
          <ResponseBlock code={`{
  "id": 142,
  "platform": "twitter",
  "content_type": "thread",
  "title": "...",
  "content": "...",
  "meta": {},
  "version": 2,
  "parent_id": null,
  "rating": 1,
  "created_at": "2025-08-05T09:21:44Z",
  "versions": [
    {
      "version_number": 2,
      "content": "...",
      "edit_instruction": "make it shorter",
      "created_at": "2025-08-05T09:35:00Z"
    }
  ]
}`} />

          <Divider />

          {/* POST /content/:id/re-edit */}
          <H2 id="re-edit">Re-edit content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Apply a plain-English edit instruction to an existing post. Returns a new content record linked to the original, preserving the version chain.
          </p>
          <Method verb="POST" path="/content/{id}/re-edit" />
          <H3>Request body</H3>
          <ParamTable params={[
            { name: 'instruction', type: 'string', required: true, desc: 'Plain-English edit instruction e.g. "make it shorter", "add a question at the end"' },
          ]} />
          <CodeBlock tabs={[{
            label: 'cURL',
            code: `curl -X POST ${BASE}/content/142/re-edit \\
  -H "Authorization: Bearer vlx-xxxxxxxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{ "instruction": "make it shorter and punchier" }'`,
          }]} />

          <Divider />

          {/* POST /content/:id/adapt */}
          <H2 id="adapt">Adapt to platform</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Reformat an existing post for a different platform. Produces a new child record adapted in length, structure, and tone for the target platform.
          </p>
          <Method verb="POST" path="/content/{id}/adapt" />
          <H3>Request body</H3>
          <ParamTable params={[
            { name: 'platform', type: 'string', required: true, desc: 'Target platform: twitter, instagram, facebook, or telegram' },
          ]} />

          <Divider />

          {/* POST /content/:id/rate */}
          <H2 id="rate">Rate content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Add a thumbs-up or thumbs-down rating to a piece of content. Ratings are used to refine the style profile automatically once enough accumulate.
          </p>
          <Method verb="POST" path="/content/{id}/rate" />
          <H3>Request body</H3>
          <ParamTable params={[
            { name: 'rating', type: 'integer', required: true, desc: '1 for thumbs up, -1 for thumbs down, 0 to remove rating' },
          ]} />

          <Divider />

          {/* DELETE /content/:id */}
          <H2 id="delete">Delete content</H2>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: 'var(--color-ink-2)', marginBottom: '1rem' }}>
            Permanently deletes a content record. Returns <code style={codeStyle}>204 No Content</code> on success.
          </p>
          <Method verb="DELETE" path="/content/{id}" />

          <Divider />

          {/* Errors */}
          <H2 id="errors">Error codes</H2>
          <div style={{ border: '1.5px solid var(--color-border)', borderRadius: '0.375rem', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'var(--color-warm)' }}>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Meaning</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { code: '400', msg: 'Invalid request — check platform/content_type values or missing required fields' },
                  { code: '401', msg: 'Missing or invalid Authorization header' },
                  { code: '403', msg: 'Monthly token budget exhausted. Resets on the 1st of the month' },
                  { code: '404', msg: 'Content or topic not found, or belongs to another user' },
                  { code: '422', msg: 'Request body failed schema validation' },
                  { code: '500', msg: 'Internal server error' },
                ].map((e, i) => (
                  <tr key={e.code} style={{ borderTop: i > 0 ? '1px solid var(--color-border)' : 'none' }}>
                    <td style={{ ...tdStyle, fontFamily: 'ui-monospace, monospace', color: 'var(--color-ink)', width: '80px' }}>{e.code}</td>
                    <td style={tdStyle}>{e.msg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: '4rem', padding: '1.5rem', background: 'var(--color-warm)', border: '1.5px solid var(--color-border)', borderRadius: '0.375rem' }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-ink-2)', marginBottom: '0.75rem' }}>Ready to start building?</p>
            <a href="https://app.voxlyai.online/api-keys" className="btn-primary" style={{ fontSize: '0.875rem' }}>
              Generate your API key
            </a>
          </div>

        </main>
      </div>
    </>
  )
}

// ─── Shared cell styles ───────────────────────────────────────────────────────
const codeStyle: React.CSSProperties = {
  fontSize: '0.82rem', padding: '0.15rem 0.45rem',
  background: 'var(--color-warm)', border: '1px solid var(--color-border)',
  borderRadius: '0.25rem', fontFamily: 'ui-monospace, monospace',
}
const thStyle: React.CSSProperties = {
  padding: '0.6rem 1rem', textAlign: 'left', fontWeight: 500,
  color: 'var(--color-ink-3)', fontSize: '0.7rem', letterSpacing: '0.05em',
  textTransform: 'uppercase', borderBottom: '1.5px solid var(--color-border)',
}
const tdStyle: React.CSSProperties = {
  padding: '0.65rem 1rem', color: 'var(--color-ink-2)',
}
