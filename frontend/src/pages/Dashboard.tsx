import { Anchor, Badge, Card, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { AlertKey, Alerts } from '../api/types'
import { useApp } from '../components/context'

const ALERTS: { key: AlertKey; label: string; color: string; hint: string }[] = [
  { key: 'expired', label: 'Expired', color: 'red', hint: 'Past their expiry date' },
  { key: 'peroxide_retest', label: 'Peroxide re-test', color: 'red',
    hint: 'Peroxide formers opened more than 6 months ago' },
  { key: 'storage_conflicts', label: 'Storage conflicts', color: 'orange',
    hint: 'Stored where their storage class is not allowed' },
  { key: 'expiring_soon', label: 'Expiring within 30 days', color: 'yellow', hint: '' },
  { key: 'low_stock', label: 'Low stock', color: 'blue', hint: '10 % or less remaining' },
]

export default function Dashboard() {
  const { me } = useApp()
  const alerts = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api<Alerts>('/api/containers/alerts/'),
  })

  return (
    <Stack>
      <Title order={3}>Welcome{me ? `, ${me.first_name || me.email}` : ''}</Title>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {ALERTS.map(({ key, label, color, hint }) => {
          const a = alerts.data?.[key]
          return (
            <Card withBorder key={key}>
              <Group justify="space-between">
                <Text fw={600}>{label}</Text>
                <Badge color={a?.count ? color : 'gray'} size="lg">
                  {a?.count ?? '…'}
                </Badge>
              </Group>
              {hint && <Text size="xs" c="dimmed">{hint}</Text>}
              <Stack gap={2} mt="xs">
                {a?.items.slice(0, 5).map((c) => (
                  <Anchor key={c.id} component={Link} to={`/containers/${c.id}`} size="sm">
                    {c.compound_detail.name} · {c.barcode}
                  </Anchor>
                ))}
              </Stack>
            </Card>
          )
        })}
        <Card withBorder>
          <Text fw={600}>Your groups</Text>
          {me?.memberships.length ? (
            me.memberships.map((m) => (
              <Group key={m.group_id} justify="space-between" mt="xs">
                <Text size="sm">{m.group_name}</Text>
                <Badge variant="light">{m.role}</Badge>
              </Group>
            ))
          ) : (
            <Text size="sm" c="dimmed" mt="xs">
              You are not in a research group yet. Ask your PI or administrator to add you.
            </Text>
          )}
        </Card>
      </SimpleGrid>
    </Stack>
  )
}
