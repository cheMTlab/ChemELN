import { useOutletContext } from 'react-router-dom'

import type { InstanceConfig, Me } from '../api/client'

export interface AppContext {
  config: InstanceConfig
  me: Me | undefined
}

export const useApp = () => useOutletContext<AppContext>()

/** Groups where the user may add containers (member role or higher). */
export function writableGroups(me: Me | undefined) {
  return (me?.memberships ?? []).filter((m) => m.role !== 'viewer')
}

export const formatAmount = (amount: string, unit: string) =>
  `${Number(amount).toLocaleString(undefined, { maximumFractionDigits: 4 })} ${unit.replace('u', 'µ')}`
