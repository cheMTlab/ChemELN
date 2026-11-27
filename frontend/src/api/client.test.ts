import { describe, expect, it } from 'vitest'

import { availableEditors, createEditor, registerEditor } from '../chem/editor'
import { getCookie } from './client'

describe('getCookie', () => {
  it('reads a cookie by name', () => {
    expect(getCookie('csrftoken', 'sessionid=abc; csrftoken=xyz%3D1')).toBe('xyz=1')
  })
  it('returns null when missing', () => {
    expect(getCookie('csrftoken', 'sessionid=abc')).toBeNull()
  })
})

describe('structure editor registry', () => {
  it('falls back to ketcher when the configured editor is not available', async () => {
    const fake = {
      getMolfile: async () => '',
      setMolfile: async () => {},
      getSmiles: async () => 'c1ccccc1',
      destroy: () => {},
    }
    registerEditor('ketcher', async () => fake)
    expect(availableEditors()).toContain('ketcher')
    const editor = await createEditor('marvinjs', document.createElement('div'))
    expect(await editor.getSmiles()).toBe('c1ccccc1')
  })
})
