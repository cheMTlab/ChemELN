/** Types for the ELN, orders, screening, bio and user-management APIs. */
import type { Capability, Role } from './client'
import type { CompoundSummary } from './types'

// --- users ---------------------------------------------------------------------------------
export interface UserAdmin {
  id: string
  email: string
  first_name: string
  last_name: string
  display_name: string
  initials: string
  job_title: string
  phone: string
  orcid: string
  is_active: boolean
  is_staff: boolean
  capabilities: Capability[]
  memberships: { id: string; group_id: string; group_name: string; role: Role }[]
  last_login: string | null
  date_joined: string
}
export interface UserSummary {
  id: string
  email: string
  display_name: string
}
export interface Group {
  id: string
  name: string
  department: string
  description: string
  member_count: number
}
export interface Member {
  id: string
  user: UserSummary
  role: Role
}

// --- orders --------------------------------------------------------------------------------
export type OrderStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'ordered'
  | 'partial'
  | 'received'
  | 'cancelled'
export interface Supplier {
  id: string
  name: string
  website: string
  customer_number: string
  contact_email: string
  phone: string
  notes: string
  is_active: boolean
}
export interface CostCentre {
  id: string
  group: string
  group_name: string
  code: string
  name: string
  budget: string | null
  currency: string
  valid_until: string | null
  is_active: boolean
  committed: string
  remaining: string | null
}
export interface Order {
  id: string
  number: string
  group: string
  group_name: string
  requested_by_name: string
  status: OrderStatus
  urgency: 'normal' | 'urgent'
  compound: string | null
  compound_detail: CompoundSummary | null
  item_name: string
  display_name: string
  cas: string
  grade: string
  purity: string | null
  supplier: string | null
  supplier_name: string
  supplier_display: string
  catalog_number: string
  package_amount: string
  package_unit: string
  quantity: number
  unit_price: string | null
  currency: string
  total_price: string | null
  cost_centre: string | null
  cost_centre_code: string
  justification: string
  delivery_location: string | null
  submitted_at: string | null
  decided_by_name: string
  decided_at: string | null
  rejection_reason: string
  ordered_at: string | null
  po_number: string
  expected_date: string | null
  received_quantity: number
  received_at: string | null
  container_barcodes: string[]
  allowed_actions: string[]
  created_at: string
}
export interface OrderEvent {
  id: string
  user_name: string
  from_status: string
  to_status: string
  note: string
  created_at: string
}

// --- ELN -----------------------------------------------------------------------------------
export type ExperimentStatus = 'planned' | 'in_progress' | 'completed' | 'failed'
export interface Project {
  id: string
  group: string
  group_name: string
  name: string
  code: string
  description: string
  status: 'active' | 'on_hold' | 'archived'
  experiment_count: number
}
export interface Template {
  id: string
  group: string | null
  name: string
  kind: string
  aim: string
  procedure: string
}
export interface ExperimentSummary {
  id: string
  code: string
  title: string
  kind: string
  status: ExperimentStatus
  tags: string[]
  group: string
  group_name: string
  project: string | null
  project_name: string
  owner_name: string
  reaction_smiles: string
  is_locked: boolean
  signed_at: string | null
  witnessed_at: string | null
  best_yield: number | null
  created_at: string
}
export type ComponentRole = 'reactant' | 'reagent' | 'catalyst' | 'solvent' | 'product'
export interface Component {
  id: string
  experiment: string
  role: ComponentRole
  position: number
  compound: string | null
  container: string | null
  container_barcode: string
  container_left: string
  name: string
  smiles: string
  mw: number | null
  density: number | null
  purity: number | null
  molarity: number | null
  equivalents: number | null
  is_limiting: boolean
  mmol: number | null
  mass_mg: number | null
  volume_ml: number | null
  actual_mass_mg: number | null
  product_purity: number | null
  yield_percent: number | null
  registered_barcode: string
  consumed: boolean
  notes: string
}
export interface Attachment {
  id: string
  file: string
  name: string
  kind: string
  description: string
  size: number
  sha256: string
  uploaded_by_name: string
  created_at: string
}
export interface Comment {
  id: string
  author_name: string
  text: string
  is_addendum: boolean
  created_at: string
}
export interface Signature {
  id: string
  kind: 'sign' | 'witness'
  user_name: string
  meaning: string
  content_hash: string
  hash: string
  seq: number
  created_at: string
}
export interface Experiment extends ExperimentSummary {
  owner: string
  template: string | null
  aim: string
  procedure: string
  observations: string
  conclusion: string
  reaction_rxn: string
  temperature: string
  duration: string
  atmosphere: string
  solvent: string
  workup: string
  started_on: string | null
  completed_on: string | null
  inventory_deducted: boolean
  signed_by_name: string
  witnessed_by_name: string
  components: Component[]
  attachments: Attachment[]
  comments: Comment[]
  signatures: Signature[]
}

// --- screening -----------------------------------------------------------------------------
export interface Variable {
  id: string
  campaign: string
  name: string
  kind: 'continuous' | 'discrete' | 'categorical'
  unit: string
  low: number | null
  high: number | null
  levels: (string | number)[]
  position: number
}
export interface ResponseDef {
  id: string
  campaign: string
  name: string
  unit: string
  goal: 'maximize' | 'minimize' | 'target' | 'monitor'
  target: number | null
  weight: number
  position: number
}
export interface Run {
  id: string
  campaign: string
  index: number
  label: string
  plate: number | null
  well: string
  factors: Record<string, string | number>
  results: Record<string, number>
  status: 'planned' | 'running' | 'done' | 'failed' | 'skipped'
  failure_reason: string
  source: string
  experiment: string | null
  experiment_code: string
  lots: string[]
  notes: string
}
export interface Campaign {
  id: string
  group: string
  group_name: string
  project: string | null
  owner_name: string
  title: string
  objective: string
  reaction_smiles: string
  reaction_rxn: string
  equipment: 'manual' | 'hte_plate' | 'flow' | 'robot'
  plate_format: number
  status: 'design' | 'running' | 'completed' | 'archived'
  notes: string
  variables: Variable[]
  responses: ResponseDef[]
  run_count: number | null
  done_count: number | null
  created_at: string
}
export interface ResponseAnalysis {
  response: string
  name: string
  n: number
  plain: string[]
  observed?: {
    min: number
    max: number
    mean: number
    best_factors: Record<string, string | number>
    best_value: number
  }
  main_effects?: {
    variable: string
    name: string
    unit: string
    numeric: boolean
    points: { x: number | string; mean: number; n: number }[]
  }[]
  model?: {
    order: string
    metrics: {
      n: number
      terms: number
      r2: number
      r2_adj: number | null
      q2: number | null
      rmse: number | null
      residual_dof: number
    }
    terms: { term: string; coef: number; se: number | null; t: number | null; significant: boolean }[]
    residuals: { observed: number; predicted: number }[]
  }
  importance?: {
    variable: string
    name: string
    swing: number
    best_at: number | string
    curve?: { x: number; y: number }[]
    levels?: Record<string, number>
  }[]
}
export interface Suggestion {
  factors: Record<string, string | number>
  predicted: Record<string, number>
  score: number
  purpose: string
  extrapolation: boolean
  warnings: string[]
}

// --- bio -----------------------------------------------------------------------------------
export interface Feature {
  name: string
  type: string
  start: number
  end: number
  strand: number
}
export interface Plasmid {
  id: string
  code: string
  name: string
  alias: string
  group: string
  group_name: string
  backbone: string
  insert: string
  insert_species?: string
  vector_type: string
  resistance: string[]
  origin?: string
  promoter: string
  tags: string[]
  copy_number?: string
  growth_temperature?: string
  sequence?: string
  features?: Feature[]
  circular?: boolean
  size_bp: number | null
  gc_content?: number | null
  source: string
  addgene_id: string
  parent?: string | null
  parent_code?: string
  verified: boolean
  notes?: string
  strain_count?: number
  sample_count?: number
  created_at: string
}
export interface Strain {
  id: string
  code: string
  name: string
  kind: 'bacterium' | 'yeast' | 'cell_line' | 'virus' | 'other'
  group: string
  group_name: string
  organism: string
  genotype: string
  parent: string | null
  plasmids: string[]
  plasmid_codes: string[]
  resistance: string[]
  biosafety_level: number
  is_gmo: boolean
  growth_conditions: string
  tissue: string
  passage: number | null
  mycoplasma_tested_on: string | null
  source: string
  notes: string
}
export interface Oligo {
  id: string
  code: string
  name: string
  group: string
  group_name: string
  sequence: string
  reverse_complement: string
  purpose: string
  target: string
  modifications: string
  scale: string
  purification: string
  supplier: string
  tm: number | null
  gc_content: number | null
  notes: string
}
export interface BioSample {
  id: string
  barcode: string
  group: string
  group_name: string
  kind: string
  name: string
  plasmid: string | null
  plasmid_code: string
  strain: string | null
  strain_code: string
  location: string | null
  location_path: string
  box_position: string
  concentration: number | null
  concentration_unit: string
  volume_ul: number | null
  passage: number | null
  prepared_on: string | null
  is_available: boolean
  notes: string
}
export interface Assay {
  id: string
  group: string
  name: string
  readout: string
  wavelength: string
  unit: string
  target: string
  higher_is_active: boolean
  protocol: string
}
export interface Plate {
  id: string
  barcode: string
  group: string
  group_name: string
  name: string
  kind: string
  format: number
  assay: string | null
  assay_name: string
  experiment: string | null
  experiment_code: string
  notes: string
  rows: number
  cols: number
  measurement_count: number | null
  created_at: string
}
export type WellRole = 'empty' | 'sample' | 'positive' | 'negative' | 'blank' | 'standard'
export interface Well {
  id: string
  name: string
  row: number
  col: number
  role: WellRole
  label: string
  compound: string | null
  compound_name: string
  strain: string | null
  strain_code: string
  plasmid: string | null
  plasmid_code: string
  concentration: number | null
  concentration_unit: string
  volume_ul: number | null
  replicate: number | null
  group_label: string
  excluded: boolean
}
export interface PlateAnalysis {
  channel: string
  channels: string[]
  timepoints: number[]
  grid: (number | null)[][]
  rows: string[]
  cols: number[]
  controls: Record<string, { n: number; mean: number; sd: number | null; cv: number | null } | null>
  z_prime?: number | null
  signal_window?: number
  percent_activity?: Record<string, number>
  hits?: { well: string; label: string; activity: number }[]
  curves: {
    label: string
    unit: string
    points: { x: number; y: number }[]
    fit: {
      bottom: number
      top: number
      ec50: number
      hill: number
      r2: number
      ec50_in_tested_range: boolean
      curve: { x: number; y: number }[]
    } | null
  }[]
  plain: string[]
}
