import Reveal from '../ui/Reveal'

export default function Testimonial() {
  return (
    <section style={{ background: 'var(--color-paper)', padding: 'clamp(2.5rem, 6vw, 4.5rem) 0' }}>
      <div className="container-v">
        <Reveal>
        <div className="max-w-3xl mx-auto text-center">
          <div className="mb-8 flex justify-center gap-1">
            {[1, 2, 3, 4, 5].map((s) => (
              <svg key={s} width="18" height="18" viewBox="0 0 18 18" fill="#0d0d0d">
                <path d="M9 1l2.163 4.38 4.837.703-3.5 3.412.826 4.818L9 12l-4.326 2.313.826-4.818L2 6.083l4.837-.703z" />
              </svg>
            ))}
          </div>

          <blockquote
            style={{
              fontFamily: 'var(--font-instrument-serif, Georgia, serif)',
              fontSize: 'clamp(1.5rem, 3.5vw, 2.5rem)',
              lineHeight: 1.25,
              fontWeight: 400,
              letterSpacing: '-0.02em',
              color: 'var(--color-ink)',
              fontStyle: 'italic',
              marginBottom: '2rem',
            }}
          >
            "I gave it 12 old tweets and it nailed my voice on the first try. The Twitter thread it generated got more engagement than most things I write myself."
          </blockquote>

          <div className="flex items-center justify-center gap-3">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium"
              style={{ background: 'var(--color-warm)', color: 'var(--color-ink)', border: '1.5px solid var(--color-border)' }}
            >
              MK
            </div>
            <div className="text-left">
              <p className="text-sm font-medium" style={{ color: 'var(--color-ink)' }}>
                Marcus K.
              </p>
              <p className="text-xs" style={{ color: 'var(--color-ink-3)' }}>
                Web3 builder & content creator
              </p>
            </div>
          </div>
        </div>
        </Reveal>
      </div>
    </section>
  )
}
