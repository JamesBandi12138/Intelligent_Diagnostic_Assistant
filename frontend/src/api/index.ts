import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface TriageRequest {
  session_id?: string;
  patient: {
    age: number;
    sex: 'male' | 'female' | 'unknown';
    pregnancy_status?: string | null;
    medical_history: string[];
    allergies: string[];
    medications: string[];
  };
  symptom_text: string;
  city?: string;
}

export async function analyzeTriage(payload: TriageRequest) {
  const response = await api.post('/api/triage/analyze', payload);
  return response.data;
}

export default api;

