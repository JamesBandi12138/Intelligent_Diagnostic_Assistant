import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export type Sex = 'male' | 'female' | 'unknown';
export type RiskLevel = 'low' | 'medium' | 'high' | 'emergency';
export type TriageStatus = 'created' | 'needs_follow_up' | 'completed' | 'collecting' | 'not_found';

export interface PatientProfile {
  age: number;
  sex: Sex;
  pregnancy_status?: string | null;
  medical_history: string[];
  allergies: string[];
  medications: string[];
}

export interface TriageAnalyzeRequest {
  session_id?: string;
  patient?: PatientProfile;
  symptom_text?: string;
  city?: string;
  answer?: string;
}

export interface DepartmentRecommendation {
  name: string;
  reason: string;
  priority: number;
}

export interface FollowUpResponse {
  session_id: string;
  status: 'needs_follow_up';
  risk_level: RiskLevel;
  question: string;
  known_facts_summary: string;
  missing_fields: string[];
}

export interface CompletedTriageResponse {
  session_id: string;
  status: 'completed';
  risk_level: RiskLevel;
  emergency_advice: string | null;
  recommended_departments: DepartmentRecommendation[];
  care_path: string;
  preparation_checklist: string[];
  report_summary: string;
  disclaimer: string;
}

export type AnalyzeTriageResponse = FollowUpResponse | CompletedTriageResponse;

export interface TriageMessage {
  role: 'user' | 'assistant';
  content: string;
  kind: string;
}

export interface AgentTraceEntry {
  agent: string;
  summary: string;
}

export interface LlmTraceEntry {
  agent: string;
  task: string;
  used: boolean;
  fallback: boolean;
  error?: string | null;
}

export interface TriageSessionDetailResponse {
  session_id: string;
  status: string;
  latest_request: TriageAnalyzeRequest | null;
  latest_result: AnalyzeTriageResponse | null;
  current_question: string | null;
  report_id?: string | null;
  messages: TriageMessage[];
  current_agent?: string | null;
  node_trace?: string[];
  agent_trace?: AgentTraceEntry[];
  route_reason?: string | null;
  knowledge_summary?: string | null;
  raw_follow_up_question?: string | null;
  llm_follow_up_question?: string | null;
  raw_report_summary?: string | null;
  llm_report_summary?: string | null;
  llm_used?: boolean;
  llm_error?: string | null;
  llm_trace?: LlmTraceEntry[];
}

export interface TriageSessionResponse {
  session_id: string;
  status: string;
}

export interface ReportCreateRequest {
  session_id: string;
}

export interface ReportPatientSnapshot {
  age: number;
  sex: Sex;
  pregnancy_status?: string | null;
  medical_history: string[];
  allergies: string[];
  medications: string[];
}

export interface ReportTriageSummary {
  chief_complaint: string;
  risk_level: RiskLevel;
  recommended_departments: DepartmentRecommendation[];
  care_path: string;
  generated_from_session_status: string;
}

export interface DoctorView {
  chief_complaint: string;
  key_facts: Record<string, string>;
  risk_notes: string;
  recommended_department_summary: string;
  preparation_checklist: string[];
}

export interface PatientView {
  what_this_means: string;
  why_this_department: string;
  what_to_prepare: string[];
  when_to_seek_urgent_care: string;
}

export interface ReportResponse {
  report_id: string;
  session_id: string;
  status: string;
  created_at: string;
  patient_snapshot: ReportPatientSnapshot;
  triage_summary: ReportTriageSummary;
  doctor_view: DoctorView;
  patient_view: PatientView;
  disclaimer: string;
}

export async function createTriageSession(): Promise<TriageSessionResponse> {
  const response = await api.post('/api/triage/sessions');
  return response.data;
}

export async function analyzeTriage(payload: TriageAnalyzeRequest): Promise<AnalyzeTriageResponse> {
  const response = await api.post('/api/triage/analyze', payload);
  return response.data;
}

export async function getTriageSession(sessionId: string): Promise<TriageSessionDetailResponse> {
  const response = await api.get(`/api/triage/sessions/${sessionId}`);
  return response.data;
}

export async function createTriageReport(payload: ReportCreateRequest): Promise<ReportResponse> {
  const response = await api.post('/api/reports', payload);
  return response.data;
}

export async function getTriageReport(reportId: string): Promise<ReportResponse> {
  const response = await api.get(`/api/reports/${reportId}`);
  return response.data;
}

export default api;
