export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface CompoundSummary {
  id: string
  name: string
  cas: string
  formula: string
  mw: number | null
  smiles: string
  signal_word: '' | 'warning' | 'danger'
  ghs_pictograms: string[]
  storage_class: string
}

export interface Compound extends CompoundSummary {
  synonyms: string[]
  molfile: string
  inchikey: string | null
  h_statements: string[]
  p_statements: string[]
  is_peroxide_former: boolean
  is_controlled: boolean
  pubchem_cid: number | null
  similarity: number | null
  container_count?: number
}

export type ContainerStatus = 'available' | 'borrowed' | 'empty' | 'missing' | 'disposed'

export interface Container {
  id: string
  barcode: string
  compound: string
  compound_detail: CompoundSummary
  group: string
  group_name: string
  owner_name: string
  location: string | null
  location_path: string
  status: ContainerStatus
  amount: string
  initial_amount: string
  unit: string
  purity: string | null
  supplier: string
  catalog_number: string
  lot_number: string
  received_date: string
  opened_date: string | null
  expiry_date: string | null
  notes: string
  is_expired: boolean
  fraction_remaining: number | null
  storage_warning: string
}

export interface ContainerEvent {
  id: string
  kind: string
  user_name: string
  amount_change: string | null
  from_path: string
  to_path: string
  note: string
  created_at: string
}

export interface Location {
  id: string
  parent: string | null
  name: string
  kind: string
  barcode: string | null
  group: string | null
  path: string
  depth: number
  container_count: number
  allowed_storage_classes: string[]
}

export interface PubChemResult {
  pubchem_cid: number
  name: string
  formula: string
  mw: number | null
  smiles: string
  cas: string
  synonyms: string[]
  ghs_pictograms: string[]
  signal_word: string
  h_statements: string[]
  p_statements: string[]
  existing_id: string | null
}

export type AlertKey = 'expired' | 'expiring_soon' | 'peroxide_retest' | 'low_stock' | 'storage_conflicts'
export type Alerts = Record<AlertKey, { count: number; items: Container[] }>

export interface ImportResult {
  dry_run: boolean
  rows: number
  created_containers: number
  created_compounds: number
  matched_compounds: number
  errors: { row: number; message: string }[]
}

export const UNITS = ['mg', 'g', 'kg', 'uL', 'mL', 'L', 'umol', 'mmol', 'mol', 'pcs'] as const
