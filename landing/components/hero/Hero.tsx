'use client'
import { motion } from 'framer-motion'
import ConversationWave from './ConversationWave'

const APP = 'https://app.voxlyai.online'

export default function Hero() {
  return (
    <section
      className="relative overflow-hidden"
      style={{
        background: 'var(--color-paper)',
        paddingTop: 'clamp(5rem, 10vw, 8rem)',
        paddingBottom: 'clamp(3rem, 7vw, 5rem)',
      }}
    >
      <div className="container-v relative z-10">
        <div className="max-w-5xl mx-auto text-center">
          {/* Announcement badge */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="badge mb-8 inline-flex">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: '#4ade80' }}
              />
              Now on OKX.AI marketplace · Agent #10008
            </span>
          </motion.div>

          {/* Main headline */}
          <motion.h1
            className="display-xl mb-6"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            Your voice,
            <br />
            <em style={{ fontStyle: 'italic' }}>every</em> platform.
          </motion.h1>

          {/* Sub-headline */}
          <motion.p
            className="body-lg max-w-2xl mx-auto mb-10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            VoxlyAI learns your writing style from a handful of samples, then generates
            platform-native posts for Twitter, Instagram, Facebook, and Telegram that
            sound exactly like you wrote them. In under five seconds.
          </motion.p>

          {/* CTAs */}
          <motion.div
            className="flex flex-col sm:flex-row gap-3 justify-center"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.34, ease: [0.16, 1, 0.3, 1] }}
          >
            <a href={`${APP}/register`} className="btn-primary text-base px-7 py-3.5">
              Start for free
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </a>
            <a href="#how-it-works" className="btn-secondary text-base px-7 py-3.5">
              See how it works
            </a>
          </motion.div>

          {/* Social proof line */}
          <motion.p
            className="eyebrow mt-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            No credit card · API key in 60 seconds · 4 platforms
          </motion.p>
        </div>

        {/* Product preview */}
        <motion.div
          className="mt-10 relative mx-auto"
          style={{ maxWidth: '860px' }}
          initial={{ opacity: 0, y: 36 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, delay: 0.55, ease: [0.16, 1, 0.3, 1] }}
        >
          <div
            className="card-flat overflow-hidden"
            style={{ borderRadius: '0.75rem', padding: 0 }}
          >
            {/* Terminal-style header */}
            <div
              className="flex items-center gap-2 px-4 py-3"
              style={{ borderBottom: '1.5px solid var(--color-border)', background: 'var(--color-warm)' }}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ff5f56' }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#febc2e' }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#28c840' }} />
              <span className="ml-3 text-xs" style={{ color: 'var(--color-ink-3)' }}>VoxlyAI · Generate content</span>
            </div>

            {/* Preview content */}
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left: input */}
              <div>
                <p className="eyebrow mb-3">Topic</p>
                <div
                  className="text-sm p-3 rounded-md mb-4"
                  style={{ background: 'var(--color-warm)', border: '1.5px solid var(--color-border)', color: 'var(--color-ink)' }}
                >
                  The future of decentralized AI agents and why ownership matters
                </div>
                <p className="eyebrow mb-2">Your voice samples</p>
                <div className="flex gap-2 flex-wrap">
                  {['Casual & direct', 'Drops jargon', 'Uses em dashes', 'Short paras'].map(t => (
                    <span key={t} className="badge text-xs">{t}</span>
                  ))}
                </div>
              </div>

              {/* Right: output */}
              <div className="space-y-4">
                {SAMPLE_POSTS.map((p) => (
                  <div key={p.platform} className="card-flat" style={{ padding: '0.875rem' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-full"
                        style={{ background: p.color + '22', color: p.color, border: `1px solid ${p.color}44` }}
                      >
                        {p.platform}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--color-ink-2)' }}>
                      {p.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Animated waveform at bottom */}
      <ConversationWave />
    </section>
  )
}

const SAMPLE_POSTS = [
  {
    platform: 'Twitter / X',
    color: '#1d9bf0',
    text: 'Decentralized AI isn\'t a buzzword. It\'s about who owns the model\'s output. If the weights live on someone else\'s server, you\'re renting intelligence, not owning it. 🧵',
  },
  {
    platform: 'Instagram',
    color: '#e1306c',
    text: 'The agents running tomorrow\'s internet won\'t ask permission. They\'ll own their compute. That shift starts now. #AI #Web3 #FutureOfWork',
  },
]
