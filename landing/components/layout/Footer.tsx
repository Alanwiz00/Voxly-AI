import Image from 'next/image'

const APP = 'https://app.voxlyai.online'

export default function Footer() {
  return (
    <footer className="section-footer">
      <div className="container-v py-14">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 mb-10">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <Image src="/logo.svg" alt="VoxlyAI" width={28} height={28} />
              <p
                className="text-2xl font-normal"
                style={{ fontFamily: 'var(--font-instrument-serif, Georgia, serif)', color: '#fff', letterSpacing: '-0.02em' }}
              >
                VoxlyAI
              </p>
            </div>
            <p className="text-sm leading-relaxed max-w-xs" style={{ color: '#888' }}>
              Your voice, amplified. AI that learns how you write and generates posts across every platform, in seconds.
            </p>
            <div className="flex gap-3 mt-6">
              <a href="https://twitter.com/voxlyai" aria-label="Twitter" className="footer-social-link" style={{ color: '#888' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.741l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </a>
              <a href="https://www.okx.ai/agents/10008" aria-label="VoxlyAI on OKX.AI" className="footer-social-link" style={{ color: '#888' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="6" height="6" rx="1"/>
                  <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>
                </svg>
              </a>
            </div>
          </div>

          {/* Links */}
          <div>
            <p className="text-xs font-medium tracking-widest uppercase mb-4" style={{ color: '#555' }}>Product</p>
            <ul className="space-y-2.5">
              {FOOTER_PRODUCT.map((l) => (
                <li key={l.label}>
                  <a href={l.href} className="text-sm hover:text-white transition-colors" style={{ color: '#888' }}>
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-xs font-medium tracking-widest uppercase mb-4" style={{ color: '#555' }}>Company</p>
            <ul className="space-y-2.5">
              {FOOTER_COMPANY.map((l) => (
                <li key={l.label}>
                  <a href={l.href} className="text-sm hover:text-white transition-colors" style={{ color: '#888' }}>
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="divider" style={{ background: '#1a1a1a' }} />
        <div className="flex flex-col md:flex-row justify-between items-center pt-8 gap-4">
          <p className="text-xs" style={{ color: '#555' }}>
            © {new Date().getFullYear()} VoxlyAI. All rights reserved.
          </p>
          <div className="flex gap-6">
            <a href="/privacy" className="text-xs hover:text-white transition-colors" style={{ color: '#555' }}>Privacy</a>
            <a href="/terms" className="text-xs hover:text-white transition-colors" style={{ color: '#555' }}>Terms</a>
          </div>
        </div>
      </div>
    </footer>
  )
}

const FOOTER_PRODUCT = [
  { label: 'Dashboard',    href: `https://app.voxlyai.online` },
  { label: 'API Docs',     href: '/api-docs' },
  { label: 'OKX.AI Agent', href: 'https://okx.ai' },
  { label: 'Changelog',    href: '#' },
]
const FOOTER_COMPANY = [
  { label: 'About',   href: '#' },
  { label: 'Privacy', href: '/privacy' },
  { label: 'Terms',   href: '/terms' },
  { label: 'Contact', href: 'mailto:hello@voxlyai.online' },
]
