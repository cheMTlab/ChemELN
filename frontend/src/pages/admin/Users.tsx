import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Drawer,
  Group,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, del, patch, post, type Role } from '../../api/client'
import type { Group as ResearchGroup, Member, UserAdmin } from '../../api/modules'
import type { Page } from '../../api/types'
import { can, hasRole, useApp } from '../../components/context'
import { fmtDateTime, notifyError, notifyOk } from '../../components/pickers'

const ROLES: { value: Role; label: string }[] = [
  { value: 'admin', label: 'Group admin' },
  { value: 'pi', label: 'PI' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer (read-only)' },
]

export default function Users() {
  const { me } = useApp()
  const manager = can(me, 'user_manager')
  return (
    <Stack>
      <Title order={2}>People & permissions</Title>
      <Text c="dimmed" size="sm">
        Two layers: a <b>role in each research group</b> (admin › PI › member › viewer) decides
        what someone can do with that group's notebooks, inventory, orders and bio records.
        <b> Instance capabilities</b> add powers across all groups (purchasing, approvals, safety).
      </Text>
      <Tabs key={String(manager)} defaultValue={manager ? 'users' : 'groups'}>
        <Tabs.List>
          {manager && <Tabs.Tab value="users">Users</Tabs.Tab>}
          <Tabs.Tab value="groups">Groups & members</Tabs.Tab>
          <Tabs.Tab value="matrix">Permission matrix</Tabs.Tab>
        </Tabs.List>
        {manager && (
          <Tabs.Panel value="users" pt="md">
            <UserList />
          </Tabs.Panel>
        )}
        <Tabs.Panel value="groups" pt="md">
          <Groups />
        </Tabs.Panel>
        <Tabs.Panel value="matrix" pt="md">
          <Matrix />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}

function UserList() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [edit, setEdit] = useState<UserAdmin | 'new' | null>(null)
  const users = useQuery({
    queryKey: ['users', q],
    queryFn: () => api<Page<UserAdmin>>(`/api/users/?q=${encodeURIComponent(q)}`),
  })
  const caps = useQuery({
    queryKey: ['capabilities'],
    queryFn: () => api<{ value: string; label: string }[]>('/api/capabilities/'),
  })
  const capLabel = (c: string) => caps.data?.find((x) => x.value === c)?.label.split(':')[0] ?? c
  return (
    <Stack>
      <Group>
        <TextInput placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button onClick={() => setEdit('new')}>Add user</Button>
      </Group>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Groups</Table.Th>
            <Table.Th>Capabilities</Table.Th>
            <Table.Th>Last login</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {users.data?.results.map((u) => (
            <Table.Tr key={u.id} onClick={() => setEdit(u)} style={{ cursor: 'pointer' }}>
              <Table.Td>
                <Text fw={500} c={u.is_active ? undefined : 'dimmed'} td={u.is_active ? undefined : 'line-through'}>
                  {u.display_name}
                </Text>
                <Text size="xs" c="dimmed">
                  {u.email} {u.job_title && `· ${u.job_title}`}
                </Text>
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  {u.memberships.map((m) => (
                    <Badge key={m.id} variant="outline" size="sm">
                      {m.group_name}: {m.role}
                    </Badge>
                  ))}
                </Group>
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  {u.is_staff && <Badge color="red">Instance admin</Badge>}
                  {!u.is_staff &&
                    u.capabilities.map((c) => (
                      <Badge key={c} color="grape" variant="light" size="sm">
                        {capLabel(c)}
                      </Badge>
                    ))}
                </Group>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{fmtDateTime(u.last_login) || 'never'}</Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Drawer
        opened={edit !== null}
        onClose={() => setEdit(null)}
        position="right"
        size="md"
        title={edit === 'new' ? 'New user' : 'Edit user'}
      >
        {edit !== null && (
          <UserForm
            key={edit === 'new' ? 'new' : edit.id}
            user={edit === 'new' ? null : edit}
            capabilities={caps.data ?? []}
            onDone={() => {
              setEdit(null)
              qc.invalidateQueries({ queryKey: ['users'] })
            }}
          />
        )}
      </Drawer>
    </Stack>
  )
}

function UserForm({
  user,
  capabilities,
  onDone,
}: {
  user: UserAdmin | null
  capabilities: { value: string; label: string }[]
  onDone: () => void
}) {
  const { me } = useApp()
  const [v, setV] = useState({
    email: user?.email ?? '',
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    initials: user?.initials ?? '',
    job_title: user?.job_title ?? '',
    phone: user?.phone ?? '',
    orcid: user?.orcid ?? '',
    is_active: user?.is_active ?? true,
    is_staff: user?.is_staff ?? false,
    capabilities: (user?.capabilities ?? []) as string[],
    password: '',
  })
  const set = (k: keyof typeof v) => (e: { currentTarget: { value: string } }) =>
    setV({ ...v, [k]: e.currentTarget.value })
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { ...v }
      if (!v.password) delete body.password
      if (!me?.is_staff) delete body.is_staff
      return user ? patch(`/api/users/${user.id}/`, body) : post('/api/users/', body)
    },
    onSuccess: () => {
      notifyOk(user ? 'User updated' : 'User created')
      onDone()
    },
    onError: notifyError,
  })
  return (
    <Stack>
      <TextInput label="Email" required value={v.email} onChange={set('email')} disabled={!!user} />
      <Group grow>
        <TextInput label="First name" value={v.first_name} onChange={set('first_name')} />
        <TextInput label="Last name" value={v.last_name} onChange={set('last_name')} />
      </Group>
      <Group grow>
        <TextInput
          label="Initials"
          description="Notebook code prefix"
          value={v.initials}
          onChange={set('initials')}
          maxLength={6}
        />
        <TextInput label="ORCID" value={v.orcid} onChange={set('orcid')} placeholder="0000-0000-0000-0000" />
      </Group>
      <Group grow>
        <TextInput label="Job title" value={v.job_title} onChange={set('job_title')} />
        <TextInput label="Phone" value={v.phone} onChange={set('phone')} />
      </Group>
      <TextInput
        label={user ? 'New password' : 'Password'}
        description="Leave empty for SSO-only accounts"
        type="password"
        value={v.password}
        onChange={set('password')}
      />
      <Checkbox.Group
        label="Instance capabilities"
        value={v.capabilities}
        onChange={(caps) => setV({ ...v, capabilities: caps })}
      >
        <Stack gap={6} mt={6}>
          {capabilities.map((c) => (
            <Checkbox key={c.value} value={c.value} label={c.label} />
          ))}
        </Stack>
      </Checkbox.Group>
      {me?.is_staff && (
        <Switch
          label="Instance administrator (full access, Django admin)"
          checked={v.is_staff}
          onChange={(e) => setV({ ...v, is_staff: e.currentTarget.checked })}
          color="red"
        />
      )}
      <Switch
        label="Account active"
        checked={v.is_active}
        onChange={(e) => setV({ ...v, is_active: e.currentTarget.checked })}
      />
      <Button onClick={() => save.mutate()} loading={save.isPending}>
        Save
      </Button>
    </Stack>
  )
}

function Groups() {
  const { me } = useApp()
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => api<Page<ResearchGroup>>('/api/groups/') })
  const [selected, setSelected] = useState<string | null>(null)
  const current = selected ?? groups.data?.results[0]?.id ?? null
  return (
    <Stack>
      <Select
        label="Research group"
        data={(groups.data?.results ?? []).map((g) => ({ value: g.id, label: `${g.name} (${g.member_count})` }))}
        value={current}
        onChange={setSelected}
        maw={400}
      />
      {current && (
        <Members groupId={current} canManage={can(me, 'user_manager') || hasRole(me, current, 'pi')} />
      )}
    </Stack>
  )
}

function Members({ groupId, canManage }: { groupId: string; canManage: boolean }) {
  const qc = useQueryClient()
  const key = ['members', groupId]
  const members = useQuery({ queryKey: key, queryFn: () => api<Member[] | Page<Member>>(`/api/groups/${groupId}/members/`) })
  const list = Array.isArray(members.data) ? members.data : (members.data?.results ?? [])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('member')
  const refresh = () => qc.invalidateQueries({ queryKey: key })
  const add = useMutation({
    mutationFn: () => post(`/api/groups/${groupId}/members/`, { user_email: email, role }),
    onSuccess: () => {
      setEmail('')
      refresh()
    },
    onError: notifyError,
  })
  const change = useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) => patch(`/api/groups/${groupId}/members/${id}/`, { role }),
    onSuccess: refresh,
    onError: notifyError,
  })
  const remove = useMutation({
    mutationFn: (id: string) => del(`/api/groups/${groupId}/members/${id}/`),
    onSuccess: refresh,
    onError: notifyError,
  })
  return (
    <Stack>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Person</Table.Th>
            <Table.Th>Role</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {list.map((m) => (
            <Table.Tr key={m.id}>
              <Table.Td>
                {m.user.display_name}
                <Text size="xs" c="dimmed">
                  {m.user.email}
                </Text>
              </Table.Td>
              <Table.Td>
                <Select
                  size="xs"
                  data={ROLES}
                  value={m.role}
                  disabled={!canManage}
                  onChange={(r) => r && change.mutate({ id: m.id, role: r as Role })}
                  w={180}
                />
              </Table.Td>
              <Table.Td>
                {canManage && (
                  <Button size="xs" variant="subtle" color="red" onClick={() => remove.mutate(m.id)}>
                    Remove
                  </Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {canManage ? (
        <Group align="end">
          <TextInput label="Add by email" value={email} onChange={(e) => setEmail(e.target.value)} w={280} />
          <Select label="Role" data={ROLES} value={role} onChange={(r) => r && setRole(r as Role)} w={180} />
          <Button onClick={() => add.mutate()} disabled={!email} loading={add.isPending}>
            Add
          </Button>
        </Group>
      ) : (
        <Alert color="gray">Only the group's PI or admin (or a user manager) can change members.</Alert>
      )}
    </Stack>
  )
}

const MATRIX: [string, string, string, string, string, string][] = [
  ['', 'Viewer', 'Member', 'PI', 'Group admin', 'Instance capability'],
  ['Read notebooks, plates, plasmids, orders of the group', '✓', '✓', '✓', '✓', 'Safety / biosafety officer: all groups'],
  ['Write experiments, campaigns, plates, bio records', '', '✓', '✓', '✓', ''],
  ['Use / move containers of the group', '', '✓', '✓', '✓', 'Inventory manager: any container'],
  ['Request reagent orders', '', '✓', '✓', '✓', ''],
  ['Approve orders, manage budgets', '', '', '✓', '✓', 'Order approver: any group'],
  ['Place orders with suppliers, receive deliveries', '', 'receive', '✓', '✓', 'Purchasing: any group'],
  ['Witness colleagues’ experiments', '', '✓', '✓', '✓', ''],
  ['Manage members', '', '', '✓', '✓ (incl. admins)', 'User manager: all groups and accounts'],
  ['Create sites, buildings, shared rooms; delete records', '', '', '', '', 'Instance admin only'],
]

function Matrix() {
  return (
    <Table withTableBorder withColumnBorders>
      <Table.Thead>
        <Table.Tr>
          {MATRIX[0].map((h, i) => (
            <Table.Th key={i}>{h}</Table.Th>
          ))}
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {MATRIX.slice(1).map((row) => (
          <Table.Tr key={row[0]}>
            {row.map((c, i) => (
              <Table.Td key={i} ta={i > 0 && i < 5 ? 'center' : undefined}>
                <Text size="sm">{c}</Text>
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}
