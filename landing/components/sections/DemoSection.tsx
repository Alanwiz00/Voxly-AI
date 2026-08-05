'use client'
import { useState } from 'react'
import SectionHeading from '../ui/SectionHeading'

const DEMO_OUTPUTS: Record<string, { lines: string[]; meta: string }> = {
  twitter: {
    lines: [
      'AI agents that own their compute aren\'t science fiction anymore.',
      '',
      'They\'re running right now, paying for API calls, renting GPU time, and executing contracts without a human in the loop.',
      '',
      'The question isn\'t whether this happens. It\'s whether the value flows back to users or gets absorbed by the platform.',
      '',
      'That\'s the bet.',
    ],
    meta: '280 chars · No hashtags · Hook → tension → thesis',
  },
  instagram: {
    lines: [
      'The agents running tomorrow\'s internet don\'t ask permission. They own their compute. 🤖⚡',
      '',
      'Decentralized AI isn\'t a buzzword. It\'s about who captures the value when intelligence becomes infrastructure.',
      '',
      'Are you building on rented ground, or your own?',
      '',
      '#AI #Web3 #DecentralizedAI #FutureOfWork #AIAgents #BlockchainAI',
    ],
    meta: '3 paras · 6 hashtags · Closes with question',
  },
  facebook: {
    lines: [
      'Something interesting is happening with AI ownership, and most people are sleeping on it.',
      '',
      'When an AI agent pays for its own compute, executes contracts, and earns revenue without human sign-off, the question of who owns that value becomes very real.',
      '',
      'The companies building decentralized AI infrastructure today are betting that the answer isn\'t "the platform hosting it."',
      '',
      'What do you think? Is decentralized AI inevitable, or is centralized infrastructure just too useful to compete with?',
    ],
    meta: '4 paras · Opens with curiosity hook · Closes with engagement prompt',
  },
  telegram: {
    lines: [
      '**AI agents with economic autonomy:**',
      '',
      '→ They own wallets',
      '→ They pay for compute',
      '→ They execute smart contracts',
      '→ They earn revenue',
      '',
      'No human in the loop. The infrastructure for this exists today.',
      '',
      'Where value accrues is the open question. Stay tuned.',
    ],
    meta: 'Markdown bold · Arrow lists · Telegram formatting',
  },
}

const TABS = ['twitter', 'instagram', 'facebook', 'telegram'] as const

export default function DemoSection() {
  const [active, setActive] = useState<typeof TABS[number]>('twitter')
  const output = DEMO_OUTPUTS[active]

  return (
    <section id="demo" className="section-dark">
      <div className="container-v section-py">
        <SectionHeading
          eyebrow="Live demo"
          title="One topic, four platforms"
          subtitle="Same topic, different structure, length, and tone for each platform. This is what platform-native means."
          light
        />

        <div
          className="rounded-lg overflow-hidden"
          style={{ border: '1.5px solid #2a2a2a', maxWidth: '780px', margin: '0 auto' }}
        >
          {/* Tabs */}
          <div
            className="flex items-center overflow-x-auto"
            style={{ borderBottom: '1.5px solid #2a2a2a', background: '#0f0f0f' }}
          >
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActive(tab)}
                className="px-5 py-3.5 text-xs font-medium transition-all whitespace-nowrap capitalize"
                style={{
                  color: active === tab ? '#fff' : '#666',
                  background: 'none',
                  border: 'none',
                  borderBottom: active === tab ? '2px solid #fff' : '2px solid transparent',
                  cursor: 'pointer',
                  padding: '0.875rem 1.25rem',
                }}
              >
                {tab === 'twitter' ? 'Twitter / X' : tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="p-7" style={{ background: '#0a0a0a', minHeight: '320px' }}>
            <div className="space-y-0">
              {output.lines.map((line, i) => (
                line === '' ? (
                  <div key={i} className="h-4" />
                ) : (
                  <p
                    key={i}
                    className="text-sm leading-relaxed"
                    style={{ color: '#ddd' }}
                    dangerouslySetInnerHTML={{
                      __html: line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'),
                    }}
                  />
                )
              ))}
            </div>
            <div
              className="mt-6 pt-4 flex items-center justify-between"
              style={{ borderTop: '1.5px solid #1f1f1f' }}
            >
              <p className="text-xs" style={{ color: '#555' }}>{output.meta}</p>
              <span className="badge" style={{ borderColor: '#2a2a2a', color: '#666', fontSize: '0.7rem' }}>
                Generated in &lt;3s
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
