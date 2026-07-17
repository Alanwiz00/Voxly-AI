"use client";
import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Save, Plus, BrainCircuit, RefreshCw, Star, Trash2,
  ChevronDown, ChevronUp, KeyRound, Copy, Check, Eye, EyeOff, Clock,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { personaApi, usersApi, apiKeysApi, topicsApi, type Persona, type ApiKeyRecord, type Topic } from "@/lib/api";
import { cn } from "@/lib/utils";

const EMPTY_PERSONA: Partial<Persona> = {
  name: "", niche: "", tone: "", target_audience: "",
  brand_voice: "", writing_style_notes: "", sample_content: "",
};

const TOPIC_LIMIT = 3;

type SettingsTab = "personas" | "topics" | "api";

// ── Tab bar ──────────────────────────────────────────────────────────────────

function TabBar({ active, isAdmin, onChange }: {
  active: SettingsTab;
  isAdmin: boolean;
  onChange: (t: SettingsTab) => void;
}) {
  const tabs: { id: SettingsTab; label: string; adminOnly?: boolean }[] = [
    { id: "personas", label: "Personas" },
    { id: "topics", label: "Topics" },
    { id: "api", label: "API Keys" },
  ];
  return (
    <div className="flex border-b border-border overflow-x-auto scrollbar-none">
      {tabs.filter((t) => !t.adminOnly || isAdmin).map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap",
            active === t.id
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Persona components (unchanged logic) ─────────────────────────────────────

function PersonaForm({ initial, onSave, onCancel, saving, isNew }: {
  initial: Partial<Persona>;
  onSave: (data: Partial<Persona>) => Promise<void>;
  onCancel: () => void;
  saving: boolean;
  isNew?: boolean;
}) {
  const [form, setForm] = useState<Partial<Persona>>(initial);
  const set = (key: keyof Persona) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  return (
    <div className="space-y-4 pt-2">
      <div className="space-y-1">
        <label className="text-sm font-medium">Persona Name</label>
        <Input placeholder="e.g. Tech Founder, Health Coach, LinkedIn Pro" value={form.name || ""} onChange={set("name")} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">Niche / Industry</label>
          <Input placeholder="e.g. SaaS, Healthcare, Fitness" value={form.niche || ""} onChange={set("niche")} />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Tone</label>
          <Input placeholder="e.g. Professional, Casual, Humorous" value={form.tone || ""} onChange={set("tone")} />
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Target Audience</label>
        <Input placeholder="e.g. Tech founders aged 25-40, early adopters" value={form.target_audience || ""} onChange={set("target_audience")} />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Brand Voice</label>
        <Textarea placeholder="Describe your brand voice in detail..." rows={3} value={form.brand_voice || ""} onChange={set("brand_voice")} />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Writing Style Notes</label>
        <Textarea placeholder="Short sentences, stories, PAS/AIDA frameworks, emojis..." rows={3} value={form.writing_style_notes || ""} onChange={set("writing_style_notes")} />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Sample Content</label>
        <Textarea placeholder="Paste 3-5 examples of your best posts. Separate with a blank line." rows={6} value={form.sample_content || ""} onChange={set("sample_content")} />
        <p className="text-xs text-muted-foreground">Separate examples with a blank line</p>
      </div>
      <div className="flex gap-2">
        <Button onClick={() => onSave(form)} disabled={saving || !form.name?.trim()}>
          <Save className="w-4 h-4 mr-2" />
          {saving ? "Saving..." : isNew ? "Create Persona" : "Save Changes"}
        </Button>
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function PersonaCard({ persona, onUpdated, onDeleted, onSetDefault }: {
  persona: Persona;
  onUpdated: (p: Persona) => void;
  onDeleted: (id: number) => void;
  onSetDefault: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);

  const save = async (data: Partial<Persona>) => {
    setSaving(true);
    try {
      const res = await personaApi.update(persona.id, data);
      onUpdated(res.data);
      setExpanded(false);
      toast.success("Persona saved");
    } catch { toast.error("Failed to save persona"); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!confirm(`Delete "${persona.name}"? This cannot be undone.`)) return;
    try {
      await personaApi.delete(persona.id);
      onDeleted(persona.id);
      toast.success("Persona deleted");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Failed to delete persona");
    }
  };

  const synthesize = async () => {
    setSynthesizing(true);
    try {
      const res = await personaApi.synthesizeStyle(persona.id);
      onUpdated(res.data);
      toast.success("Style profile updated from your ratings");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Rate at least 3 posts first to build a style profile");
    } finally { setSynthesizing(false); }
  };

  return (
    <Card className={persona.is_default ? "border-indigo-300 bg-indigo-50/30 dark:bg-indigo-950/20" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">{persona.name}</CardTitle>
            {persona.is_default && (
              <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                <Star className="w-3 h-3" /> Default
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {!persona.is_default && (
              <Button variant="ghost" size="sm" className="text-xs text-slate-500" onClick={() => onSetDefault(persona.id)}>
                Set default
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={() => setExpanded((v) => !v)}>
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </Button>
            {!persona.is_default && (
              <Button variant="ghost" size="icon" onClick={remove}>
                <Trash2 className="w-4 h-4 text-red-400" />
              </Button>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {[persona.niche, persona.tone, persona.target_audience].filter(Boolean).join(" · ") || "No details yet. Click to edit."}
        </p>
      </CardHeader>
      {expanded && (
        <CardContent className="space-y-4 border-t pt-4">
          <PersonaForm initial={persona} onSave={save} onCancel={() => setExpanded(false)} saving={saving} />
          <div className="border-t pt-4 space-y-3">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-indigo-500" />
              <p className="text-sm font-medium">Style Learning</p>
            </div>
            {persona.learned_style ? (
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <p className="text-xs text-muted-foreground">Learned from your ratings</p>
                  {persona.style_synthesized_at && (
                    <span className="text-xs text-muted-foreground">
                      Updated {new Date(persona.style_synthesized_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className="bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 rounded-lg p-3">
                  <pre className="text-xs font-sans text-indigo-900 dark:text-indigo-200 whitespace-pre-wrap leading-relaxed">{persona.learned_style}</pre>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No learned style yet. Rate at least 3 generated posts and VoxlyAI will automatically build a style profile that improves every future generation.
              </p>
            )}
            <Button variant="outline" size="sm" onClick={synthesize} disabled={synthesizing}>
              <RefreshCw className={`w-3 h-3 mr-2 ${synthesizing ? "animate-spin" : ""}`} />
              {synthesizing ? "Analysing..." : "Refresh Style Now"}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// ── Topics section ────────────────────────────────────────────────────────────

function TopicsSection({ isAdmin }: { isAdmin: boolean }) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", keywords: "" });
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [recrawlingId, setRecrawlingId] = useState<number | null>(null);
  const [flushing, setFlushing] = useState(false);

  const load = useCallback(async () => {
    const res = await topicsApi.list();
    setTopics(res.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const atLimit = !isAdmin && topics.length >= TOPIC_LIMIT;

  const create = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      await topicsApi.create({ name: form.name.trim(), keywords: form.keywords.trim() || undefined });
      setForm({ name: "", keywords: "" });
      setShowForm(false);
      await load();
      toast.success("Topic created. It will be crawled automatically.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Failed to create topic");
    } finally { setCreating(false); }
  };

  const remove = async (id: number) => {
    setDeletingId(id);
    try {
      await topicsApi.delete(id);
      setTopics((prev) => prev.filter((t) => t.id !== id));
      toast.success("Topic deleted");
    } catch { toast.error("Failed to delete topic"); }
    finally { setDeletingId(null); }
  };

  const recrawl = async (id: number) => {
    setRecrawlingId(id);
    try {
      await topicsApi.crawl(id);
      toast.success("Crawl queued. Results will appear after the job completes.");
    } catch { toast.error("Failed to queue crawl"); }
    finally { setRecrawlingId(null); }
  };

  const flushQueue = async () => {
    setFlushing(true);
    try {
      const res = await topicsApi.flushQueue();
      const count = (res.data as { queued: number }).queued;
      toast.success(`Re-queued ${count} topic${count !== 1 ? "s" : ""} for immediate crawl.`);
    } catch { toast.error("Failed to flush queue"); }
    finally { setFlushing(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            Topics are crawled every 12 hours. Use them as source context when generating content.
          </p>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground mt-1">
              <span className={cn(
                "font-medium",
                topics.length >= TOPIC_LIMIT ? "text-amber-600 dark:text-amber-400" : "text-foreground"
              )}>
                {topics.length} of {TOPIC_LIMIT}
              </span>{" "}topics used
            </p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {isAdmin && (
            <Button
              size="sm"
              variant="outline"
              onClick={flushQueue}
              disabled={flushing || topics.length === 0}
              title="Re-queue all topics for immediate crawl — use when jobs appear stuck"
            >
              <RefreshCw className={`w-4 h-4 mr-1.5 ${flushing ? "animate-spin" : ""}`} />
              {flushing ? "Flushing..." : "Flush Queue"}
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => setShowForm(true)}
            disabled={showForm || atLimit}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Add Topic
          </Button>
        </div>
      </div>

      {atLimit && (
        <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
          You have reached the 3-topic limit. Delete an existing topic to add a new one.
        </div>
      )}

      {showForm && (
        <Card className="border-dashed">
          <CardContent className="pt-4 space-y-3">
            <Input
              placeholder="Topic name (e.g. AI in healthcare)"
              value={form.name}
              autoFocus
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              onKeyDown={(e) => e.key === "Enter" && create()}
            />
            <Input
              placeholder="Keywords, comma-separated (optional)"
              value={form.keywords}
              onChange={(e) => setForm((f) => ({ ...f, keywords: e.target.value }))}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={create} disabled={creating || !form.name.trim()}>
                {creating ? "Creating..." : "Create"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setShowForm(false); setForm({ name: "", keywords: "" }); }}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {topics.length === 0 && !showForm ? (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center text-muted-foreground text-sm">
            No topics yet. Add one to start crawling content automatically.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {topics.map((topic) => (
            <div key={topic.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border bg-card">
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-foreground">{topic.name}</span>
                  {topic.is_active && <Badge variant="secondary" className="text-xs">Active</Badge>}
                </div>
                {topic.keywords && (
                  <p className="text-xs text-muted-foreground truncate">
                    {topic.keywords}
                  </p>
                )}
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3 flex-shrink-0" />
                  {topic.last_crawled_at
                    ? `Last crawled ${new Date(topic.last_crawled_at).toLocaleString()}`
                    : "Not yet crawled"}
                </div>
              </div>
              {isAdmin && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 h-8 w-8"
                  disabled={recrawlingId === topic.id}
                  onClick={() => recrawl(topic.id)}
                  title="Re-queue this topic for immediate crawl"
                >
                  <RefreshCw className={`w-4 h-4 text-muted-foreground ${recrawlingId === topic.id ? "animate-spin" : ""}`} />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 h-8 w-8"
                disabled={deletingId === topic.id}
                onClick={() => remove(topic.id)}
              >
                <Trash2 className="w-4 h-4 text-red-400" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── API Keys section ──────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={copy}>
      {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
    </Button>
  );
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://your-api-domain.com";

const SNIPPET_AUTH = `Authorization: Bearer YOUR_API_KEY`;

const SNIPPET_GENERATE = `curl -X POST ${API_BASE}/generate/ \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "platform": "twitter",
    "content_type": "idea",
    "topic_name": "AI productivity tools"
  }'`;

const SNIPPET_PLATFORMS = `"platform": "twitter" | "instagram" | "facebook" | "telegram"`;
const SNIPPET_TYPES = `"content_type": "idea" | "long_form" | "thread" | "article"`;

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative group">
      {label && <p className="text-xs text-muted-foreground mb-1 font-medium">{label}</p>}
      <pre className="bg-slate-900 dark:bg-slate-950 text-slate-100 text-xs rounded-md p-3 overflow-x-auto leading-relaxed whitespace-pre">
        {code}
      </pre>
      <button
        onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-700 hover:bg-slate-600 text-slate-200 rounded px-1.5 py-0.5 text-xs flex items-center gap-1"
      >
        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function ApiGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
      >
        <span className="flex items-center gap-2 text-muted-foreground">
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
          How to use the API
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t pt-4">
          <div>
            <p className="text-xs text-muted-foreground mb-3">
              Pass your API key as a Bearer token in every request header.
            </p>
            <CodeBlock code={SNIPPET_AUTH} label="Authentication header" />
          </div>

          <div>
            <p className="text-xs font-medium mb-1">Generate content</p>
            <p className="text-xs text-muted-foreground mb-2">
              POST to <code className="bg-muted px-1 rounded">/generate/</code> with a platform, content type, and topic.
            </p>
            <CodeBlock code={SNIPPET_GENERATE} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <CodeBlock code={SNIPPET_PLATFORMS} label="Platforms" />
            <CodeBlock code={SNIPPET_TYPES} label="Content types" />
          </div>

          <div className="rounded-md bg-muted/50 px-3 py-2.5 text-xs text-muted-foreground space-y-1">
            <p><span className="font-medium text-foreground">topic_id</span> — use a saved topic ID instead of topic_name for crawled context</p>
            <p><span className="font-medium text-foreground">persona_id</span> — pin a specific persona; omit to auto-select</p>
            <p><span className="font-medium text-foreground">idea</span> type returns 3 posts; all other types return 1</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ApiIdsReference() {
  const [open, setOpen] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      topicsApi.list().then((r) => setTopics(r.data)),
      personaApi.list().then((r) => setPersonas(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const hasTopics = topics.length > 0;
  const hasPersonas = personas.length > 0;

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors text-muted-foreground"
      >
        <ChevronDown className={`w-4 h-4 transition-transform shrink-0 ${open ? "rotate-180" : ""}`} />
        Your topic &amp; persona IDs
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t pt-4">
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-9 bg-muted rounded-md animate-pulse" />
              ))}
            </div>
          ) : !hasTopics && !hasPersonas ? (
            <p className="text-xs text-muted-foreground">
              No topics or personas yet. Add them in the Topics and Personas tabs, then come back here to copy their IDs for use in API requests.
            </p>
          ) : (
            <>
              {hasTopics && (
                <div>
                  <p className="text-xs font-medium text-foreground mb-2">Topics</p>
                  <div className="space-y-1.5">
                    {topics.map((t) => (
                      <div key={t.id} className="flex items-center justify-between gap-3 px-3 py-2 bg-muted/40 rounded-md">
                        <span className="text-sm truncate flex-1">{t.name}</span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <code className="text-xs font-mono text-muted-foreground">topic_id: {t.id}</code>
                          <CopyButton text={String(t.id)} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {hasPersonas && (
                <div>
                  <p className="text-xs font-medium text-foreground mb-2">Personas</p>
                  <div className="space-y-1.5">
                    {personas.map((p) => (
                      <div key={p.id} className="flex items-center justify-between gap-3 px-3 py-2 bg-muted/40 rounded-md">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <span className="text-sm truncate">{p.name}</span>
                          {p.is_default && (
                            <span className="text-xs text-muted-foreground shrink-0">(default)</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <code className="text-xs font-mono text-muted-foreground">persona_id: {p.id}</code>
                          <CopyButton text={String(p.id)} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ApiKeysSection({ apiKeys, setApiKeys }: {
  apiKeys: ApiKeyRecord[];
  setApiKeys: React.Dispatch<React.SetStateAction<ApiKeyRecord[]>>;
}) {
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [revealedKey, setRevealedKey] = useState<{ id: number; key: string } | null>(null);
  const [showKeyValue, setShowKeyValue] = useState(false);

  const create = async () => {
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const res = await apiKeysApi.create(newKeyName.trim());
      const record = res.data;
      setApiKeys((prev) => [record, ...prev]);
      setNewKeyName("");
      if (record.key) { setRevealedKey({ id: record.id, key: record.key }); setShowKeyValue(false); }
      toast.success("API key created. Copy it now, it won't be shown again.");
    } catch { toast.error("Failed to create API key"); }
    finally { setCreating(false); }
  };

  const revoke = async (id: number, name: string) => {
    if (!confirm(`Revoke "${name}"? Any agent using this key will lose access immediately.`)) return;
    try {
      await apiKeysApi.revoke(id);
      setApiKeys((prev) => prev.filter((k) => k.id !== id));
      if (revealedKey?.id === id) setRevealedKey(null);
      toast.success("API key revoked");
    } catch { toast.error("Failed to revoke API key"); }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <KeyRound className="w-5 h-5 text-indigo-500" />
          <div>
            <CardTitle>API Keys</CardTitle>
            <CardDescription className="mt-0.5">
              Let AI agents and external tools generate content on your behalf.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder='e.g. My App, Automation Bot, Website'
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
          <Button onClick={create} disabled={creating || !newKeyName.trim()}>
            <Plus className="w-4 h-4 mr-2" />
            {creating ? "Creating..." : "Create"}
          </Button>
        </div>
        {revealedKey && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 p-3 space-y-2">
            <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
              Copy your key now. It will never be shown again.
            </p>
            <div className="flex items-center gap-2 bg-white dark:bg-slate-900 rounded-md border px-3 py-2">
              <code className="flex-1 text-xs font-mono text-slate-800 dark:text-slate-200 break-all select-all">
                {showKeyValue ? revealedKey.key : revealedKey.key.slice(0, 13) + "•".repeat(20)}
              </code>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => setShowKeyValue((v) => !v)}>
                {showKeyValue ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </Button>
              <CopyButton text={revealedKey.key} />
            </div>
            <Button variant="ghost" size="sm" className="text-xs text-muted-foreground h-6" onClick={() => setRevealedKey(null)}>
              Done, I've saved it
            </Button>
          </div>
        )}
        {apiKeys.length === 0 ? (
          <p className="text-sm text-muted-foreground">No API keys yet. Create one above.</p>
        ) : (
          <div className="space-y-2">
            {apiKeys.map((k) => (
              <div key={k.id} className="flex items-center justify-between px-3 py-2.5 bg-muted/40 rounded-md gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{k.name}</p>
                  <p className="text-xs text-muted-foreground font-mono mt-0.5">
                    {k.key_prefix}••••••••••••
                    <span className="font-sans ml-3">
                      {k.last_used_at
                        ? `Last used ${new Date(k.last_used_at).toLocaleDateString()}`
                        : `Created ${new Date(k.created_at).toLocaleDateString()}`}
                    </span>
                  </p>
                </div>
                <Button variant="ghost" size="icon" className="shrink-0" onClick={() => revoke(k.id, k.name)}>
                  <Trash2 className="w-4 h-4 text-red-400" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Usage guide */}
        <ApiGuide />

        {/* Topic & Persona ID reference */}
        <ApiIdsReference />
      </CardContent>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [showNewPersonaForm, setShowNewPersonaForm] = useState(false);
  const [creatingPersona, setCreatingPersona] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([]);

  const initialTab = (searchParams.get("tab") as SettingsTab | null) ?? "personas";
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  const switchTab = (tab: SettingsTab) => {
    setActiveTab(tab);
    router.replace(`/settings?tab=${tab}`, { scroll: false });
  };

  useEffect(() => {
    personaApi.list().then((r) => setPersonas(r.data));
    apiKeysApi.list().then((res) => setApiKeys(res.data));
    usersApi.me().then((r) => {
      if (r.data.is_admin) setIsAdmin(true);
    });
  }, []);

  const createPersona = async (data: Partial<Persona>) => {
    setCreatingPersona(true);
    try {
      const res = await personaApi.create({ ...data, name: data.name || "Default" });
      setPersonas((prev) => [...prev, res.data]);
      setShowNewPersonaForm(false);
      toast.success("Persona created");
    } catch { toast.error("Failed to create persona"); }
    finally { setCreatingPersona(false); }
  };

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your personas, topics, and account</p>
      </div>

      <TabBar active={activeTab} isAdmin={isAdmin} onChange={switchTab} />

      {/* Personas tab */}
      {activeTab === "personas" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              The AI auto-selects the best persona for each topic. The default is used as fallback.
            </p>
            <Button onClick={() => setShowNewPersonaForm(true)} disabled={showNewPersonaForm} size="sm">
              <Plus className="w-4 h-4 mr-2" />
              New Persona
            </Button>
          </div>

          {showNewPersonaForm && (
            <Card className="border-dashed border-indigo-300">
              <CardHeader>
                <CardTitle className="text-base">Create New Persona</CardTitle>
                <CardDescription>Give it a distinct name so you can identify it easily.</CardDescription>
              </CardHeader>
              <CardContent>
                <PersonaForm
                  initial={{ ...EMPTY_PERSONA }}
                  onSave={createPersona}
                  onCancel={() => setShowNewPersonaForm(false)}
                  saving={creatingPersona}
                  isNew
                />
              </CardContent>
            </Card>
          )}

          {personas.length === 0 && !showNewPersonaForm && (
            <Card className="border-dashed">
              <CardContent className="py-10 text-center text-muted-foreground">
                <p>No personas yet. Create one to generate content in your voice.</p>
              </CardContent>
            </Card>
          )}

          {personas.map((p) => (
            <PersonaCard
              key={p.id}
              persona={p}
              onUpdated={(updated) => setPersonas((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))}
              onDeleted={(id) => setPersonas((prev) => prev.filter((x) => x.id !== id))}
              onSetDefault={async (id) => {
                try {
                  const res = await personaApi.setDefault(id);
                  setPersonas((prev) => prev.map((x) => ({ ...x, is_default: x.id === id })));
                  toast.success(`"${res.data.name}" is now your default persona`);
                } catch { toast.error("Failed to set default"); }
              }}
            />
          ))}
        </div>
      )}

      {/* Topics tab */}
      {activeTab === "topics" && <TopicsSection isAdmin={isAdmin} />}

      {/* API Keys tab */}
      {activeTab === "api" && (
        <ApiKeysSection apiKeys={apiKeys} setApiKeys={setApiKeys} />
      )}

    </div>
  );
}
