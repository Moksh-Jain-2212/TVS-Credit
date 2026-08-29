const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type BorrowerSummary = {
  account_id: number;
  loan_count: number;
  latest_loan_id: number;
  latest_decision: string;
  latest_confidence_score: number;
};

export type RepaymentCandidate = {
  amount: number;
  tenure_months: number;
  estimated_emi: number;
  capacity: number;
  risk_probability: number;
  cash_flow_forecast_p10: number;
  cash_flow_forecast_p50: number;
  stress_probability: number;
  minimum_projected_buffer: number;
  confidence_score: number;
  emi_to_expected_cash_flow: number;
  classification: "SAFE" | "BORDERLINE" | "UNSAFE";
  classification_reasons: string[];
};

export type AdaptiveObservation = {
  event: string;
  simulated: boolean;
  updated_risk_probability: number;
  updated_confidence_score: number;
  maximum_safe_exposure: number;
  recommended_amount: number;
  recommended_tenure: number | null;
  recommended_emi: number | null;
  decision_state: string;
  decision_reasons: string[];
};

export type DemoAction =
  | "on_time"
  | "late"
  | "missed"
  | "income_shock_20"
  | "emergency_expense"
  | "additional_evidence";

export type DemoSimulationResponse = {
  application_id: number;
  mock_simulation: boolean;
  action: DemoAction;
  applied_adjustments: Record<string, string | number | null>;
  result: {
    decision_state: string | null;
    recommended_amount: number | null;
    recommended_tenure: number | null;
    recommended_emi: number | null;
    maximum_safe_exposure: number | null;
    updated_confidence_score: number | null;
    updated_risk_probability: number | null;
    stress_probability: number | null;
    stress_survival: number | null;
    minimum_remaining_cash_buffer: number | null;
    reason: string;
    decision_reasons: string[];
  };
};

export type AnalysisResponse = {
  application_id: number;
  financial_profile: {
    bureau_available: boolean;
    bureau_status: string;
    months_of_history: number;
    mean_monthly_inflow: number;
    mean_monthly_outflow: number;
    mean_monthly_net_cash_flow: number;
    positive_cash_flow_month_ratio: number | null;
    income_volatility: number | null;
    balance_volatility: number | null;
    income_trend: number | null;
    stability_history_status: string | null;
    income_stability_score: number | null;
    cash_flow_stability_score: number | null;
    phase7_income_trend: number | null;
    average_balance: number | null;
    minimum_balance: number | null;
    transaction_density: number | null;
    confidence_score: number;
    confidence_band: string;
  };
  forecast: {
    status: string;
    method: string;
    history_months: number;
    p10_conservative: number;
    p50_expected: number;
    p90_optimistic: number;
  };
  stress_test: {
    stress_probability: number;
    minimum_remaining_cash_buffer: number;
    worst_scenario: string | null;
  };
  repayment_envelope: {
    all_evaluated_combinations: RepaymentCandidate[];
    safe_combinations: RepaymentCandidate[];
    maximum_safe_exposure: number;
    recommended_amount: number;
    recommended_tenure: number | null;
    recommended_emi: number | null;
  };
  decision: {
    decision_state: string;
    requested_amount: number;
    recommended_amount: number;
    recommended_tenure: number | null;
    recommended_emi: number | null;
    reasons: string[];
    loan_officer_explanation: {
      risk?: {
        probability?: number;
        band?: string;
      };
      capacity?: {
        expected_monthly_cash_flow?: number;
        conservative_monthly_cash_flow?: number;
        scheduled_payment?: number;
      };
    };
  };
  credit_path: {
    starter_credit_eligible: boolean;
    starter_amount: number;
    starter_tenure: number | null;
    starter_emi: number | null;
    starter_reason: string;
    simulated_events: string[];
    simulated_observations: AdaptiveObservation[];
    final_decision: string;
    final_recommended_amount: number;
  };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

export async function platformRequest<T>(path: string, init?: RequestInit, token?: string | null): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) {
    return `Request failed with ${response.status}`;
  }
  try {
    const parsed = JSON.parse(body) as { detail?: unknown; error?: { message?: string } };
    if (typeof parsed.error?.message === "string") {
      return parsed.error.message;
    }
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    return JSON.stringify(parsed.detail ?? parsed);
  } catch {
    return body;
  }
}

export type AuthUser = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: "USER" | "ADMIN";
  is_verified: boolean;
  is_active: boolean;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
};

export type RegisterResponse = {
  user: AuthUser;
  otp_delivery: OtpDelivery;
};

export type OtpDelivery = {
  mode: "SMTP_EMAIL" | "MOCK_CONSOLE" | string;
  label: string;
  mocked: boolean;
  development_otp?: string;
};

export type PlatformApplication = {
  id: number;
  requested_amount: number | null;
  requested_tenure: number | null;
  loan_purpose: string | null;
  employment_type: string | null;
  declared_monthly_income: number | null;
  declared_monthly_expenses: number | null;
  existing_monthly_emi: number | null;
  status: string;
  financial_data_source: string | null;
  demo_financial_profile_connected: boolean;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  latest_underwriting?: PlatformUnderwriting | null;
  latest_admin_decision?: PlatformAdminDecision | null;
  notifications?: string[];
};

export type BehavioralRiskAssessment = {
  id?: number;
  base_model_risk_probability: number | null;
  behavioral_risk_score: number | null;
  behavioral_risk_probability: number | null;
  combined_risk_probability: number | null;
  behavioral_data_coverage: number | null;
  behavioral_assessment_confidence: number | null;
  source_coverage: Array<Record<string, unknown>>;
  source_component_scores: Array<Record<string, unknown>>;
  factor_contributions: Array<Record<string, unknown>>;
  policy_version?: string | null;
  created_at?: string;
};

export type PlatformUnderwriting = {
  id: number;
  risk_probability: number | null;
  confidence_score: number | null;
  confidence_band: string | null;
  cash_flow_p10: number | null;
  cash_flow_p50: number | null;
  cash_flow_p90: number | null;
  stress_probability: number | null;
  minimum_remaining_buffer: number | null;
  worst_stress_scenario: string | null;
  maximum_safe_exposure: number | null;
  recommended_amount: number | null;
  recommended_tenure: number | null;
  recommended_emi: number | null;
  nadi_decision_state: string | null;
  decision_reasons: string[] | null;
  loan_officer_explanation?: Record<string, unknown> | null;
  borrower_explanation?: Record<string, unknown> | null;
  behavioral_risk?: BehavioralRiskAssessment | null;
  repayment_envelope?: {
    all_evaluated_combinations: RepaymentCandidate[];
    safe_combinations: RepaymentCandidate[];
    maximum_safe_exposure: number;
    recommended_amount: number;
    recommended_tenure: number | null;
    recommended_emi: number | null;
  } | null;
};

export type PlatformAdminDecision = {
  id: number;
  decision: string;
  approved_amount: number | null;
  approved_tenure: number | null;
  approved_emi: number | null;
  remarks: string | null;
  created_at: string;
};

export type AdminApplicationRow = {
  id: number;
  applicant: string;
  applicant_email: string;
  requested_amount: number | null;
  requested_tenure: number | null;
  submitted_at: string | null;
  risk: string | null;
  risk_probability: number | null;
  historical_model_risk_probability?: number | null;
  behavioral_risk_probability?: number | null;
  behavioral_data_coverage?: number | null;
  confidence_band: string | null;
  confidence_score: number | null;
  nadi_recommendation: string | null;
  recommended_amount?: number | null;
  application_status: string;
  final_admin_decision: string | null;
};

export type AlternativeDataSource = {
  source_type: string;
  label: string;
  requested: string;
  why: string;
  excluded: string;
  mock_available: boolean;
  consent_status: string | null;
  connection_status: string | null;
  connection_mode: string | null;
  connected_at: string | null;
  last_refreshed_at: string | null;
  quality_score: number | null;
  period_start: string | null;
  period_end: string | null;
  active: boolean;
  snapshot?: {
    id: number;
    source_type: string;
    collected_at: string;
    normalized_features: Record<string, unknown>;
    data_quality: Record<string, unknown>;
    provenance: Record<string, unknown>;
  } | null;
};

export type AlternativeDataReadiness = {
  ready: boolean;
  connected_source_count: number;
  connected_sources: string[];
  missing_sources: string[];
  behavioral_data_coverage: number;
  behavioral_assessment_confidence: number;
  message: string;
};

export type AlternativeDataStatus = {
  application_id: number;
  sources: AlternativeDataSource[];
  readiness: AlternativeDataReadiness;
};

export type GrokExplanation = {
  id: number;
  provider: string;
  model: string;
  prompt_version: string;
  status: string;
  structured_response: {
    executive_summary: string;
    approval_recommendation: string;
    risk_drivers: string[];
    supportive_evidence: string[];
    evidence_gaps: string[];
    fair_lending_notes: string[];
    borrower_friendly_summary: string;
    questions_for_officer: string[];
  };
  error_metadata: Record<string, unknown> | null;
  created_at: string;
};

export type AdminApplicationDetail = {
  borrower: AuthUser & { created_at: string };
  application: PlatformApplication & { source_account_id?: number; source_loan_id?: number };
  linked_financial_evidence: Record<string, string | null>;
  alternative_data: AlternativeDataStatus;
  transaction_summary: Record<string, number | string | null>;
  transactions: PlatformTransaction[];
  financial_profile: AnalysisResponse["financial_profile"] | null;
  forecast: AnalysisResponse["forecast"] | null;
  stress_test: AnalysisResponse["stress_test"] | null;
  repayment_envelope: PlatformUnderwriting["repayment_envelope"];
  risk: {
    probability: number | null;
    band: string | null;
    historical_model_probability?: number | null;
    behavioral_probability?: number | null;
    combined_probability?: number | null;
  };
  behavioral_risk: {
    score: number | null;
    score_band?: string | null;
    probability: number | null;
    calibration_status?: string | null;
    coverage: number | null;
    assessment_confidence: number | null;
    source_coverage: Array<Record<string, unknown>>;
    source_component_scores: Array<Record<string, unknown>>;
    factor_contributions: Array<Record<string, unknown>>;
    policy_version: string | null;
  };
  evidence_confidence: { score: number | null; band: string | null };
  nadi_recommendation: {
    decision: string | null;
    recommended_amount: number | null;
    recommended_tenure: number | null;
    recommended_emi: number | null;
    maximum_safe_exposure: number | null;
    reasons: string[];
  };
  explanations: {
    loan_officer: Record<string, unknown> | null;
    borrower: Record<string, unknown> | null;
    grok: GrokExplanation | null;
  };
  admin_decisions: PlatformAdminDecision[];
  audit_history: { id: number; action: string; actor_user_id: number | null; created_at: string; metadata: Record<string, unknown> | null }[];
};

export type PlatformTransaction = {
  date: string;
  type: string;
  operation: string | null;
  amount: number;
  balance: number;
  category: string | null;
};

export function register(payload: {
  name: string;
  email: string;
  phone?: string | null;
  password: string;
}): Promise<RegisterResponse> {
  return platformRequest<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function verifyOtp(email: string, otp: string): Promise<AuthUser> {
  return platformRequest<AuthUser>("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify({ email, otp }),
  });
}

export function resendOtp(email: string): Promise<RegisterResponse> {
  return platformRequest<RegisterResponse>("/auth/resend-otp", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return platformRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function refreshToken(refresh_token: string): Promise<TokenResponse> {
  return platformRequest<TokenResponse>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token }),
  });
}

export function logoutSession(refresh_token: string | null, token: string | null): Promise<{ status: string }> {
  return platformRequest<{ status: string }>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token }),
  }, token);
}

export function getMe(token: string): Promise<AuthUser> {
  return platformRequest<AuthUser>("/auth/me", undefined, token);
}

export function createPlatformApplication(
  payload: Partial<PlatformApplication>,
  token: string,
): Promise<PlatformApplication> {
  return platformRequest<PlatformApplication>("/user/applications", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function updatePlatformApplication(
  id: number,
  payload: Partial<PlatformApplication>,
  token: string,
): Promise<PlatformApplication> {
  return platformRequest<PlatformApplication>(`/user/applications/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  }, token);
}

export function listPlatformApplications(token: string): Promise<PlatformApplication[]> {
  return platformRequest<PlatformApplication[]>("/user/applications", undefined, token);
}

export function getPlatformApplication(id: number, token: string): Promise<PlatformApplication> {
  return platformRequest<PlatformApplication>(`/user/applications/${id}`, undefined, token);
}

export function connectDemoFinancialProfile(id: number, token: string): Promise<Record<string, string | number>> {
  return platformRequest<Record<string, string | number>>(
    `/user/applications/${id}/connect-demo-financial-profile`,
    { method: "POST" },
    token,
  );
}

export function getAlternativeDataStatus(id: number, token: string): Promise<AlternativeDataStatus> {
  return platformRequest<AlternativeDataStatus>(`/user/applications/${id}/alternative-data`, undefined, token);
}

export function grantAlternativeDataConsent(id: number, sourceType: string, token: string): Promise<AlternativeDataSource> {
  return platformRequest<AlternativeDataSource>(`/user/applications/${id}/alternative-data/${sourceType}/consent`, {
    method: "POST",
    body: JSON.stringify({ granted: true }),
  }, token);
}

export function revokeAlternativeDataConsent(id: number, sourceType: string, token: string): Promise<AlternativeDataSource> {
  return platformRequest<AlternativeDataSource>(`/user/applications/${id}/alternative-data/${sourceType}/consent`, {
    method: "DELETE",
  }, token);
}

export function connectMockAlternativeData(id: number, sourceType: string, token: string): Promise<AlternativeDataSource & { underwriting?: PlatformUnderwriting | null }> {
  return platformRequest<AlternativeDataSource & { underwriting?: PlatformUnderwriting | null }>(
    `/user/applications/${id}/alternative-data/${sourceType}/connect-mock`,
    { method: "POST" },
    token,
  );
}

export function refreshAlternativeData(id: number, sourceType: string, token: string): Promise<AlternativeDataSource & { underwriting?: PlatformUnderwriting | null }> {
  return platformRequest<AlternativeDataSource & { underwriting?: PlatformUnderwriting | null }>(
    `/user/applications/${id}/alternative-data/${sourceType}/refresh`,
    { method: "POST" },
    token,
  );
}

export function submitPlatformApplication(id: number, token: string): Promise<{ application: PlatformApplication; underwriting: PlatformUnderwriting }> {
  return platformRequest<{ application: PlatformApplication; underwriting: PlatformUnderwriting }>(
    `/user/applications/${id}/submit`,
    { method: "POST" },
    token,
  );
}

export function getAdminDashboard(token: string): Promise<{ counts: Record<string, number>; recent_applications: AdminApplicationRow[] }> {
  return platformRequest<{ counts: Record<string, number>; recent_applications: AdminApplicationRow[] }>("/admin/dashboard", undefined, token);
}

export function listAdminApplications(
  token: string,
  params?: { status?: string; nadi_decision?: string; risk_band?: string; confidence_band?: string; limit?: number; offset?: number },
): Promise<AdminApplicationRow[]> {
  const search = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  return platformRequest<AdminApplicationRow[]>(`/admin/applications${search.size ? `?${search.toString()}` : ""}`, undefined, token);
}

export function getAdminApplication(id: number, token: string): Promise<AdminApplicationDetail> {
  return platformRequest<AdminApplicationDetail>(`/admin/applications/${id}`, undefined, token);
}

export function getAdminUser(id: number, token: string): Promise<{ user: AuthUser & { created_at: string }; applications: PlatformApplication[] }> {
  return platformRequest<{ user: AuthUser & { created_at: string }; applications: PlatformApplication[] }>(`/admin/users/${id}`, undefined, token);
}

export function analyzeAdminApplication(id: number, token: string): Promise<AdminApplicationDetail> {
  return platformRequest<AdminApplicationDetail>(`/admin/applications/${id}/analyze`, { method: "POST" }, token);
}

export function decideAdminApplication(
  id: number,
  payload: { decision: string; approved_amount?: number | null; approved_tenure?: number | null; approved_emi?: number | null; remarks?: string | null },
  token: string,
): Promise<AdminApplicationDetail> {
  return platformRequest<AdminApplicationDetail>(`/admin/applications/${id}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function getGrokExplanation(id: number, token: string): Promise<GrokExplanation> {
  return platformRequest<GrokExplanation>(`/admin/applications/${id}/grok-explanation`, undefined, token);
}

export function generateGrokExplanation(id: number, token: string): Promise<GrokExplanation> {
  return platformRequest<GrokExplanation>(`/admin/applications/${id}/grok-explanation`, { method: "POST" }, token);
}

export function getBorrowers(): Promise<BorrowerSummary[]> {
  return request<BorrowerSummary[]>("/borrowers?limit=50");
}

export function analyzeApplication(applicationId: number): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(`/applications/${applicationId}/analyze`, {
    method: "POST",
  });
}

export function runDemoSimulation(
  applicationId: number,
  action: DemoAction,
): Promise<DemoSimulationResponse> {
  return request<DemoSimulationResponse>(`/applications/${applicationId}/demo-simulation`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}
