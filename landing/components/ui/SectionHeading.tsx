interface SectionHeadingProps {
  eyebrow?: string
  title: string
  subtitle?: string
  center?: boolean
  light?: boolean
}

export default function SectionHeading({
  eyebrow,
  title,
  subtitle,
  center = false,
  light = false,
}: SectionHeadingProps) {
  return (
    <div className={`${center ? 'text-center' : ''} mb-8`}>
      {eyebrow && (
        <p className="eyebrow mb-4">{eyebrow}</p>
      )}
      <h2 className="display-lg" style={{ color: light ? '#fff' : undefined }}>
        {title}
      </h2>
      {subtitle && (
        <p
          className="mt-5 max-w-2xl text-lg leading-relaxed"
          style={{ color: light ? '#aaa' : 'var(--color-ink-2)', marginInline: center ? 'auto' : undefined }}
        >
          {subtitle}
        </p>
      )}
    </div>
  )
}
