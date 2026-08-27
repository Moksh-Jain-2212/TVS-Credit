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
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
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
