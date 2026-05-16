"use client";
import { useEffect, useState } from "react";
import { Save, Plus, X, BrainCircuit, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { personaApi, usersApi, type Persona } from "@/lib/api";

export default function SettingsPage() {
  const [persona, setPersona] = useState<Partial<Persona>>({});
  const [saving, setSaving] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [allowedEmails, setAllowedEmails] = useState<{ id: number; email: string }[]>([]);
  const [newEmail, setNewEmail] = useState("");

  useEffect(() => {
    personaApi.get().then((r) => { if (r.data) setPersona(r.data); });
    usersApi.me().then((r) => {
      if (r.data.is_admin) {
        setIsAdmin(true);
        usersApi.listAllowedEmails().then((res) => setAllowedEmails(res.data));
      }
    });
  }, []);

  const savePersona = async () => {
    setSaving(true);
    try {
      const res = await personaApi.upsert(persona);
      setPersona(res.data);
      toast.success("Persona saved and embedded");
    } catch {
      toast.error("Failed to save persona");
    } finally {
      setSaving(false);
    }
  };

  const synthesizeStyle = async () => {
    setSynthesizing(true);
    try {
      const res = await personaApi.synthesizeStyle();
      setPersona(res.data);
      toast.success("Style profile updated from your edit history");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Not enough edit history yet");
    } finally {
      setSynthesizing(false);
    }
  };

  const addEmail = async () => {
    if (!newEmail.trim()) return;
    try {
      await usersApi.addAllowedEmail(newEmail.trim());
      const r = await usersApi.listAllowedEmails();
      setAllowedEmails(r.data);
      setNewEmail("");
      toast.success("Email authorized");
    } catch {
      toast.error("Failed to add email (may already exist)");
    }
  };

  const removeEmail = async (email: string) => {
    await usersApi.removeAllowedEmail(email);
    setAllowedEmails((prev) => prev.filter((e) => e.email !== email));
    toast.success("Email removed");
  };

  return (
    <div className="p-8 space-y-8 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Configure your persona profile and access control</p>
      </div>

      {/* Persona */}
      <Card>
        <CardHeader>
          <CardTitle>Persona Profile</CardTitle>
          <CardDescription>
            This defines your voice. The AI uses it to match your style, tone, and audience on every generation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Niche / Industry</label>
              <Input
                placeholder="e.g. SaaS, Healthcare, Fitness"
                value={persona.niche || ""}
                onChange={(e) => setPersona((p) => ({ ...p, niche: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Tone</label>
              <Input
                placeholder="e.g. Professional, Casual, Humorous"
                value={persona.tone || ""}
                onChange={(e) => setPersona((p) => ({ ...p, tone: e.target.value }))}
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Target Audience</label>
            <Input
              placeholder="e.g. Tech founders aged 25-40, early adopters"
              value={persona.target_audience || ""}
              onChange={(e) => setPersona((p) => ({ ...p, target_audience: e.target.value }))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Brand Voice</label>
            <Textarea
              placeholder="Describe your brand voice in detail. e.g. Thought-provoking, data-driven, avoids buzzwords..."
              rows={3}
              value={persona.brand_voice || ""}
              onChange={(e) => setPersona((p) => ({ ...p, brand_voice: e.target.value }))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Writing Style Notes</label>
            <Textarea
              placeholder="Any specific patterns you use: short sentences, stories, frameworks (PAS, AIDA), emojis..."
              rows={3}
              value={persona.writing_style_notes || ""}
              onChange={(e) => setPersona((p) => ({ ...p, writing_style_notes: e.target.value }))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Sample Content</label>
            <Textarea
              placeholder="Paste 3-5 examples of your best posts. The AI will learn your style from these."
              rows={6}
              value={persona.sample_content || ""}
              onChange={(e) => setPersona((p) => ({ ...p, sample_content: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">Separate examples with a blank line</p>
          </div>

          <Button onClick={savePersona} disabled={saving}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Saving..." : "Save Persona"}
          </Button>
        </CardContent>
      </Card>

      {/* Style Learning */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-indigo-500" />
            Style Learning
          </CardTitle>
          <CardDescription>
            The AI analyzes your re-edit history to infer consistent style preferences. These are combined
            with your manual persona to make every generation feel more like you over time.
            Auto-updates every 5 re-edits.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {persona.learned_style ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-700">Learned Style Profile</p>
                {persona.style_synthesized_at && (
                  <span className="text-xs text-muted-foreground">
                    Last updated {new Date(persona.style_synthesized_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-4">
                <pre className="text-sm font-sans text-indigo-900 whitespace-pre-wrap leading-relaxed">
                  {persona.learned_style}
                </pre>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No learned style yet. Make at least 3 re-edits on generated content — the AI will
              start recognising your patterns and build a style profile automatically.
            </p>
          )}
          <Button
            variant="outline"
            onClick={synthesizeStyle}
            disabled={synthesizing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${synthesizing ? "animate-spin" : ""}`} />
            {synthesizing ? "Analysing edit history…" : "Refresh Style Now"}
          </Button>
        </CardContent>
      </Card>

      {/* Access control — admin only */}
      {isAdmin && <Card>
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
      </Card>}
    </div>
  );
}
