import {
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Modal,
  NavLink,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, post } from '../../api/client'
import type { Experiment, ExperimentSummary, Project, Template } from '../../api/modules'
import type { Page } from '../../api/types'
import { useApp } from '../../components/context'
import { defaultGroup, fmt, fmtDate, GroupPicker, notifyError, StatusBadge } from '../../components/pickers'

const KINDS = [
  { value: 'synthesis', label: 'Synthesis' },
  { value: 'analysis', label: 'Analysis' },
  { value: 'biology', label: 'Biology' },
  { value: 'screening', label: 'Screening run' },
  { value: 'general', label: 'General' },
]

export default function Notebook() {
  const [project, setProject] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [dq] = useDebouncedValue(q, 250)
  const [status, setStatus] = useState<string | null>(null)
  const [mine, setMine] = useState(false)
  const [newExp, setNewExp] = useState(false)
  const [newProject, setNewProject] = useState(false)
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api<Page<Project>>('/api/projects/') })
  const params = new URLSearchParams({ q: dq })
  if (project) params.set('project', project)
  if (status) params.set('status', status)
  if (mine) params.set('mine', '1')
  const exps = useQuery({
    queryKey: ['experiments', params.toString()],
    queryFn: () => api<Page<ExperimentSummary>>(`/api/experiments/?${params}`),
  })
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 3 }}>
        <Card withBorder padding="xs">
          <Group justify="space-between" mb="xs">
            <Text fw={600}>Projects</Text>
            <Button size="compact-xs" variant="light" onClick={() => setNewProject(true)}>
              New
            </Button>
          </Group>
          <NavLink label="All experiments" active={!project} onClick={() => setProject(null)} />
          {projects.data?.results.map((p) => (
            <NavLink
              key={p.id}
              label={p.name}
              description={`${p.group_name} · ${p.experiment_count} exp.`}
              active={project === p.id}
              onClick={() => setProject(p.id)}
              rightSection={p.status !== 'active' ? <Badge size="xs">{p.status}</Badge> : null}
            />
          ))}
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 9 }}>
        <Stack>
          <Group justify="space-between">
            <Title order={2}>Lab notebook</Title>
            <Button onClick={() => setNewExp(true)}>New experiment</Button>
          </Group>
          <Group>
            <TextInput
              placeholder="Search code, title, procedure, reagent, tag"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              w={340}
            />
            <Select
              placeholder="Any status"
              clearable
              data={['planned', 'in_progress', 'completed', 'failed'].map((s) => ({ value: s, label: s.replace('_', ' ') }))}
              value={status}
              onChange={setStatus}
              w={160}
            />
            <Button variant={mine ? 'filled' : 'default'} onClick={() => setMine(!mine)}>
              Mine
            </Button>
          </Group>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Code</Table.Th>
                <Table.Th>Title</Table.Th>
                <Table.Th>Author</Table.Th>
                <Table.Th>Yield</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Signed</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {exps.data?.results.map((e) => (
                <Table.Tr key={e.id}>
                  <Table.Td>
                    <Text component={Link} to={`/eln/${e.id}`} fw={600} c="blue">
                      {e.code}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {e.title}
                    <Text size="xs" c="dimmed">
                      {e.project_name || e.group_name} · {fmtDate(e.created_at)}
                      {e.tags.map((t) => ` #${t}`)}
                    </Text>
                  </Table.Td>
                  <Table.Td>{e.owner_name}</Table.Td>
                  <Table.Td>{e.best_yield !== null ? `${fmt(e.best_yield, 1)} %` : ''}</Table.Td>
                  <Table.Td>
                    <StatusBadge status={e.status} />
                  </Table.Td>
                  <Table.Td>
                    {e.witnessed_at ? (
                      <Badge color="green">witnessed</Badge>
                    ) : e.signed_at ? (
                      <Badge color="teal" variant="light">signed</Badge>
                    ) : null}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {exps.data?.count === 0 && <Text c="dimmed">No experiments yet.</Text>}
        </Stack>
      </Grid.Col>
      <NewExperiment opened={newExp} onClose={() => setNewExp(false)} project={project} projects={projects.data?.results ?? []} />
      <NewProject opened={newProject} onClose={() => setNewProject(false)} />
    </Grid>
  )
}

function NewExperiment({
  opened,
  onClose,
  project,
  projects,
}: {
  opened: boolean
  onClose: () => void
  project: string | null
  projects: Project[]
}) {
  const { me } = useApp()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const projectGroup = projects.find((p) => p.id === project)?.group
  const [v, setV] = useState({
    group: projectGroup ?? defaultGroup(me),
    project: project,
    title: '',
    kind: 'synthesis',
    template: null as string | null,
    aim: '',
  })
  const templates = useQuery({ queryKey: ['templates'], queryFn: () => api<Page<Template>>('/api/experiment-templates/') })
  const create = useMutation({
    mutationFn: () => post<Experiment>('/api/experiments/', v),
    onSuccess: (e) => {
      qc.invalidateQueries({ queryKey: ['experiments'] })
      onClose()
      navigate(`/eln/${e.id}`)
    },
    onError: notifyError,
  })
  return (
    <Modal opened={opened} onClose={onClose} title="New experiment" size="lg">
      <Stack>
        <TextInput label="Title" required value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} data-autofocus />
        <Group grow>
          <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g, project: null })} />
          <Select
            label="Project"
            clearable
            data={projects.filter((p) => p.group === v.group).map((p) => ({ value: p.id, label: p.name }))}
            value={v.project}
            onChange={(p) => setV({ ...v, project: p })}
          />
        </Group>
        <Group grow>
          <Select label="Type" data={KINDS} value={v.kind} onChange={(k) => k && setV({ ...v, kind: k })} />
          <Select
            label="Start from template"
            clearable
            data={(templates.data?.results ?? []).map((t) => ({ value: t.id, label: t.name }))}
            value={v.template}
            onChange={(t) => setV({ ...v, template: t })}
          />
        </Group>
        <Textarea label="Aim" autosize minRows={2} value={v.aim} onChange={(e) => setV({ ...v, aim: e.target.value })} />
        <Button onClick={() => create.mutate()} disabled={!v.title || !v.group} loading={create.isPending}>
          Create
        </Button>
      </Stack>
    </Modal>
  )
}

function NewProject({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { me } = useApp()
  const qc = useQueryClient()
  const [v, setV] = useState({ group: defaultGroup(me), name: '', code: '', description: '' })
  const create = useMutation({
    mutationFn: () => post('/api/projects/', v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      onClose()
    },
    onError: notifyError,
  })
  return (
    <Modal opened={opened} onClose={onClose} title="New project">
      <Stack>
        <GroupPicker value={v.group} onChange={(g) => setV({ ...v, group: g })} />
        <TextInput label="Name" required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        <TextInput label="Code" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} />
        <Textarea label="Description" value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
        <Button onClick={() => create.mutate()} disabled={!v.name}>
          Create
        </Button>
      </Stack>
    </Modal>
  )
}
