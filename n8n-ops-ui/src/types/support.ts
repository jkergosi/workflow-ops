// Support request types

export type IntentKind = 'bug' | 'feature' | 'task';
export type Severity = 'sev1' | 'sev2' | 'sev3' | 'sev4';
export type Frequency = 'once' | 'intermittent' | 'always';
export type Priority = 'low' | 'medium' | 'high';

export interface Attachment {
  name: string;
  url: string;
  content_type: string;
}

export interface BugReportCreate {
  title: string;
  what_happened: string;
  expected_behavior: string;
  steps_to_reproduce?: string;
  severity?: Severity;
  frequency?: Frequency;
  include_diagnostics: boolean;
  attachments?: Attachment[];
}

export interface FeatureRequestCreate {
  title: string;
  problem_goal: string;
  desired_outcome: string;
  priority?: Priority;
  acceptance_criteria?: string[];
  who_is_this_for?: string;
}

export interface HelpRequestCreate {
  title: string;
  details: string;
  include_diagnostics: boolean;
  attachments?: Attachment[];
}

export interface Diagnostics {
  app_id: string;
  app_env: string;
  app_version?: string;
  git_sha?: string;
  route: string;
  correlation_id: string;
  tenant_id?: string;
  workspace_id?: string;
}

export interface SupportRequestCreate {
  intent_kind: IntentKind;
  bug_report?: BugReportCreate;
  feature_request?: FeatureRequestCreate;
  help_request?: HelpRequestCreate;
  diagnostics?: Diagnostics;
}

export interface SupportRequestResponse {
  jsm_request_key: string;
}

export interface UploadUrlRequest {
  filename: string;
  content_type: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  public_url: string;
}

// Admin config types
export interface SupportConfig {
  tenant_id: string;
  n8n_webhook_url?: string;
  n8n_api_key?: string;
  jsm_portal_url?: string;
  jsm_cloud_instance?: string;
  jsm_api_token?: string;
  jsm_project_key?: string;
  jsm_bug_request_type_id?: string;
  jsm_feature_request_type_id?: string;
  jsm_help_request_type_id?: string;
  jsm_widget_embed_code?: string;
  updated_at?: string;
}

export interface SupportConfigUpdate {
  n8n_webhook_url?: string;
  n8n_api_key?: string;
  jsm_portal_url?: string;
  jsm_cloud_instance?: string;
  jsm_api_token?: string;
  jsm_project_key?: string;
  jsm_bug_request_type_id?: string;
  jsm_feature_request_type_id?: string;
  jsm_help_request_type_id?: string;
  jsm_widget_embed_code?: string;
}

export interface TestConnectionResult {
  success: boolean;
  message: string;
}
