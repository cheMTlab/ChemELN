/**
 * Marvin JS adapter (ChemAxon; the editor used by Reaxys). Proprietary, so NOT shipped.
 *
 * To enable: an administrator with a ChemAxon licence copies the Marvin JS distribution to
 * frontend/public/vendor/marvinjs/ (git-ignored) and sets STRUCTURE_EDITOR=marvinjs.
 * If the files are missing, CheMTlab falls back to Ketcher.
 */
import type { EditorFactory } from './editor'

interface MarvinSketcher {
  exportStructure(format: string): Promise<string>
  importStructure(format: string, data: string): Promise<void>
}

interface MarvinWindow extends Window {
  marvin?: { onReady(cb: () => void): void; sketcherInstance: MarvinSketcher }
}

const BASE = '/vendor/marvinjs'

export async function marvinAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/editorws.html`, { method: 'HEAD' })
    return res.ok
  } catch {
    return false
  }
}

export const createMarvin: EditorFactory = (container) =>
  new Promise((resolve, reject) => {
    const iframe = document.createElement('iframe')
    iframe.src = `${BASE}/editorws.html`
    iframe.style.cssText = 'width:100%;height:100%;border:0'
    iframe.title = 'Marvin JS structure editor'
    iframe.onerror = () => reject(new Error('Marvin JS could not be loaded'))
    iframe.onload = () => {
      const win = iframe.contentWindow as MarvinWindow | null
      if (!win?.marvin) {
        reject(new Error('Marvin JS files not found'))
        return
      }
      win.marvin.onReady(() => {
        const sketcher = win.marvin!.sketcherInstance
        resolve({
          getMolfile: () => sketcher.exportStructure('mol'),
          setMolfile: (molfile) => sketcher.importStructure('mol', molfile),
          getSmiles: () => sketcher.exportStructure('smiles'),
          getRxn: () => sketcher.exportStructure('rxn'),
          destroy: () => iframe.remove(),
        })
      })
    }
    container.appendChild(iframe)
  })
