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

export interface TriageSessionDetailResponse {
  session_id: string;
  status: string;
  latest_request: TriageAnalyzeRequest | null;
  latest_result: AnalyzeTriageResponse | null;
  current_question: string | null;
  messages: TriageMessage[];
}

export interface TriageSessionResponse {
  session_id: string;
  status: string;
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

export default api;
