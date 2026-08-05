import SectionHeading from '../ui/SectionHeading'
import Reveal from '../ui/Reveal'

const CAPS = [
  {
    number: '01',
    title: 'Voice learning',
    desc: 'Paste 8–20 writing samples and VoxlyAI extracts your vocabulary, sentence rhythm, tone, and quirks, not just keywords. Your profile is private and never shared.',
    detail: 'Vocabulary analysis · Sentence rhythm · Tone classification · Style persistence',
  },
  {
    number: '02',
    title: 'Platform-native output',
    desc: 'Twitter threads with hooks, Instagram captions with hashtag pacing, Facebook posts with engagement prompts, Telegram messages with your exact formatting. Each platform gets the right format, length, and tone.',
    detail: 'Twitter/X · Instagram · Facebook · Telegram',
  },
  {
    number: '03',
    title: 'Topic intelligence',
    desc: 'Feed it a URL, a headline, or a rough idea. VoxlyAI extracts the key angles, filters what\'s relevant for each platform, and structures the output so it performs.',
    detail: 'URL ingestion · Content extraction · Angle selection · Platform fit',
  },
  {
    number: '04',
    title: 'REST API + agents',
    desc: 'Every feature is available via a clean REST API with `vlx-` prefixed keys. Use it in your pipeline, trigger it from n8n, or call it from the OKX.AI marketplace.',
    detail: 'REST API · API keys · Webhook triggers · OKX.AI agent',
  },
]

export default function Capabilities() {
  return (
    <section id="capabilities" className="section-warm">
      <div className="container-v section-py">
        <SectionHeading
          eyebrow="Capabilities"
          title="Built around how you actually write"
          subtitle="Not a generic AI assistant. A content engine that understands your specific voice and generates for the platform, ready to publish."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {CAPS.map((cap, i) => (
            <Reveal key={cap.number} delay={i * 0.08}>
            <div className="card-flat group">
              <div className="flex items-start justify-between mb-5">
                <span
                  className="text-xs font-mono font-medium"
                  style={{ color: 'var(--color-ink-3)' }}
                >
                  {cap.number}
                </span>
              </div>
              <h3
                className="text-xl font-medium mb-3"
                style={{ color: 'var(--color-ink)', letterSpacing: '-0.01em' }}
              >
                {cap.title}
              </h3>
              <p className="text-sm leading-relaxed mb-5" style={{ color: 'var(--color-ink-2)' }}>
                {cap.desc}
              </p>
              <div
                className="text-xs leading-relaxed pt-4"
                style={{ borderTop: '1.5px solid var(--color-border)', color: 'var(--color-ink-3)' }}
              >
                {cap.detail}
              </div>
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
