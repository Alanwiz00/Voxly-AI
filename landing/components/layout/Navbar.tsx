'use client'
import { useEffect, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'

const APP = 'https://app.voxlyai.online'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled ? 'nav-scrolled' : 'bg-transparent'
      }`}
    >
      <div className="container-v">
        <nav className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 text-[var(--color-ink)] no-underline">
            <Image src="/logo.svg" alt="VoxlyAI" width={28} height={28} priority />
            <span
              className="text-xl font-serif font-normal tracking-tight"
              style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)' }}
            >
              Voxly<span style={{ color: 'var(--color-ink-3)' }}>AI</span>
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-sm font-medium text-[var(--color-ink-2)] hover:text-[var(--color-ink)] transition-colors"
              >
                {l.label}
              </a>
            ))}
          </div>

          {/* CTA */}
          <div className="hidden md:flex items-center gap-3">
            <a href={`${APP}/login`} className="btn-secondary text-sm py-2 px-4">
              Sign in
            </a>
            <a href={`${APP}/register`} className="btn-primary text-sm py-2 px-4">
              Get started free
            </a>
          </div>

          {/* Mobile burger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 text-[var(--color-ink)] rounded-md"
            aria-label="Toggle menu"
          >
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {menuOpen ? (
                <>
                  <line x1="4" y1="4" x2="18" y2="18" />
                  <line x1="18" y1="4" x2="4" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="19" y2="6" />
                  <line x1="3" y1="11" x2="19" y2="11" />
                  <line x1="3" y1="16" x2="19" y2="16" />
                </>
              )}
            </svg>
          </button>
        </nav>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-[var(--color-border)] py-4 space-y-3 bg-[var(--color-paper)]">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setMenuOpen(false)}
                className="block text-sm font-medium py-2 text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
              >
                {l.label}
              </a>
            ))}
            <div className="pt-3 flex flex-col gap-2">
              <a href={`${APP}/login`} className="btn-secondary text-sm w-full justify-center">
                Sign in
              </a>
              <a href={`${APP}/register`} className="btn-primary text-sm w-full justify-center">
                Get started free
              </a>
            </div>
          </div>
        )}
      </div>
    </header>
  )
}

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Capabilities',  href: '#capabilities' },
  { label: 'API docs',      href: '/api-docs' },
]
