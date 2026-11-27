import {
  Badge,
  Button,
  Checkbox,
  Group,
  Image,
  Menu,
  Pagination,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Container, Page } from '../api/types'
import Hazards from '../components/Hazards'
import StructureEditorModal from '../components/StructureEditorModal'
import { formatAmount, useApp } from '../components/context'

const STATUS_COLOR: Record<string, string> = {
  available: 'green', borrowed: 'blue', empty: 'gray', missing: 'orange', disposed: 'dark',
}

export default function Inventory() {
  const { config } = useApp()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(params.get('q') ?? '')
  const [drawing, setDrawing] = useState(false)
  const [mode, setMode] = useState<'substructure' | 'similar'>('substructure')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const query = new URLSearchParams(params)
  const results = useQuery({
    queryKey: ['containers', query.toString()],
    queryFn: () => api<Page<Container>>(`/api/containers/?${query}`),
  })

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v)
      else next.delete(k)
    }
    next.delete('page')
    setParams(next)
  }

  async function onSearch() {
    const value = text.trim()
    // A barcode scanner types the code and presses Enter: jump straight to that container.
    if (value) {
      const hit = await api<Page<Container>>(`/api/containers/?barcode=${encodeURIComponent(value)}`)
      if (hit.count === 1) return navigate(`/containers/${hit.results[0].id}`)
    }
    update({ q: value || null })
  }

  function toggle(id: string) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const printLabels = (layout: string) =>
    window.open(`/api/containers/labels/?layout=${layout}&ids=${[...selected].join(',')}`)

  const structureQuery = params.get('substructure') ?? params.get('similar')
  const page = Number(params.get('page') ?? 1)

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Inventory</Title>
        <Button component={Link} to="/inventory/new">Add container</Button>
      </Group>

      <Group align="flex-end">
        <TextInput
          flex={1}
          label="Search or scan"
          placeholder="Name, CAS, formula, synonym, or scan a barcode"
          value={text}
          onChange={(e) => setText(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          autoFocus
        />
        <Button onClick={onSearch}>Search</Button>
        <SegmentedControl
          value={mode}
          onChange={(v) => setMode(v as typeof mode)}
          data={[{ label: 'Substructure', value: 'substructure' },
                 { label: 'Similar', value: 'similar' }]}
        />
        <Button variant="light" onClick={() => setDrawing(true)}>Draw structure</Button>
      </Group>

      {structureQuery && (
        <Group gap="xs">
          <Badge variant="light" size="lg">
            {params.has('substructure') ? 'Substructure' : 'Similarity'} search active
          </Badge>
          <Button size="xs" variant="subtle"
            onClick={() => update({ substructure: null, similar: null })}>
            Clear
          </Button>
        </Group>
      )}

      <Group justify="space-between">
        <Text size="sm" c="dimmed">{results.data?.count ?? 0} containers</Text>
        <Menu>
          <Menu.Target>
            <Button size="xs" variant="default" disabled={!selected.size}>
              Print labels ({selected.size})
            </Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={() => printLabels('roll-62x29')}>Label printer (62 × 29 mm)</Menu.Item>
            <Menu.Item onClick={() => printLabels('a4-3x7')}>A4 sheet (3 × 7)</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>

      <Table.ScrollContainer minWidth={800}>
        <Table highlightOnHover verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th />
              <Table.Th>Structure</Table.Th>
              <Table.Th>Compound</Table.Th>
              <Table.Th>Amount</Table.Th>
              <Table.Th>Location</Table.Th>
              <Table.Th>Group</Table.Th>
              <Table.Th>Hazards</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {results.data?.results.map((c) => (
              <Table.Tr key={c.id} style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/containers/${c.id}`)}>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Checkbox checked={selected.has(c.id)} onChange={() => toggle(c.id)}
                    aria-label={`Select ${c.barcode}`} />
                </Table.Td>
                <Table.Td>
                  {c.compound_detail.smiles && (
                    <Image src={`/api/compounds/${c.compound}/depict/`} w={90} h={60}
                      fit="contain" alt="" />
                  )}
                </Table.Td>
                <Table.Td>
                  <Text fw={500}>{c.compound_detail.name}</Text>
                  <Text size="xs" c="dimmed">
                    {c.compound_detail.cas || c.compound_detail.formula} · {c.barcode}
                  </Text>
                </Table.Td>
                <Table.Td>{formatAmount(c.amount, c.unit)}</Table.Td>
                <Table.Td>
                  <Text size="sm">{c.location_path || '—'}</Text>
                  {c.storage_warning && <Badge color="orange" size="xs">storage conflict</Badge>}
                </Table.Td>
                <Table.Td>{c.group_name}</Table.Td>
                <Table.Td>
                  <Hazards pictograms={c.compound_detail.ghs_pictograms}
                    signalWord={c.compound_detail.signal_word} />
                </Table.Td>
                <Table.Td>
                  <Badge color={c.is_expired ? 'red' : STATUS_COLOR[c.status]} variant="light">
                    {c.is_expired ? 'expired' : c.status}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {(results.data?.count ?? 0) > 50 && (
        <Pagination
          total={Math.ceil((results.data?.count ?? 0) / 50)}
          value={page}
          onChange={(p) => { const n = new URLSearchParams(params); n.set('page', String(p)); setParams(n) }}
        />
      )}

      <StructureEditorModal
        opened={drawing}
        onClose={() => setDrawing(false)}
        editorKind={config.structure_editor}
        submitLabel="Search"
        onSubmit={async (molfile) => {
          // Molfiles are too long for a URL; the server turns the drawing into SMILES.
          const { smiles } = await api<{ smiles: string }>('/api/chem/analyse/', {
            method: 'POST',
            body: JSON.stringify({ structure: molfile }),
          })
          update(mode === 'substructure'
            ? { substructure: smiles, similar: null }
            : { similar: smiles, substructure: null })
        }}
      />
    </Stack>
  )
}
