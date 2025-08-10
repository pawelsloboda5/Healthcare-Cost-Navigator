export type Provider = {
  provider_id?: string;
  provider_name?: string;
  provider_city?: string;
  provider_state?: string;
  provider_zip_code?: string;
  drg_code?: string;
  drg_description?: string;
  average_covered_charges?: number | string;
  average_total_payments?: number | string;
  average_medicare_payments?: number | string;
  total_discharges?: number | string;
  overall_rating?: number | string;
  quality_rating?: number | string;
};

export type AskResponse = {
  success: boolean;
  answer: string;
  explanation_pending?: boolean;
  template_used?: number;
  confidence_score?: number; // 0..1
  sql_query?: string;
  execution_time_ms?: number;
  results?: Array<Record<string, any>>;
};

export type CostAnalysis = {
  drg_code: string;
  drg_description?: string;
  average_cost: number;
  median_cost: number;
  cost_variance: number;
  total_providers: number;
  cheapest_provider?: { provider_name: string; provider_city: string; provider_state: string; cost: number };
  most_expensive_provider?: { provider_name: string; provider_city: string; provider_state: string; cost: number };
};

export type TemplateStats = { template_statistics?: Record<string, number> };

export type HealthStatus = { status: string; service: string };

