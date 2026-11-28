import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  FileInput,
  Group,
  Menu,
  Modal,
  NumberInput,
  Radio,
  ScrollArea,
  Select,
  Stack,
  Table,
  Tabs,
  TagsInput,
  Text,
  TextInput,
  Textarea,
  Timeline,
  Title,
  Tooltip,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api, del, patch, post } from '../../api/client'
import type { Component, ComponentRole, Experiment } from '../../api/modules'
import { hasRole, useApp } from '../../components/context'
import {
  CompoundPicker,
  ContainerPicker,
  fmt,
  fmtDateTime,
  LocationPicker,
  notifyError,
  notifyOk,
  StatusBadge,
} from '../../components/pickers'
import { ReactionScheme, SmilesImage } from '../../components/SmilesImage'
import StructureEditorModal from '../../components/StructureEditorModal'

const ROLE_LABEL: Record<ComponentRole, string> = {
  reactant: 'Reactant',
  reagent: 'Reagent',
  catalyst: 'Catalyst',
  solvent: 'Solvent',
  product: 'Product',
}

export default function ExperimentPage() {
  const { id } = useParams()
  const { me, config } = useApp()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const key = ['experiment', id]
  const exp = useQuery({ queryKey: key, queryFn: () => api<Experiment>(`/api/experiments/${id}/`) })
  const refresh = () => qc.invalidateQueries({ queryKey: key })
  const [drawing, setDrawing] = useState(false)
  const [verify, setVerify] = useState<null | { intact: boolean | null; content_hash: string }>(null)

  const update = useMutation({
    mutationFn: (body: Partial<Experiment>) => patch<Experiment>(`/api/experiments/${id}/`, body),
    onSuccess: (data) => {
      qc.setQueryData(key, data)
      qc.invalidateQueries({ queryKey: ['experiments'] })
    },
    onError: notifyError,
  })
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => post<unknown>(`/api/experiments/${id}/${path}/`, body),
    onSuccess: (_d, { path }) => {
      notifyOk(
        {
          sign: 'Signed. The record is now locked.',
          witness: 'Witnessed.',
          'deduct-inventory': 'Amounts booked out of the inventory.',
          'import-reaction': 'Reaction imported.',
        }[path] ?? 'Done',
      )
      refresh()
    },
    onError: notifyError,
  })
  const duplicate = useMutation({
    mutationFn: () => post<Experiment>(`/api/experiments/${id}/duplicate/`),
    onSuccess: (e) => navigate(`/eln/${e.id}`),
    onError: notifyError,
  })

  const e = exp.data
  if (!e) return null
  const canWrite = hasRole(me, e.group, 'member')
  const locked = e.is_locked
  const editable = canWrite && !locked
  const isOwner = e.owner === me?.id

  return (
    <Stack>
      <Group justify="space-between" align="start">
        <div>
          <Group gap="xs">
            <Anchor component={Link} to="/eln" size="sm">
              Notebook
            </Anchor>
            <Text size="sm" c="dimmed">
              / {e.project_name || e.group_name}
            </Text>
          </Group>
          <Title order={2}>
            {e.code} · {e.title}
          </Title>
          <Text size="sm" c="dimmed">
            {e.owner_name} · {e.kind} · created {fmtDateTime(e.created_at)}
          </Text>
        </div>
        <Group>
          <Select
            data={['planned', 'in_progress', 'completed', 'failed'].map((s) => ({ value: s, label: s.replace('_', ' ') }))}
            value={e.status}
            onChange={(s) => s && update.mutate({ status: s as Experiment['status'] })}
            disabled={!canWrite}
            w={150}
          />
          <Menu>
            <Menu.Target>
              <Button variant="default">More</Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={() => duplicate.mutate()}>Repeat / scale up (duplicate)</Menu.Item>
              <Menu.Item onClick={() => window.print()}>Print / save as PDF</Menu.Item>
              <Menu.Item
                onClick={async () => setVerify(await api(`/api/experiments/${id}/verify/`))}
              >
                Verify signatures
              </Menu.Item>
              {!locked && isOwner && (
                <Menu.Item
                  color="red"
                  onClick={async () => {
                    if (!confirm('Delete this draft experiment?')) return
                    try {
                      await del(`/api/experiments/${id}/`)
                      navigate('/eln')
                    } catch (err) {
                      notifyError(err)
                    }
                  }}
                >
                  Delete draft
                </Menu.Item>
              )}
            </Menu.Dropdown>
          </Menu>
          {!locked && isOwner && (
            <Button
              color="teal"
              onClick={() =>
                confirm('Sign this experiment? Its content becomes permanent; later notes go in as addenda.') &&
                action.mutate({ path: 'sign' })
              }
            >
              Sign
            </Button>
          )}
          {locked && !e.witnessed_at && !isOwner && canWrite && (
            <Button color="green" onClick={() => action.mutate({ path: 'witness' })}>
              Witness
            </Button>
          )}
        </Group>
      </Group>
      {locked && (
        <Alert color="teal" title="Signed record">
          Signed by {e.signed_by_name} on {fmtDateTime(e.signed_at)}
          {e.witnessed_at ? `, witnessed by ${e.witnessed_by_name} on ${fmtDateTime(e.witnessed_at)}` : ', waiting for a witness'}
          . Content can no longer change. Use comments for addenda.
        </Alert>
      )}
      <TagsInput
        label="Tags"
        value={e.tags}
        onChange={(tags) => update.mutate({ tags })}
        disabled={!canWrite}
        placeholder="Add tag and press Enter"
        maw={600}
      />
      <Tabs defaultValue={e.kind === 'synthesis' ? 'reaction' : 'procedure'} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="reaction">Reaction & stoichiometry</Tabs.Tab>
          <Tabs.Tab value="procedure">Procedure & results</Tabs.Tab>
          <Tabs.Tab value="files">Attachments ({e.attachments.length})</Tabs.Tab>
          <Tabs.Tab value="audit">Signatures & comments ({e.comments.length})</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="reaction" pt="md">
          <ReactionTab e={e} editable={editable} canWrite={canWrite} onDraw={() => setDrawing(true)} onChange={refresh} onUpdate={(b) => update.mutate(b)} onAction={(path, body) => action.mutate({ path, body })} />
        </Tabs.Panel>
        <Tabs.Panel value="procedure" pt="md">
          <ProcedureTab e={e} editable={editable} onSave={(b) => update.mutate(b, { onSuccess: () => notifyOk('Saved') })} />
        </Tabs.Panel>
        <Tabs.Panel value="files" pt="md">
          <Attachments e={e} editable={editable} onChange={refresh} />
        </Tabs.Panel>
        <Tabs.Panel value="audit" pt="md">
          <Audit e={e} onChange={refresh} />
        </Tabs.Panel>
      </Tabs>
      <StructureEditorModal
        opened={drawing}
        onClose={() => setDrawing(false)}
        editorKind={config.structure_editor}
        initialMolfile={e.reaction_rxn || undefined}
        mode="reaction"
        title="Draw the reaction (reactants → products)"
        submitLabel="Use reaction"
        onSubmit={(rxn) => action.mutate({ path: 'import-reaction', body: { reaction: rxn, replace: true } })}
      />
      <Modal opened={!!verify} onClose={() => setVerify(null)} title="Signature verification">
        {verify && (
          <Stack>
            {verify.intact === null ? (
              <Text>Not signed yet.</Text>
            ) : verify.intact ? (
              <Alert color="green">The stored content matches every signature.</Alert>
            ) : (
              <Alert color="red">The content has changed since it was signed!</Alert>
            )}
            <Text size="xs">Current content hash:</Text>
            <Code block>{verify.content_hash}</Code>
          </Stack>
        )}
      </Modal>
    </Stack>
  )
}

// --- reaction ----------------------------------------------------------------------------

function ReactionTab({
  e,
  editable,
  canWrite,
  onDraw,
  onChange,
  onUpdate,
  onAction,
}: {
  e: Experiment
  editable: boolean
  canWrite: boolean
  onDraw: () => void
  onChange: () => void
  onUpdate: (b: Partial<Experiment>) => void
  onAction: (path: string, body?: unknown) => void
}) {
  const [smiles, setSmiles] = useState('')
  const [registering, setRegistering] = useState<Component | null>(null)
  const linked = e.components.filter((c) => c.container && !c.consumed && c.role !== 'product')
  return (
    <Stack>
      <Card withBorder>
        <Group justify="space-between" mb="xs">
          <Text fw={600}>Reaction scheme</Text>
          {editable && (
            <Group>
              <Button size="xs" onClick={onDraw}>
                {e.reaction_smiles ? 'Edit drawing' : 'Draw reaction'}
              </Button>
              <TextInput
                size="xs"
                placeholder="…or paste reaction SMILES  A.B>>C"
                value={smiles}
                onChange={(ev) => setSmiles(ev.target.value)}
                w={260}
              />
              <Button size="xs" variant="light" disabled={!smiles.includes('>')} onClick={() => onAction('import-reaction', { reaction: smiles })}>
                Import
              </Button>
            </Group>
          )}
        </Group>
        {e.reaction_smiles ? (
          <ScrollArea>
            <ReactionScheme smiles={e.reaction_smiles} />
          </ScrollArea>
        ) : (
          <Text c="dimmed" size="sm">
            Draw the reaction in the structure editor: reactants and products become rows of the
            stoichiometry table, with molar masses filled in.
          </Text>
        )}
        <Group grow mt="md">
          <Conditions e={e} editable={editable} onUpdate={onUpdate} />
        </Group>
      </Card>
      <Stoichiometry e={e} editable={editable} onChange={onChange} onRegister={setRegistering} />
      {canWrite && linked.length > 0 && (
        <Alert color="blue" title="Inventory">
          <Group justify="space-between">
            <Text size="sm">
              {linked.length} row(s) are linked to bottles in the inventory. When you have weighed them out, book
              the amounts out so stock levels stay correct.
            </Text>
            <Button onClick={() => onAction('deduct-inventory')}>Deduct from inventory</Button>
          </Group>
        </Alert>
      )}
      <RegisterProduct component={registering} onClose={() => setRegistering(null)} onDone={onChange} />
    </Stack>
  )
}

function Conditions({ e, editable, onUpdate }: { e: Experiment; editable: boolean; onUpdate: (b: Partial<Experiment>) => void }) {
  const [v, setV] = useState({ temperature: e.temperature, duration: e.duration, atmosphere: e.atmosphere, solvent: e.solvent })
  useEffect(() => setV({ temperature: e.temperature, duration: e.duration, atmosphere: e.atmosphere, solvent: e.solvent }), [e])
  const field = (k: keyof typeof v, label: string, ph: string) => (
    <TextInput
      label={label}
      placeholder={ph}
      value={v[k]}
      disabled={!editable}
      onChange={(ev) => setV({ ...v, [k]: ev.target.value })}
      onBlur={() => v[k] !== e[k] && onUpdate({ [k]: v[k] })}
    />
  )
  return (
    <>
      {field('temperature', 'Temperature', 'e.g. 80 °C, reflux')}
      {field('duration', 'Time', 'e.g. 16 h')}
      {field('atmosphere', 'Atmosphere', 'N₂, Ar, air')}
      {field('solvent', 'Solvent (summary)', 'e.g. THF (0.2 M)')}
    </>
  )
}

const NUM_FIELDS: { key: keyof Component; label: string; digits: number; tip?: string }[] = [
  { key: 'mw', label: 'MW', digits: 2, tip: 'g/mol' },
  { key: 'equivalents', label: 'Eq.', digits: 3 },
  { key: 'mmol', label: 'mmol', digits: 3 },
  { key: 'mass_mg', label: 'Mass (mg)', digits: 2 },
  { key: 'volume_ml', label: 'Vol. (mL)', digits: 3 },
  { key: 'density', label: 'ρ (g/mL)', digits: 3 },
  { key: 'molarity', label: 'c (M)', digits: 3, tip: 'For solutions' },
  { key: 'purity', label: 'Purity %', digits: 1 },
]

function Stoichiometry({
  e,
  editable,
  onChange,
  onRegister,
}: {
  e: Experiment
  editable: boolean
  onChange: () => void
  onRegister: (c: Component) => void
}) {
  const save = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Component> }) => patch(`/api/reaction-components/${id}/`, body),
    onSuccess: onChange,
    onError: notifyError,
  })
  const remove = useMutation({
    mutationFn: (id: string) => del(`/api/reaction-components/${id}/`),
    onSuccess: onChange,
    onError: notifyError,
  })
  const [adding, setAdding] = useState(false)
  const rows = e.components
  const limiting = rows.find((r) => r.is_limiting)?.id ?? ''
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <div>
          <Text fw={600}>Stoichiometry</Text>
          <Text size="xs" c="dimmed">
            Set the scale on the limiting reagent (mass, volume or mmol) and equivalents on the others;
            everything else is calculated. Products: enter the isolated mass to get the yield.
          </Text>
        </div>
        {editable && (
          <Button size="xs" variant="light" onClick={() => setAdding(true)}>
            Add row
          </Button>
        )}
      </Group>
      <ScrollArea>
        <Radio.Group value={limiting} onChange={(id) => save.mutate({ id, body: { is_limiting: true } })}>
          <Table withColumnBorders fz="sm" miw={1100}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Lim.</Table.Th>
                <Table.Th>Role</Table.Th>
                <Table.Th>Substance</Table.Th>
                <Table.Th>Bottle</Table.Th>
                {NUM_FIELDS.map((f) => (
                  <Table.Th key={f.key}>
                    <Tooltip label={f.tip} disabled={!f.tip}>
                      <span>{f.label}</span>
                    </Tooltip>
                  </Table.Th>
                ))}
                <Table.Th>Isolated (mg)</Table.Th>
                <Table.Th>Yield</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((c) => (
                <Table.Tr key={c.id} bg={c.role === 'product' ? 'var(--mantine-color-green-light)' : undefined}>
                  <Table.Td>{c.role !== 'product' && <Radio value={c.id} disabled={!editable} />}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" size="sm" color={c.role === 'product' ? 'green' : 'gray'}>
                      {ROLE_LABEL[c.role]}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      {c.smiles && <SmilesImage smiles={c.smiles} width={70} height={50} />}
                      <EditableText value={c.name} disabled={!editable} onSave={(name) => save.mutate({ id: c.id, body: { name } })} />
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {c.container_barcode ? (
                      <Text size="xs">
                        {c.container_barcode}
                        <br />
                        <Text span c="dimmed" size="xs">
                          {c.consumed ? 'deducted' : `${c.container_left} left`}
                        </Text>
                      </Text>
                    ) : (
                      c.role !== 'product' && editable && (
                        <ContainerPicker size="xs" value={null} w={170} onChange={(container) => container && save.mutate({ id: c.id, body: { container } })} />
                      )
                    )}
                    {c.registered_barcode && <Badge color="green" size="xs">{c.registered_barcode}</Badge>}
                  </Table.Td>
                  {NUM_FIELDS.map((f) => (
                    <Table.Td key={f.key}>
                      <NumCell
                        value={c[f.key] as number | null}
                        digits={f.digits}
                        disabled={!editable || (c.role === 'product' && ['volume_ml', 'density', 'molarity'].includes(f.key))}
                        onSave={(val) => save.mutate({ id: c.id, body: { [f.key]: val } })}
                      />
                    </Table.Td>
                  ))}
                  <Table.Td>
                    {c.role === 'product' && (
                      <NumCell value={c.actual_mass_mg} digits={2} disabled={!editable} onSave={(val) => save.mutate({ id: c.id, body: { actual_mass_mg: val } })} />
                    )}
                  </Table.Td>
                  <Table.Td>
                    {c.yield_percent !== null && <b>{fmt(c.yield_percent, 1)} %</b>}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      {c.role === 'product' && !c.registered_barcode && c.actual_mass_mg && (
                        <Button size="compact-xs" variant="light" color="green" onClick={() => onRegister(c)}>
                          To inventory
                        </Button>
                      )}
                      {editable && !c.consumed && (
                        <ActionIcon size="sm" variant="subtle" color="red" onClick={() => remove.mutate(c.id)} title="Remove row">
                          ×
                        </ActionIcon>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Radio.Group>
      </ScrollArea>
      <AddComponent experimentId={e.id} opened={adding} onClose={() => setAdding(false)} onDone={onChange} />
    </Card>
  )
}

function NumCell({ value, digits, disabled, onSave }: { value: number | null; digits: number; disabled?: boolean; onSave: (v: number | null) => void }) {
  const [v, setV] = useState<string | number>(value ?? '')
  useEffect(() => setV(value === null ? '' : Number(value.toFixed(digits))), [value, digits])
  if (disabled) return <Text size="sm">{fmt(value, digits)}</Text>
  return (
    <NumberInput
      size="xs"
      w={90}
      hideControls
      value={v}
      decimalScale={digits + 2}
      onChange={setV}
      onBlur={() => {
        const next = v === '' ? null : Number(v)
        if (next !== value && !(next !== null && value !== null && Math.abs(next - value) < 10 ** -digits)) onSave(next)
      }}
    />
  )
}

function EditableText({ value, disabled, onSave }: { value: string; disabled?: boolean; onSave: (v: string) => void }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  if (disabled) return <Text size="sm">{value}</Text>
  return <TextInput size="xs" value={v} w={150} onChange={(e) => setV(e.target.value)} onBlur={() => v !== value && onSave(v)} />
}

function AddComponent({ experimentId, opened, onClose, onDone }: { experimentId: string; opened: boolean; onClose: () => void; onDone: () => void }) {
  const [v, setV] = useState({ role: 'reagent' as ComponentRole, compound: null as string | null, container: null as string | null, name: '', smiles: '', equivalents: 1 as number | '' })
  const add = useMutation({
    mutationFn: () => post('/api/reaction-components/', { experiment: experimentId, ...v, equivalents: v.equivalents === '' ? null : v.equivalents }),
    onSuccess: () => {
      onDone()
      onClose()
      setV({ ...v, compound: null, container: null, name: '', smiles: '' })
    },
    onError: notifyError,
  })
  return (
    <Modal opened={opened} onClose={onClose} title="Add a row">
      <Stack>
        <Select label="Role" data={Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))} value={v.role} onChange={(r) => r && setV({ ...v, role: r as ComponentRole })} />
        {v.role !== 'product' && (
          <ContainerPicker label="From a bottle in the inventory (recommended)" value={v.container} onChange={(c) => setV({ ...v, container: c })} />
        )}
        <CompoundPicker label="…or a compound" value={v.compound} onChange={(c) => setV({ ...v, compound: c })} />
        <Group grow>
          <TextInput label="…or a name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
          <TextInput label="SMILES" value={v.smiles} onChange={(e) => setV({ ...v, smiles: e.target.value })} />
        </Group>
        <NumberInput label="Equivalents" value={v.equivalents} onChange={(x) => setV({ ...v, equivalents: x === '' ? '' : Number(x) })} />
        <Button onClick={() => add.mutate()} disabled={!v.container && !v.compound && !v.name && !v.smiles}>
          Add
        </Button>
      </Stack>
    </Modal>
  )
}

function RegisterProduct({ component, onClose, onDone }: { component: Component | null; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState('')
  const [location, setLocation] = useState<string | null>(null)
  const reg = useMutation({
    mutationFn: () => post<{ barcode: string }>(`/api/reaction-components/${component!.id}/register/`, { name, location }),
    onSuccess: (c) => {
      notifyOk(`Product stored as ${c.barcode}`)
      onDone()
      onClose()
    },
    onError: notifyError,
  })
  return (
    <Modal opened={!!component} onClose={onClose} title="Put the product into the inventory">
      {component && (
        <Stack>
          {component.smiles && <SmilesImage smiles={component.smiles} width={200} height={140} />}
          <Text size="sm">
            {fmt(component.actual_mass_mg, 1)} mg {component.yield_percent !== null && `(${fmt(component.yield_percent, 1)} % yield)`} will be
            stored as a new container labelled with this experiment's code.
          </Text>
          {!component.compound && (
            <TextInput label="Compound name (new compound)" placeholder={component.name} value={name} onChange={(e) => setName(e.target.value)} />
          )}
          <LocationPicker label="Location" value={location} onChange={setLocation} />
          <Button onClick={() => reg.mutate()} loading={reg.isPending}>
            Create container
          </Button>
        </Stack>
      )}
    </Modal>
  )
}

// --- procedure ---------------------------------------------------------------------------

function ProcedureTab({ e, editable, onSave }: { e: Experiment; editable: boolean; onSave: (b: Partial<Experiment>) => void }) {
  const pick = (x: Experiment) => ({
    aim: x.aim,
    procedure: x.procedure,
    observations: x.observations,
    workup: x.workup,
    conclusion: x.conclusion,
    started_on: x.started_on,
    completed_on: x.completed_on,
  })
  const [v, setV] = useState(pick(e))
  useEffect(() => setV(pick(e)), [e])
  const dirty = JSON.stringify(v) !== JSON.stringify(pick(e))
  const area = (k: 'aim' | 'procedure' | 'observations' | 'workup' | 'conclusion', label: string, rows = 4) => (
    <Textarea label={label} autosize minRows={rows} value={v[k]} readOnly={!editable} onChange={(ev) => setV({ ...v, [k]: ev.target.value })} />
  )
  return (
    <Stack>
      <Group grow>
        <TextInput label="Started" type="date" value={v.started_on ?? ''} readOnly={!editable} onChange={(ev) => setV({ ...v, started_on: ev.target.value || null })} />
        <TextInput label="Finished" type="date" value={v.completed_on ?? ''} onChange={(ev) => setV({ ...v, completed_on: ev.target.value || null })} />
      </Group>
      {area('aim', 'Aim', 2)}
      {area('procedure', 'Procedure', 8)}
      {area('observations', 'Observations', 4)}
      {area('workup', 'Work-up & purification', 3)}
      {area('conclusion', 'Results & conclusion', 3)}
      {(editable || dirty) && (
        <Group>
          <Button onClick={() => onSave(editable ? v : { completed_on: v.completed_on })} disabled={!dirty}>
            Save
          </Button>
          {dirty && <Text size="sm" c="orange">Unsaved changes</Text>}
        </Group>
      )}
    </Stack>
  )
}

// --- attachments -------------------------------------------------------------------------

function Attachments({ e, editable, onChange }: { e: Experiment; editable: boolean; onChange: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [kind, setKind] = useState<string | null>('NMR')
  const [description, setDescription] = useState('')
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('experiment', e.id)
      fd.append('file', file!)
      fd.append('kind', kind ?? '')
      fd.append('description', description)
      return post('/api/attachments/', fd)
    },
    onSuccess: () => {
      setFile(null)
      setDescription('')
      onChange()
    },
    onError: notifyError,
  })
  return (
    <Stack>
      {editable && (
        <Group align="end">
          <FileInput label="File" placeholder="Spectrum, chromatogram, photo…" value={file} onChange={setFile} w={280} />
          <Select label="Type" data={['NMR', 'MS', 'IR', 'UV-Vis', 'HPLC', 'GC', 'X-ray', 'Photo', 'Other']} value={kind} onChange={setKind} w={120} />
          <TextInput label="Description" value={description} onChange={(ev) => setDescription(ev.target.value)} w={260} />
          <Button onClick={() => upload.mutate()} disabled={!file} loading={upload.isPending}>
            Upload
          </Button>
        </Group>
      )}
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>File</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th>Size</Table.Th>
            <Table.Th>SHA-256</Table.Th>
            <Table.Th>Uploaded</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {e.attachments.map((a) => (
            <Table.Tr key={a.id}>
              <Table.Td>
                <Anchor href={a.file} target="_blank">
                  {a.name}
                </Anchor>
                {a.description && <Text size="xs" c="dimmed">{a.description}</Text>}
              </Table.Td>
              <Table.Td>{a.kind}</Table.Td>
              <Table.Td>{(a.size / 1024).toFixed(1)} kB</Table.Td>
              <Table.Td>
                <Code>{a.sha256.slice(0, 12)}…</Code>
              </Table.Td>
              <Table.Td>
                <Text size="xs">
                  {a.uploaded_by_name}, {fmtDateTime(a.created_at)}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {e.attachments.length === 0 && <Text c="dimmed">No files yet.</Text>}
    </Stack>
  )
}

// --- audit -------------------------------------------------------------------------------

function Audit({ e, onChange }: { e: Experiment; onChange: () => void }) {
  const [text, setText] = useState('')
  const add = useMutation({
    mutationFn: () => post('/api/comments/', { experiment: e.id, text }),
    onSuccess: () => {
      setText('')
      onChange()
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Card withBorder>
        <Text fw={600} mb="xs">
          Signatures
        </Text>
        {e.signatures.length === 0 ? (
          <Text size="sm" c="dimmed">
            Not signed. The author signs when the record is complete; a group colleague then witnesses it.
          </Text>
        ) : (
          <Timeline bulletSize={16}>
            {e.signatures.map((s) => (
              <Timeline.Item key={s.id} title={`${s.kind === 'sign' ? 'Signed' : 'Witnessed'} by ${s.user_name}`}>
                <Text size="xs" c="dimmed">
                  {fmtDateTime(s.created_at)} · ledger #{s.seq}
                </Text>
                <Text size="sm">“{s.meaning}”</Text>
                <Code>{s.hash.slice(0, 24)}…</Code>
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Card>
      <Card withBorder>
        <Text fw={600} mb="xs">
          Discussion {e.is_locked && '& addenda'}
        </Text>
        <Stack gap="xs">
          {e.comments.map((c) => (
            <Card key={c.id} padding="xs" bg="var(--mantine-color-default-hover)">
              <Group gap="xs">
                <Text size="sm" fw={500}>
                  {c.author_name}
                </Text>
                <Text size="xs" c="dimmed">
                  {fmtDateTime(c.created_at)}
                </Text>
                {c.is_addendum && <Badge size="xs">addendum</Badge>}
              </Group>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {c.text}
              </Text>
            </Card>
          ))}
          <Textarea placeholder={e.is_locked ? 'Add an addendum (correction, extra observation)…' : 'Comment…'} value={text} onChange={(ev) => setText(ev.target.value)} autosize />
          <Group>
            <Button size="xs" onClick={() => add.mutate()} disabled={!text.trim()}>
              Post
            </Button>
          </Group>
        </Stack>
      </Card>
      <StatusBadge status={e.status} />
    </Stack>
  )
}
