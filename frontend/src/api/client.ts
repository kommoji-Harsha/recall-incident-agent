import type {
  AnalyzeRequest,
  AnalyzeResponse,
  HealthStatus,
  LearningCurveData,
  ObservationsResponse,
  OutcomeRequest,
  OutcomeResponse,
  PostmortemRequest,
  PostmortemResponse,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Ignore JSON parse error on non-JSON error pages
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/api/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<HealthStatus>(res);
  },

  async analyze(req: AnalyzeRequest): Promise<AnalyzeResponse> {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<AnalyzeResponse>(res);
  },

  async recordOutcome(req: OutcomeRequest): Promise<OutcomeResponse> {
    const res = await fetch(`${API_BASE}/api/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<OutcomeResponse>(res);
  },

  async submitPostmortem(req: PostmortemRequest): Promise<PostmortemResponse> {
    const res = await fetch(`${API_BASE}/api/postmortem`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<PostmortemResponse>(res);
  },

  async getObservations(limit: number = 50): Promise<ObservationsResponse> {
    const res = await fetch(`${API_BASE}/api/memory/observations?limit=${limit}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<ObservationsResponse>(res);
  },

  // Typed placeholder for Learning Curve evaluation (Task 3 endpoint)
  async getLearningCurve(): Promise<LearningCurveData> {
    const res = await fetch(`${API_BASE}/api/eval/learning-curve`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<LearningCurveData>(res);
  },
};
