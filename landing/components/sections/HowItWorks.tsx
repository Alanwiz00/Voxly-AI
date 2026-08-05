import SectionHeading from '../ui/SectionHeading'
import Reveal from '../ui/Reveal'

const STEPS = [
  {
    step: 'Step 1',
    title: 'Upload your writing samples',
    desc: 'Paste 8–20 posts, tweets, or articles you\'ve already written. The more samples, the sharper VoxlyAI\'s model of your voice becomes.',
    visual: (
      <div
        className="rounded-md p-4 space-y-2"
        style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)' }}
      >
        {['"Hot take: async-first teams ship 2× faster..."', '"Just got back from ETHDenver: three things..."', '"Nobody talks about the real cost of context switching..."'].map((s, i) => (
          <div
            key={i}
            className="text-xs p-2.5 rounded"
            style={{ background: 'var(--color-paper)', border: '1px solid var(--color-border)', color: 'var(--color-ink-2)' }}
          >
            {s}
          </div>
        ))}
      </div>
    ),
  },
  {
    step: 'Step 2',
    title: 'VoxlyAI learns your style',
    desc: 'The system extracts vocabulary patterns, sentence structures, tonal cues, and your platform-specific habits, building a private style profile.',
    visual: (
      <div
        className="rounded-md p-4 space-y-3"
        style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)' }}
      >
        {[
          { label: 'Vocabulary', value: 'Technical but accessible', w: '82%' },
          { label: 'Sentence length', value: 'Short → Medium mix', w: '64%' },
          { label: 'Tone', value: 'Direct & opinionated', w: '91%' },
        ].map((m) => (
          <div key={m.label}>
            <div className="flex justify-between mb-1">
              <span className="text-xs" style={{ color: 'var(--color-ink-3)' }}>{m.label}</span>
              <span className="text-xs" style={{ color: 'var(--color-ink-2)' }}>{m.value}</span>
            </div>
            <div className="h-1 rounded-full" style={{ background: 'var(--color-border)' }}>
              <div className="h-1 rounded-full" style={{ width: m.w, background: 'var(--color-ink)' }} />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    step: 'Step 3',
    title: 'Enter a topic or URL',
    desc: 'Give it a headline, a URL, or a rough idea. VoxlyAI extracts the key angles and selects what works for each platform.',
    visual: (
      <div
        className="rounded-md p-4"
        style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)' }}
      >
        <p className="text-xs mb-2" style={{ color: 'var(--color-ink-3)' }}>Topic / URL</p>
        <div
          className="text-xs p-3 rounded mb-3"
          style={{ background: 'var(--color-paper)', border: '1px solid var(--color-border)', color: 'var(--color-ink)' }}
        >
          The rise of autonomous AI agents in DeFi protocols
        </div>
        <p className="text-xs mb-2" style={{ color: 'var(--color-ink-3)' }}>Generate for</p>
        <div className="flex gap-2 flex-wrap">
          {['Twitter / X', 'Instagram', 'Facebook', 'Telegram'].map((p) => (
            <span key={p} className="badge text-xs">{p}</span>
          ))}
        </div>
      </div>
    ),
  },
  {
    step: 'Step 4',
    title: 'Review & publish',
    desc: 'Get platform-native drafts in under 5 seconds. Edit, rate, or re-generate. Every interaction sharpens your style profile.',
    visual: (
      <div
        className="rounded-md p-4"
        style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)' }}
      >
        <div className="text-xs p-3 rounded mb-3" style={{ background: 'var(--color-paper)', border: '1px solid var(--color-border)', color: 'var(--color-ink)' }}>
          DeFi protocols with AI agents running 24/7 aren't just a product update. They're a structural change in who controls liquidity. 🧵
        </div>
        <div className="flex gap-2">
          <button className="btn-primary text-xs py-1.5 px-3" style={{ fontSize: '0.7rem' }}>Copy</button>
          <button className="btn-secondary text-xs py-1.5 px-3" style={{ fontSize: '0.7rem' }}>Re-generate</button>
        </div>
      </div>
    ),
  },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" style={{ background: 'var(--color-paper)' }}>
      <div className="container-v section-py">
        <SectionHeading
          eyebrow="How it works"
          title="From idea to published in seconds"
          subtitle="Four steps. No prompting expertise required, no template hunting, no platform-by-platform rewrites."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {STEPS.map((s, i) => (
            <Reveal key={s.step} delay={i * 0.08}>
            <div className="card-flat">
              <p className="eyebrow mb-4">{s.step}</p>
              <h3
                className="text-lg font-medium mb-3"
                style={{ color: 'var(--color-ink)', letterSpacing: '-0.01em' }}
              >
                {s.title}
              </h3>
              <p className="text-sm leading-relaxed mb-5" style={{ color: 'var(--color-ink-2)' }}>
                {s.desc}
              </p>
              {s.visual}
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
