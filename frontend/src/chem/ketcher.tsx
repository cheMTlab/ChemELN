/** Ketcher (Apache-2.0) adapter, the default structure editor. Loaded lazily (it is large). */
import 'ketcher-react/dist/index.css'

import type { Ketcher } from 'ketcher-core'
import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import { createRoot } from 'react-dom/client'

import type { EditorFactory } from './editor'

const structServiceProvider = new StandaloneStructServiceProvider()

export const createKetcher: EditorFactory = (container) =>
  new Promise((resolve, reject) => {
    const root = createRoot(container)
    root.render(
      <Editor
        staticResourcesUrl=""
        structServiceProvider={structServiceProvider}
        errorHandler={(message: string) => reject(new Error(message))}
        onInit={(ketcher: Ketcher) =>
          resolve({
            getMolfile: () => ketcher.getMolfile(),
            setMolfile: (molfile) => ketcher.setMolecule(molfile),
            getSmiles: () => ketcher.getSmiles(),
            getRxn: () => ketcher.getRxn(),
            destroy: () => root.unmount(),
          })
        }
      />,
    )
  })
