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

export type Role = 'admin' | 'pi' | 'member' | 'viewer'

export type Capability =
  | 'user_manager'
  | 'purchasing'
  | 'order_approver'
  | 'safety_officer'
  | 'inventory_manager'
  | 'biosafety_officer'

export interface Me {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string
  initials: string
  job_title: string
  phone: string
  orcid: string
  is_staff: boolean
  capabilities: Capability[]
  memberships: { id: string; group_id: string; group_name: string; role: Role }[]
}

/** JSON helpers on top of `api`. */
export const post = <T = unknown>(path: string, body?: unknown) =>
  api<T>(path, {
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  })
export const patch = <T = unknown>(path: string, body: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export const del = (path: string) => api(path, { method: 'DELETE' })

/** Turn a DRF error body into one readable line. */
export function errorText(e: unknown): string {
  if (!(e instanceof ApiError)) return e instanceof Error ? e.message : 'Something went wrong'
  const b = e.body as unknown
  if (!b) return `Error ${e.status}`
  if (typeof b === 'string') return b
  if (Array.isArray(b)) return b.join(' ')
  return Object.entries(b as Record<string, unknown>)
    .map(([k, v]) => {
      const msg = Array.isArray(v) ? v.join(' ') : typeof v === 'object' ? JSON.stringify(v) : String(v)
      return k === 'detail' || k === 'non_field_errors' ? msg : `${k}: ${msg}`
    })
    .join(' · ')
}
