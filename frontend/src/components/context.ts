import { useOutletContext } from 'react-router-dom'

import type { Capability, InstanceConfig, Me, Role } from '../api/client'

export interface AppContext {
  config: InstanceConfig
  me: Me | undefined
}

export const useApp = () => useOutletContext<AppContext>()

/** Groups where the user may add containers (member role or higher). */
export function writableGroups(me: Me | undefined) {
  return (me?.memberships ?? []).filter((m) => m.role !== 'viewer')
}

export function can(me: Me | undefined, capability: Capability): boolean {
  return !!me && (me.is_staff || me.capabilities?.includes(capability))
}

const RANK: Record<Role, number> = { viewer: 0, member: 1, pi: 2, admin: 3 }

/** True if the user holds at least `minimum` in the group (instance staff always do). */
export function hasRole(me: Me | undefined, groupId: string | null | undefined, minimum: Role) {
  if (!me) return false
  if (me.is_staff) return true
  const m = me.memberships.find((x) => x.group_id === groupId)
  return !!m && RANK[m.role] >= RANK[minimum]
}

export const isPiAnywhere = (me: Me | undefined) =>
  !!me && (me.is_staff || me.memberships.some((m) => RANK[m.role] >= RANK.pi))

export const formatAmount = (amount: string, unit: string) =>
  `${Number(amount).toLocaleString(undefined, { maximumFractionDigits: 4 })} ${unit.replace('u', 'µ')}`
