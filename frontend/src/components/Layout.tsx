import { AppShell, Burger, Button, Group, NavLink, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink as RouterLink, Outlet, useLocation } from 'react-router-dom'

import { logout } from '../api/auth'
import { api, type InstanceConfig, type Me } from '../api/client'

const LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/inventory/new', label: 'Add container' },
  { to: '/locations', label: 'Locations' },
  { to: '/import', label: 'Import' },
]

export default function Layout({ config }: { config: InstanceConfig }) {
  const [opened, { toggle, close }] = useDisclosure()
  const queryClient = useQueryClient()
  const { pathname } = useLocation()
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/api/me/') })

  async function onLogout() {
    await logout()
    queryClient.clear()
    window.location.assign('/login')
  }

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4}>{config.instance_name}</Title>
          </Group>
          <Group gap="sm">
            <Text size="sm" visibleFrom="sm">
              {me.data?.display_name}
            </Text>
            <Button size="xs" variant="subtle" onClick={onLogout}>
              Sign out
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            component={RouterLink}
            to={l.to}
            label={l.label}
            active={l.to === '/' ? pathname === '/' : pathname === l.to}
            onClick={close}
          />
        ))}
        {me.data?.is_staff && (
          <NavLink href="/admin/" label="Administration" target="_blank" />
        )}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet context={{ config, me: me.data }} />
      </AppShell.Main>
    </AppShell>
  )
}
