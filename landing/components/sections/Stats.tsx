'use client'
import { useEffect, useRef, useState } from 'react'

const STATS = [
  { value: 5,  suffix: 's',  label: 'Average generation time' },
  { value: 4,  suffix: '',   label: 'Native platforms supported' },
  { value: 8,  suffix: '+',  label: 'Writing samples to learn your voice' },
  { value: 100, suffix: 'k', label: 'Free tokens every month' },
]

function AnimatedNumber({ value, suffix }: { value: number; suffix: string }) {
  const [current, setCurrent] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true
          const duration = 1200
          const start = performance.now()
          const step = (now: number) => {
            const p = Math.min((now - start) / duration, 1)
            const ease = 1 - Math.pow(1 - p, 3)
            setCurrent(Math.round(ease * value))
            if (p < 1) requestAnimationFrame(step)
          }
          requestAnimationFrame(step)
        }
      },
      { threshold: 0.5 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [value])

  return (
    <span ref={ref} className="stat-number">
      {current}{suffix}
    </span>
  )
}

export default function Stats() {
  return (
    <section style={{ background: 'var(--color-paper)', padding: 'clamp(2rem, 5vw, 3.5rem) 0' }}>
      <div className="container-v">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-10">
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col gap-2">
              <AnimatedNumber value={s.value} suffix={s.suffix} />
              <p className="text-sm" style={{ color: 'var(--color-ink-3)' }}>{s.label}</p>
            </div>
          ))}
        </div>
        <div className="divider mt-10" />
      </div>
    </section>
  )
}
