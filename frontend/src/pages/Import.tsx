import { Alert, Button, Code, FileInput, Group, List, Select, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'

import { ApiError, getCookie } from '../api/client'
import type { ImportResult } from '../api/types'
import { useApp, writableGroups } from '../components/context'

export default function Import() {
  const { me } = useApp()
  const groups = writableGroups(me)
  const [file, setFile] = useState<File | null>(null)
  const [group, setGroup] = useState<string | null>(groups[0]?.group_id ?? null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(dryRun: boolean) {
    if (!file || !group) return
    setBusy(true)
    setError(null)
    const body = new FormData()
    body.append('file', file)
    body.append('group', group)
    body.append('dry_run', String(dryRun))
    try {
      const res = await fetch('/api/containers/import/', {
        method: 'POST',
        body,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCookie('csrftoken') ?? '' },
      })
      const data = await res.json()
      if (!res.ok) throw new ApiError(res.status, data)
      setResult(data)
    } catch (e) {
      setError(e instanceof ApiError ? JSON.stringify(e.body) : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack maw={800}>
      <Title order={3}>Import containers</Title>
      <Text size="sm">
        Upload a <b>CSV</b> (comma, semicolon or tab separated) or an <b>SDF</b> file. Recognised
        columns: <Code>name, cas, smiles, amount, unit, location, supplier, catalog_number,
        lot_number, purity, barcode, expiry_date, received_date, price</Code>. Locations are
        matched by barcode or full path, e.g. <Code>Main Site/Chem Building/Lab 101/Shelf A</Code>.
        Existing compounds are reused (matched by structure, CAS, then name).
      </Text>
      <Group grow>
        <FileInput label="File" accept=".csv,.txt,.sdf,.sd" value={file}
          onChange={(f) => { setFile(f); setResult(null) }} />
        <Select label="Group" value={group} onChange={setGroup}
          data={groups.map((g) => ({ value: g.group_id, label: g.group_name }))} />
      </Group>
      <Group>
        <Button variant="light" onClick={() => run(true)} loading={busy} disabled={!file}>
          Check file (nothing is saved)
        </Button>
        <Button onClick={() => run(false)} loading={busy}
          disabled={!result?.dry_run || result.errors.length > 0}>
          Import {result?.created_containers ?? ''} containers
        </Button>
      </Group>
      {error && <Alert color="red">{error}</Alert>}
      {result && (
        <Alert color={result.errors.length ? 'orange' : 'green'}
          title={result.dry_run ? 'Check result' : 'Imported'}>
          {result.rows} rows · {result.created_containers} containers ·{' '}
          {result.created_compounds} new compounds · {result.matched_compounds} existing compounds
          {result.errors.length > 0 && (
            <>
              <Text mt="xs" fw={600}>Fix these rows and check again (nothing was saved):</Text>
              <List size="sm">
                {result.errors.map((e) => (
                  <List.Item key={e.row}>Row {e.row}: {e.message}</List.Item>
                ))}
              </List>
            </>
          )}
        </Alert>
      )}
    </Stack>
  )
}
