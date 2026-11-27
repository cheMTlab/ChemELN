import {
  Alert,
  Button,
  Center,
  Divider,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { login, startSso } from '../api/auth'
import type { InstanceConfig } from '../api/client'

export default function Login({ config }: { config: InstanceConfig }) {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      await queryClient.invalidateQueries({ queryKey: ['session'] })
    } catch {
      setError('Wrong email or password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w={380}>
        <Stack>
          <div>
            <Title order={2}>{config.instance_name}</Title>
            <Text c="dimmed" size="sm">
              Lab notebook &amp; chemical inventory
            </Text>
          </div>

          {config.sso_providers.map((p) => (
            <Button key={p.id} variant="filled" onClick={() => startSso(p.id)}>
              Sign in with {p.name}
            </Button>
          ))}
          {config.sso_providers.length > 0 && <Divider label="or" labelPosition="center" />}

          <form onSubmit={onSubmit}>
            <Stack>
              {error && <Alert color="red">{error}</Alert>}
              <TextInput
                label="Email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
              <PasswordInput
                label="Password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
              <Button type="submit" loading={busy} variant="light">
                Sign in
              </Button>
            </Stack>
          </form>
          <Text size="xs" c="dimmed" ta="center">
            v{config.version} · Your data stays on this institution&apos;s server.
          </Text>
        </Stack>
      </Paper>
    </Center>
  )
}
