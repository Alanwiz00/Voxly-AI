"use client";
import { useEffect, useState } from "react";
import { Save, Plus, X, BrainCircuit, RefreshCw, Star, Trash2, ChevronDown, ChevronUp, KeyRound, Copy, Check, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { personaApi, usersApi, apiKeysApi, type Persona, type ApiKeyRecord } from "@/lib/api";

const EMPTY_PERSONA: Partial<Persona> = {
  name: "", niche: "", tone: "", target_audience: "",
  brand_voice: "", writing_style_notes: "", sample_content: "",
};

function PersonaForm({
  initial, onSave, onCancel, saving, isNew,
}: {
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
          {saving ? "Saving…" : isNew ? "Create Persona" : "Save Changes"}
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
    <Card className={persona.is_default ? "border-indigo-300 bg-indigo-50/30" : ""}>
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
                <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                  <pre className="text-xs font-sans text-indigo-900 whitespace-pre-wrap leading-relaxed">{persona.learned_style}</pre>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No learned style yet. 👍 Rate at least 3 generated posts and VoxlyAI will automatically build a style profile that improves every future generation.
              </p>
            )}
            <Button variant="outline" size="sm" onClick={synthesize} disabled={synthesizing}>
              <RefreshCw className={`w-3 h-3 mr-2 ${synthesizing ? "animate-spin" : ""}`} />
              {synthesizing ? "Analysing…" : "Refresh Style Now"}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

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

export default function SettingsPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [showNewForm, setShowNewForm] = useState(false);
  const [creatingNew, setCreatingNew] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [allowedEmails, setAllowedEmails] = useState<{ id: number; email: string }[]>([]);
  const [newEmail, setNewEmail] = useState("");

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [creatingKey, setCreatingKey] = useState(false);
  const [revealedKey, setRevealedKey] = useState<{ id: number; key: string } | null>(null);
  const [showKeyValue, setShowKeyValue] = useState(false);

  useEffect(() => {
    personaApi.list().then((r) => setPersonas(r.data));
    usersApi.me().then((r) => {
      if (r.data.is_admin) {
        setIsAdmin(true);
        usersApi.listAllowedEmails().then((res) => setAllowedEmails(res.data));
        apiKeysApi.list().then((res) => setApiKeys(res.data));
      }
    });
  }, []);

  const createPersona = async (data: Partial<Persona>) => {
    setCreatingNew(true);
    try {
      const res = await personaApi.create({ ...data, name: data.name || "Default" });
      setPersonas((prev) => [...prev, res.data]);
      setShowNewForm(false);
      toast.success("Persona created");
    } catch { toast.error("Failed to create persona"); }
    finally { setCreatingNew(false); }
  };

  const createKey = async () => {
    if (!newKeyName.trim()) return;
    setCreatingKey(true);
    try {
      const res = await apiKeysApi.create(newKeyName.trim());
      const record = res.data;
      setApiKeys((prev) => [record, ...prev]);
      setNewKeyName("");
      if (record.key) {
        setRevealedKey({ id: record.id, key: record.key });
        setShowKeyValue(false);
      }
      toast.success("API key created. Copy it now, it won't be shown again.");
    } catch { toast.error("Failed to create API key"); }
    finally { setCreatingKey(false); }
  };

  const revokeKey = async (id: number, name: string) => {
    if (!confirm(`Revoke "${name}"? Any agent using this key will lose access immediately.`)) return;
    try {
      await apiKeysApi.revoke(id);
      setApiKeys((prev) => prev.filter((k) => k.id !== id));
      if (revealedKey?.id === id) setRevealedKey(null);
      toast.success("API key revoked");
    } catch { toast.error("Failed to revoke API key"); }
  };

  const addEmail = async () => {
    if (!newEmail.trim()) return;
    try {
      await usersApi.addAllowedEmail(newEmail.trim());
      const r = await usersApi.listAllowedEmails();
      setAllowedEmails(r.data);
      setNewEmail("");
      toast.success("Email authorized");
    } catch { toast.error("Failed to add email (may already exist)"); }
  };

  const removeEmail = async (email: string) => {
    await usersApi.removeAllowedEmail(email);
    setAllowedEmails((prev) => prev.filter((e) => e.email !== email));
    toast.success("Email removed");
  };

  return (
    <div className="p-4 md:p-8 space-y-6 md:space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your personas and access control</p>
      </div>

      {/* Personas */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Personas</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              The AI auto-selects the best persona for every topic and context. The default is used as fallback.
            </p>
          </div>
          <Button onClick={() => setShowNewForm(true)} disabled={showNewForm}>
            <Plus className="w-4 h-4 mr-2" />
            New Persona
          </Button>
        </div>

        {showNewForm && (
          <Card className="border-dashed border-indigo-300">
            <CardHeader>
              <CardTitle className="text-base">Create New Persona</CardTitle>
              <CardDescription>Give it a distinct name so you can identify it easily.</CardDescription>
            </CardHeader>
            <CardContent>
              <PersonaForm
                initial={{ ...EMPTY_PERSONA }}
                onSave={createPersona}
                onCancel={() => setShowNewForm(false)}
                saving={creatingNew}
                isNew
              />
            </CardContent>
          </Card>
        )}

        {personas.length === 0 && !showNewForm && (
          <Card className="border-dashed">
            <CardContent className="py-10 text-center text-slate-400">
              <p>No personas yet. Create one to start generating content in your voice.</p>
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

      {/* API Keys — admin only */}
      {isAdmin && <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-indigo-500" />
            <div>
              <CardTitle>API Keys</CardTitle>
              <CardDescription className="mt-0.5">
                Use API keys to let AI agents and external tools generate content on your behalf.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Create new key */}
          <div className="flex gap-2">
            <Input
              placeholder='Key name, e.g. "MCP Server" or "Fetch Agent"'
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createKey()}
            />
            <Button onClick={createKey} disabled={creatingKey || !newKeyName.trim()}>
              <Plus className="w-4 h-4 mr-2" />
              {creatingKey ? "Creating…" : "Create"}
            </Button>
          </div>

          {/* Newly created key reveal */}
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

          {/* Keys list */}
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
                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    onClick={() => revokeKey(k.id, k.name)}
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>}

      {/* Access control — admin only */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>Authorized Emails</CardTitle>
            <CardDescription>Only listed emails can sign in. Your email is always allowed.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="email@example.com"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addEmail()}
              />
              <Button onClick={addEmail} disabled={!newEmail.trim()}>
                <Plus className="w-4 h-4 mr-2" />
                Add
              </Button>
            </div>
            <div className="space-y-2">
              {allowedEmails.map((entry) => (
                <div key={entry.id} className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-md">
                  <span className="text-sm">{entry.email}</span>
                  <Button variant="ghost" size="icon" onClick={() => removeEmail(entry.email)}>
                    <X className="w-4 h-4 text-muted-foreground" />
                  </Button>
                </div>
              ))}
              {allowedEmails.length === 0 && (
                <p className="text-sm text-muted-foreground">No emails added yet.</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
