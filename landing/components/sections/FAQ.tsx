'use client'
import { useState } from 'react'
import SectionHeading from '../ui/SectionHeading'

const FAQS = [
  {
    q: 'How many writing samples do I need?',
    a: 'Eight is the minimum for a usable style profile. Twenty or more gives much sharper results. You can upload samples gradually; the profile sharpens with each addition.',
  },
  {
    q: 'Is my writing style stored privately?',
    a: 'Yes. Your style profile is linked to your account and is never used to train models for other users or shared in any way.',
  },
  {
    q: 'What\'s the difference between the free plan and the API?',
    a: 'The free plan includes 100,000 tokens per month through the web app. API access is on the same account. Generate your key from the dashboard and start calling immediately.',
  },
  {
    q: 'Can I generate for multiple platforms at once?',
    a: 'Yes. Use POST /generate/batch or select multiple platforms in the dashboard. Each platform gets a separate, platform-native draft. Not the same post reformatted.',
  },
  {
    q: 'What is the OKX.AI agent?',
    a: 'VoxlyAI is listed on the OKX.AI marketplace as agent #10008. You can call it directly from any OKX.AI workflow without a separate API key.',
  },
  {
    q: 'How does re-editing work?',
    a: 'After generating a post, you can give plain-English re-edit instructions ("make it shorter", "add a question at the end", "less formal"). The system applies the edit while preserving your voice. Each re-edit is saved as a version.',
  },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <section style={{ background: 'var(--color-warm)' }}>
      <div className="container-v section-py">
        <SectionHeading
          eyebrow="FAQ"
          title="Common questions"
        />

        <div className="max-w-2xl">
          {FAQS.map((faq, i) => (
            <div key={i} className="faq-item">
              <button
                className="faq-trigger"
                onClick={() => setOpen(open === i ? null : i)}
                aria-expanded={open === i}
              >
                <span>{faq.q}</span>
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 18 18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    flexShrink: 0,
                    transform: open === i ? 'rotate(45deg)' : 'rotate(0deg)',
                    transition: 'transform 0.25s ease',
                  }}
                >
                  <path d="M9 3v12M3 9h12" />
                </svg>
              </button>
              <div className={`faq-body ${open === i ? 'open' : ''}`}>
                <p>{faq.a}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
