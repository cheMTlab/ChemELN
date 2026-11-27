import { Alert, Box, Button, Group, Loader, Modal } from '@mantine/core'
import { useEffect, useRef, useState } from 'react'

import { createEditor, registerDefaultEditors, type StructureEditor } from '../chem/editor'

interface Props {
  opened: boolean
  onClose: () => void
  /** Receives the drawn structure as a molfile. */
  onSubmit: (molfile: string) => void
  editorKind: string
  initialMolfile?: string
  title?: string
  submitLabel?: string
}

export default function StructureEditorModal({
  opened,
  onClose,
  onSubmit,
  editorKind,
  initialMolfile,
  title = 'Draw structure',
  submitLabel = 'Use structure',
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<StructureEditor | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!opened || !hostRef.current) return
    let cancelled = false
    registerDefaultEditors()
    setReady(false)
    setError(null)
    createEditor(editorKind, hostRef.current)
      .then(async (editor) => {
        if (cancelled) return editor.destroy()
        editorRef.current = editor
        if (initialMolfile) await editor.setMolfile(initialMolfile)
        setReady(true)
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
      editorRef.current?.destroy()
      editorRef.current = null
    }
  }, [opened, editorKind, initialMolfile])

  async function submit() {
    if (!editorRef.current) return
    onSubmit(await editorRef.current.getMolfile())
    onClose()
  }

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="90%" centered>
      {error && <Alert color="red">The structure editor could not start: {error}</Alert>}
      <Box pos="relative" h="65vh">
        {!ready && !error && (
          <Group justify="center" pos="absolute" inset={0}>
            <Loader />
          </Group>
        )}
        <div ref={hostRef} style={{ width: '100%', height: '100%' }} />
      </Box>
      <Group justify="flex-end" mt="md">
        <Button variant="default" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={!ready}>
          {submitLabel}
        </Button>
      </Group>
    </Modal>
  )
}
