import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import Hero from '@/components/hero/Hero'
import LogoCloud from '@/components/sections/LogoCloud'
import Stats from '@/components/sections/Stats'
import Capabilities from '@/components/sections/Capabilities'
import DemoSection from '@/components/sections/DemoSection'
import HowItWorks from '@/components/sections/HowItWorks'
import Testimonial from '@/components/sections/Testimonial'
import ApiSection from '@/components/sections/ApiSection'
import FAQ from '@/components/sections/FAQ'
import CTA from '@/components/sections/CTA'
import Newsletter from '@/components/sections/Newsletter'

export default function Home() {
  return (
    <>
      <Navbar />

      {/* Paper → Paper → Warm → Dark → Paper → Paper → Warm → Paper → Warm → Paper → Footer */}
      <Hero />
      <LogoCloud />
      <Stats />
      <Capabilities />
      <DemoSection />
      <HowItWorks />
      <Testimonial />
      <ApiSection />
      <FAQ />
      <CTA />
      <Newsletter />

      <Footer />
    </>
  )
}
