import { Badge, Button, Card, Group, Modal, Progress, Select, SimpleGrid, Stack, Text, Textarea, TextInput, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, post } from '../../api/client'
import type { Campaign } from '../../api/modules'
import type { Page } from '../../api/types'
import { useApp } from '../../components/context'
import { defaultGroup, fmtDate, GroupPicker, notifyError, StatusBadge } from '../../components/pickers'

export const EQUIPMENT = [
  { value: 'manual', label: 'Manual (flasks / vials)' },
  { value: 'hte_plate', label: 'HTE plate' },
  { value: 'flow', label: 'Flow reactor' },
  { value: 'robot', label: 'Automated platform' },
]

export default function Campaigns() {
  const [creating, setCreating] = useState(false)
  const list = useQuery({ queryKey: ['campaigns'], queryFn: () => api<Page<Campaign>>('/api/campaigns/') })
  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={2}>Reaction screening & optimization</Title>
          <Text c="dimmed" size="sm">
            Define variables and goals, generate a design, enter results (or import a CSV), and let the
            model show what matters and what to try next.
          </Text>
        </div>
        <Button onClick={() => setCreating(true)}>New campaign</Button>
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {list.data?.results.map((c) => (
          <Card key={c.id} withBorder component={Link} to={`/screening/${c.id}`}>
            <Group justify="space-between" mb={4}>
              <Text fw={600}>{c.title}</Text>
              <StatusBadge status={c.status} />
            </Group>
            <Text size="xs" c="dimmed" mb="xs">
              {c.group_name} · {c.owner_name} · {fmtDate(c.created_at)}
            </Text>
            <Text size="sm" lineClamp={2} mb="xs">
              {c.objective}
            </Text>
            <Group gap={4} mb="xs">
              <Badge variant="outline" size="sm">
                {EQUIPMENT.find((e) => e.value === c.equipment)?.label}
              </Badge>
              {c.variables.map((v) => (
                <Badge key={v.id} variant="light" size="sm">
                  {v.name}
                </Badge>
              ))}
            </Group>
            <Progress value={c.run_count ? (100 * (c.done_count ?? 0)) / c.run_count : 0} size="sm" />
            <Text size="xs" c="dimmed">
              {c.done_count ?? 0} / {c.run_count ?? 0} runs done
            </Text>
          </Card>
        ))}
      </SimpleGrid>
      {list.data?.count === 0 && <Text c="dimmed">No campaigns yet.</Text>}
      <NewCampaign opened={creating} onClose={() => setCreating(false)} />
    </Stack>
  )
}

function NewCampaign({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { me } = useApp()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [v, setV] = useState({ group: defaultGroup(me), title: '', objective: '', equipment: 'manual', plate_format: '96', reaction_smiles: '' })
  const create = useMutation({
    mutationFn: () => post<Campaign>('/api/campaigns/', { ...v, plate_format: Number(v.plate_format) }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      nav(`/screening/${c.id}`)
    },
    onError: notifyError,
  })
  return (
    <Modal opened={opened} onClose={onClose} title="New optimization campaign" size="lg">
      <Stack>
        <TextInput label="Title" required value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} placeholder="e.g. Suzuki coupling of 4-bromoanisole" />
        <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} />
        <Textarea label="Objective" autosize value={v.objective} onChange={(e) => setV({ ...v, objective: e.target.value })} placeholder="Maximise yield above 90 % while keeping Pd ≤ 1 mol%" />
        <TextInput label="Reaction SMILES (optional)" value={v.reaction_smiles} onChange={(e) => setV({ ...v, reaction_smiles: e.target.value })} placeholder="COc1ccc(Br)cc1.OB(O)c1ccccc1>>COc1ccc(-c2ccccc2)cc1" />
        <Group grow>
          <Select label="Equipment" data={EQUIPMENT} value={v.equipment} onChange={(e) => e && setV({ ...v, equipment: e })} />
          {v.equipment === 'hte_plate' && (
            <Select label="Plate format" data={['6', '12', '24', '48', '96', '384']} value={v.plate_format} onChange={(p) => p && setV({ ...v, plate_format: p })} />
          )}
        </Group>
        <Button onClick={() => create.mutate()} disabled={!v.title || !v.group}>
          Create
        </Button>
      </Stack>
    </Modal>
  )
}
