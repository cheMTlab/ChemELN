/**
 * Add a container in two steps: (1) find or create the compound, (2) container details.
 * Compound sources: existing compounds, PubChem (if enabled by the admin), or a drawn structure.
 */
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Group,
  Image,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Stepper,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import {
  type Compound,
  type Container,
  type Location,
  type Page,
  type PubChemResult,
  UNITS,
} from '../api/types'
import Hazards from '../components/Hazards'
import StructureEditorModal from '../components/StructureEditorModal'
import { useApp, writableGroups } from '../components/context'

const errorText = (e: unknown) =>
  e instanceof ApiError ? Object.values(e.body as object).flat().join(' ') : String(e)

export default function NewContainer() {
  const { config, me } = useApp()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [compound, setCompound] = useState<Compound | null>(null)
  const [error, setError] = useState<string | null>(null)

  // --- step 1: compound -----------------------------------------------------------------
  const [search, setSearch] = useState('')
  const [submitted, setSubmitted] = useState('')
  const existing = useQuery({
    queryKey: ['compounds', submitted],
    queryFn: () => api<Page<Compound>>(`/api/compounds/?q=${encodeURIComponent(submitted)}`),
    enabled: submitted.length > 1,
  })
  const [draft, setDraft] = useState<Partial<PubChemResult> & { structure?: string }>({})
  const [drawing, setDrawing] = useState(false)
  const [busy, setBusy] = useState(false)

  async function lookupPubChem() {
    setError(null)
    setBusy(true)
    try {
      const data = await api<PubChemResult>(
        `/api/compounds/lookup/?q=${encodeURIComponent(search.trim())}`,
      )
      if (data.existing_id) {
        setCompound(await api<Compound>(`/api/compounds/${data.existing_id}/`))
        setStep(1)
      } else {
        setDraft({ ...data, structure: data.smiles })
      }
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  async function createCompound() {
    setError(null)
    setBusy(true)
    try {
      const created = await api<Compound>('/api/compounds/', {
        method: 'POST',
        body: JSON.stringify({
          name: draft.name,
          cas: draft.cas ?? '',
          structure: draft.structure ?? '',
          synonyms: draft.synonyms ?? [],
          ghs_pictograms: draft.ghs_pictograms ?? [],
          signal_word: draft.signal_word ?? '',
          h_statements: draft.h_statements ?? [],
          p_statements: draft.p_statements ?? [],
          pubchem_cid: draft.pubchem_cid ?? null,
        }),
      })
      setCompound(created)
      setStep(1)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  // --- step 2: container ----------------------------------------------------------------
  const groups = writableGroups(me)
  const [form, setForm] = useState({
    group: groups[0]?.group_id ?? '',
    location: '',
    amount: '' as number | string,
    unit: 'g',
    purity: '' as number | string,
    supplier: '',
    catalog_number: '',
    lot_number: '',
    expiry_date: '',
    copies: 1 as number | string,
  })
  const [locSearch, setLocSearch] = useState('')
  const locations = useQuery({
    queryKey: ['locations', locSearch],
    queryFn: () => api<Page<Location>>(`/api/locations/?q=${encodeURIComponent(locSearch)}`),
  })
  const [printAfter, setPrintAfter] = useState(true)
  const set = (k: keyof typeof form) => (v: unknown) => setForm((f) => ({ ...f, [k]: v }))

  async function saveContainer() {
    if (!compound) return
    setError(null)
    setBusy(true)
    try {
      const ids: string[] = []
      for (let i = 0; i < Number(form.copies || 1); i++) {
        const c = await api<Container>('/api/containers/', {
          method: 'POST',
          body: JSON.stringify({
            compound: compound.id,
            group: form.group,
            location: form.location || null,
            amount: String(form.amount),
            unit: form.unit,
            purity: form.purity === '' ? null : String(form.purity),
            supplier: form.supplier,
            catalog_number: form.catalog_number,
            lot_number: form.lot_number,
            expiry_date: form.expiry_date || null,
          }),
        })
        ids.push(c.id)
      }
      if (printAfter) window.open(`/api/containers/labels/?layout=roll-62x29&ids=${ids.join(',')}`)
      navigate(ids.length === 1 ? `/containers/${ids[0]}` : `/inventory?compound=${compound.id}`)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  if (!groups.length) {
    return <Alert>You need to be a member of a research group to add containers.</Alert>
  }

  return (
    <Stack maw={900}>
      <Title order={3}>Add container</Title>
      {error && <Alert color="red" withCloseButton onClose={() => setError(null)}>{error}</Alert>}
      <Stepper active={step} onStepClick={(s) => s < step && setStep(s)}>
        <Stepper.Step label="Compound" description={compound?.name ?? 'Find or create'}>
          <Stack mt="md">
            <Group align="flex-end">
              <TextInput flex={1} label="Name or CAS number" value={search}
                onChange={(e) => setSearch(e.currentTarget.value)}
                onKeyDown={(e) => e.key === 'Enter' && setSubmitted(search.trim())} />
              <Button onClick={() => setSubmitted(search.trim())}>Search here</Button>
              {config.external_lookups && (
                <Button variant="light" loading={busy} onClick={lookupPubChem}
                  disabled={!search.trim()}>
                  Look up in PubChem
                </Button>
              )}
              <Button variant="default" onClick={() => setDrawing(true)}>Draw structure</Button>
            </Group>

            {existing.data?.results.map((c) => (
              <Card key={c.id} withBorder padding="xs" style={{ cursor: 'pointer' }}
                onClick={() => { setCompound(c); setStep(1) }}>
                <Group>
                  {c.smiles && <Image src={`/api/compounds/${c.id}/depict/`} w={80} h={55}
                    fit="contain" alt="" />}
                  <div style={{ flex: 1 }}>
                    <Text fw={500}>{c.name}</Text>
                    <Text size="xs" c="dimmed">{[c.cas, c.formula].filter(Boolean).join(' · ')}</Text>
                  </div>
                  <Hazards pictograms={c.ghs_pictograms} signalWord={c.signal_word} />
                </Group>
              </Card>
            ))}
            {existing.data?.count === 0 && (
              <Text size="sm" c="dimmed">Not in this inventory yet. Create it below.</Text>
            )}

            <Card withBorder>
              <Text fw={600} mb="xs">New compound</Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <TextInput label="Name" required value={draft.name ?? ''}
                  onChange={(e) => setDraft({ ...draft, name: e.currentTarget.value })} />
                <TextInput label="CAS number" value={draft.cas ?? ''}
                  onChange={(e) => setDraft({ ...draft, cas: e.currentTarget.value })} />
              </SimpleGrid>
              <Text size="sm" mt="xs" c="dimmed">
                {draft.structure ? 'Structure set ✓' : 'No structure (fine for mixtures)'}
                {draft.formula && ` · ${draft.formula}`}
              </Text>
              {draft.ghs_pictograms && (
                <Hazards pictograms={draft.ghs_pictograms} signalWord={draft.signal_word} />
              )}
              <Button mt="sm" onClick={createCompound} loading={busy} disabled={!draft.name}>
                Create compound and continue
              </Button>
            </Card>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Container" description="Amount, location, supplier">
          <Stack mt="md">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <Select label="Group" required value={form.group} onChange={set('group')}
                data={groups.map((g) => ({ value: g.group_id, label: g.group_name }))} />
              <Select label="Location" searchable clearable value={form.location || null}
                onSearchChange={setLocSearch} onChange={(v) => set('location')(v ?? '')}
                data={(locations.data?.results ?? []).map((l) => ({ value: l.id, label: l.path }))} />
              <Group grow align="flex-end">
                <NumberInput label="Amount" required min={0} decimalScale={4}
                  value={form.amount} onChange={set('amount')} />
                <Select label="Unit" data={[...UNITS]} value={form.unit}
                  onChange={(v) => set('unit')(v ?? 'g')} />
              </Group>
              <NumberInput label="Purity (%)" min={0} max={100} value={form.purity}
                onChange={set('purity')} />
              <TextInput label="Supplier" value={form.supplier}
                onChange={(e) => set('supplier')(e.currentTarget.value)} />
              <TextInput label="Catalogue number" value={form.catalog_number}
                onChange={(e) => set('catalog_number')(e.currentTarget.value)} />
              <TextInput label="Lot number" value={form.lot_number}
                onChange={(e) => set('lot_number')(e.currentTarget.value)} />
              <TextInput label="Expiry date" type="date" value={form.expiry_date}
                onChange={(e) => set('expiry_date')(e.currentTarget.value)} />
              <NumberInput label="Number of identical containers" min={1} max={50}
                value={form.copies} onChange={set('copies')} />
            </SimpleGrid>
            <Checkbox label="Print labels after saving" checked={printAfter}
              onChange={(e) => setPrintAfter(e.currentTarget.checked)} />
            <Group>
              <Button onClick={saveContainer} loading={busy}
                disabled={!form.group || form.amount === ''}>
                Save
              </Button>
            </Group>
          </Stack>
        </Stepper.Step>
      </Stepper>

      <StructureEditorModal
        opened={drawing}
        onClose={() => setDrawing(false)}
        editorKind={config.structure_editor}
        onSubmit={async (molfile) => {
          try {
            const info = await api<{ formula: string; existing_id: string | null }>(
              '/api/chem/analyse/', { method: 'POST', body: JSON.stringify({ structure: molfile }) },
            )
            if (info.existing_id) {
              setCompound(await api<Compound>(`/api/compounds/${info.existing_id}/`))
              setStep(1)
            } else {
              setDraft((d) => ({ ...d, structure: molfile, formula: info.formula }))
            }
          } catch (e) {
            setError(errorText(e))
          }
        }}
      />
    </Stack>
  )
}
