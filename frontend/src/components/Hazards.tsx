import { Badge, Group, Tooltip } from '@mantine/core'

const PICTOGRAMS: Record<string, string> = {
  GHS01: 'Explosive',
  GHS02: 'Flammable',
  GHS03: 'Oxidizing',
  GHS04: 'Compressed gas',
  GHS05: 'Corrosive',
  GHS06: 'Toxic',
  GHS07: 'Harmful / irritant',
  GHS08: 'Health hazard',
  GHS09: 'Environmental hazard',
}

/** GHS pictogram: red-bordered diamond with the code (no copyrighted artwork needed). */
function Diamond({ code }: { code: string }) {
  return (
    <Tooltip label={`${code}: ${PICTOGRAMS[code] ?? code}`}>
      <svg width="26" height="26" viewBox="0 0 26 26" role="img" aria-label={PICTOGRAMS[code]}>
        <rect x="5" y="5" width="16" height="16" transform="rotate(45 13 13)" fill="#fff"
          stroke="#e03131" strokeWidth="2.2" />
        <text x="13" y="16" textAnchor="middle" fontSize="7" fontWeight="700" fill="#212529">
          {code.slice(3)}
        </text>
      </svg>
    </Tooltip>
  )
}

export default function Hazards({
  pictograms,
  signalWord,
}: {
  pictograms: string[]
  signalWord?: string
}) {
  if (!pictograms.length && !signalWord) return null
  return (
    <Group gap={2} wrap="nowrap">
      {pictograms.map((p) => (
        <Diamond key={p} code={p} />
      ))}
      {signalWord && (
        <Badge size="xs" color={signalWord === 'danger' ? 'red' : 'orange'} ml={4}>
          {signalWord}
        </Badge>
      )}
    </Group>
  )
}
