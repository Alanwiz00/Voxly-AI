import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: BASE_URL });

// Cache the backend token for the session lifetime
let _cachedToken: string | null = null;

async function getBackendToken(): Promise<string | null> {
  if (_cachedToken) return _cachedToken;
  try {
    const res = await fetch("/api/auth/backend-token");
    if (!res.ok) return null;
    const data = await res.json();
    _cachedToken = data.token ?? null;
    return _cachedToken;
  } catch {
    return null;
  }
}

export function clearTokenCache() {
  _cachedToken = null;
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
  created_at: string;
}

export interface Persona {
  id: number;
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
    idea_count?: number;
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
  delete: (id: number) => api.delete(`/content/${id}`),
};

// Persona
export const personaApi = {
  get: () => api.get<Persona | null>("/persona/"),
  upsert: (data: Partial<Persona>) => api.put<Persona>("/persona/", data),
  synthesizeStyle: () => api.post<Persona>("/persona/synthesize-style"),
};

// Users / allowed emails
export const usersApi = {
  me: () => api.get("/users/me"),
  listAllowedEmails: () => api.get("/users/allowed-emails"),
  addAllowedEmail: (email: string) => api.post("/users/allowed-emails", { email }),
  removeAllowedEmail: (email: string) => api.delete(`/users/allowed-emails/${email}`),
};
