/**
 * Pluggable structure editor.
 *
 * Every editor (Ketcher by default; Marvin JS for institutions with a ChemAxon licence) is
 * wrapped in the same small interface, so the rest of CheMTlab never depends on a vendor API.
 * Concrete adapters are registered in M1 (inventory) when the editor is first needed.
 */

export interface StructureEditor {
  /** MDL Molfile (V2000/V3000) of the current drawing. */
  getMolfile(): Promise<string>
  setMolfile(molfile: string): Promise<void>
  getSmiles(): Promise<string>
  /** Reaction drawing as RXN, for the ELN (M3). */
  getRxn?(): Promise<string>
  destroy(): void
}

export type EditorFactory = (container: HTMLElement) => Promise<StructureEditor>

const registry = new Map<string, EditorFactory>()

export function registerEditor(kind: string, factory: EditorFactory): void {
  registry.set(kind, factory)
}

export function availableEditors(): string[] {
  return [...registry.keys()]
}

/** Create the editor the instance is configured for, falling back to Ketcher. */
export async function createEditor(
  kind: string,
  container: HTMLElement,
): Promise<StructureEditor> {
  const factory = registry.get(kind) ?? registry.get('ketcher')
  if (!factory) throw new Error(`No structure editor registered (wanted "${kind}")`)
  try {
    return await factory(container)
  } catch (err) {
    const fallback = registry.get('ketcher')
    if (kind === 'ketcher' || !fallback) throw err
    container.replaceChildren()
    return fallback(container)
  }
}

let defaultsRegistered = false

/** Register the built-in adapters. Both are code-split, so they load only when first used. */
export function registerDefaultEditors(): void {
  if (defaultsRegistered) return
  defaultsRegistered = true
  registerEditor('ketcher', async (el) => (await import('./ketcher')).createKetcher(el))
  registerEditor('marvinjs', async (el) => {
    const marvin = await import('./marvin')
    if (!(await marvin.marvinAvailable())) throw new Error('Marvin JS not installed')
    return marvin.createMarvin(el)
  })
}
