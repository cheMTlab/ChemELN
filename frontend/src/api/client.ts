/** Minimal fetch wrapper: same-origin session cookies + Django CSRF protection. */

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.body = body
  }
}

export function getCookie(name: string, cookieString: string = document.cookie): string | null {
  for (const part of cookieString.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return decodeURIComponent(rest.join('='))
  }
  return null
}

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (UNSAFE.has(method)) {
    const token = getCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
  }
  const res = await fetch(path, { ...init, method, headers, credentials: 'same-origin' })
  const text = await res.text()
  const body = text ? JSON.parse(text) : null
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}

export interface InstanceConfig {
  instance_name: string
  version: string
  structure_editor: 'ketcher' | 'marvinjs' | string
  sso_providers: { id: string; name: string }[]
  open_signup: boolean
  external_lookups: boolean
  ai_enabled: boolean
}

export interface Me {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string
  orcid: string
  is_staff: boolean
  memberships: { group_id: string; group_name: string; role: 'admin' | 'pi' | 'member' | 'viewer' }[]
}
