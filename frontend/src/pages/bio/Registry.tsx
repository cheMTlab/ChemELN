import {
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Code,
  Drawer,
  FileButton,
  Grid,
  Group,
  MultiSelect,
  NumberInput,
  ScrollArea,
  Select,
  Stack,
  Table,
  Tabs,
  TagsInput,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { api, patch, post } from '../../api/client'
import type { BioSample, Feature, Oligo, Plasmid, Strain } from '../../api/modules'
import type { Page } from '../../api/types'
import { hasRole, useApp } from '../../components/context'
import { defaultGroup, Field, fmt, GroupPicker, LocationPicker, notifyError, notifyOk } from '../../components/pickers'
import PlasmidMap from './PlasmidMap'

export default function Registry() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'plasmids'
  return (
    <Stack>
      <Title order={2}>Biology registry</Title>
      <Tabs value={tab} onChange={(t) => setParams({ tab: t ?? 'plasmids' })} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="plasmids">Plasmids</Tabs.Tab>
          <Tabs.Tab value="strains">Strains & cell lines</Tabs.Tab>
          <Tabs.Tab value="oligos">Oligos / primers</Tabs.Tab>
          <Tabs.Tab value="samples">Samples & stocks</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="plasmids" pt="md">
          <Plasmids />
        </Tabs.Panel>
        <Tabs.Panel value="strains" pt="md">
          <Strains />
        </Tabs.Panel>
        <Tabs.Panel value="oligos" pt="md">
          <Oligos />
        </Tabs.Panel>
        <Tabs.Panel value="samples" pt="md">
          <Samples />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

function useList<T>(key: string, url: string) {
  const [q, setQ] = useState('')
  const [dq] = useDebouncedValue(q, 250)
  const query = useQuery({
    queryKey: [key, dq, url],
    queryFn: () => api<Page<T>>(`${url}${url.includes('?') ? '&' : '?'}q=${encodeURIComponent(dq)}`),
  })
  return { q, setQ, items: query.data?.results ?? [], count: query.data?.count ?? 0 }
}

// --- plasmids ----------------------------------------------------------------------------

function Plasmids() {
  const [seq, setSeq] = useState('')
  const [dseq] = useDebouncedValue(seq, 400)
  const l = useList<Plasmid>('plasmids', `/api/plasmids/?sequence=${encodeURIComponent(dseq)}`)
  const [open, setOpen] = useState<string | 'new' | null>(null)
  return (
    <Stack>
      <Group>
        <TextInput placeholder="Name, insert, promoter, resistance, tag" value={l.q} onChange={(e) => l.setQ(e.target.value)} w={300} />
        <TextInput placeholder="Contains sequence (either strand)" value={seq} onChange={(e) => setSeq(e.target.value)} w={260} />
        <Button onClick={() => setOpen('new')}>New plasmid</Button>
      </Group>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Code</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Backbone / insert</Table.Th>
            <Table.Th>Resistance</Table.Th>
            <Table.Th>Size</Table.Th>
            <Table.Th>Source</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {l.items.map((p) => (
            <Table.Tr key={p.id} onClick={() => setOpen(p.id)} style={{ cursor: 'pointer' }}>
              <Table.Td fw={600}>{p.code}</Table.Td>
              <Table.Td>
                {p.name} {p.verified && <Badge size="xs" color="green">verified</Badge>}
                <Text size="xs" c="dimmed">
                  {p.vector_type} {p.tags.length > 0 && `· ${p.tags.join(', ')}`}
                </Text>
              </Table.Td>
              <Table.Td>
                {p.backbone}
                {p.insert && ` · ${p.insert}`}
              </Table.Td>
              <Table.Td>
                {p.resistance.map((r) => (
                  <Badge key={r} size="sm" variant="light" mr={4}>
                    {r}
                  </Badge>
                ))}
              </Table.Td>
              <Table.Td>{p.size_bp ? `${p.size_bp.toLocaleString()} bp` : ''}</Table.Td>
              <Table.Td>
                {p.addgene_id ? (
                  <Anchor href={`https://www.addgene.org/${p.addgene_id}/`} target="_blank" onClick={(e) => e.stopPropagation()}>
                    Addgene {p.addgene_id}
                  </Anchor>
                ) : (
                  p.source
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Drawer opened={open !== null} onClose={() => setOpen(null)} position="right" size="xl" title={open === 'new' ? 'New plasmid' : 'Plasmid'}>
        {open !== null && <PlasmidEditor id={open === 'new' ? null : open} onCreated={(id) => setOpen(id)} />}
      </Drawer>
    </Stack>
  )
}

const EMPTY_PLASMID = {
  name: '',
  alias: '',
  backbone: '',
  insert: '',
  insert_species: '',
  vector_type: '',
  resistance: [] as string[],
  origin: '',
  promoter: '',
  tags: [] as string[],
  copy_number: '',
  growth_temperature: '',
  sequence: '',
  features: [] as Feature[],
  circular: true,
  source: '',
  addgene_id: '',
  verified: false,
  notes: '',
}

function PlasmidEditor({ id, onCreated }: { id: string | null; onCreated: (id: string) => void }) {
  const { me } = useApp()
  const qc = useQueryClient()
  const plasmid = useQuery({ queryKey: ['plasmid', id], queryFn: () => api<Plasmid>(`/api/plasmids/${id}/`), enabled: !!id })
  const p = plasmid.data
  const [group, setGroup] = useState<string | null>(defaultGroup(me))
  const [v, setV] = useState<typeof EMPTY_PLASMID | null>(id ? null : EMPTY_PLASMID)
  const form = v ?? (p ? { ...EMPTY_PLASMID, ...p, sequence: p.sequence ?? '', features: p.features ?? [] } as typeof EMPTY_PLASMID : null)
  const editable = !id || (p && hasRole(me, p.group, 'member'))
  const save = useMutation({
    mutationFn: () => (id ? patch<Plasmid>(`/api/plasmids/${id}/`, form) : post<Plasmid>('/api/plasmids/', { ...form, group })),
    onSuccess: (saved) => {
      notifyOk(`${saved.code} saved`)
      qc.invalidateQueries({ queryKey: ['plasmids'] })
      qc.setQueryData(['plasmid', saved.id], saved)
      setV(null)
      if (!id) onCreated(saved.id)
    },
    onError: notifyError,
  })
  const genbank = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return post<{ name: string; circular: boolean; definition: string; features: Feature[]; sequence: string }>('/api/plasmids/parse-genbank/', fd)
    },
    onSuccess: (gb) => {
      setV({ ...(form ?? EMPTY_PLASMID), name: form?.name || gb.name, notes: form?.notes || gb.definition, sequence: gb.sequence, features: gb.features, circular: gb.circular })
      notifyOk(`Read ${gb.sequence.length} bp and ${gb.features.length} features. Review and save.`)
    },
    onError: notifyError,
  })
  if (!form) return null
  const set = (patchObj: Partial<typeof EMPTY_PLASMID>) => setV({ ...form, ...patchObj })
  const size = form.sequence ? form.sequence.replace(/\s/g, '').length : p?.size_bp ?? null
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 5 }}>
        <PlasmidMap name={form.name || p?.code || 'new'} size={size} features={form.features} circular={form.circular} />
        {p && (
          <Stack gap={4} mt="sm">
            <Field label="Code">{p.code}</Field>
            <Field label="GC content">{p.gc_content ? `${p.gc_content} %` : ''}</Field>
            <Field label="Strains carrying it">{p.strain_count}</Field>
            <Field label="Stocks">{p.sample_count}</Field>
            {p.sequence && (
              <Anchor href={`/api/plasmids/${p.id}/fasta/`} size="sm">
                Download FASTA
              </Anchor>
            )}
          </Stack>
        )}
        {form.features.length > 0 && (
          <Table fz="xs" mt="sm">
            <Table.Tbody>
              {form.features.map((f, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{f.name}</Table.Td>
                  <Table.Td>{f.type}</Table.Td>
                  <Table.Td>
                    {f.start}–{f.end} {f.strand === -1 ? '(−)' : ''}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Stack gap="xs">
          {!id && <GroupPicker value={group} onChange={setGroup} />}
          {editable && (
            <FileButton onChange={(f) => f && genbank.mutate(f)} accept=".gb,.gbk,.genbank,.txt">
              {(props) => (
                <Button {...props} variant="light" size="xs" loading={genbank.isPending}>
                  Import GenBank file (.gb)
                </Button>
              )}
            </FileButton>
          )}
          <Group grow>
            <TextInput label="Name" required value={form.name} onChange={(e) => set({ name: e.target.value })} readOnly={!editable} />
            <TextInput label="Alias" value={form.alias} onChange={(e) => set({ alias: e.target.value })} readOnly={!editable} />
          </Group>
          <Group grow>
            <TextInput label="Backbone" value={form.backbone} onChange={(e) => set({ backbone: e.target.value })} readOnly={!editable} placeholder="pET-28a(+)" />
            <TextInput label="Insert" value={form.insert} onChange={(e) => set({ insert: e.target.value })} readOnly={!editable} />
            <TextInput label="Insert species" value={form.insert_species} onChange={(e) => set({ insert_species: e.target.value })} readOnly={!editable} />
          </Group>
          <Group grow>
            <Select label="Vector type" data={['Bacterial expression', 'Mammalian expression', 'Lentiviral', 'AAV', 'Yeast', 'CRISPR', 'Cloning', 'Other']} value={form.vector_type || null} onChange={(x) => set({ vector_type: x ?? '' })} readOnly={!editable} clearable />
            <TextInput label="Promoter" value={form.promoter} onChange={(e) => set({ promoter: e.target.value })} readOnly={!editable} />
            <TextInput label="Origin" value={form.origin} onChange={(e) => set({ origin: e.target.value })} readOnly={!editable} />
          </Group>
          <Group grow>
            <TagsInput label="Resistance" data={['Ampicillin', 'Kanamycin', 'Chloramphenicol', 'Spectinomycin', 'Tetracycline', 'Zeocin', 'Puromycin', 'Hygromycin', 'Blasticidin', 'G418']} value={form.resistance} onChange={(resistance) => set({ resistance })} readOnly={!editable} />
            <TagsInput label="Tags" data={['His6', 'GST', 'MBP', 'FLAG', 'HA', 'Myc', 'GFP', 'mCherry', 'Strep']} value={form.tags} onChange={(tags) => set({ tags })} readOnly={!editable} />
          </Group>
          <Group grow>
            <TextInput label="Copy number" value={form.copy_number} onChange={(e) => set({ copy_number: e.target.value })} readOnly={!editable} />
            <TextInput label="Growth temp." value={form.growth_temperature} onChange={(e) => set({ growth_temperature: e.target.value })} readOnly={!editable} />
            <TextInput label="Source" value={form.source} onChange={(e) => set({ source: e.target.value })} readOnly={!editable} />
            <TextInput label="Addgene ID" value={form.addgene_id} onChange={(e) => set({ addgene_id: e.target.value })} readOnly={!editable} />
          </Group>
          <Group>
            <Checkbox label="Circular" checked={form.circular} onChange={(e) => set({ circular: e.currentTarget.checked })} disabled={!editable} />
            <Checkbox label="Sequence verified" checked={form.verified} onChange={(e) => set({ verified: e.currentTarget.checked })} disabled={!editable} />
          </Group>
          <Textarea label={`Sequence (${size ?? 0} bp)`} autosize minRows={3} maxRows={8} ff="monospace" value={form.sequence} onChange={(e) => set({ sequence: e.target.value })} readOnly={!editable} />
          <Textarea label="Notes" autosize value={form.notes} onChange={(e) => set({ notes: e.target.value })} readOnly={!editable} />
          {editable && (
            <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!form.name}>
              Save
            </Button>
          )}
        </Stack>
      </Grid.Col>
    </Grid>
  )
}

// --- strains -----------------------------------------------------------------------------

const KIND_LABEL: Record<string, string> = {
  bacterium: 'Bacterium',
  yeast: 'Yeast',
  cell_line: 'Cell line',
  virus: 'Virus',
  other: 'Other',
}

function Strains() {
  const { me } = useApp()
  const qc = useQueryClient()
  const [kind, setKind] = useState<string | null>(null)
  const l = useList<Strain>('strains', `/api/strains/?kind=${kind ?? ''}`)
  const plasmids = useQuery({ queryKey: ['plasmids', 'all'], queryFn: () => api<Page<Plasmid>>('/api/plasmids/?page_size=500') })
  const [v, setV] = useState({ group: defaultGroup(me), name: '', kind: 'bacterium', organism: '', genotype: '', plasmids: [] as string[], resistance: [] as string[], biosafety_level: '1', is_gmo: false, source: '', tissue: '', passage: '' as number | '' })
  const [adding, setAdding] = useState(false)
  const add = useMutation({
    mutationFn: () => post('/api/strains/', { ...v, biosafety_level: Number(v.biosafety_level), passage: v.passage === '' ? null : v.passage }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strains'] })
      setAdding(false)
      setV({ ...v, name: '', genotype: '', plasmids: [] })
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Group>
        <TextInput placeholder="Name, organism, genotype, source" value={l.q} onChange={(e) => l.setQ(e.target.value)} w={300} />
        <Select placeholder="Any type" clearable data={Object.entries(KIND_LABEL).map(([value, label]) => ({ value, label }))} value={kind} onChange={setKind} w={150} />
        <Button onClick={() => setAdding(true)}>New strain / cell line</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Code</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Organism</Table.Th>
            <Table.Th>Genotype</Table.Th>
            <Table.Th>Plasmids</Table.Th>
            <Table.Th>Biosafety</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {l.items.map((s) => (
            <Table.Tr key={s.id}>
              <Table.Td fw={600}>{s.code}</Table.Td>
              <Table.Td>
                {s.name}
                <Text size="xs" c="dimmed">
                  {KIND_LABEL[s.kind]} {s.source && `· ${s.source}`} {s.passage && `· P${s.passage}`}
                </Text>
              </Table.Td>
              <Table.Td fs="italic">{s.organism}</Table.Td>
              <Table.Td>
                <Text size="xs" ff="monospace">
                  {s.genotype}
                </Text>
              </Table.Td>
              <Table.Td>{s.plasmid_codes.join(', ')}</Table.Td>
              <Table.Td>
                <Badge color={s.biosafety_level >= 2 ? 'orange' : 'green'}>BSL-{s.biosafety_level}</Badge>
                {s.is_gmo && <Badge ml={4} variant="outline">GMO</Badge>}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Drawer opened={adding} onClose={() => setAdding(false)} position="right" size="md" title="New strain / cell line">
        <Stack>
          <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} />
          <TextInput label="Name" required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} placeholder="BL21(DE3) pET-GFP" />
          <Group grow>
            <Select label="Type" data={Object.entries(KIND_LABEL).map(([value, label]) => ({ value, label }))} value={v.kind} onChange={(k) => k && setV({ ...v, kind: k })} />
            <TextInput label="Organism" value={v.organism} onChange={(e) => setV({ ...v, organism: e.target.value })} placeholder="E. coli" />
          </Group>
          <Textarea label="Genotype" value={v.genotype} onChange={(e) => setV({ ...v, genotype: e.target.value })} />
          <MultiSelect label="Plasmids" searchable data={(plasmids.data?.results ?? []).map((p) => ({ value: p.id, label: `${p.code} ${p.name}` }))} value={v.plasmids} onChange={(x) => setV({ ...v, plasmids: x })} />
          <TagsInput label="Resistance" value={v.resistance} onChange={(x) => setV({ ...v, resistance: x })} />
          <Group grow>
            <Select label="Biosafety level" data={['1', '2', '3', '4']} value={v.biosafety_level} onChange={(b) => b && setV({ ...v, biosafety_level: b })} />
            <Checkbox mt="lg" label="Genetically modified" checked={v.is_gmo} onChange={(e) => setV({ ...v, is_gmo: e.currentTarget.checked })} />
          </Group>
          {v.kind === 'cell_line' && (
            <Group grow>
              <TextInput label="Tissue" value={v.tissue} onChange={(e) => setV({ ...v, tissue: e.target.value })} />
              <NumberInput label="Passage" value={v.passage} onChange={(x) => setV({ ...v, passage: x === '' ? '' : Number(x) })} />
            </Group>
          )}
          <TextInput label="Source" value={v.source} onChange={(e) => setV({ ...v, source: e.target.value })} placeholder="ATCC CRL-1573, lab of…" />
          <Button onClick={() => add.mutate()} disabled={!v.name}>
            Save
          </Button>
        </Stack>
      </Drawer>
    </Stack>
  )
}

// --- oligos ------------------------------------------------------------------------------

function Oligos() {
  const { me } = useApp()
  const qc = useQueryClient()
  const l = useList<Oligo>('oligos', '/api/oligos/')
  const [v, setV] = useState({ group: defaultGroup(me), name: '', sequence: '', purpose: 'PCR', target: '', modifications: '' })
  const tools = useQuery({
    queryKey: ['oligo-tools', v.sequence],
    queryFn: () => post<{ length: number; gc_content: number; tm: number | null; reverse_complement: string }>('/api/bio/oligo-tools/', { sequence: v.sequence }),
    enabled: v.sequence.replace(/\s/g, '').length >= 6,
    retry: false,
  })
  const add = useMutation({
    mutationFn: () => post('/api/oligos/', v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['oligos'] })
      setV({ ...v, name: '', sequence: '', target: '' })
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Card withBorder>
        <Group align="end">
          <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} w={180} />
          <TextInput label="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} w={160} />
          <TextInput label="Sequence 5'→3'" ff="monospace" value={v.sequence} onChange={(e) => setV({ ...v, sequence: e.target.value })} w={320} />
          <Select label="Purpose" data={['PCR', 'Sequencing', 'qPCR', 'Mutagenesis', 'gRNA', 'Probe', 'Other']} value={v.purpose} onChange={(x) => setV({ ...v, purpose: x ?? '' })} w={130} />
          <TextInput label="Target" value={v.target} onChange={(e) => setV({ ...v, target: e.target.value })} w={140} />
          <TextInput label="Modifications" value={v.modifications} onChange={(e) => setV({ ...v, modifications: e.target.value })} w={120} />
          <Button onClick={() => add.mutate()} disabled={!v.name || !v.sequence}>
            Add
          </Button>
        </Group>
        {tools.data && (
          <Text size="sm" mt="xs">
            {tools.data.length} nt · GC {tools.data.gc_content} % · Tm ≈ {tools.data.tm} °C · rev. comp.{' '}
            <Code>{tools.data.reverse_complement}</Code>
          </Text>
        )}
      </Card>
      <TextInput placeholder="Search name, sequence, target" value={l.q} onChange={(e) => l.setQ(e.target.value)} w={300} />
      <ScrollArea>
        <Table striped fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Code</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Sequence</Table.Th>
              <Table.Th>Length</Table.Th>
              <Table.Th>Tm</Table.Th>
              <Table.Th>GC</Table.Th>
              <Table.Th>Purpose / target</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {l.items.map((o) => (
              <Table.Tr key={o.id}>
                <Table.Td fw={600}>{o.code}</Table.Td>
                <Table.Td>{o.name}</Table.Td>
                <Table.Td>
                  <Code>{o.modifications && `${o.modifications}-`}{o.sequence}</Code>
                </Table.Td>
                <Table.Td>{o.sequence.length}</Table.Td>
                <Table.Td>{fmt(o.tm, 1)} °C</Table.Td>
                <Table.Td>{fmt(o.gc_content, 0)} %</Table.Td>
                <Table.Td>
                  {o.purpose} {o.target && `· ${o.target}`}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </Stack>
  )
}

// --- samples -----------------------------------------------------------------------------

const SAMPLE_KINDS = [
  { value: 'glycerol', label: 'Glycerol stock' },
  { value: 'dna', label: 'DNA prep' },
  { value: 'rna', label: 'RNA' },
  { value: 'cells', label: 'Frozen cells' },
  { value: 'protein', label: 'Protein' },
  { value: 'antibody', label: 'Antibody' },
  { value: 'serum', label: 'Serum / tissue' },
  { value: 'other', label: 'Other' },
]

function Samples() {
  const { me } = useApp()
  const qc = useQueryClient()
  const l = useList<BioSample>('bio-samples', '/api/bio-samples/')
  const plasmids = useQuery({ queryKey: ['plasmids', 'all'], queryFn: () => api<Page<Plasmid>>('/api/plasmids/?page_size=500') })
  const strains = useQuery({ queryKey: ['strains', 'all'], queryFn: () => api<Page<Strain>>('/api/strains/?page_size=500') })
  const [v, setV] = useState({ group: defaultGroup(me), kind: 'glycerol', name: '', plasmid: null as string | null, strain: null as string | null, location: null as string | null, box_position: '', concentration: '' as number | '', concentration_unit: 'ng/µL', volume_ul: '' as number | '' })
  const add = useMutation({
    mutationFn: () => post<BioSample>('/api/bio-samples/', { ...v, concentration: v.concentration === '' ? null : v.concentration, volume_ul: v.volume_ul === '' ? null : v.volume_ul }),
    onSuccess: (s) => {
      notifyOk(`Stored as ${s.barcode}`)
      qc.invalidateQueries({ queryKey: ['bio-samples'] })
      setV({ ...v, name: '', box_position: '' })
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Card withBorder>
        <Stack gap="xs">
          <Group grow align="end">
            <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} />
            <Select label="Type" data={SAMPLE_KINDS} value={v.kind} onChange={(k) => k && setV({ ...v, kind: k })} />
            <TextInput label="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
            <Select label="Plasmid" clearable searchable data={(plasmids.data?.results ?? []).map((p) => ({ value: p.id, label: `${p.code} ${p.name}` }))} value={v.plasmid} onChange={(x) => setV({ ...v, plasmid: x })} />
            <Select label="Strain" clearable searchable data={(strains.data?.results ?? []).map((s) => ({ value: s.id, label: `${s.code} ${s.name}` }))} value={v.strain} onChange={(x) => setV({ ...v, strain: x })} />
          </Group>
          <Group grow align="end">
            <LocationPicker label="Freezer / box" value={v.location} onChange={(x) => setV({ ...v, location: x })} />
            <TextInput label="Box position" value={v.box_position} onChange={(e) => setV({ ...v, box_position: e.target.value })} placeholder="A1" />
            <NumberInput label="Concentration" value={v.concentration} onChange={(x) => setV({ ...v, concentration: x === '' ? '' : Number(x) })} />
            <TextInput label="Unit" value={v.concentration_unit} onChange={(e) => setV({ ...v, concentration_unit: e.target.value })} />
            <NumberInput label="Volume (µL)" value={v.volume_ul} onChange={(x) => setV({ ...v, volume_ul: x === '' ? '' : Number(x) })} />
            <Button onClick={() => add.mutate()} disabled={!v.name}>
              Add sample
            </Button>
          </Group>
        </Stack>
      </Card>
      <TextInput placeholder="Search barcode, name, position" value={l.q} onChange={(e) => l.setQ(e.target.value)} w={300} />
      <Table striped fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Barcode</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th>Plasmid / strain</Table.Th>
            <Table.Th>Where</Table.Th>
            <Table.Th>Amount</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {l.items.map((s) => (
            <Table.Tr key={s.id} opacity={s.is_available ? 1 : 0.5}>
              <Table.Td ff="monospace">{s.barcode}</Table.Td>
              <Table.Td>{s.name}</Table.Td>
              <Table.Td>{SAMPLE_KINDS.find((k) => k.value === s.kind)?.label}</Table.Td>
              <Table.Td>{[s.plasmid_code, s.strain_code].filter(Boolean).join(' / ')}</Table.Td>
              <Table.Td>
                {s.location_path} {s.box_position && `· ${s.box_position}`}
              </Table.Td>
              <Table.Td>
                {s.concentration !== null && `${fmt(s.concentration)} ${s.concentration_unit}`}
                {s.volume_ul !== null && ` · ${fmt(s.volume_ul)} µL`}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  )
}
