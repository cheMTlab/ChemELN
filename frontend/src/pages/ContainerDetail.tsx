import {
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Image,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  Timeline,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { type Container, type ContainerEvent, type Location, type Page, UNITS } from '../api/types'
import Hazards from '../components/Hazards'
import { formatAmount } from '../components/context'

const errorText = (e: unknown) =>
  e instanceof ApiError ? JSON.stringify(e.body) : 'Something went wrong'

export default function ContainerDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const container = useQuery({
    queryKey: ['container', id],
    queryFn: () => api<Container>(`/api/containers/${id}/`),
  })
  const events = useQuery({
    queryKey: ['container-events', id],
    queryFn: () => api<ContainerEvent[]>(`/api/containers/${id}/events/`),
  })
  const [useAmount, setUseAmount] = useState<number | string>('')
  const [useUnit, setUseUnit] = useState<string | null>(null)
  const [locationSearch, setLocationSearch] = useState('')
  const locations = useQuery({
    queryKey: ['locations', locationSearch],
    queryFn: () => api<Page<Location>>(`/api/locations/?q=${encodeURIComponent(locationSearch)}`),
  })

  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: object }) =>
      api<Container>(`/api/containers/${id}/${path}/`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      qc.setQueryData(['container', id], data)
      qc.invalidateQueries({ queryKey: ['container-events', id] })
      qc.invalidateQueries({ queryKey: ['containers'] })
      setUseAmount('')
    },
  })

  const c = container.data
  if (!c) return null
  const comp = c.compound_detail

  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={3}>{comp.name}</Title>
          <Text c="dimmed">
            {c.barcode} · {comp.cas && `CAS ${comp.cas} · `}{comp.formula}
          </Text>
        </div>
        <Button variant="default"
          onClick={() => window.open(`/api/containers/labels/?ids=${c.id}&layout=roll-62x29`)}>
          Print label
        </Button>
      </Group>

      {c.storage_warning && <Alert color="orange">{c.storage_warning}</Alert>}
      {c.is_expired && <Alert color="red">This container expired on {c.expiry_date}.</Alert>}
      {act.isError && <Alert color="red">{errorText(act.error)}</Alert>}

      <Grid>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card withBorder>
            <Group align="flex-start" wrap="nowrap">
              {comp.smiles && (
                <Image src={`/api/compounds/${comp.id}/depict/`} w={220} h={150} fit="contain"
                  alt={comp.name} />
              )}
              <Table>
                <Table.Tbody>
                  <Row label="Amount" value={`${formatAmount(c.amount, c.unit)} of ${formatAmount(c.initial_amount, c.unit)}`} />
                  <Row label="Status" value={<Badge variant="light">{c.status}</Badge>} />
                  <Row label="Location" value={c.location_path || '—'} />
                  <Row label="Group / owner" value={`${c.group_name} / ${c.owner_name || '—'}`} />
                  <Row label="Supplier" value={[c.supplier, c.catalog_number].filter(Boolean).join(' · ') || '—'} />
                  <Row label="Lot" value={c.lot_number || '—'} />
                  <Row label="Purity" value={c.purity ? `${Number(c.purity)} %` : '—'} />
                  <Row label="Received / opened" value={`${c.received_date} / ${c.opened_date ?? '—'}`} />
                  <Row label="Expiry" value={c.expiry_date ?? '—'} />
                  <Row label="Hazards" value={<Hazards pictograms={comp.ghs_pictograms} signalWord={comp.signal_word} />} />
                </Table.Tbody>
              </Table>
            </Group>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack>
            <Card withBorder>
              <Text fw={600} mb="xs">Use</Text>
              <Group align="flex-end" wrap="nowrap">
                <NumberInput label="Amount" value={useAmount} onChange={setUseAmount} min={0}
                  decimalScale={4} flex={1} />
                <Select label="Unit" data={[...UNITS]} value={useUnit ?? c.unit}
                  onChange={setUseUnit} w={90} />
              </Group>
              <Button mt="sm" fullWidth disabled={!useAmount} loading={act.isPending}
                onClick={() => act.mutate({
                  path: 'use', body: { amount: String(useAmount), unit: useUnit ?? c.unit },
                })}>
                Record use
              </Button>
            </Card>

            <Card withBorder>
              <Text fw={600} mb="xs">Move</Text>
              <Select
                searchable
                placeholder="Search locations or scan a location barcode"
                onSearchChange={setLocationSearch}
                data={(locations.data?.results ?? []).map((l) => ({ value: l.id, label: l.path }))}
                onChange={(loc) => loc && act.mutate({ path: 'move', body: { location: loc } })}
              />
            </Card>

            <Card withBorder>
              <Text fw={600} mb="xs">Status</Text>
              <Group gap="xs">
                {(['available', 'borrowed', 'missing', 'empty', 'disposed'] as const).map((s) => (
                  <Button key={s} size="xs" variant={c.status === s ? 'filled' : 'default'}
                    onClick={() => act.mutate({ path: 'status', body: { status: s } })}>
                    {s}
                  </Button>
                ))}
              </Group>
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>

      <Card withBorder>
        <Text fw={600} mb="sm">History</Text>
        <Timeline bulletSize={12} lineWidth={2}>
          {events.data?.map((e) => (
            <Timeline.Item key={e.id} title={`${e.kind}${e.amount_change ? ` (${Number(e.amount_change)} ${c.unit})` : ''}`}>
              <Text size="xs" c="dimmed">
                {new Date(e.created_at).toLocaleString()} · {e.user_name}
                {e.to_path && ` · → ${e.to_path}`}
                {e.note && ` · ${e.note}`}
              </Text>
            </Timeline.Item>
          ))}
        </Timeline>
      </Card>
    </Stack>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Table.Tr>
      <Table.Td c="dimmed" w={150}>{label}</Table.Td>
      <Table.Td>{value}</Table.Td>
    </Table.Tr>
  )
}
