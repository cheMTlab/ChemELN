// ketcher-standalone ships typings that its package.json "exports" map hides from TypeScript.
declare module 'ketcher-standalone' {
  import type { StructServiceProvider } from 'ketcher-core'

  export class StandaloneStructServiceProvider implements StructServiceProvider {
    mode: StructServiceProvider['mode']
    createStructService: StructServiceProvider['createStructService']
  }
}
