import { LineChart } from '@mantine/charts'
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  FileButton,
  Grid,
  Group,
  List,
  Modal,
  NumberInput,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api, post } from '../../api/client'
import type { Assay, Plate, PlateAnalysis, Well, WellRole } from '../../api/modules'
import type { Page } from '../../api/types'
import { hasRole, useApp } from '../../components/context'
import { CompoundPicker, defaultGroup, fmt, fmtDate, GroupPicker, notifyError, notifyOk } from '../../components/pickers'

const ROLE_COLOR: Record<WellRole, string> = {
  empty: 'transparent',
  sample: 'var(--mantine-color-blue-5)',
  positive: 'var(--mantine-color-green-6)',
  negative: 'var(--mantine-color-red-6)',
  blank: 'var(--mantine-color-gray-5)',
  standard: 'var(--mantine-color-yellow-5)',
}
const ROLES: { value: WellRole; label: string }[] = [
  { value: 'sample', label: 'Sample' },
  { value: 'positive', label: 'Positive control' },
  { value: 'negative', label: 'Negative control' },
  { value: 'blank', label: 'Blank' },
  { value: 'standard', label: 'Standard' },
  { value: 'empty', label: 'Empty' },
]

export function PlateList() {
  const { me } = useApp()
  const nav = useNavigate()
  const qc = useQueryClient()
  const plates = useQuery({ queryKey: ['plates'], queryFn: () => api<Page<Plate>>('/api/plates/') })
  const assays = useQuery({ queryKey: ['assays'], queryFn: () => api<Page<Assay>>('/api/assays/') })
  const [creating, setCreating] = useState(false)
  const [assayOpen, setAssayOpen] = useState(false)
  const [v, setV] = useState({ group: defaultGroup(me), name: '', format: '96', kind: 'assay', assay: null as string | null, template: null as string | null })
  const [a, setA] = useState({ group: defaultGroup(me), name: '', readout: 'absorbance', wavelength: '', unit: '', target: '', higher_is_active: false })
  const create = useMutation({
    mutationFn: () => post<Plate>('/api/plates/', { ...v, format: Number(v.format) }),
    onSuccess: (p) => nav(`/plates/${p.id}`),
    onError: notifyError,
  })
  const createAssay = useMutation({
    mutationFn: () => post('/api/assays/', a),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assays'] })
      setAssayOpen(false)
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={2}>Well plates & assays</Title>
          <Text size="sm" c="dimmed">
            Lay out samples and controls, import plate-reader data, check assay quality (Z′) and fit dose-response curves.
          </Text>
        </div>
        <Group>
          <Button variant="default" onClick={() => setAssayOpen(true)}>
            New assay
          </Button>
          <Button onClick={() => setCreating(true)}>New plate</Button>
        </Group>
      </Group>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Barcode</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Format</Table.Th>
            <Table.Th>Assay</Table.Th>
            <Table.Th>Readings</Table.Th>
            <Table.Th>Created</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {plates.data?.results.map((p) => (
            <Table.Tr key={p.id} onClick={() => nav(`/plates/${p.id}`)} style={{ cursor: 'pointer' }}>
              <Table.Td ff="monospace">{p.barcode}</Table.Td>
              <Table.Td>
                {p.name}
                <Text size="xs" c="dimmed">
                  {p.group_name} · {p.kind}
                </Text>
              </Table.Td>
              <Table.Td>{p.format}-well</Table.Td>
              <Table.Td>{p.assay_name}</Table.Td>
              <Table.Td>{p.measurement_count ? <Badge>{p.measurement_count}</Badge> : ''}</Table.Td>
              <Table.Td>{fmtDate(p.created_at)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Modal opened={creating} onClose={() => setCreating(false)} title="New plate">
        <Stack>
          <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} />
          <TextInput label="Name" required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} placeholder="IC50 run 1 – kinase X" />
          <Group grow>
            <Select label="Format" data={['6', '12', '24', '48', '96', '384', '1536']} value={v.format} onChange={(f) => f && setV({ ...v, format: f })} />
            <Select label="Kind" data={[{ value: 'assay', label: 'Assay' }, { value: 'culture', label: 'Culture' }, { value: 'library', label: 'Compound library' }, { value: 'pcr', label: 'PCR / qPCR' }, { value: 'storage', label: 'Storage' }]} value={v.kind} onChange={(k) => k && setV({ ...v, kind: k })} />
          </Group>
          <Select label="Assay" clearable data={(assays.data?.results ?? []).map((x) => ({ value: x.id, label: x.name }))} value={v.assay} onChange={(x) => setV({ ...v, assay: x })} />
          <Select
            label="Copy layout from"
            clearable
            data={(plates.data?.results ?? []).filter((p) => String(p.format) === v.format).map((p) => ({ value: p.id, label: `${p.name} (${p.barcode})` }))}
            value={v.template}
            onChange={(x) => setV({ ...v, template: x })}
          />
          <Button onClick={() => create.mutate()} disabled={!v.name}>
            Create
          </Button>
        </Stack>
      </Modal>
      <Modal opened={assayOpen} onClose={() => setAssayOpen(false)} title="New assay">
        <Stack>
          <GroupPicker value={a.group} onChange={(g) => setA({ ...a, group: g })} />
          <TextInput label="Name" required value={a.name} onChange={(e) => setA({ ...a, name: e.target.value })} />
          <Group grow>
            <Select label="Readout" data={['absorbance', 'fluorescence', 'luminescence', 'OD600', 'qPCR Ct', 'other']} value={a.readout} onChange={(r) => r && setA({ ...a, readout: r })} />
            <TextInput label="Wavelength" value={a.wavelength} onChange={(e) => setA({ ...a, wavelength: e.target.value })} placeholder="ex485/em520" />
          </Group>
          <TextInput label="Target" value={a.target} onChange={(e) => setA({ ...a, target: e.target.value })} />
          <Checkbox label="Signal rises with activity (off = inhibition assay)" checked={a.higher_is_active} onChange={(e) => setA({ ...a, higher_is_active: e.currentTarget.checked })} />
          <Button onClick={() => createAssay.mutate()} disabled={!a.name}>
            Create
          </Button>
        </Stack>
      </Modal>
    </Stack>
  )
}

export function PlatePage() {
  const { id } = useParams()
  const { me } = useApp()
  const qc = useQueryClient()
  const plate = useQuery({ queryKey: ['plate', id], queryFn: () => api<Plate>(`/api/plates/${id}/`) })
  const wells = useQuery({ queryKey: ['wells', id], queryFn: () => api<Well[]>(`/api/plates/${id}/wells/`) })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['wells', id] })
    qc.invalidateQueries({ queryKey: ['plate-analysis', id] })
    qc.invalidateQueries({ queryKey: ['plate', id] })
  }
  const p = plate.data
  if (!p || !wells.data) return null
  const canWrite = hasRole(me, p.group, 'member')
  return (
    <Stack>
      <div>
        <Anchor component={Link} to="/plates" size="sm">
          Plates
        </Anchor>
        <Group justify="space-between">
          <Title order={2}>{p.name}</Title>
          <Group>
            <Badge variant="outline" size="lg" ff="monospace">
              {p.barcode}
            </Badge>
            <Button component="a" href={`/api/plates/${p.id}/export/`} variant="default" size="xs">
              Export CSV
            </Button>
          </Group>
        </Group>
        <Text size="sm" c="dimmed">
          {p.format}-well {p.kind} plate · {p.group_name} {p.assay_name && `· ${p.assay_name}`}
        </Text>
      </div>
      <Tabs defaultValue={p.measurement_count ? 'analysis' : 'layout'} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="layout">Layout</Tabs.Tab>
          <Tabs.Tab value="readings">Import readings</Tabs.Tab>
          <Tabs.Tab value="analysis">Results & QC</Tabs.Tab>
          <Tabs.Tab value="kinetics">Kinetics</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="layout" pt="md">
          <Layout plate={p} wells={wells.data} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="readings" pt="md">
          <Readings plate={p} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="analysis" pt="md">
          <Results plate={p} wells={wells.data} />
        </Tabs.Panel>
        <Tabs.Panel value="kinetics" pt="md">
          <Kinetics plate={p} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

// --- plate grid --------------------------------------------------------------------------

const rowName = (i: number) => (i < 26 ? String.fromCharCode(65 + i) : String.fromCharCode(64 + Math.floor(i / 26)) + String.fromCharCode(65 + (i % 26)))

function PlateGrid({
  plate,
  cell,
  selected,
  onToggle,
  onSelectMany,
}: {
  plate: Plate
  cell: (name: string, r: number, c: number) => { bg: string; text?: string; tip?: string; border?: string; fg?: string }
  selected?: Set<string>
  onToggle?: (name: string) => void
  onSelectMany?: (names: string[]) => void
}) {
  const size = plate.format >= 384 ? 22 : plate.format >= 96 ? 38 : 56
  const all = (pred: (r: number, c: number) => boolean) => {
    const names: string[] = []
    for (let r = 0; r < plate.rows; r++) for (let c = 0; c < plate.cols; c++) if (pred(r, c)) names.push(`${rowName(r)}${c + 1}`)
    return names
  }
  return (
    <ScrollArea>
      <table style={{ borderCollapse: 'separate', borderSpacing: 2, userSelect: 'none' }}>
        <thead>
          <tr>
            <th>
              {onSelectMany && (
                <Text size="xs" c="blue" style={{ cursor: 'pointer' }} onClick={() => onSelectMany(all(() => true))}>
                  all
                </Text>
              )}
            </th>
            {Array.from({ length: plate.cols }, (_, c) => (
              <th key={c} onClick={() => onSelectMany?.(all((_r, cc) => cc === c))} style={{ cursor: onSelectMany ? 'pointer' : undefined }}>
                <Text size="xs">{c + 1}</Text>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: plate.rows }, (_, r) => (
            <tr key={r}>
              <th onClick={() => onSelectMany?.(all((rr) => rr === r))} style={{ cursor: onSelectMany ? 'pointer' : undefined }}>
                <Text size="xs">{rowName(r)}</Text>
              </th>
              {Array.from({ length: plate.cols }, (_, c) => {
                const name = `${rowName(r)}${c + 1}`
                const info = cell(name, r, c)
                const isSel = selected?.has(name)
                return (
                  <td key={c}>
                    <Tooltip label={info.tip ?? name} disabled={!info.tip} openDelay={300}>
                      <div
                        onClick={() => onToggle?.(name)}
                        style={{
                          width: size,
                          height: size * 0.8,
                          borderRadius: size / 2,
                          background: info.bg,
                          color: info.fg,
                          border: isSel ? '3px solid var(--mantine-color-orange-6)' : info.border ?? '1px solid var(--mantine-color-default-border)',
                          display: 'grid',
                          placeItems: 'center',
                          fontSize: size > 30 ? 10 : 7,
                          cursor: onToggle ? 'pointer' : 'default',
                          overflow: 'hidden',
                        }}
                      >
                        {info.text}
                      </div>
                    </Tooltip>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollArea>
  )
}

// --- layout ------------------------------------------------------------------------------

function Layout({ plate, wells, canWrite, onChange }: { plate: Plate; wells: Well[]; canWrite: boolean; onChange: () => void }) {
  const byName = useMemo(() => new Map(wells.map((w) => [w.name, w])), [wells])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [vals, setVals] = useState({ role: 'sample' as WellRole, label: '', concentration: '' as number | '', concentration_unit: 'µM', compound: null as string | null, group_label: '', excluded: false })
  const [dil, setDil] = useState({ start_well: 'A2', direction: 'row', steps: 10, top: 100, factor: 3, unit: 'µM', label: '', compound: null as string | null, replicates: 2 })
  const apply = useMutation({
    mutationFn: (values: Record<string, unknown>) => post(`/api/plates/${plate.id}/layout/`, { wells: [...selected], values }),
    onSuccess: () => {
      onChange()
      setSelected(new Set())
    },
    onError: notifyError,
  })
  const dilution = useMutation({
    mutationFn: () => post<{ updated: number }>(`/api/plates/${plate.id}/dilution/`, dil),
    onSuccess: (r) => {
      notifyOk(`${r.updated} wells filled`)
      onChange()
    },
    onError: notifyError,
  })
  const toggle = (n: string) => {
    const s = new Set(selected)
    if (s.has(n)) s.delete(n)
    else s.add(n)
    setSelected(s)
  }
  const many = (names: string[]) => {
    const allIn = names.every((n) => selected.has(n))
    const s = new Set(selected)
    names.forEach((n) => (allIn ? s.delete(n) : s.add(n)))
    setSelected(s)
  }
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 8 }}>
        <PlateGrid
          plate={plate}
          selected={selected}
          onToggle={canWrite ? toggle : undefined}
          onSelectMany={canWrite ? many : undefined}
          cell={(name) => {
            const w = byName.get(name)
            if (!w) return { bg: 'transparent' }
            return {
              bg: ROLE_COLOR[w.role],
              fg: w.role === 'empty' ? undefined : 'white',
              text: w.concentration ? fmt(w.concentration, 2) : w.role === 'positive' ? '+' : w.role === 'negative' ? '−' : w.role === 'blank' ? 'B' : '',
              border: w.excluded ? '2px dashed var(--mantine-color-red-7)' : undefined,
              tip: [name, w.role, w.label, w.compound_name, w.strain_code, w.plasmid_code, w.concentration && `${w.concentration} ${w.concentration_unit}`, w.replicate && `rep ${w.replicate}`, w.excluded && 'EXCLUDED'].filter(Boolean).join(' · '),
            }
          }}
        />
        <Group gap="md" mt="xs">
          {ROLES.map((r) => (
            <Group key={r.value} gap={4}>
              <div style={{ width: 12, height: 12, borderRadius: 6, background: ROLE_COLOR[r.value], border: '1px solid var(--mantine-color-default-border)' }} />
              <Text size="xs">{r.label}</Text>
            </Group>
          ))}
        </Group>
        {canWrite && <Text size="xs" c="dimmed" mt={4}>Click wells, row letters or column numbers to select; then apply properties on the right.</Text>}
      </Grid.Col>
      {canWrite && (
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card withBorder>
              <Text fw={600} mb="xs">
                Selected: {selected.size} well(s)
              </Text>
              <Stack gap="xs">
                <Select label="Role" data={ROLES} value={vals.role} onChange={(r) => r && setVals({ ...vals, role: r as WellRole })} />
                <TextInput label="Label / sample ID" value={vals.label} onChange={(e) => setVals({ ...vals, label: e.target.value })} />
                <CompoundPicker label="Compound" value={vals.compound} onChange={(c) => setVals({ ...vals, compound: c })} />
                <Group grow>
                  <NumberInput label="Concentration" value={vals.concentration} onChange={(x) => setVals({ ...vals, concentration: x === '' ? '' : Number(x) })} />
                  <Select label="Unit" data={['nM', 'µM', 'mM', 'µg/mL', 'mg/mL', '%']} value={vals.concentration_unit} onChange={(u) => u && setVals({ ...vals, concentration_unit: u })} />
                </Group>
                <TextInput label="Curve group" description="Wells with the same group form one dose-response" value={vals.group_label} onChange={(e) => setVals({ ...vals, group_label: e.target.value })} />
                <Group grow>
                  <Button disabled={!selected.size} onClick={() => apply.mutate({ ...vals, concentration: vals.concentration === '' ? null : vals.concentration })}>
                    Apply
                  </Button>
                  <Button variant="light" color="red" disabled={!selected.size} onClick={() => apply.mutate({ excluded: true })}>
                    Exclude
                  </Button>
                  <Button variant="subtle" disabled={!selected.size} onClick={() => apply.mutate({ excluded: false })}>
                    Include
                  </Button>
                </Group>
              </Stack>
            </Card>
            <Card withBorder>
              <Text fw={600} mb="xs">
                Serial dilution
              </Text>
              <Stack gap="xs">
                <Group grow>
                  <TextInput label="Start well" value={dil.start_well} onChange={(e) => setDil({ ...dil, start_well: e.target.value })} />
                  <Select label="Along" data={[{ value: 'row', label: 'Row →' }, { value: 'column', label: 'Column ↓' }]} value={dil.direction} onChange={(d) => d && setDil({ ...dil, direction: d })} />
                </Group>
                <Group grow>
                  <NumberInput label="Steps" min={2} value={dil.steps} onChange={(x) => setDil({ ...dil, steps: Number(x) || 8 })} />
                  <NumberInput label="Top conc." value={dil.top} onChange={(x) => setDil({ ...dil, top: Number(x) })} />
                  <NumberInput label="Factor" min={1.1} step={0.5} value={dil.factor} onChange={(x) => setDil({ ...dil, factor: Number(x) })} />
                </Group>
                <Group grow>
                  <Select label="Unit" data={['nM', 'µM', 'mM', 'µg/mL']} value={dil.unit} onChange={(u) => u && setDil({ ...dil, unit: u })} />
                  <NumberInput label="Replicates" min={1} max={4} value={dil.replicates} onChange={(x) => setDil({ ...dil, replicates: Number(x) || 1 })} />
                </Group>
                <TextInput label="Name" value={dil.label} onChange={(e) => setDil({ ...dil, label: e.target.value })} placeholder="Cmpd-7" />
                <CompoundPicker label="Compound" value={dil.compound} onChange={(c) => setDil({ ...dil, compound: c })} />
                <Button onClick={() => dilution.mutate()}>Fill series</Button>
              </Stack>
            </Card>
          </Stack>
        </Grid.Col>
      )}
    </Grid>
  )
}

// --- readings ----------------------------------------------------------------------------

function Readings({ plate, canWrite, onChange }: { plate: Plate; canWrite: boolean; onChange: () => void }) {
  const [text, setText] = useState('')
  const [channel, setChannel] = useState('signal')
  const [timepoint, setTimepoint] = useState<number | ''>(0)
  const imp = useMutation({
    mutationFn: (file?: File) => {
      const fd = new FormData()
      if (file) fd.append('file', file)
      else fd.append('text', text)
      fd.append('channel', channel)
      fd.append('timepoint', String(timepoint || 0))
      return post<{ imported: number; channels: string[] }>(`/api/plates/${plate.id}/import-readings/`, fd)
    },
    onSuccess: (r) => {
      notifyOk(`${r.imported} readings imported (${r.channels.join(', ')})`)
      setText('')
      onChange()
    },
    onError: notifyError,
  })
  if (!canWrite) return <Alert>Only group members can import readings.</Alert>
  return (
    <Stack maw={900}>
      <Text size="sm">
        Paste or upload a plate-reader export. Two layouts are recognised automatically:
      </Text>
      <List size="sm">
        <List.Item>
          <b>Grid</b>: rows A, B, C… and one column per plate column (the usual reader export; CSV, semicolon or tab).
        </List.Item>
        <List.Item>
          <b>Long</b>: columns <code>well</code>, <code>value</code> and optionally <code>channel</code>, <code>time</code> (kinetic reads, growth curves).
        </List.Item>
      </List>
      <Group>
        <TextInput label="Channel / read name" value={channel} onChange={(e) => setChannel(e.target.value)} w={200} />
        <NumberInput label="Time point (min)" value={timepoint} onChange={(x) => setTimepoint(x === '' ? '' : Number(x))} w={160} />
      </Group>
      <Textarea ff="monospace" autosize minRows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder={',1,2,3,…\nA,0.512,0.498,…\nB,…'} />
      <Group>
        <Button onClick={() => imp.mutate(undefined)} disabled={!text.trim()} loading={imp.isPending}>
          Import pasted data
        </Button>
        <FileButton onChange={(f) => f && imp.mutate(f)} accept=".csv,.txt,.tsv">
          {(props) => (
            <Button {...props} variant="default">
              Upload file
            </Button>
          )}
        </FileButton>
      </Group>
    </Stack>
  )
}

// --- results -----------------------------------------------------------------------------

function Results({ plate, wells }: { plate: Plate; wells: Well[] }) {
  const [channel, setChannel] = useState<string | null>(null)
  const [mode, setMode] = useState('raw')
  const a = useQuery({
    queryKey: ['plate-analysis', plate.id, channel],
    queryFn: () => api<PlateAnalysis>(`/api/plates/${plate.id}/analysis/?channel=${channel ?? 'signal'}`),
  })
  const byName = useMemo(() => new Map(wells.map((w) => [w.name, w])), [wells])
  const d = a.data
  if (!d) return null
  if (!d.channels.length) return <Alert>No readings yet. Import plate-reader data first.</Alert>
  const values = d.grid.flat().filter((x): x is number => x !== null)
  const pct = d.percent_activity ?? {}
  const lo = mode === 'pct' ? 0 : Math.min(...values)
  const hi = mode === 'pct' ? 100 : Math.max(...values)
  const color = (v: number | null | undefined) => {
    if (v === null || v === undefined) return 'transparent'
    const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)))
    return `hsl(${240 - 240 * t} 75% ${45 + 15 * t}%)`
  }
  return (
    <Stack>
      <Group>
        <Select label="Channel" data={d.channels} value={channel ?? d.channel} onChange={setChannel} w={180} />
        <SegmentedControl
          mt="lg"
          value={mode}
          onChange={setMode}
          data={[
            { value: 'raw', label: 'Raw signal' },
            { value: 'pct', label: '% activity', disabled: !d.percent_activity },
          ]}
        />
      </Group>
      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <PlateGrid
            plate={plate}
            cell={(name, r, c) => {
              const raw = d.grid[r]?.[c]
              const v = mode === 'pct' ? pct[name] : raw
              const w = byName.get(name)
              return {
                bg: color(v),
                fg: 'white',
                text: v !== undefined && v !== null ? fmt(v, mode === 'pct' ? 0 : 2) : '',
                border: w?.role === 'positive' ? '2px solid var(--mantine-color-green-7)' : w?.role === 'negative' ? '2px solid var(--mantine-color-red-7)' : w?.excluded ? '2px dashed black' : undefined,
                tip: `${name} · ${w?.role ?? ''} ${w?.label ?? ''} · raw ${fmt(raw)}${pct[name] !== undefined ? ` · ${fmt(pct[name], 1)} %` : ''}`,
              }
            }}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card withBorder>
              <Text fw={600}>Assay quality</Text>
              {d.z_prime !== undefined && d.z_prime !== null ? (
                <Text size="xl" fw={700} c={d.z_prime >= 0.5 ? 'green' : d.z_prime > 0 ? 'orange' : 'red'}>
                  Z′ = {fmt(d.z_prime, 2)}
                </Text>
              ) : null}
              <List size="sm" spacing={2}>
                {d.plain.map((p, i) => (
                  <List.Item key={i}>{p}</List.Item>
                ))}
              </List>
              <Table fz="xs" mt="xs">
                <Table.Tbody>
                  {Object.entries(d.controls).map(([k, s]) =>
                    s ? (
                      <Table.Tr key={k}>
                        <Table.Td>{k}</Table.Td>
                        <Table.Td>n={s.n}</Table.Td>
                        <Table.Td>mean {fmt(s.mean)}</Table.Td>
                        <Table.Td>CV {fmt(s.cv, 1)} %</Table.Td>
                      </Table.Tr>
                    ) : null,
                  )}
                </Table.Tbody>
              </Table>
            </Card>
            {d.hits && d.hits.length > 0 && (
              <Card withBorder>
                <Text fw={600}>Hits (≥ 50 % activity)</Text>
                <ScrollArea h={180}>
                  <Table fz="xs">
                    <Table.Tbody>
                      {d.hits.map((h) => (
                        <Table.Tr key={h.well}>
                          <Table.Td>{h.well}</Table.Td>
                          <Table.Td>{h.label}</Table.Td>
                          <Table.Td>{fmt(h.activity, 1)} %</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              </Card>
            )}
          </Stack>
        </Grid.Col>
      </Grid>
      {d.curves.length > 0 && (
        <>
          <Title order={4}>Dose-response</Title>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            {d.curves.map((cv) => (
              <Card key={cv.label} withBorder>
                <Group justify="space-between">
                  <Text fw={600}>{cv.label}</Text>
                  {cv.fit ? (
                    <Badge color={cv.fit.ec50_in_tested_range ? 'blue' : 'orange'} size="lg" tt="none">
                      IC50/EC50 {fmt(cv.fit.ec50, 3)} {cv.unit}
                    </Badge>
                  ) : (
                    <Badge color="gray">no fit (≥ 4 concentrations needed)</Badge>
                  )}
                </Group>
                <DoseResponse curve={cv} />
                {cv.fit && (
                  <Text size="xs" c="dimmed">
                    4PL: bottom {fmt(cv.fit.bottom, 1)}, top {fmt(cv.fit.top, 1)}, Hill {fmt(cv.fit.hill, 2)}, R² {fmt(cv.fit.r2, 3)}
                    {!cv.fit.ec50_in_tested_range && ' · EC50 outside the tested range (extrapolated)'}
                  </Text>
                )}
              </Card>
            ))}
          </SimpleGrid>
        </>
      )}
    </Stack>
  )
}

function DoseResponse({ curve }: { curve: PlateAnalysis['curves'][number] }) {
  const data = useMemo(() => {
    const rows: { logc: number; fit?: number; measured?: number }[] = []
    for (const p of curve.fit?.curve ?? []) rows.push({ logc: Math.log10(p.x), fit: p.y })
    for (const p of curve.points) if (p.x > 0) rows.push({ logc: Math.log10(p.x), measured: p.y })
    return rows.sort((a, b) => a.logc - b.logc)
  }, [curve])
  return (
    <LineChart
      h={220}
      data={data}
      dataKey="logc"
      connectNulls
      withDots
      curveType="monotone"
      xAxisLabel={`log10 conc. (${curve.unit})`}
      xAxisProps={{ type: 'number', domain: ['dataMin', 'dataMax'], tickFormatter: (v: number) => v.toFixed(1) }}
      series={[
        { name: 'fit', color: 'blue.6', strokeDasharray: '0' },
        { name: 'measured', color: 'orange.6', strokeDasharray: '1 1000' },
      ]}
    />
  )
}

// --- kinetics ----------------------------------------------------------------------------

function Kinetics({ plate }: { plate: Plate }) {
  const [channel, setChannel] = useState('signal')
  const [wellsShown, setWellsShown] = useState('A1,B1,C1')
  const k = useQuery({
    queryKey: ['kinetics', plate.id, channel],
    queryFn: () => api<{ series: Record<string, { t: number; v: number }[]>; max_specific_rate_per_min: Record<string, number> }>(`/api/plates/${plate.id}/kinetics/?channel=${encodeURIComponent(channel)}`),
  })
  const names = wellsShown.split(/[ ,;]+/).map((s) => s.trim().toUpperCase()).filter(Boolean)
  const data = useMemo(() => {
    const byT = new Map<number, Record<string, number>>()
    for (const n of names) for (const p of k.data?.series[n] ?? []) byT.set(p.t, { ...(byT.get(p.t) ?? { t: p.t }), [n]: p.v })
    return [...byT.values()].sort((a, b) => a.t - b.t)
  }, [k.data, wellsShown]) // eslint-disable-line react-hooks/exhaustive-deps
  const colors = ['blue.6', 'red.6', 'green.6', 'orange.6', 'grape.6', 'teal.6', 'pink.6', 'cyan.6']
  return (
    <Stack>
      <Group>
        <TextInput label="Channel" value={channel} onChange={(e) => setChannel(e.target.value)} w={160} />
        <TextInput label="Wells" value={wellsShown} onChange={(e) => setWellsShown(e.target.value)} w={300} />
      </Group>
      {data.length ? (
        <LineChart h={300} data={data} dataKey="t" xAxisLabel="time (min)" series={names.map((n, i) => ({ name: n, color: colors[i % colors.length] }))} curveType="monotone" connectNulls />
      ) : (
        <Text c="dimmed">No time-course data for these wells on this channel.</Text>
      )}
      {k.data && Object.keys(k.data.max_specific_rate_per_min).length > 0 && (
        <Text size="sm">
          Max. specific rate (per min): {names.map((n) => `${n}: ${fmt(k.data!.max_specific_rate_per_min[n], 4)}`).join(' · ')}
        </Text>
      )}
    </Stack>
  )
}
