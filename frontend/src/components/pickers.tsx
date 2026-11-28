/** Shared form widgets: searchable pickers for compounds, containers, locations, groups. */
import { Badge, Group, Image, Select, type SelectProps, Text } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'

import { api, errorText } from '../api/client'
import type { CompoundSummary, Container, Location, Page } from '../api/types'
import { useApp, writableGroups } from './context'

type PickerProps = Omit<SelectProps, 'data' | 'onChange' | 'value' | 'searchValue'> & {
  value: string | null
  onChange: (id: string | null, item?: unknown) => void
}

function useSearch<T>(key: string, url: (q: string) => string, enabled = true) {
  const [search, setSearch] = useState('')
  const [q] = useDebouncedValue(search, 250)
  const query = useQuery({
    queryKey: [key, 'picker', q],
    queryFn: () => api<Page<T> | T[]>(url(q)),
    enabled,
  })
  const items: T[] = Array.isArray(query.data) ? query.data : (query.data?.results ?? [])
  return { search, setSearch, items, loading: query.isFetching }
}

export function CompoundPicker({ value, onChange, ...rest }: PickerProps) {
  const s = useSearch<CompoundSummary>('compounds', (q) => `/api/compounds/?q=${encodeURIComponent(q)}`)
  const [chosen, setChosen] = useState<CompoundSummary | null>(null)
  const items = chosen && !s.items.some((c) => c.id === chosen.id) ? [chosen, ...s.items] : s.items
  return (
    <Select
      searchable
      clearable
      placeholder="Name, CAS or formula"
      nothingFoundMessage={s.loading ? 'Searching…' : 'No compound found'}
      filter={({ options }) => options}
      {...rest}
      data={items.map((c) => ({ value: c.id, label: `${c.name}${c.cas ? ` (${c.cas})` : ''}` }))}
      value={value}
      searchValue={s.search}
      onSearchChange={s.setSearch}
      onChange={(id) => {
        const item = items.find((c) => c.id === id) ?? null
        setChosen(item)
        onChange(id, item)
      }}
    />
  )
}

export function ContainerPicker({ value, onChange, ...rest }: PickerProps) {
  const s = useSearch<Container>(
    'containers',
    (q) => `/api/containers/?status=available&q=${encodeURIComponent(q)}`,
  )
  const [chosen, setChosen] = useState<Container | null>(null)
  const items = chosen && !s.items.some((c) => c.id === chosen.id) ? [chosen, ...s.items] : s.items
  return (
    <Select
      searchable
      clearable
      placeholder="Search bottles by compound, CAS or barcode"
      nothingFoundMessage={s.loading ? 'Searching…' : 'No container found'}
      filter={({ options }) => options}
      {...rest}
      data={items.map((c) => ({
        value: c.id,
        label: `${c.compound_detail.name} · ${c.barcode} · ${Number(c.amount)} ${c.unit}`,
      }))}
      value={value}
      searchValue={s.search}
      onSearchChange={s.setSearch}
      onChange={(id) => {
        const item = items.find((c) => c.id === id) ?? null
        setChosen(item)
        onChange(id, item)
      }}
    />
  )
}

export function LocationPicker({ value, onChange, ...rest }: PickerProps) {
  const s = useSearch<Location>('locations', (q) => `/api/locations/?q=${encodeURIComponent(q)}`)
  return (
    <Select
      searchable
      clearable
      placeholder="Search locations"
      filter={({ options }) => options}
      {...rest}
      data={s.items.map((l) => ({ value: l.id, label: l.path }))}
      value={value}
      searchValue={s.search}
      onSearchChange={s.setSearch}
      onChange={(id) => onChange(id)}
    />
  )
}

/** Group selector limited to groups where the user can write. */
export function GroupPicker({ value, onChange, ...rest }: PickerProps) {
  const { me } = useApp()
  const groups = writableGroups(me)
  return (
    <Select
      label="Group"
      required
      {...rest}
      data={groups.map((g) => ({ value: g.group_id, label: g.group_name }))}
      value={value}
      onChange={(id) => onChange(id)}
    />
  )
}

export function defaultGroup(me: ReturnType<typeof useApp>['me']): string | null {
  return writableGroups(me)[0]?.group_id ?? null
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'gray',
  submitted: 'yellow',
  approved: 'teal',
  rejected: 'red',
  ordered: 'blue',
  partial: 'indigo',
  received: 'green',
  cancelled: 'gray',
  planned: 'gray',
  in_progress: 'blue',
  completed: 'green',
  failed: 'red',
  running: 'blue',
  done: 'green',
  skipped: 'gray',
  design: 'violet',
  archived: 'gray',
  active: 'green',
  on_hold: 'yellow',
}

export function StatusBadge({ status, label }: { status: string; label?: ReactNode }) {
  return (
    <Badge color={STATUS_COLORS[status] ?? 'gray'} variant="light">
      {label ?? status.replace('_', ' ')}
    </Badge>
  )
}

export function StructureThumb({ id, size = 64 }: { id?: string | null; size?: number }) {
  if (!id) return null
  return <Image src={`/api/compounds/${id}/depict/`} w={size} h={size * 0.66} fit="contain" />
}

export function notifyError(e: unknown) {
  notifications.show({ color: 'red', title: 'Not saved', message: errorText(e) })
}

export function notifyOk(message: string) {
  notifications.show({ color: 'green', message })
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Group gap={6} wrap="nowrap" align="baseline">
      <Text size="sm" c="dimmed" w={130} style={{ flexShrink: 0 }}>
        {label}
      </Text>
      <Text size="sm" component="div">
        {children || '—'}
      </Text>
    </Group>
  )
}

export const fmt = (x: number | null | undefined, digits = 3) =>
  x === null || x === undefined || Number.isNaN(x)
    ? ''
    : Number(x).toLocaleString(undefined, { maximumFractionDigits: digits })

export const fmtDate = (s: string | null | undefined) =>
  s ? new Date(s).toLocaleDateString() : ''

export const fmtDateTime = (s: string | null | undefined) =>
  s ? new Date(s).toLocaleString() : ''
