export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Not applicable' | 'Insufficient data'
export type Role = 'admin' | 'faculty' | 'placement_officer' | 'judge_demo'

export interface AuthUser { username: string; role: Role }
export interface Meta { total?: number; count?: number; limit?: number; offset?: number; has_more?: boolean; status_counts?: Record<string, number> }
export interface Envelope<T> { status: 'success'; data: T; meta: Meta }

export interface StudentListItem {
  student_id: string; student_name: string; department: string; year_of_study: number | null; section: string | null
  cgpa: number | null; overall_attendance_pct: number | null; placement_status: string | null
  success_score: number | null; academic_risk_level: RiskLevel; placement_risk_level: RiskLevel; segment: string | null
}

export interface RiskView {
  level: RiskLevel; points: number; max_points: number; reasons: string[]; suggested_actions: string[]
  missing_inputs: string[]; note: string | null; is_probability: boolean
}
export interface RiskItem {
  student_id: string; student_name: string; department: string; year_of_study: number | null; section: string | null
  success_score: number | null; segment: string | null; academic_risk: RiskView; placement_risk: RiskView
}

export interface DashboardSummary {
  total_students: number; average_success_score: number | null; average_attendance_pct: number | null
  students_flagged_academic_support: number; students_flagged_placement_support: number
  students_high_priority_support: number; students_strong_placement_readiness: number
  high_risk_academic: number; high_risk_placement: number; students_with_incomplete_data: number
  segments: Record<string, number>; placement_status_counts: Record<string, number>
  open_interventions: number; total_interventions: number; disclaimer?: string
}
export interface DepartmentMetric {
  department: string; students: number; average_success_score: number | null; average_cgpa: number | null
  average_attendance_pct: number | null; average_lms_score: number | null; average_placement_readiness: number | null
  flagged_academic_support: number; flagged_placement_support: number; priority_support: number
  strong_placement_readiness: number; placed_students: number; segments: Record<string, number>
}
export interface SegmentSummary {
  segment: string; description: string; students: number; percentage: number; average_success_score: number | null
  average_attendance_pct: number | null; average_placement_readiness: number | null; by_department: Record<string, number>
}

type Fields = Record<string, string | number | null>
export interface Recommendation {
  id: string; category: string; priority: string; title: string; description: string; suggested_steps: string[]
  related_intervention_type: string | null; existing_open_intervention: unknown
}
export interface Intervention {
  intervention_id: string; student_id: string; student_name?: string; intervention_type: string
  assigned_date: string; status: string; follow_up_notes: string
}
export interface Profile {
  student_id: string
  personal: Fields; academics: Fields; attendance: Fields; lms: Fields; engagement: Fields
  feedback: Fields; skills: Fields; placement: Fields
  success_score: { score: number | null; coverage: number; components: Record<string, { score: number | null; weight: number }>; note: string }
  segment: { name: string; description: string | null }
  risk: { academic: RiskView; placement: RiskView; disclaimer: string }
  recommendations: Recommendation[]
  interventions: Intervention[]
  data_quality: { completeness_pct: number; missing_fields: string[] }
}

export interface Metadata {
  departments: string[]; years_of_study: number[]; admission_years: number[]; sections: string[]
  placement_statuses: string[]; risk_levels: string[]; segments: string[]
  intervention_types: string[]; intervention_statuses: string[]
  score_weights: Record<string, number>; segment_rules: Record<string, number>
  datasets: Record<string, { file: string; rows: number; columns: string[]; role?: string }>
  data_notes: string[]; warnings: string[]
}
export interface Health { service: string; student_count: number; intervention_count: number; warning_count: number; warnings: string[]; loaded_at?: string }
