export interface Collector {
  id: number;
  full_name: string;
  email: string;
  region: string;
}

export type CustomerStatus =
  | 'Active'
  | 'Past Due'
  | 'In Dispute'
  | 'Promise to Pay'
  | 'Collections Hold'
  | 'Closed';

export interface CustomerSummary {
  id: number;
  account_number: string;
  full_name: string;
  company_name: string | null;
  phone_number: string;
  status: CustomerStatus;
  ar_balance: string;
  overdue_amount: string;
  days_past_due: number;
  risk_level: 'Low' | 'Medium' | 'High';
  last_contact_date: string | null;
}

export interface Customer extends CustomerSummary {
  collector_id: number;
  alternate_phone_number: string | null;
  email: string;
  address: string;
  shipping_address: string | null;
  home_address: string | null;
  office_address: string | null;
}

export interface PaymentCommitment {
  amount: number | null;
  due_date: string | null;
  method: string | null;
  invoices: string[];
  confidence: 'High' | 'Medium' | 'Low';
}

export interface Risk {
  category: string;
  description: string;
  severity: 'High' | 'Medium' | 'Low';
}

export interface FollowUpAction {
  action: string;
  owner: string;
  due_date: string | null;
}

export type Sentiment = 'Positive' | 'Neutral' | 'Negative';

export interface CallLogListItem {
  id: number;
  call_datetime: string;
  duration_seconds: number;
  direction: 'Inbound' | 'Outbound';
  sentiment: Sentiment | null;
  call_outcome: string | null;
  analysis_status: 'Pending' | 'Completed' | 'Failed';
  audio_filename: string | null;
}

export interface CallLog extends CallLogListItem {
  customer_id: number;
  collector_id: number;
  transcript: string | null;
  call_log_summary: string | null;
  interaction_notes: string | null;
  sentiment_score: number | null;
  payment_commitments: PaymentCommitment[] | null;
  risks: Risk[] | null;
  follow_up_actions: FollowUpAction[] | null;
  dispute_raised: boolean;
  analysis_engine: string | null;
  analysis_error: string | null;
  analyzed_at: string | null;
}

export interface PortfolioInsights {
  customer_count: number;
  total_ar_balance: string;
  total_overdue: string;
  high_risk_customers: number;
  customers_in_dispute: number;
  calls_analyzed: number;
  calls_pending_analysis: number;
  open_commitment_amount: number;
  open_commitment_count: number;
  sentiment_breakdown: Record<string, number>;
  outcome_breakdown: Record<string, number>;
  top_risks: (Risk & { customer_id: number; customer_name: string; call_id: number })[];
  upcoming_commitments: (PaymentCommitment & { customer_id: number; customer_name: string; call_id: number })[];
}
