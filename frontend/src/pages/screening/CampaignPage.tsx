import { BarChart, LineChart, ScatterChart } from '@mantine/charts'
import {
  Accordion,
  ActionIcon,
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
  NumberInput,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  TagsInput,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, del, patch, post } from '../../api/client'
import type { Campaign, ResponseAnalysis, ResponseDef, Run, Suggestion, Variable } from '../../api/modules'
import { hasRole, useApp } from '../../components/context'
import { fmt, notifyError, notifyOk, StatusBadge } from '../../components/pickers'
import { ReactionScheme } from '../../components/SmilesImage'
import { EQUIPMENT } from './Campaigns'

const PLATE_SHAPES: Record<number, [number, number]> = { 6: [2, 3], 12: [3, 4], 24: [4, 6], 48: [6, 8], 96: [8, 12], 384: [16, 24] }

export default function CampaignPage() {
  const { id } = useParams()
  const { me } = useApp()
  const qc = useQueryClient()
  const campaign = useQuery({ queryKey: ['campaign', id], queryFn: () => api<Campaign>(`/api/campaigns/${id}/`) })
  const runs = useQuery({
    queryKey: ['runs', id],
    queryFn: () => api<Run[]>(`/api/campaign-runs/?campaign=${id}`),
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['campaign', id] })
    qc.invalidateQueries({ queryKey: ['runs', id] })
    qc.invalidateQueries({ queryKey: ['analysis', id] })
  }
  const c = campaign.data
  if (!c) return null
  const canWrite = hasRole(me, c.group, 'member')
  const allRuns = runs.data ?? []
  return (
    <Stack>
      <div>
        <Anchor component={Link} to="/screening" size="sm">
          Screening
        </Anchor>
        <Group justify="space-between">
          <Title order={2}>{c.title}</Title>
          <Group>
            <Badge variant="outline">{EQUIPMENT.find((e) => e.value === c.equipment)?.label}</Badge>
            <Select
              data={['design', 'running', 'completed', 'archived']}
              value={c.status}
              disabled={!canWrite}
              w={130}
              onChange={async (s) => {
                await patch(`/api/campaigns/${id}/`, { status: s })
                refresh()
              }}
            />
          </Group>
        </Group>
        <Text c="dimmed">{c.objective}</Text>
      </div>
      {c.reaction_smiles && <ReactionScheme smiles={c.reaction_smiles} />}
      <Tabs defaultValue={c.variables.length ? 'runs' : 'setup'} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="setup">1 · Variables & goals</Tabs.Tab>
          <Tabs.Tab value="design">2 · Design</Tabs.Tab>
          <Tabs.Tab value="runs">3 · Runs ({allRuns.length})</Tabs.Tab>
          {c.equipment === 'hte_plate' && <Tabs.Tab value="plate">Plate map</Tabs.Tab>}
          <Tabs.Tab value="analysis">4 · Analysis</Tabs.Tab>
          <Tabs.Tab value="next">5 · What next?</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="setup" pt="md">
          <Setup c={c} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="design" pt="md">
          <Design c={c} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="runs" pt="md">
          <Runs c={c} runs={allRuns} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="plate" pt="md">
          <PlateMap c={c} runs={allRuns} />
        </Tabs.Panel>
        <Tabs.Panel value="analysis" pt="md">
          <Analysis c={c} />
        </Tabs.Panel>
        <Tabs.Panel value="next" pt="md">
          <Next c={c} canWrite={canWrite} onChange={refresh} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

// --- setup -------------------------------------------------------------------------------

function Setup({ c, canWrite, onChange }: { c: Campaign; canWrite: boolean; onChange: () => void }) {
  const [v, setV] = useState({ name: '', kind: 'continuous' as Variable['kind'], unit: '', low: '' as number | '', high: '' as number | '', levels: [] as string[] })
  const [r, setR] = useState({ name: 'Yield', unit: '%', goal: 'maximize' as ResponseDef['goal'], target: '' as number | '', weight: 1 })
  const addVar = useMutation({
    mutationFn: () =>
      post('/api/campaign-variables/', {
        campaign: c.id,
        ...v,
        low: v.low === '' ? null : v.low,
        high: v.high === '' ? null : v.high,
        levels: v.kind === 'discrete' ? v.levels.map(Number) : v.levels,
        position: c.variables.length,
      }),
    onSuccess: () => {
      setV({ ...v, name: '', unit: '', low: '', high: '', levels: [] })
      onChange()
    },
    onError: notifyError,
  })
  const addResp = useMutation({
    mutationFn: () => post('/api/campaign-responses/', { campaign: c.id, ...r, target: r.target === '' ? null : r.target, position: c.responses.length }),
    onSuccess: () => {
      setR({ ...r, name: '', unit: '' })
      onChange()
    },
    onError: notifyError,
  })
  const remove = useMutation({
    mutationFn: (path: string) => del(path),
    onSuccess: onChange,
    onError: notifyError,
  })
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Card withBorder>
          <Text fw={600}>Variables (what you change)</Text>
          <Text size="xs" c="dimmed" mb="xs">
            Continuous: a range (temperature, time, loading). Discrete: fixed numbers (equivalents 1, 1.5, 2).
            Categorical: choices (solvent, base, ligand, catalyst batch).
          </Text>
          <Table>
            <Table.Tbody>
              {c.variables.map((x) => (
                <Table.Tr key={x.id}>
                  <Table.Td fw={500}>{x.name}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" size="sm">
                      {x.kind}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {x.kind === 'continuous' ? `${x.low} – ${x.high} ${x.unit}` : `${x.levels.join(', ')} ${x.unit}`}
                  </Table.Td>
                  <Table.Td>
                    {canWrite && (
                      <ActionIcon variant="subtle" color="red" onClick={() => remove.mutate(`/api/campaign-variables/${x.id}/`)}>
                        ×
                      </ActionIcon>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {canWrite && (
            <Stack mt="sm" gap="xs">
              <Group grow align="end">
                <TextInput label="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} placeholder="Temperature" />
                <Select label="Type" data={['continuous', 'discrete', 'categorical']} value={v.kind} onChange={(k) => k && setV({ ...v, kind: k as Variable['kind'] })} />
                <TextInput label="Unit" value={v.unit} onChange={(e) => setV({ ...v, unit: e.target.value })} placeholder="°C" />
              </Group>
              {v.kind === 'continuous' ? (
                <Group grow>
                  <NumberInput label="Low" value={v.low} onChange={(x) => setV({ ...v, low: x === '' ? '' : Number(x) })} />
                  <NumberInput label="High" value={v.high} onChange={(x) => setV({ ...v, high: x === '' ? '' : Number(x) })} />
                </Group>
              ) : (
                <TagsInput label="Levels (Enter after each)" value={v.levels} onChange={(levels) => setV({ ...v, levels })} placeholder={v.kind === 'discrete' ? '1, 1.5, 2' : 'THF, toluene, DMF'} />
              )}
              <Button onClick={() => addVar.mutate()} disabled={!v.name}>
                Add variable
              </Button>
            </Stack>
          )}
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Card withBorder>
          <Text fw={600}>Responses (what you measure)</Text>
          <Text size="xs" c="dimmed" mb="xs">
            Several goals are combined (weighted desirability): e.g. maximise yield, minimise cost or E-factor,
            hit a target ee.
          </Text>
          <Table>
            <Table.Tbody>
              {c.responses.map((x) => (
                <Table.Tr key={x.id}>
                  <Table.Td fw={500}>
                    {x.name} {x.unit && `(${x.unit})`}
                  </Table.Td>
                  <Table.Td>
                    {x.goal}
                    {x.goal === 'target' && ` ${x.target}`}
                  </Table.Td>
                  <Table.Td>×{x.weight}</Table.Td>
                  <Table.Td>
                    {canWrite && (
                      <ActionIcon variant="subtle" color="red" onClick={() => remove.mutate(`/api/campaign-responses/${x.id}/`)}>
                        ×
                      </ActionIcon>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {canWrite && (
            <Stack mt="sm" gap="xs">
              <Group grow>
                <TextInput label="Name" value={r.name} onChange={(e) => setR({ ...r, name: e.target.value })} />
                <TextInput label="Unit" value={r.unit} onChange={(e) => setR({ ...r, unit: e.target.value })} />
              </Group>
              <Group grow>
                <Select label="Goal" data={['maximize', 'minimize', 'target', 'monitor']} value={r.goal} onChange={(g) => g && setR({ ...r, goal: g as ResponseDef['goal'] })} />
                {r.goal === 'target' && <NumberInput label="Target" value={r.target} onChange={(x) => setR({ ...r, target: x === '' ? '' : Number(x) })} />}
                <NumberInput label="Weight" min={0.1} step={0.5} value={r.weight} onChange={(x) => setR({ ...r, weight: Number(x) || 1 })} />
              </Group>
              <Button onClick={() => addResp.mutate()} disabled={!r.name}>
                Add response
              </Button>
            </Stack>
          )}
        </Card>
      </Grid.Col>
    </Grid>
  )
}

// --- design ------------------------------------------------------------------------------

const DESIGNS = [
  { value: 'full_factorial', label: 'Full factorial', help: 'Every combination. Best for 2–3 variables.' },
  { value: 'latin_hypercube', label: 'Latin hypercube', help: 'Space-filling first screen; scales to many variables.' },
  { value: 'center_points', label: 'Centre points', help: 'Replicates at the centre: measures noise and curvature.' },
  { value: 'ofat', label: 'One factor at a time', help: 'Classical scan around the centre (misses interactions).' },
  { value: 'random', label: 'Random', help: 'Random points in the space.' },
]

function Design({ c, canWrite, onChange }: { c: Campaign; canWrite: boolean; onChange: () => void }) {
  const [d, setD] = useState({ design: 'full_factorial', n: 12, levels: 3, replace: false })
  const nLevels = c.variables.reduce((acc, v) => acc * (v.kind === 'continuous' ? d.levels : v.levels.length || 1), 1)
  const gen = useMutation({
    mutationFn: () => post<Run[]>(`/api/campaigns/${c.id}/generate/`, d),
    onSuccess: (runs) => {
      notifyOk(`${runs.length} runs in the plan`)
      onChange()
    },
    onError: notifyError,
  })
  if (!c.variables.length) return <Alert>Add variables first.</Alert>
  return (
    <Card withBorder maw={700}>
      <Stack>
        <SegmentedControl fullWidth value={d.design} onChange={(x) => setD({ ...d, design: x })} data={DESIGNS.map(({ value, label }) => ({ value, label }))} />
        <Text size="sm">{DESIGNS.find((x) => x.value === d.design)?.help}</Text>
        <Group grow>
          {['full_factorial', 'ofat'].includes(d.design) ? (
            <NumberInput label="Levels per continuous variable" min={2} max={11} value={d.levels} onChange={(x) => setD({ ...d, levels: Number(x) || 3 })} />
          ) : (
            <NumberInput label="Number of runs" min={1} max={2000} value={d.n} onChange={(x) => setD({ ...d, n: Number(x) || 1 })} />
          )}
        </Group>
        {d.design === 'full_factorial' && <Text size="sm">This makes <b>{nLevels}</b> runs{c.equipment === 'hte_plate' && ` (${Math.ceil(nLevels / c.plate_format)} plate(s) of ${c.plate_format})`}.</Text>}
        <Checkbox label="Replace runs that are still planned" checked={d.replace} onChange={(e) => setD({ ...d, replace: e.currentTarget.checked })} />
        <Button disabled={!canWrite} onClick={() => gen.mutate()} loading={gen.isPending}>
          Generate runs
        </Button>
        <Text size="xs" c="dimmed">
          Run order is randomised to avoid drifts (e.g. catalyst ageing) being mistaken for effects.
        </Text>
      </Stack>
    </Card>
  )
}

// --- runs --------------------------------------------------------------------------------

function factorLabel(_v: Variable, val: string | number | undefined) {
  if (val === undefined || val === null) return ''
  return typeof val === 'number' ? `${fmt(val, 3)}` : String(val)
}

function Runs({ c, runs, canWrite, onChange }: { c: Campaign; runs: Run[]; canWrite: boolean; onChange: () => void }) {
  const save = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Run> }) => patch(`/api/campaign-runs/${id}/`, body),
    onSuccess: onChange,
    onError: notifyError,
  })
  const importCsv = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return post<{ updated: number; errors: string[] }>(`/api/campaigns/${c.id}/import-results/`, fd)
    },
    onSuccess: (r) => {
      notifyOk(`${r.updated} runs updated${r.errors.length ? `; ${r.errors.length} problems: ${r.errors.slice(0, 3).join('; ')}` : ''}`)
      onChange()
    },
    onError: notifyError,
  })
  const addManual = useMutation({
    mutationFn: () => post('/api/campaign-runs/', { campaign: c.id, factors: Object.fromEntries(c.variables.map((v) => [v.id, v.kind === 'continuous' ? v.low : v.levels[0]])), source: 'manual' }),
    onSuccess: onChange,
    onError: notifyError,
  })
  return (
    <Stack>
      <Group>
        <Button component="a" href={`/api/campaigns/${c.id}/export/`} variant="default">
          Export CSV (robot / Excel)
        </Button>
        {canWrite && (
          <>
            <FileButton onChange={(f) => f && importCsv.mutate(f)} accept=".csv,text/csv">
              {(props) => (
                <Button {...props} variant="default" loading={importCsv.isPending}>
                  Import results CSV
                </Button>
              )}
            </FileButton>
            <Button variant="subtle" onClick={() => addManual.mutate()}>
              Add manual run
            </Button>
          </>
        )}
        <Text size="xs" c="dimmed">
          CSV needs a <code>run</code> (or <code>well</code>) column plus one column per response name.
        </Text>
      </Group>
      <ScrollArea>
        <Table striped withColumnBorders fz="sm" miw={700}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>#</Table.Th>
              {c.equipment === 'hte_plate' && <Table.Th>Well</Table.Th>}
              {c.variables.map((v) => (
                <Table.Th key={v.id}>
                  {v.name} {v.unit && <Text span size="xs" c="dimmed">({v.unit})</Text>}
                </Table.Th>
              ))}
              {c.responses.map((r) => (
                <Table.Th key={r.id} bg="var(--mantine-color-blue-light)">
                  {r.name} {r.unit && <Text span size="xs">({r.unit})</Text>}
                </Table.Th>
              ))}
              <Table.Th>Status</Table.Th>
              <Table.Th>Lots / notes</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {runs.map((run) => (
              <Table.Tr key={run.id} opacity={run.status === 'skipped' ? 0.5 : 1}>
                <Table.Td>
                  {run.index}
                  {run.source === 'suggestion' && (
                    <Tooltip label={run.notes}>
                      <Badge size="xs" color="grape" ml={4}>
                        AI
                      </Badge>
                    </Tooltip>
                  )}
                </Table.Td>
                {c.equipment === 'hte_plate' && (
                  <Table.Td>
                    {run.plate && run.plate > 1 ? `P${run.plate}:` : ''}
                    {run.well}
                  </Table.Td>
                )}
                {c.variables.map((v) => (
                  <Table.Td key={v.id}>{factorLabel(v, run.factors[v.id])}</Table.Td>
                ))}
                {c.responses.map((r) => (
                  <Table.Td key={r.id}>
                    <ResultCell
                      value={run.results[r.id]}
                      disabled={!canWrite}
                      onSave={(val) => {
                        const results = { ...run.results }
                        if (val === null) delete results[r.id]
                        else results[r.id] = val
                        save.mutate({ id: run.id, body: { results } })
                      }}
                    />
                  </Table.Td>
                ))}
                <Table.Td>
                  <Select
                    size="xs"
                    w={110}
                    data={['planned', 'running', 'done', 'failed', 'skipped']}
                    value={run.status}
                    disabled={!canWrite}
                    onChange={(s) => s && save.mutate({ id: run.id, body: { status: s as Run['status'] } })}
                    renderOption={({ option }) => <StatusBadge status={option.value} />}
                  />
                </Table.Td>
                <Table.Td>
                  <NotesCell run={run} disabled={!canWrite} onSave={(body) => save.mutate({ id: run.id, body })} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
      {runs.length === 0 && <Text c="dimmed">No runs yet. Generate a design first.</Text>}
    </Stack>
  )
}

function ResultCell({ value, disabled, onSave }: { value: number | undefined; disabled: boolean; onSave: (v: number | null) => void }) {
  const [v, setV] = useState<string | number>(value ?? '')
  useEffect(() => setV(value ?? ''), [value])
  if (disabled) return <>{fmt(value)}</>
  return (
    <NumberInput
      size="xs"
      w={90}
      hideControls
      value={v}
      onChange={setV}
      onBlur={() => {
        const next = v === '' ? null : Number(v)
        if (next !== (value ?? null)) onSave(next)
      }}
    />
  )
}

function NotesCell({ run, disabled, onSave }: { run: Run; disabled: boolean; onSave: (b: Partial<Run>) => void }) {
  const [lots, setLots] = useState(run.lots)
  const [notes, setNotes] = useState(run.notes)
  useEffect(() => {
    setLots(run.lots)
    setNotes(run.notes)
  }, [run])
  if (disabled) return <Text size="xs">{[...run.lots, run.notes].filter(Boolean).join(' · ')}</Text>
  return (
    <Group gap={4} wrap="nowrap">
      <TagsInput size="xs" w={150} placeholder="Lot barcodes" value={lots} onChange={(l) => { setLots(l); onSave({ lots: l }) }} />
      <TextInput size="xs" w={160} placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== run.notes && onSave({ notes })} />
    </Group>
  )
}

// --- plate map ---------------------------------------------------------------------------

function PlateMap({ c, runs }: { c: Campaign; runs: Run[] }) {
  const [resp, setResp] = useState<string | null>(c.responses[0]?.id ?? null)
  const [plate, setPlate] = useState('1')
  const plates = [...new Set(runs.map((r) => r.plate ?? 1))].sort()
  const [rows, cols] = PLATE_SHAPES[c.plate_format] ?? [8, 12]
  const byWell = new Map(runs.filter((r) => String(r.plate ?? 1) === plate).map((r) => [r.well, r]))
  const vals = runs.map((r) => (resp ? r.results[resp] : undefined)).filter((x): x is number => x !== undefined)
  const lo = Math.min(...vals)
  const hi = Math.max(...vals)
  return (
    <Stack>
      <Group>
        <Select label="Colour by" data={c.responses.map((r) => ({ value: r.id, label: r.name }))} value={resp} onChange={setResp} />
        {plates.length > 1 && <Select label="Plate" data={plates.map(String)} value={plate} onChange={(p) => p && setPlate(p)} w={100} />}
      </Group>
      <ScrollArea>
        <table style={{ borderCollapse: 'separate', borderSpacing: 3 }}>
          <thead>
            <tr>
              <th />
              {Array.from({ length: cols }, (_, i) => (
                <th key={i}>
                  <Text size="xs">{i + 1}</Text>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }, (_, r) => (
              <tr key={r}>
                <th>
                  <Text size="xs">{String.fromCharCode(65 + r)}</Text>
                </th>
                {Array.from({ length: cols }, (_, ci) => {
                  const name = `${String.fromCharCode(65 + r)}${ci + 1}`
                  const run = byWell.get(name)
                  const val = run && resp ? run.results[resp] : undefined
                  const t = val === undefined || hi === lo ? null : (val - lo) / (hi - lo)
                  return (
                    <td key={ci}>
                      <Tooltip
                        label={
                          run
                            ? `${name} · run ${run.index}: ` +
                              c.variables.map((v) => `${v.name}=${factorLabel(v, run.factors[v.id])}`).join(', ') +
                              (val !== undefined ? ` → ${fmt(val)}` : '')
                            : name
                        }
                      >
                        <div
                          style={{
                            width: 44,
                            height: 34,
                            borderRadius: 17,
                            display: 'grid',
                            placeItems: 'center',
                            fontSize: 11,
                            border: '1px solid var(--mantine-color-default-border)',
                            background: !run
                              ? 'transparent'
                              : t === null
                                ? 'var(--mantine-color-gray-light)'
                                : `hsl(${220 - 180 * t} 70% ${55 + 10 * (1 - t)}%)`,
                            color: t !== null ? 'white' : undefined,
                          }}
                        >
                          {val !== undefined ? fmt(val, 0) : run ? run.index : ''}
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
    </Stack>
  )
}

// --- analysis ----------------------------------------------------------------------------

function Analysis({ c }: { c: Campaign }) {
  const a = useQuery({
    queryKey: ['analysis', c.id],
    queryFn: () => api<{ responses: ResponseAnalysis[]; counts: Record<string, number> }>(`/api/campaigns/${c.id}/analysis/`),
  })
  const [layer, setLayer] = useState('plain')
  if (!a.data) return null
  if (!c.responses.length) return <Alert>Define at least one response.</Alert>
  return (
    <Stack>
      <Group>
        <SegmentedControl
          value={layer}
          onChange={setLayer}
          data={[
            { value: 'plain', label: 'Plain language' },
            { value: 'expert', label: 'Expert details' },
          ]}
        />
        <Text size="sm" c="dimmed">
          {a.data.counts.done} done · {a.data.counts.planned} planned · {a.data.counts.failed} failed
        </Text>
      </Group>
      {a.data.responses.map((r) => (
        <ResponseCard key={r.response} r={r} c={c} layer={layer} />
      ))}
    </Stack>
  )
}

function ResponseCard({ r, c, layer }: { r: ResponseAnalysis; c: Campaign; layer: string }) {
  const unit = c.responses.find((x) => x.id === r.response)?.unit ?? ''
  const varName = (id: string) => c.variables.find((v) => v.id === id)?.name ?? id
  return (
    <Card withBorder>
      <Title order={4} mb="xs">
        {r.name}
      </Title>
      <List spacing={4} mb="md">
        {r.plain.map((p, i) => (
          <List.Item key={i}>
            <Text size="sm">{p}</Text>
          </List.Item>
        ))}
      </List>
      {r.observed && (
        <Text size="sm" mb="md">
          Best run: <b>{fmt(r.observed.best_value)} {unit}</b> at{' '}
          {Object.entries(r.observed.best_factors)
            .map(([k, v]) => `${varName(k)} = ${typeof v === 'number' ? fmt(v) : v}`)
            .join(', ')}
        </Text>
      )}
      {r.importance && (
        <SimpleGrid cols={{ base: 1, md: 2 }} mb="md">
          <div>
            <Text size="sm" fw={600}>
              What matters most (swing of {r.name} across each variable's range)
            </Text>
            <BarChart
              h={60 + 40 * r.importance.length}
              data={r.importance.map((i) => ({ variable: i.name, swing: i.swing }))}
              dataKey="variable"
              orientation="vertical"
              series={[{ name: 'swing', color: 'blue.6', label: `Δ ${unit}` }]}
              yAxisProps={{ width: 110 }}
            />
          </div>
          <div>
            <Text size="sm" fw={600}>
              Model check: predicted vs measured
            </Text>
            {r.model && (
              <ScatterChart
                h={240}
                data={[{ color: 'teal.6', name: 'runs', data: r.model.residuals.map((p) => ({ measured: p.observed, predicted: p.predicted })) }]}
                dataKey={{ x: 'measured', y: 'predicted' }}
                xAxisLabel="measured"
                yAxisLabel="predicted"
              />
            )}
          </div>
        </SimpleGrid>
      )}
      {r.importance && (
        <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }}>
          {r.importance.map((imp) => (
            <Card key={imp.variable} withBorder padding="xs">
              <Text size="sm" fw={600}>
                {imp.name}: best at {typeof imp.best_at === 'number' ? fmt(imp.best_at) : imp.best_at}
              </Text>
              {imp.curve ? (
                <EffectLine imp={imp} effects={r.main_effects?.find((m) => m.variable === imp.variable)} unit={unit} />
              ) : (
                <BarChart
                  h={160}
                  data={Object.entries(imp.levels ?? {}).map(([level, y]) => ({ level, predicted: y, observed: r.main_effects?.find((m) => m.variable === imp.variable)?.points.find((p) => String(p.x) === level)?.mean }))}
                  dataKey="level"
                  series={[
                    { name: 'predicted', color: 'blue.6' },
                    { name: 'observed', color: 'gray.5' },
                  ]}
                />
              )}
            </Card>
          ))}
        </SimpleGrid>
      )}
      {layer === 'expert' && r.model && (
        <Accordion mt="md" defaultValue="model">
          <Accordion.Item value="model">
            <Accordion.Control>
              Model: {r.model.order} · R² {fmt(r.model.metrics.r2)} · adj. R² {fmt(r.model.metrics.r2_adj)} · Q² (LOO) {fmt(r.model.metrics.q2)} · RMSE {fmt(r.model.metrics.rmse)} · {r.model.metrics.residual_dof} residual d.o.f.
            </Accordion.Control>
            <Accordion.Panel>
              <Text size="xs" c="dimmed" mb="xs">
                Numeric variables coded to [−1, +1]; categorical levels relative to the first level. |t| ≥ 2 marked as likely real.
              </Text>
              <Table fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Term</Table.Th>
                    <Table.Th>Coefficient</Table.Th>
                    <Table.Th>Std. error</Table.Th>
                    <Table.Th>t</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {r.model.terms.map((t) => (
                    <Table.Tr key={t.term} fw={t.significant ? 600 : undefined}>
                      <Table.Td>{t.term}</Table.Td>
                      <Table.Td>{fmt(t.coef, 4)}</Table.Td>
                      <Table.Td>{fmt(t.se, 4)}</Table.Td>
                      <Table.Td>{fmt(t.t, 2)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </Card>
  )
}

function EffectLine({
  imp,
  effects,
  unit,
}: {
  imp: NonNullable<ResponseAnalysis['importance']>[number]
  effects?: NonNullable<ResponseAnalysis['main_effects']>[number]
  unit: string
}) {
  const data = useMemo(() => {
    const rows: Record<string, number | undefined>[] = (imp.curve ?? []).map((p) => ({ x: p.x, model: p.y }))
    for (const p of effects?.points ?? []) rows.push({ x: Number(p.x), observed: p.mean })
    return rows.sort((a, b) => (a.x ?? 0) - (b.x ?? 0))
  }, [imp, effects])
  return (
    <LineChart
      h={170}
      data={data}
      dataKey="x"
      connectNulls
      series={[
        { name: 'model', color: 'blue.6', label: `model (${unit})` },
        { name: 'observed', color: 'orange.6', label: 'observed mean' },
      ]}
      curveType="monotone"
      withDots={false}
      xAxisProps={{ type: 'number', domain: ['dataMin', 'dataMax'] }}
    />
  )
}

// --- what next ---------------------------------------------------------------------------

function Next({ c, canWrite, onChange }: { c: Campaign; canWrite: boolean; onChange: () => void }) {
  const [k, setK] = useState(4)
  const [explore, setExplore] = useState(true)
  const [sug, setSug] = useState<Suggestion[] | null>(null)
  const [factors, setFactors] = useState<Record<string, string | number>>({})
  const [resp, setResp] = useState<string | null>(c.responses[0]?.id ?? null)
  const [pred, setPred] = useState<null | { prediction: number; interval95: number[] | null; extrapolation: boolean; warnings: string[] }>(null)
  const suggest = useMutation({
    mutationFn: (add: boolean) => post<{ suggestions: Suggestion[] }>(`/api/campaigns/${c.id}/suggest/`, { k, explore, add }),
    onSuccess: (r, add) => {
      setSug(r.suggestions)
      if (add) {
        notifyOk('Suggestions added to the run list')
        onChange()
      }
    },
    onError: notifyError,
  })
  const predict = useMutation({
    mutationFn: () => post<typeof pred>(`/api/campaigns/${c.id}/predict/`, { response: resp, factors }),
    onSuccess: setPred,
    onError: notifyError,
  })
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Card withBorder>
          <Text fw={600}>Suggested next runs</Text>
          <Text size="xs" c="dimmed" mb="sm">
            Picks diverse conditions with the best predicted combined goal, plus one run in the most uncertain region
            (to learn, not to win). Anything outside what you have tested is flagged.
          </Text>
          <Group align="end" mb="sm">
            <NumberInput label="How many" min={1} max={24} value={k} onChange={(x) => setK(Number(x) || 4)} w={110} />
            <Checkbox label="Include an exploration run" checked={explore} onChange={(e) => setExplore(e.currentTarget.checked)} />
            <Button onClick={() => suggest.mutate(false)} loading={suggest.isPending}>
              Suggest
            </Button>
            {sug && canWrite && (
              <Button variant="light" onClick={() => suggest.mutate(true)}>
                Add to runs
              </Button>
            )}
          </Group>
          {sug && (
            <Table fz="sm">
              <Table.Thead>
                <Table.Tr>
                  {c.variables.map((v) => (
                    <Table.Th key={v.id}>{v.name}</Table.Th>
                  ))}
                  {c.responses.filter((r) => r.goal !== 'monitor').map((r) => (
                    <Table.Th key={r.id}>pred. {r.name}</Table.Th>
                  ))}
                  <Table.Th>Why</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sug.map((s, i) => (
                  <Table.Tr key={i}>
                    {c.variables.map((v) => (
                      <Table.Td key={v.id}>{factorLabel(v, s.factors[v.id])}</Table.Td>
                    ))}
                    {c.responses.filter((r) => r.goal !== 'monitor').map((r) => (
                      <Table.Td key={r.id}>{fmt(s.predicted[r.id], 1)}</Table.Td>
                    ))}
                    <Table.Td>
                      <Text size="xs">{s.purpose}</Text>
                      {s.extrapolation && (
                        <Tooltip label={s.warnings.join('; ')} multiline w={280}>
                          <Badge color="orange" size="xs">
                            extrapolation
                          </Badge>
                        </Tooltip>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Card withBorder>
          <Text fw={600} mb="xs">
            What if…? (predict any condition)
          </Text>
          <Stack gap="xs">
            {c.variables.map((v) =>
              v.kind === 'categorical' ? (
                <Select key={v.id} label={v.name} data={v.levels.map(String)} value={factors[v.id] !== undefined ? String(factors[v.id]) : null} onChange={(x) => x && setFactors({ ...factors, [v.id]: x })} />
              ) : (
                <NumberInput key={v.id} label={`${v.name} ${v.unit ? `(${v.unit})` : ''}`} value={factors[v.id] as number | undefined} onChange={(x) => setFactors({ ...factors, [v.id]: Number(x) })} />
              ),
            )}
            <Select label="Response" data={c.responses.map((r) => ({ value: r.id, label: r.name }))} value={resp} onChange={setResp} />
            <Button onClick={() => predict.mutate()} disabled={Object.keys(factors).length < c.variables.length}>
              Predict
            </Button>
            {pred && (
              <Alert color={pred.extrapolation ? 'orange' : 'blue'} title={`≈ ${fmt(pred.prediction, 2)}`}>
                {pred.interval95 && `95 % range ${fmt(pred.interval95[0], 1)} – ${fmt(pred.interval95[1], 1)}. `}
                {pred.extrapolation ? `Extrapolation: ${pred.warnings.join('; ')}. Treat as a hypothesis to test.` : 'Inside the tested region.'}
              </Alert>
            )}
          </Stack>
        </Card>
      </Grid.Col>
    </Grid>
  )
}
