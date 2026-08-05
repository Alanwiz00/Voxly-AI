'use client'
import { useState } from 'react'

export default function Newsletter() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setSubmitted(true)
  }

  return (
    <section style={{ background: 'var(--color-paper)', padding: 'clamp(2rem, 5vw, 3.5rem) 0' }}>
      <div className="container-v">
        <div
          className="max-w-2xl mx-auto text-center"
          style={{
            borderTop: '1.5px solid var(--color-border)',
            paddingTop: 'clamp(2rem, 4vw, 3rem)',
          }}
        >
          <p className="eyebrow mb-4">Stay sharp</p>
          <h2
            className="display-md mb-4"
            style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)' }}
          >
            Content strategy for<br />people who think.
          </h2>
          <p className="text-base leading-relaxed mb-8" style={{ color: 'var(--color-ink-2)' }}>
            Occasional notes on AI content strategy, platform algorithm changes, and how to stay ahead. No fluff. Only what actually matters.
          </p>

          {submitted ? (
            <div
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-medium"
              style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)', color: 'var(--color-ink)' }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 8l4 4 8-8" />
              </svg>
              You&apos;re in. We&apos;ll be in touch.
            </div>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto"
            >
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="flex-1 px-4 py-3 text-sm rounded-full"
                style={{
                  border: '1.5px solid var(--color-border)',
                  background: 'var(--color-paper)',
                  color: 'var(--color-ink)',
                  outline: 'none',
                  fontFamily: 'inherit',
                }}
              />
              <button type="submit" className="btn-primary whitespace-nowrap">
                Subscribe
              </button>
            </form>
          )}
        </div>
      </div>
    </section>
  )
}
