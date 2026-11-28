import { Box, Group, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'

import { post } from '../api/client'

/** Depicts a SMILES string with RDKit on the server (cached per SMILES). */
export function SmilesImage({ smiles, width = 140, height = 100 }: { smiles: string; width?: number; height?: number }) {
  const q = useQuery({
    queryKey: ['depict', smiles],
    queryFn: () => post<{ svg: string }>('/api/chem/analyse/', { structure: smiles }),
    enabled: !!smiles,
    staleTime: Infinity,
    retry: false,
  })
  if (!smiles) return null
  if (!q.data) return <Box w={width} h={height} />
  return (
    <Box
      w={width}
      h={height}
      style={{ background: 'white', borderRadius: 6 }}
      dangerouslySetInnerHTML={{
        __html: q.data.svg.replace(/width='[^']*'/, `width='${width}'`).replace(/height='[^']*'/, `height='${height}'`),
      }}
    />
  )
}

/** Reaction scheme: reactants + reactants → products, from a reaction SMILES "A.B>C>D". */
export function ReactionScheme({ smiles }: { smiles: string }) {
  if (!smiles || !smiles.includes('>')) return null
  const [left, agents, right] = smiles.split('>')
  const parts = (s: string) => (s ? s.split('.').filter(Boolean) : [])
  return (
    <Group gap="xs" wrap="wrap" align="center">
      {parts(left).map((s, i) => (
        <Group key={`l${i}`} gap="xs">
          {i > 0 && <Text size="xl">+</Text>}
          <SmilesImage smiles={s} />
        </Group>
      ))}
      <Box ta="center" px="xs">
        <Text size="xs" c="dimmed">
          {parts(agents).length ? `${parts(agents).length} agent(s)` : ''}
        </Text>
        <Text size="xl">⟶</Text>
      </Box>
      {parts(right).map((s, i) => (
        <Group key={`r${i}`} gap="xs">
          {i > 0 && <Text size="xl">+</Text>}
          <SmilesImage smiles={s} />
        </Group>
      ))}
    </Group>
  )
}
