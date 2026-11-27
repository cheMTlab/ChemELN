import { Alert, Box, Button, Group, Loader, Modal } from '@mantine/core'
import { useEffect, useRef, useState } from 'react'

import { createEditor, registerDefaultEditors, type StructureEditor } from '../chem/editor'

interface Props {
  opened: boolean
  onClose: () => void
  /** Receives the drawing: a molfile, or an RXN file when `mode="reaction"`. */
  onSubmit: (data: string) => void
  editorKind: string
  initialMolfile?: string
  mode?: 'molecule' | 'reaction'
  title?: string
  submitLabel?: string
}

export default function StructureEditorModal({
  opened,
  onClose,
  onSubmit,
  editorKind,
  initialMolfile,
  mode = 'molecule',
  title = 'Draw structure',
  submitLabel = 'Use structure',
}: Props) {
  // A callback ref (stored in state) rather than useRef: Mantine mounts the modal body after
  // the open transition starts, so the element appears *after* the first effect run. With a
  // plain ref the effect saw `null`, returned early and never re-ran (endless spinner).
  const [host, setHost] = useState<HTMLDivElement | null>(null)
  const editorRef = useRef<StructureEditor | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!opened || !host) return
    let cancelled = false
    registerDefaultEditors()
    setReady(false)
    setError(null)
    createEditor(editorKind, host)
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
  }, [opened, host, editorKind, initialMolfile])

  async function submit() {
    const editor = editorRef.current
    if (!editor) return
    try {
      const data =
        mode === 'reaction' && editor.getRxn ? await editor.getRxn() : await editor.getMolfile()
      onSubmit(data)
      onClose()
    } catch (e) {
      setError((e as Error).message || 'Could not read the drawing')
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="90%" centered>
      {error && <Alert color="red">Structure editor: {error}</Alert>}
      <Box pos="relative" h="70vh">
        {!ready && !error && (
          <Group justify="center" pos="absolute" inset={0}>
            <Loader />
          </Group>
        )}
        <div ref={setHost} style={{ width: '100%', height: '100%' }} />
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
