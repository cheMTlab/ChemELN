import { AppShell, Badge, Burger, Button, Group, NavLink, ScrollArea, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink as RouterLink, Outlet, useLocation } from 'react-router-dom'

import { logout } from '../api/auth'
import { api, type InstanceConfig, type Me } from '../api/client'

const SECTIONS: { title: string; links: { to: string; label: string; exact?: boolean }[] }[] = [
  { title: '', links: [{ to: '/', label: 'Dashboard', exact: true }] },
  {
    title: 'Notebook',
    links: [
      { to: '/eln', label: 'Experiments' },
      { to: '/screening', label: 'Reaction screening' },
    ],
  },
  {
    title: 'Biology',
    links: [
      { to: '/bio', label: 'Plasmids, strains, oligos' },
      { to: '/plates', label: 'Well plates & assays' },
    ],
  },
  {
    title: 'Chemicals',
    links: [
      { to: '/inventory', label: 'Inventory' },
      { to: '/inventory/new', label: 'Add container', exact: true },
      { to: '/orders', label: 'Orders' },
      { to: '/locations', label: 'Locations' },
      { to: '/import', label: 'Import' },
    ],
  },
  { title: 'Lab', links: [{ to: '/people', label: 'People & permissions' }] },
]

export default function Layout({ config }: { config: InstanceConfig }) {
  const [opened, { toggle, close }] = useDisclosure()
  const queryClient = useQueryClient()
  const { pathname } = useLocation()
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/api/me/') })
  const orders = useQuery({
    queryKey: ['orders', 'summary'],
    queryFn: () => api<{ to_approve: number }>('/api/orders/summary/'),
    refetchInterval: 120_000,
  })

  async function onLogout() {
    await logout()
    queryClient.clear()
    window.location.assign('/login')
  }

  const isActive = (to: string, exact?: boolean) =>
    exact ? pathname === to : pathname === to || (pathname.startsWith(to + '/') && to !== '/inventory') || (to === '/inventory' && (pathname === '/inventory' || pathname.startsWith('/containers')))

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
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
        <ScrollArea>
          {SECTIONS.map((s) => (
            <div key={s.title}>
              {s.title && (
                <Text size="xs" fw={700} c="dimmed" tt="uppercase" mt="sm" mb={2} px="xs">
                  {s.title}
                </Text>
              )}
              {s.links.map((l) => (
                <NavLink
                  key={l.to}
                  component={RouterLink}
                  to={l.to}
                  label={l.label}
                  active={isActive(l.to, l.exact)}
                  onClick={close}
                  rightSection={
                    l.to === '/orders' && orders.data?.to_approve ? (
                      <Badge size="xs" color="yellow" circle>
                        {orders.data.to_approve}
                      </Badge>
                    ) : null
                  }
                />
              ))}
            </div>
          ))}
          {me.data?.is_staff && <NavLink href="/admin/" label="Django administration" target="_blank" mt="sm" />}
        </ScrollArea>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet context={{ config, me: me.data }} />
      </AppShell.Main>
    </AppShell>
  )
}
