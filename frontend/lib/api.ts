import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: BASE_URL });

// Cache the short-lived backend token until shortly before it expires
let _cachedToken: string | null = null;
let _tokenExpiresAt = 0;

async function getBackendToken(): Promise<string | null> {
  if (_cachedToken && Date.now() < _tokenExpiresAt) return _cachedToken;
  try {
    const res = await fetch("/api/auth/backend-token", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    _cachedToken = data.token ?? null;
    // Refresh a minute early; uses the local clock so client/server skew doesn't matter
    _tokenExpiresAt = Date.now() + ((data.expires_in ?? 0) - 60) * 1000;
    return _cachedToken;
  } catch {
    return null;
  }
}

export function clearTokenCache() {
  _cachedToken = null;
  _tokenExpiresAt = 0;
}

api.interceptors.request.use(async (config) => {
  const token = await getBackendToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Types
export type Platform = "twitter" | "instagram" | "facebook" | "telegram";
export type ContentType = "idea" | "long_form" | "thread" | "article";

export interface Topic {
  id: number;
  name: string;
  keywords: string | null;
  description: string | null;
  is_active: boolean;
  last_crawled_at: string | null;
}

export interface GeneratedContent {
  id: number;
  platform: Platform;
  content_type: ContentType;
  title: string | null;
  content: string;
  meta: Record<string, unknown>;
  version: number;
  parent_id: number | null;
  rating?: number | null;
  created_at: string;
}

export interface Persona {
  id: number;
  name: string;
  is_default: boolean;
  niche: string | null;
  target_audience: string | null;
  tone: string | null;
  brand_voice: string | null;
  writing_style_notes: string | null;
  sample_content: string | null;
  learned_style: string | null;
  style_synthesized_at: string | null;
}

// Topics
export const topicsApi = {
  list: () => api.get<Topic[]>("/topics/"),
  create: (data: Partial<Topic>) => api.post<Topic>("/topics/", data),
  update: (id: number, data: Partial<Topic>) => api.patch<Topic>(`/topics/${id}`, data),
  delete: (id: number) => api.delete(`/topics/${id}`),
  crawl: (id: number) => api.post(`/topics/${id}/crawl`),
  flushQueue: () => api.post("/topics/flush"),
  crawlResults: (id: number) => api.get(`/topics/${id}/crawl-results`),
  generatedContent: (id: number) => api.get<GeneratedContent[]>(`/topics/${id}/content`),
};

// Content generation
export const generateApi = {
  generate: (data: {
    topic_id?: number;
    topic_name?: string;
    platform: Platform;
    content_type: ContentType;
    persona_id?: number;
  }) => api.post<{ content_type: ContentType; results: GeneratedContent[] }>("/generate/", data),
  fromSource: (form: FormData) =>
    api.post<{ content_type: ContentType; results: GeneratedContent[] }>("/generate/from-source", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};

// Content history & re-edit
export const contentApi = {
  list: (params?: { platform?: Platform; content_type?: ContentType; limit?: number; offset?: number }) =>
    api.get<GeneratedContent[]>("/content/", { params }),
  get: (id: number) => api.get<GeneratedContent & { versions: unknown[] }>(`/content/${id}`),
  reEdit: (id: number, instruction: string) =>
    api.post<GeneratedContent>(`/content/${id}/re-edit`, { instruction }),
  adapt: (id: number, platform: Platform) =>
    api.post<GeneratedContent>(`/content/${id}/adapt`, { platform }),
  summarize: (id: number, platform: Platform) =>
    api.post<GeneratedContent>(`/content/${id}/summarize`, { platform }),
  delete: (id: number) => api.delete(`/content/${id}`),
  rate: (id: number, rating: number) => api.post<GeneratedContent>(`/content/${id}/rate`, { rating }),
};

// Persona
export const personaApi = {
  list: () => api.get<Persona[]>("/persona/"),
  create: (data: Partial<Persona> & { name: string }) => api.post<Persona>("/persona/", data),
  update: (id: number, data: Partial<Persona>) => api.put<Persona>(`/persona/${id}`, data),
  delete: (id: number) => api.delete(`/persona/${id}`),
  setDefault: (id: number) => api.post<Persona>(`/persona/${id}/set-default`),
  synthesizeStyle: (id: number) => api.post<Persona>(`/persona/${id}/synthesize-style`),
};

// Users / allowed emails
export interface CurrentUser {
  id: number;
  email: string;
  name: string | null;
  is_admin: boolean;
}

export const usersApi = {
  me: () => api.get<CurrentUser>("/users/me"),
  listAllowedEmails: () => api.get("/users/allowed-emails"),
  addAllowedEmail: (email: string) => api.post("/users/allowed-emails", { email }),
  removeAllowedEmail: (email: string) => api.delete(`/users/allowed-emails/${email}`),
};

// API Keys
export interface ApiKeyRecord {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  key?: string | null;
}

export const apiKeysApi = {
  list: () => api.get<ApiKeyRecord[]>("/api-keys/"),
  create: (name: string) => api.post<ApiKeyRecord>("/api-keys/", { name }),
  revoke: (id: number) => api.delete(`/api-keys/${id}`),
};

// Listening & outreach (admin only)
export type OutreachIntent = "any" | "seeking_live_alerts" | "seeking_tips" | "tipster_complaint" | "odds_discussion";

export interface ListeningCampaign {
  id: number;
  name: string;
  x_query: string;
  harm_terms: string[];
  allowed_markets: string[];
  link_base: string;
  daily_cap: number;
  monthly_budget_usd: number;
  max_results_per_poll: number;
  poll_every_minutes: number;
  last_polled_at: string | null;
  status: "active" | "paused";
  spend_this_month_usd: number;
  pace_allowance_usd: number;
  queued: number;
  sent_today: number;
  created_at: string | null;
}

export type ListeningCampaignInput = Pick<
  ListeningCampaign,
  "name" | "x_query" | "harm_terms" | "allowed_markets" | "link_base" | "daily_cap" | "monthly_budget_usd" | "max_results_per_poll" | "poll_every_minutes"
>;

export interface OutreachTemplate {
  id: number;
  campaign_id: number;
  name: string;
  intent: OutreachIntent;
  body: string;
  arcon_cert_no: string | null;
  approved: boolean;
  approved_at: string | null;
  active: boolean;
}

export interface OutreachProof {
  alertId: string;
  match: string;
  alertType: string;
  minuteAtFire: number | null;
  firedAt: string | null;
  outcome: string;
  proofUrl: string | null;
}

export interface OutreachDraft {
  id: number;
  code: string;
  text: string | null;
  proof: OutreachProof | null;
  status: "queued" | "sent" | "skipped";
  edited: boolean;
  sent_at: string | null;
  reply_url: string | null;
  post: {
    id: string;
    author_id: string | null;
    author_handle: string | null;
    text: string | null;
    posted_at: string | null;
    matched_terms: string[];
    verdict: { intent?: string; market?: string; confidence?: number; teams?: string[] } | null;
  };
}

export interface CampaignStats {
  posts_found: number;
  stages: Record<string, number>;
  drop_reasons: Record<string, number>;
  sent: number;
  events: Record<string, number>;
  spend_this_month_usd: number;
  cost_per_reply_usd: number | null;
}

export const listeningApi = {
  campaigns: () =>
    api.get<{ campaigns: ListeningCampaign[]; spend_this_month_usd: number; monthly_budget_usd: number; x_configured: boolean }>(
      "/listening/campaigns"
    ),
  createCampaign: (data: ListeningCampaignInput) => api.post<ListeningCampaign>("/listening/campaigns", data),
  updateCampaign: (id: number, data: Partial<ListeningCampaignInput & { status: "active" | "paused" }>) =>
    api.patch<ListeningCampaign>(`/listening/campaigns/${id}`, data),
  pauseAll: () => api.post<{ paused: number }>("/listening/pause-all"),
  size: (id: number) =>
    api.post<{ posts_last_7_days: number; est_posts_per_month: number; est_read_cost_per_month_usd: number }>(
      `/listening/campaigns/${id}/size`
    ),
  pollNow: (id: number) => api.post<{ read: number; dropped: number; drafted: number }>(`/listening/campaigns/${id}/poll`),
  stats: (id: number) => api.get<CampaignStats>(`/listening/campaigns/${id}/stats`),
  templates: (campaignId: number) => api.get<OutreachTemplate[]>(`/listening/campaigns/${campaignId}/templates`),
  createTemplate: (
    campaignId: number,
    data: { name: string; intent: OutreachIntent; body: string; arcon_cert_no?: string | null }
  ) => api.post<OutreachTemplate>(`/listening/campaigns/${campaignId}/templates`, data),
  updateTemplate: (id: number, data: Partial<Pick<OutreachTemplate, "name" | "intent" | "body" | "arcon_cert_no" | "active">>) =>
    api.patch<OutreachTemplate>(`/listening/templates/${id}`, data),
  queue: (campaignId: number) =>
    api.get<{ campaign: { id: number; name: string; status: string }; daily_cap: number; sent_today: number; drafts: OutreachDraft[] }>(
      `/listening/campaigns/${campaignId}/queue`
    ),
  editDraft: (id: number, text: string) => api.patch<OutreachDraft>(`/listening/drafts/${id}`, { text }),
  markSent: (id: number, reply_url?: string) => api.post<OutreachDraft>(`/listening/drafts/${id}/sent`, { reply_url: reply_url || null }),
  skip: (id: number, do_not_contact = false) => api.post<OutreachDraft>(`/listening/drafts/${id}/skip`, { do_not_contact }),
};
