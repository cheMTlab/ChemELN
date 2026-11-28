import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Drawer,
  Grid,
  Group,
  NumberInput,
  Progress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Timeline,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api, patch, post } from '../../api/client'
import type { CostCentre, Order, OrderEvent, Supplier } from '../../api/modules'
import { type Page, UNITS } from '../../api/types'
import { can, hasRole, isPiAnywhere, useApp } from '../../components/context'
import {
  CompoundPicker,
  defaultGroup,
  Field,
  fmtDate,
  fmtDateTime,
  GroupPicker,
  LocationPicker,
  notifyError,
  notifyOk,
  StatusBadge,
} from '../../components/pickers'

const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Waiting for approval',
  approved: 'Approved',
  rejected: 'Rejected',
  ordered: 'Ordered',
  partial: 'Partially received',
  received: 'Received',
  cancelled: 'Cancelled',
}

const VIEWS: Record<string, string> = {
  open: 'status=open',
  approve: 'to_approve=1',
  receive: 'status=ordered,partial',
  mine: 'mine=1',
  history: 'status=received,cancelled,rejected',
}

const money = (v: string | null | undefined, cur = '') =>
  v === null || v === undefined ? '' : `${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })} ${cur}`

export default function Orders() {
  const { me } = useApp()
  const [view, setView] = useState('open')
  const [q, setQ] = useState('')
  const [creating, setCreating] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const summary = useQuery({
    queryKey: ['orders', 'summary'],
    queryFn: () =>
      api<{ to_approve: number; to_receive: number; open_spend: string | null; by_status: Record<string, number> }>(
        '/api/orders/summary/',
      ),
  })
  const orders = useQuery({
    queryKey: ['orders', view, q],
    queryFn: () => api<Page<Order>>(`/api/orders/?${VIEWS[view]}&q=${encodeURIComponent(q)}`),
  })
  const approver = isPiAnywhere(me) || can(me, 'order_approver')
  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reagent orders</Title>
        <Button onClick={() => setCreating(true)}>New order</Button>
      </Group>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Stat label="Open orders" value={(summary.data?.by_status.submitted ?? 0) + (summary.data?.by_status.approved ?? 0) + (summary.data?.by_status.ordered ?? 0) + (summary.data?.by_status.partial ?? 0) + (summary.data?.by_status.draft ?? 0)} />
        <Stat label="Waiting for your approval" value={summary.data?.to_approve ?? 0} color={summary.data?.to_approve ? 'yellow' : undefined} />
        <Stat label="Expected deliveries" value={summary.data?.to_receive ?? 0} />
        <Stat label="Committed, not yet received" value={money(summary.data?.open_spend ?? '0')} />
      </SimpleGrid>
      <Tabs defaultValue="orders">
        <Tabs.List>
          <Tabs.Tab value="orders">Orders</Tabs.Tab>
          <Tabs.Tab value="budgets">Budgets</Tabs.Tab>
          <Tabs.Tab value="suppliers">Suppliers</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="orders" pt="md">
          <Group mb="sm">
            <SegmentedControl
              value={view}
              onChange={setView}
              data={[
                { value: 'open', label: 'Open' },
                ...(approver ? [{ value: 'approve', label: 'To approve' }] : []),
                { value: 'receive', label: 'To receive' },
                { value: 'mine', label: 'Mine' },
                { value: 'history', label: 'History' },
              ]}
            />
            <TextInput placeholder="Order no., item, CAS, cat. no., PO" value={q} onChange={(e) => setQ(e.target.value)} w={300} />
          </Group>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Order</Table.Th>
                <Table.Th>Item</Table.Th>
                <Table.Th>Quantity</Table.Th>
                <Table.Th>Supplier</Table.Th>
                <Table.Th>Total</Table.Th>
                <Table.Th>Group / requester</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {orders.data?.results.map((o) => (
                <Table.Tr key={o.id} onClick={() => setOpenId(o.id)} style={{ cursor: 'pointer' }}>
                  <Table.Td>
                    <Text fw={500}>{o.number}</Text>
                    <Text size="xs" c="dimmed">
                      {fmtDate(o.created_at)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {o.display_name} {o.urgency === 'urgent' && <Badge color="red" size="xs">urgent</Badge>}
                    <Text size="xs" c="dimmed">
                      {o.cas} {o.catalog_number && `· ${o.catalog_number}`}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {o.quantity} × {Number(o.package_amount)} {o.package_unit}
                  </Table.Td>
                  <Table.Td>{o.supplier_display}</Table.Td>
                  <Table.Td>{money(o.total_price, o.currency)}</Table.Td>
                  <Table.Td>
                    {o.group_name}
                    <Text size="xs" c="dimmed">
                      {o.requested_by_name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={o.status} label={STATUS_LABEL[o.status]} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {orders.data?.results.length === 0 && <Text c="dimmed">No orders here.</Text>}
        </Tabs.Panel>
        <Tabs.Panel value="budgets" pt="md">
          <Budgets />
        </Tabs.Panel>
        <Tabs.Panel value="suppliers" pt="md">
          <Suppliers />
        </Tabs.Panel>
      </Tabs>
      <Drawer opened={creating} onClose={() => setCreating(false)} title="New order" position="right" size="lg">
        {creating && <OrderForm onDone={(id) => { setCreating(false); setOpenId(id) }} />}
      </Drawer>
      <Drawer opened={!!openId} onClose={() => setOpenId(null)} position="right" size="xl" title="Order">
        {openId && <OrderDetail id={openId} />}
      </Drawer>
    </Stack>
  )
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="xl" fw={700} c={color}>
        {value}
      </Text>
    </Card>
  )
}

function OrderForm({ onDone, initial }: { onDone: (id: string) => void; initial?: Order }) {
  const { me } = useApp()
  const qc = useQueryClient()
  const [mode, setMode] = useState(initial?.compound || !initial ? 'compound' : 'free')
  const [v, setV] = useState({
    group: initial?.group ?? defaultGroup(me),
    compound: initial?.compound ?? null,
    item_name: initial?.item_name ?? '',
    cas: initial?.cas ?? '',
    grade: initial?.grade ?? '',
    supplier: initial?.supplier ?? null,
    supplier_name: initial?.supplier_name ?? '',
    catalog_number: initial?.catalog_number ?? '',
    package_amount: initial ? Number(initial.package_amount) : 100,
    package_unit: initial?.package_unit ?? 'g',
    quantity: initial?.quantity ?? 1,
    unit_price: initial?.unit_price ? Number(initial.unit_price) : ('' as number | ''),
    cost_centre: initial?.cost_centre ?? null,
    urgency: initial?.urgency ?? 'normal',
    justification: initial?.justification ?? '',
    delivery_location: initial?.delivery_location ?? null,
  })
  const suppliers = useQuery({ queryKey: ['suppliers'], queryFn: () => api<Page<Supplier>>('/api/suppliers/') })
  const budgets = useQuery({
    queryKey: ['cost-centres', v.group],
    queryFn: () => api<Page<CostCentre>>(`/api/cost-centres/?group=${v.group}`),
    enabled: !!v.group,
  })
  const save = useMutation({
    mutationFn: (submit: boolean) => {
      const body = {
        ...v,
        compound: mode === 'compound' ? v.compound : null,
        unit_price: v.unit_price === '' ? null : v.unit_price,
      }
      const req = initial ? patch<Order>(`/api/orders/${initial.id}/`, body) : post<Order>('/api/orders/', body)
      return req.then((o) => (submit ? post<Order>(`/api/orders/${o.id}/transition/`, { action: 'submit' }) : o))
    },
    onSuccess: (o) => {
      notifyOk(`${o.number}: ${STATUS_LABEL[o.status]}`)
      qc.invalidateQueries({ queryKey: ['orders'] })
      onDone(o.id)
    },
    onError: notifyError,
  })
  const total = v.unit_price === '' ? null : Number(v.unit_price) * v.quantity
  const cc = budgets.data?.results.find((b) => b.id === v.cost_centre)
  return (
    <Stack>
      <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g, cost_centre: null })} />
      <SegmentedControl
        value={mode}
        onChange={setMode}
        data={[
          { value: 'compound', label: 'Compound in the database' },
          { value: 'free', label: 'Other item (free text)' },
        ]}
      />
      {mode === 'compound' ? (
        <CompoundPicker label="Compound" value={v.compound} onChange={(id) => setV({ ...v, compound: id })} />
      ) : (
        <Group grow>
          <TextInput label="Item" required value={v.item_name} onChange={(e) => setV({ ...v, item_name: e.target.value })} />
          <TextInput label="CAS number" value={v.cas} onChange={(e) => setV({ ...v, cas: e.target.value })} />
        </Group>
      )}
      <Group grow>
        <Select
          label="Supplier"
          searchable
          clearable
          data={(suppliers.data?.results ?? []).map((s) => ({ value: s.id, label: s.name }))}
          value={v.supplier}
          onChange={(s) => setV({ ...v, supplier: s })}
        />
        {!v.supplier && (
          <TextInput label="…or supplier name" value={v.supplier_name} onChange={(e) => setV({ ...v, supplier_name: e.target.value })} />
        )}
      </Group>
      <Group grow>
        <TextInput label="Catalogue number" value={v.catalog_number} onChange={(e) => setV({ ...v, catalog_number: e.target.value })} />
        <TextInput label="Grade / purity" value={v.grade} onChange={(e) => setV({ ...v, grade: e.target.value })} />
      </Group>
      <Group grow align="end">
        <NumberInput label="Package size" min={0} value={v.package_amount} onChange={(x) => setV({ ...v, package_amount: Number(x) })} />
        <Select label="Unit" data={[...UNITS]} value={v.package_unit} onChange={(u) => u && setV({ ...v, package_unit: u })} />
        <NumberInput label="Packages" min={1} value={v.quantity} onChange={(x) => setV({ ...v, quantity: Number(x) || 1 })} />
        <NumberInput label="Price per package" min={0} decimalScale={2} value={v.unit_price} onChange={(x) => setV({ ...v, unit_price: x === '' ? '' : Number(x) })} />
      </Group>
      {total !== null && <Text size="sm">Total: <b>{total.toFixed(2)}</b></Text>}
      <Select
        label="Charge to (cost centre)"
        clearable
        data={(budgets.data?.results ?? []).filter((b) => b.is_active).map((b) => ({
          value: b.id,
          label: `${b.code} ${b.name}${b.remaining !== null ? ` · ${money(b.remaining, b.currency)} left` : ''}`,
        }))}
        value={v.cost_centre}
        onChange={(c) => setV({ ...v, cost_centre: c })}
      />
      {cc && cc.remaining !== null && total !== null && total > Number(cc.remaining) && (
        <Alert color="orange">This order exceeds the remaining budget; the approver must override.</Alert>
      )}
      <LocationPicker label="Deliver to (default storage)" value={v.delivery_location} onChange={(l) => setV({ ...v, delivery_location: l })} />
      <Checkbox label="Urgent" checked={v.urgency === 'urgent'} onChange={(e) => setV({ ...v, urgency: e.currentTarget.checked ? 'urgent' : 'normal' })} />
      <Textarea label="Justification / notes for the approver" autosize minRows={2} value={v.justification} onChange={(e) => setV({ ...v, justification: e.target.value })} />
      <Group>
        <Button variant="default" onClick={() => save.mutate(false)} loading={save.isPending}>
          Save draft
        </Button>
        <Button onClick={() => save.mutate(true)} loading={save.isPending}>
          Submit for approval
        </Button>
      </Group>
    </Stack>
  )
}

function OrderDetail({ id }: { id: string }) {
  const qc = useQueryClient()
  const { me } = useApp()
  const order = useQuery({ queryKey: ['order', id], queryFn: () => api<Order>(`/api/orders/${id}/`) })
  const events = useQuery({ queryKey: ['order-events', id], queryFn: () => api<OrderEvent[]>(`/api/orders/${id}/events/`) })
  const [note, setNote] = useState('')
  const [po, setPo] = useState('')
  const [expected, setExpected] = useState('')
  const [override, setOverride] = useState(false)
  const [editing, setEditing] = useState(false)
  const [recv, setRecv] = useState({ quantity: 1, location: null as string | null, lot_number: '', expiry_date: '' })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['order', id] })
    qc.invalidateQueries({ queryKey: ['order-events', id] })
    qc.invalidateQueries({ queryKey: ['orders'] })
  }
  const act = useMutation({
    mutationFn: (action: string) =>
      post<Order>(`/api/orders/${id}/transition/`, {
        action,
        note,
        po_number: po,
        expected_date: expected || null,
        override_budget: override,
      }),
    onSuccess: (o) => {
      notifyOk(`${o.number}: ${STATUS_LABEL[o.status]}`)
      setNote('')
      refresh()
    },
    onError: notifyError,
  })
  const receive = useMutation({
    mutationFn: () => post<{ barcode: string }[]>(`/api/orders/${id}/receive/`, { ...recv, expiry_date: recv.expiry_date || null }),
    onSuccess: (cs) => {
      notifyOk(`Booked in: ${cs.map((c) => c.barcode).join(', ')}`)
      refresh()
      qc.invalidateQueries({ queryKey: ['containers'] })
    },
    onError: notifyError,
  })
  const linkCompound = useMutation({
    mutationFn: (compound: string | null) => patch(`/api/orders/${id}/`, { compound }),
    onSuccess: refresh,
    onError: notifyError,
  })
  const o = order.data
  if (!o) return null
  if (editing) return <OrderForm initial={o} onDone={() => { setEditing(false); refresh() }} />
  const a = o.allowed_actions
  const steps = ['draft', 'submitted', 'approved', 'ordered', 'received']
  const stepIndex = o.status === 'partial' ? 3.5 : steps.indexOf(o.status)
  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={3}>{o.number}</Title>
          <Text>{o.display_name}</Text>
        </div>
        <StatusBadge status={o.status} label={STATUS_LABEL[o.status]} />
      </Group>
      {stepIndex >= 0 && <Progress value={(stepIndex / 4) * 100} />}
      {o.rejection_reason && <Alert color="red" title="Rejected">{o.rejection_reason}</Alert>}
      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Stack gap={4}>
            <Field label="Group">{o.group_name}</Field>
            <Field label="Requested by">{o.requested_by_name}</Field>
            <Field label="CAS">{o.cas}</Field>
            <Field label="Supplier">{o.supplier_display}</Field>
            <Field label="Catalogue no.">{o.catalog_number}</Field>
            <Field label="Grade">{o.grade}</Field>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Stack gap={4}>
            <Field label="Quantity">{o.quantity} × {Number(o.package_amount)} {o.package_unit}</Field>
            <Field label="Price">{money(o.unit_price, o.currency)} each · total {money(o.total_price, o.currency)}</Field>
            <Field label="Cost centre">{o.cost_centre_code}</Field>
            <Field label="Approved by">{o.decided_by_name && `${o.decided_by_name}, ${fmtDate(o.decided_at)}`}</Field>
            <Field label="PO number">{o.po_number}</Field>
            <Field label="Expected">{fmtDate(o.expected_date)}</Field>
            <Field label="Received">{o.received_quantity} / {o.quantity}</Field>
          </Stack>
        </Grid.Col>
      </Grid>
      {o.justification && <Text size="sm" fs="italic">“{o.justification}”</Text>}
      {o.container_barcodes.length > 0 && (
        <Group gap={6}>
          <Text size="sm">Containers:</Text>
          {o.container_barcodes.map((b) => (
            <Anchor key={b} component={Link} to={`/inventory?q=${b}`} size="sm">
              {b}
            </Anchor>
          ))}
        </Group>
      )}
      <Divider label="Next step" />
      {(o.status === 'draft' || o.status === 'rejected') && (o.requested_by_name === me?.display_name || hasRole(me, o.group, 'pi')) && (
        <Button variant="default" onClick={() => setEditing(true)}>Edit order</Button>
      )}
      {a.some((x) => ['approve', 'reject', 'cancel', 'submit'].includes(x)) && (
        <Textarea label="Note (required for rejection)" value={note} onChange={(e) => setNote(e.target.value)} autosize />
      )}
      {a.includes('approve') && (
        <Checkbox label="Approve even if over budget" checked={override} onChange={(e) => setOverride(e.currentTarget.checked)} />
      )}
      {a.includes('place') && (
        <Group grow>
          <TextInput label="Purchase order number" value={po} onChange={(e) => setPo(e.target.value)} />
          <TextInput label="Expected delivery" type="date" value={expected} onChange={(e) => setExpected(e.target.value)} />
        </Group>
      )}
      <Group>
        {a.includes('submit') && <Button onClick={() => act.mutate('submit')}>Submit for approval</Button>}
        {a.includes('approve') && <Button color="teal" onClick={() => act.mutate('approve')}>Approve</Button>}
        {a.includes('reject') && <Button color="red" variant="light" onClick={() => act.mutate('reject')}>Reject</Button>}
        {a.includes('place') && <Button onClick={() => act.mutate('place')}>Mark as ordered</Button>}
        {a.includes('cancel') && <Button color="gray" variant="subtle" onClick={() => act.mutate('cancel')}>Cancel order</Button>}
      </Group>
      {a.includes('receive') && (
        <Card withBorder>
          <Stack>
            <Text fw={600}>Receive delivery → inventory</Text>
            {!o.compound ? (
              <>
                <Alert color="yellow">Link this item to a compound so the bottles can be created.</Alert>
                <CompoundPicker label="Compound" value={null} onChange={(c) => c && linkCompound.mutate(c)} />
              </>
            ) : (
              <>
                <Group grow>
                  <NumberInput label="Packages received" min={1} max={o.quantity - o.received_quantity} value={recv.quantity} onChange={(x) => setRecv({ ...recv, quantity: Number(x) || 1 })} />
                  <TextInput label="Lot number" value={recv.lot_number} onChange={(e) => setRecv({ ...recv, lot_number: e.target.value })} />
                  <TextInput label="Expiry date" type="date" value={recv.expiry_date} onChange={(e) => setRecv({ ...recv, expiry_date: e.target.value })} />
                </Group>
                <LocationPicker label="Store in" value={recv.location} onChange={(l) => setRecv({ ...recv, location: l })} />
                <Button onClick={() => receive.mutate()} loading={receive.isPending}>
                  Book in & create labelled containers
                </Button>
              </>
            )}
          </Stack>
        </Card>
      )}
      <Divider label="History" />
      <Timeline bulletSize={14} lineWidth={2}>
        <Timeline.Item title="Created">
          <Text size="xs" c="dimmed">{fmtDateTime(o.created_at)}</Text>
        </Timeline.Item>
        {events.data?.map((e) => (
          <Timeline.Item key={e.id} title={STATUS_LABEL[e.to_status] ?? e.to_status}>
            <Text size="xs" c="dimmed">
              {e.user_name} · {fmtDateTime(e.created_at)}
            </Text>
            {e.note && <Text size="sm">{e.note}</Text>}
          </Timeline.Item>
        ))}
      </Timeline>
    </Stack>
  )
}

function Budgets() {
  const { me } = useApp()
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['cost-centres'], queryFn: () => api<Page<CostCentre>>('/api/cost-centres/') })
  const [v, setV] = useState({ group: defaultGroup(me), code: '', name: '', budget: '' as number | '', valid_until: '' })
  const add = useMutation({
    mutationFn: () => post('/api/cost-centres/', { ...v, budget: v.budget === '' ? null : v.budget, valid_until: v.valid_until || null }),
    onSuccess: () => {
      setV({ ...v, code: '', name: '', budget: '' })
      qc.invalidateQueries({ queryKey: ['cost-centres'] })
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Cost centre</Table.Th>
            <Table.Th>Group</Table.Th>
            <Table.Th>Budget</Table.Th>
            <Table.Th w="30%">Used</Table.Th>
            <Table.Th>Remaining</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {list.data?.results.map((b) => {
            const pct = b.budget ? (100 * Number(b.committed)) / Number(b.budget) : 0
            return (
              <Table.Tr key={b.id}>
                <Table.Td>
                  <b>{b.code}</b> {b.name}
                  {b.valid_until && <Text size="xs" c="dimmed">until {fmtDate(b.valid_until)}</Text>}
                </Table.Td>
                <Table.Td>{b.group_name}</Table.Td>
                <Table.Td>{money(b.budget, b.currency) || 'no limit'}</Table.Td>
                <Table.Td>
                  {b.budget && <Progress value={Math.min(100, pct)} color={pct > 100 ? 'red' : pct > 80 ? 'orange' : 'blue'} />}
                  <Text size="xs">{money(b.committed, b.currency)}</Text>
                </Table.Td>
                <Table.Td c={b.remaining !== null && Number(b.remaining) < 0 ? 'red' : undefined}>{money(b.remaining, b.currency)}</Table.Td>
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
      {isPiAnywhere(me) && (
        <Card withBorder>
          <Text fw={600} mb="xs">New cost centre (PIs)</Text>
          <Group align="end">
            <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} w={200} />
            <TextInput label="Code" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} w={120} />
            <TextInput label="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
            <NumberInput label="Budget" value={v.budget} onChange={(x) => setV({ ...v, budget: x === '' ? '' : Number(x) })} w={140} />
            <TextInput label="Valid until" type="date" value={v.valid_until} onChange={(e) => setV({ ...v, valid_until: e.target.value })} />
            <Button onClick={() => add.mutate()} disabled={!v.code || !v.name}>Add</Button>
          </Group>
        </Card>
      )}
    </Stack>
  )
}

function Suppliers() {
  const { me } = useApp()
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['suppliers'], queryFn: () => api<Page<Supplier>>('/api/suppliers/') })
  const [v, setV] = useState({ name: '', website: '', customer_number: '', contact_email: '' })
  const add = useMutation({
    mutationFn: () => post('/api/suppliers/', v),
    onSuccess: () => {
      setV({ name: '', website: '', customer_number: '', contact_email: '' })
      qc.invalidateQueries({ queryKey: ['suppliers'] })
    },
    onError: notifyError,
  })
  const canEdit = can(me, 'purchasing') || isPiAnywhere(me)
  return (
    <Stack>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Supplier</Table.Th>
            <Table.Th>Customer no.</Table.Th>
            <Table.Th>Contact</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {list.data?.results.map((s) => (
            <Table.Tr key={s.id}>
              <Table.Td>
                {s.website ? <Anchor href={s.website} target="_blank">{s.name}</Anchor> : s.name}
              </Table.Td>
              <Table.Td>{s.customer_number}</Table.Td>
              <Table.Td>{s.contact_email}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {canEdit && (
        <Group align="end">
          <TextInput label="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
          <TextInput label="Website" value={v.website} onChange={(e) => setV({ ...v, website: e.target.value })} />
          <TextInput label="Customer no." value={v.customer_number} onChange={(e) => setV({ ...v, customer_number: e.target.value })} />
          <TextInput label="Email" value={v.contact_email} onChange={(e) => setV({ ...v, contact_email: e.target.value })} />
          <Button onClick={() => add.mutate()} disabled={!v.name}>Add supplier</Button>
        </Group>
      )}
    </Stack>
  )
}
