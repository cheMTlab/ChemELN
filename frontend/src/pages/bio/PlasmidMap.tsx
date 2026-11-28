import { Box, Text } from '@mantine/core'

import type { Feature } from '../../api/modules'

const COLORS: Record<string, string> = {
  CDS: '#4dabf7',
  gene: '#4dabf7',
  promoter: '#51cf66',
  terminator: '#ff6b6b',
  rep_origin: '#fcc419',
  misc_feature: '#adb5bd',
  primer_bind: '#cc5de8',
  protein_bind: '#20c997',
  RBS: '#ff922b',
}

/** Circular (or linear) plasmid map drawn in SVG from 1-based feature coordinates. */
export default function PlasmidMap({
  name,
  size,
  features,
  circular = true,
}: {
  name: string
  size: number | null
  features: Feature[]
  circular?: boolean
}) {
  if (!size) return <Text c="dimmed">Add a sequence (or GenBank file) to draw the map.</Text>
  if (!circular) return <LinearMap size={size} features={features} name={name} />
  const R = 120
  const cx = 170
  const cy = 170
  const angle = (bp: number) => (bp / size) * 2 * Math.PI - Math.PI / 2
  const pt = (bp: number, r: number) => [cx + r * Math.cos(angle(bp)), cy + r * Math.sin(angle(bp))]
  const arc = (f: Feature, r: number) => {
    const [x1, y1] = pt(f.start, r)
    const [x2, y2] = pt(f.end, r)
    const large = (f.end - f.start) / size > 0.5 ? 1 : 0
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`
  }
  const ticks = Array.from({ length: 8 }, (_, i) => Math.round((i * size) / 8))
  return (
    <Box>
      <svg viewBox="0 0 340 340" width="100%" style={{ maxWidth: 420 }}>
        <circle cx={cx} cy={cy} r={R} fill="none" stroke="var(--mantine-color-dimmed)" strokeWidth={2} />
        {ticks.map((t) => {
          const [x1, y1] = pt(t, R - 4)
          const [x2, y2] = pt(t, R + 4)
          const [tx, ty] = pt(t, R - 16)
          return (
            <g key={t}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--mantine-color-dimmed)" />
              <text x={tx} y={ty} fontSize={8} textAnchor="middle" fill="var(--mantine-color-dimmed)">
                {t}
              </text>
            </g>
          )
        })}
        {features.map((f, i) => {
          const r = R + (f.strand === -1 ? -10 : 10) + (i % 2) * 0
          const mid = (f.start + f.end) / 2
          const [lx, ly] = pt(mid, R + 38)
          return (
            <g key={i}>
              <path d={arc(f, r)} fill="none" stroke={COLORS[f.type] ?? '#868e96'} strokeWidth={9} strokeLinecap="butt">
                <title>
                  {f.name} ({f.type}) {f.start}–{f.end} {f.strand === -1 ? '(−)' : '(+)'}
                </title>
              </path>
              <text x={lx} y={ly} fontSize={9} textAnchor="middle" fill="var(--mantine-color-text)">
                {f.name.slice(0, 18)}
              </text>
            </g>
          )
        })}
        <text x={cx} y={cy - 4} textAnchor="middle" fontWeight={700} fontSize={13} fill="var(--mantine-color-text)">
          {name}
        </text>
        <text x={cx} y={cy + 12} textAnchor="middle" fontSize={10} fill="var(--mantine-color-dimmed)">
          {size.toLocaleString()} bp
        </text>
      </svg>
    </Box>
  )
}

function LinearMap({ size, features, name }: { size: number; features: Feature[]; name: string }) {
  const W = 600
  const x = (bp: number) => 20 + ((W - 40) * bp) / size
  return (
    <svg viewBox={`0 0 ${W} 120`} width="100%">
      <text x={20} y={16} fontSize={12} fontWeight={700} fill="var(--mantine-color-text)">
        {name} · {size} bp
      </text>
      <line x1={20} x2={W - 20} y1={60} y2={60} stroke="var(--mantine-color-dimmed)" strokeWidth={2} />
      {features.map((f, i) => (
        <g key={i}>
          <rect x={x(f.start)} y={f.strand === -1 ? 62 : 48} width={Math.max(2, x(f.end) - x(f.start))} height={10} fill={COLORS[f.type] ?? '#868e96'}>
            <title>{`${f.name} ${f.start}–${f.end}`}</title>
          </rect>
          <text x={x(f.start)} y={f.strand === -1 ? 90 : 42} fontSize={9} fill="var(--mantine-color-text)">
            {f.name.slice(0, 16)}
          </text>
        </g>
      ))}
    </svg>
  )
}
