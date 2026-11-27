import { Anchor, Badge, Group, NavLink, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { Location, Page } from '../api/types'

/** One level of the location tree; children load when expanded. */
function Level({ parent }: { parent: string }) {
  const { data } = useQuery({
    queryKey: ['locations', 'children', parent],
    queryFn: () => api<Page<Location>>(`/api/locations/?parent=${parent}`),
  })
  return (
    <>
      {data?.results.map((loc) => <Node key={loc.id} loc={loc} />)}
      {data?.count === 0 && parent === 'root' && (
        <Text c="dimmed" size="sm">
          No locations yet. Administrators create the site, buildings and rooms in Administration;
          group PIs can add cabinets and shelves inside their rooms.
        </Text>
      )}
    </>
  )
}

function Node({ loc }: { loc: Location }) {
  const [open, setOpen] = useState(false)
  return (
    <NavLink
      opened={open}
      onChange={setOpen}
      childrenOffset={20}
      label={
        <Group gap="xs">
          <Text size="sm">{loc.name}</Text>
          <Badge size="xs" variant="light">{loc.kind}</Badge>
          {loc.allowed_storage_classes.length > 0 && (
            <Badge size="xs" color="orange" variant="outline">
              {loc.allowed_storage_classes.join(', ')}
            </Badge>
          )}
        </Group>
      }
      rightSection={
        <Anchor component={Link} to={`/inventory?location=${loc.id}`} size="xs"
          onClick={(e) => e.stopPropagation()}>
          {loc.container_count} containers
        </Anchor>
      }
    >
      {open && <Level parent={loc.id} />}
    </NavLink>
  )
}

export default function Locations() {
  return (
    <Stack maw={800}>
      <Title order={3}>Locations</Title>
      <Level parent="root" />
    </Stack>
  )
}
