'use client'
import { motion } from 'framer-motion'

const WAVES = [
  {
    color: '#93c5fd',
    opacity: 0.35,
    strokeWidth: 1.5,
    initialD: 'M0,60 C160,20 320,100 480,60 C640,20 800,90 960,55 C1040,38 1120,70 1200,60',
    animateD: 'M0,80 C160,40 320,120 480,75 C640,35 800,105 960,65 C1040,48 1120,85 1200,75',
    duration: 9,
    delay: 0,
  },
  {
    color: '#f9a8d4',
    opacity: 0.30,
    strokeWidth: 1.2,
    initialD: 'M0,70 C140,30 280,110 420,65 C560,25 700,95 840,55 C920,38 1060,80 1200,65',
    animateD: 'M0,55 C140,15 280,90 420,50 C560,10 700,80 840,40 C920,25 1060,65 1200,50',
    duration: 11,
    delay: 1.5,
  },
  {
    color: '#fde68a',
    opacity: 0.25,
    strokeWidth: 1,
    initialD: 'M0,50 C180,10 360,90 540,55 C720,15 900,80 1080,50 C1140,35 1180,60 1200,50',
    animateD: 'M0,65 C180,25 360,105 540,70 C720,30 900,95 1080,65 C1140,50 1180,75 1200,65',
    duration: 13,
    delay: 0.8,
  },
  {
    color: '#c4b5fd',
    opacity: 0.28,
    strokeWidth: 1.3,
    initialD: 'M0,45 C200,5 400,85 600,50 C800,15 1000,75 1200,45',
    animateD: 'M0,60 C200,20 400,100 600,65 C800,30 1000,90 1200,60',
    duration: 10,
    delay: 2,
  },
  {
    color: '#86efac',
    opacity: 0.22,
    strokeWidth: 1,
    initialD: 'M0,55 C150,18 300,95 450,58 C600,22 750,88 900,55 C1050,22 1150,72 1200,58',
    animateD: 'M0,40 C150,3 300,80 450,43 C600,7 750,73 900,40 C1050,7 1150,57 1200,43',
    duration: 14,
    delay: 0.4,
  },
]

export default function ConversationWave() {
  return (
    <div
      className="absolute inset-x-0 bottom-0 overflow-hidden pointer-events-none"
      style={{ height: '200px' }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
        className="w-full h-full"
        style={{ transform: 'scaleY(-1)' }}
      >
        {WAVES.map((wave, i) => (
          <motion.path
            key={i}
            d={wave.initialD}
            fill="none"
            stroke={wave.color}
            strokeWidth={wave.strokeWidth}
            opacity={wave.opacity}
            animate={{ d: [wave.initialD, wave.animateD, wave.initialD] }}
            transition={{
              duration: wave.duration,
              delay: wave.delay,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        ))}
      </svg>
    </div>
  )
}
