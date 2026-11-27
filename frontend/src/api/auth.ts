/** Login/logout via django-allauth's headless "browser" API (session cookies). */
import { ApiError, api, getCookie } from './client'

const BASE = '/_allauth/browser/v1'

export async function isLoggedIn(): Promise<boolean> {
  try {
    await api(`${BASE}/auth/session`)
    return true
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return false
    throw e
  }
}

export async function login(email: string, password: string): Promise<void> {
  await api(`${BASE}/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function logout(): Promise<void> {
  try {
    await api(`${BASE}/auth/session`, { method: 'DELETE' })
  } catch (e) {
    // allauth answers 401 once the session is gone, which is what we want.
    if (!(e instanceof ApiError && e.status === 401)) throw e
  }
}

/** Institutional SSO: a real form POST, because the browser must follow the IdP redirect. */
export function startSso(providerId: string): void {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = `${BASE}/auth/provider/redirect`
  const fields: Record<string, string> = {
    provider: providerId,
    process: 'login',
    callback_url: `${window.location.origin}/`,
    csrfmiddlewaretoken: getCookie('csrftoken') ?? '',
  }
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
}
