import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['var(--font-instrument-serif)', 'Georgia', 'serif'],
        sans:  ['var(--font-inter)',            'system-ui', 'sans-serif'],
      },
      colors: {
        paper:  '#ffffff',
        warm:   '#f3f2ee',
        dark:   '#080808',
        ink:    '#0d0d0d',
        ink2:   '#3a3a3a',
        ink3:   '#767676',
        border: '#e4e2dc',
      },
      maxWidth: {
        container: '1280px',
      },
    },
  },
  plugins: [],
}
export default config
