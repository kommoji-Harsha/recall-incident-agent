export type MemoryStatus = 'off' | 'ok' | 'no_match' | 'unavailable';

export type PriorOutcome = 'worked' | 'failed' | 'unknown';

export type OutcomeResult = 'fixed' | 'didnt_work';

export interface RootCause {
  text: string;
  confidence: number;
  sources: string[];
}

export interface FixStep {
  rank: number;
  step: string;
  rationale: string;
  source_incident_ids: string[];
  source_memory_ids: string[];
  prior_outcome: PriorOutcome;
}

export interface RecalledMemoryItem {
  id: string;
  text: string;
  type: string;
  context?: string | null;
  metadata?: Record<string, string>;
  tags?: string[];
  entities?: string[];
  occurred_start?: string | null;
  mentioned_at?: string | null;
  document_id?: string | null;
  chunk_id?: string | null;
  source_fact_ids?: string[];
  scores?: {
    final?: number | null;
    reranker?: number | null;
    semantic?: number | null;
    keyword?: number | null;
  };
  source_incident_id?: string | null;
}

export interface AnalysisOutput {
  likely_root_cause: RootCause;
  fix_steps: FixStep[];
  runbooks: string[];
  memory_used: RecalledMemoryItem[];
  memory_status: MemoryStatus;
  warnings: string[];
  model_used: string;
}

export interface AnalyzeRequest {
  alert_text: string;
  memory_enabled?: boolean;
  compare?: boolean;
}

export interface AnalyzeResponse {
  analysis_id: string;
  memory_on: AnalysisOutput;
  memory_off: AnalysisOutput | null;
}

export interface OutcomeRequest {
  analysis_id: string;
  result: OutcomeResult;
  notes?: string;
}

export interface OutcomeResponse {
  status: string;
  analysis_id: string;
  result: OutcomeResult;
  retained_doc_id: string;
  idempotent_duplicate: boolean;
}

export interface PostmortemRequest {
  title?: string | null;
  text: string;
}

export interface PostmortemResponse {
  postmortem_id: string;
  status: string;
  recalled_sample: Array<{
    id: string;
    text: string;
    document_id?: string | null;
    type: string;
  }>;
}

export interface Observation {
  id: string;
  text: string;
  context?: string | null;
  metadata?: Record<string, string>;
  tags?: string[];
  occurred_start?: string | null;
}

export interface ObservationsResponse {
  count: number;
  observations: Observation[];
}

export interface HealthStatus {
  status: 'ok' | 'degraded';
  hindsight_reachable: boolean;
  bootstrap_error?: string | null;
  groq_configured: boolean;
  primary_model?: string | null;
  fallback_model?: string | null;
}

export interface LearningCurveSeries {
  interaction: number;
  accuracy_memory_on: number;
  accuracy_memory_off: number;
  recalled_count: number;
}

export interface LearningCurveData {
  status: string;
  evaluated_interactions: number;
  series: LearningCurveSeries[];
}
