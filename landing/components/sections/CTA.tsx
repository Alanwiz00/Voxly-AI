const APP = 'https://app.voxlyai.online'

export default function CTA() {
  return (
    <section style={{ background: 'var(--color-warm)', padding: 'clamp(2.5rem, 6vw, 4.5rem) 0' }}>
      <div className="container-v">
        <div className="max-w-3xl mx-auto text-center">
          <p className="eyebrow mb-4">Get started today</p>
          <h2
            className="display-lg mb-6"
            style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)' }}
          >
            Your audience is waiting.<br />
            Your voice is ready.
          </h2>
          <p
            className="text-lg leading-relaxed mb-8 max-w-xl mx-auto"
            style={{ color: 'var(--color-ink-2)' }}
          >
            Start free. No credit card. Get your API key in 60 seconds and generate your first post in under five.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a href={`${APP}/login`} className="btn-primary text-base px-8 py-3.5">
              Create free account
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </a>
            <a href="/api-docs" className="btn-secondary text-base px-8 py-3.5">
              View API docs
            </a>
          </div>
          <p className="eyebrow mt-8">
            100k free tokens · 4 platforms · vlx- API keys
          </p>
        </div>
      </div>
    </section>
  )
}
