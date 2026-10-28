"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Pause, Play, Search, Radar, Inbox, ChevronDown, ChevronUp, Pencil } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  listeningApi, usersApi,
  type ListeningCampaign, type ListeningCampaignInput, type OutreachTemplate, type OutreachIntent,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// X recent-search limit on self-serve access; the backend enforces it too.
const X_QUERY_MAX_CHARS = 512;

const SELECT_CLS =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring";

const INTENT_LABELS: Record<OutreachIntent, string> = {
  any: "Any eligible post",
  seeking_live_alerts: "Asking for live alerts",
  seeking_tips: "Asking for tips",
  tipster_complaint: "Complaining about tipsters",
  odds_discussion: "Discussing odds",
};

const EMPTY_CAMPAIGN: ListeningCampaignInput = {
  name: "",
  x_query: "",
  harm_terms: [],
  allowed_markets: ["NG"],
  link_base: "",
  daily_cap: 15,
  monthly_budget_usd: 6,
  max_results_per_poll: 10,
  poll_every_minutes: 30,
};

const errorDetail = (err: unknown, fallback: string) =>
  (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

const splitList = (value: string) => value.split(",").map((v) => v.trim()).filter(Boolean);

function CampaignForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: ListeningCampaignInput;
  submitLabel: string;
  onSubmit: (data: ListeningCampaignInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [markets, setMarkets] = useState(initial.allowed_markets.join(", "));
  const [harm, setHarm] = useState(initial.harm_terms.join(", "));
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await onSubmit({ ...form, allowed_markets: splitList(markets), harm_terms: splitList(harm) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Name</span>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="BetEye live alerts, Nigeria" />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Signup link</span>
          <Input value={form.link_base} onChange={(e) => setForm({ ...form, link_base: e.target.value })} placeholder="https://t.me/Beteyebot/BETEYE" />
        </label>
      </div>
      <label className="space-y-1 text-sm block">
        <span className="font-medium">X search query</span>
        <Textarea
          rows={2}
          className="font-mono text-xs"
          value={form.x_query}
          onChange={(e) => setForm({ ...form, x_query: e.target.value })}
          placeholder={'("live alerts" OR "any tips" OR "who has tips") (arsenal OR chelsea OR "man united") lang:en -is:retweet'}
        />
        <span className={cn("text-xs", form.x_query.length > X_QUERY_MAX_CHARS ? "text-destructive" : "text-muted-foreground")}>
          {form.x_query.length} / {X_QUERY_MAX_CHARS} characters. One combined query is billed once per post. Exclude retweets and harm
          words here so they&apos;re never billed.
        </span>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Allowed markets</span>
          <Input value={markets} onChange={(e) => setMarkets(e.target.value)} placeholder="NG" />
          <span className="text-xs text-muted-foreground">2-letter country codes, comma-separated</span>
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Extra harm words</span>
          <Input value={harm} onChange={(e) => setHarm(e.target.value)} placeholder="on top of the built-in list" />
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Daily cap</span>
          <Input type="number" min={1} value={form.daily_cap} onChange={(e) => setForm({ ...form, daily_cap: Number(e.target.value) })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Monthly X budget ($)</span>
          <Input type="number" min={0} value={form.monthly_budget_usd} onChange={(e) => setForm({ ...form, monthly_budget_usd: Number(e.target.value) })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Posts per search</span>
          <Input type="number" min={10} max={100} value={form.max_results_per_poll} onChange={(e) => setForm({ ...form, max_results_per_poll: Number(e.target.value) })} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Search every (min)</span>
          <Input type="number" min={10} max={1440} value={form.poll_every_minutes} onChange={(e) => setForm({ ...form, poll_every_minutes: Number(e.target.value) })} />
        </label>
      </div>
      <p className="text-xs text-muted-foreground">
        Spend is paced evenly through the month: a search runs only while this campaign is at or under its share so far, and unspent budget carries forward.
      </p>
      <div className="flex gap-2">
        <Button size="sm" onClick={submit} disabled={saving || !form.name.trim() || !form.x_query.trim()}>
          {saving ? "Saving..." : submitLabel}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

function TemplatesPanel({ campaignId }: { campaignId: number }) {
  const [templates, setTemplates] = useState<OutreachTemplate[]>([]);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState<OutreachIntent>("any");
  const [body, setBody] = useState("");
  const [cert, setCert] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listeningApi.templates(campaignId).then((r) => setTemplates(r.data));
  }, [campaignId]);

  const create = async () => {
    setSaving(true);
    try {
      const res = await listeningApi.createTemplate(campaignId, { name, intent, body, arcon_cert_no: cert || null });
      setTemplates((prev) => [...prev, res.data]);
      setName(""); setBody(""); setCert(""); setIntent("any");
      toast.success("Template saved");
    } catch (err) {
      toast.error(errorDetail(err, "Template rejected"));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (t: OutreachTemplate) => {
    const res = await listeningApi.updateTemplate(t.id, { active: !t.active });
    setTemplates((prev) => prev.map((x) => (x.id === t.id ? res.data : x)));
  };

  return (
    <div className="space-y-3 pt-3">
      {templates.length === 0 && <p className="text-sm text-muted-foreground">No templates yet. Nothing drafts until one is approved.</p>}
      {templates.map((t) => (
        <div key={t.id} className="rounded-md border p-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{t.name}</span>
            <Badge variant="outline">{INTENT_LABELS[t.intent]}</Badge>
            {t.approved ? (
              <Badge className="bg-green-100 text-green-800">Approved · {t.arcon_cert_no}</Badge>
            ) : (
              <Badge className="bg-amber-100 text-amber-800">Not approved: won&apos;t draft</Badge>
            )}
            {!t.active && <Badge variant="secondary">Off</Badge>}
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => toggle(t)}>
              {t.active ? "Turn off" : "Turn on"}
            </Button>
          </div>
          <pre className="whitespace-pre-wrap text-xs font-sans text-muted-foreground bg-muted/50 rounded p-2">{t.body}</pre>
        </div>
      ))}
      <div className="rounded-md border border-dashed p-3 space-y-2">
        <p className="text-sm font-medium">New template</p>
        <div className="grid gap-2 sm:grid-cols-2">
          <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <select className={SELECT_CLS} value={intent} onChange={(e) => setIntent(e.target.value as OutreachIntent)}>
            {(Object.keys(INTENT_LABELS) as OutreachIntent[]).map((i) => <option key={i} value={i}>{INTENT_LABELS[i]}</option>)}
          </select>
        </div>
        <Textarea
          rows={4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={"BetEye flagged a {alert_type} at {minute}' in {match}, and it {outcome}.\n\nFree live alerts on Telegram: {link}\n\n18+ · Play responsibly"}
        />
        <p className="text-xs text-muted-foreground">
          Slots: {"{match} {alert_type} {minute} {outcome} {proof_url} {link}"}. Must include {"{link}"}, &quot;18+&quot; and &quot;Play responsibly&quot;.
          Changing approved wording clears its approval.
        </p>
        <Input placeholder="ARCON certificate number (leave empty until approved)" value={cert} onChange={(e) => setCert(e.target.value)} />
        <Button size="sm" onClick={create} disabled={saving || !name.trim() || !body.trim()}>
          {saving ? "Saving..." : "Save template"}
        </Button>
      </div>
    </div>
  );
}

function CampaignCard({ campaign, onChange }: { campaign: ListeningCampaign; onChange: (c: ListeningCampaign) => void }) {
  const [editing, setEditing] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [sizing, setSizing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active = campaign.status === "active";

  const setStatus = async () => {
    setBusy(true);
    try {
      const res = await listeningApi.updateCampaign(campaign.id, { status: active ? "paused" : "active" });
      onChange(res.data);
    } catch (err) {
      toast.error(errorDetail(err, "Couldn't change status"));
    } finally {
      setBusy(false);
    }
  };

  const size = async () => {
    setBusy(true);
    try {
      const r = (await listeningApi.size(campaign.id)).data;
      setSizing(`${r.posts_last_7_days.toLocaleString()} posts last week · about ${r.est_posts_per_month.toLocaleString()}/month · ~$${r.est_read_cost_per_month_usd} to read them all`);
    } catch (err) {
      toast.error(errorDetail(err, "Couldn't size this query"));
    } finally {
      setBusy(false);
    }
  };

  const pollNow = async () => {
    setBusy(true);
    try {
      const r = (await listeningApi.pollNow(campaign.id)).data;
      toast.success(`Read ${r.read} posts · ${r.drafted} drafted · ${r.dropped} dropped`);
      const refreshed = (await listeningApi.campaigns()).data.campaigns.find((c) => c.id === campaign.id);
      if (refreshed) onChange(refreshed);
    } catch (err) {
      toast.error(errorDetail(err, "Search failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">{campaign.name}</CardTitle>
              <Badge className={active ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-700"}>{active ? "Active" : "Paused"}</Badge>
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground break-all">{campaign.x_query}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/listening/${campaign.id}/queue`}>
              <Button size="sm"><Inbox className="w-4 h-4 mr-1.5" />Queue ({campaign.queued})</Button>
            </Link>
            <Button size="sm" variant="outline" onClick={setStatus} disabled={busy}>
              {active ? <><Pause className="w-4 h-4 mr-1.5" />Pause</> : <><Play className="w-4 h-4 mr-1.5" />Activate</>}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">X spend this month</p>
            <p className="font-medium">${campaign.spend_this_month_usd.toFixed(2)} of ${campaign.monthly_budget_usd}</p>
            <p className="text-xs text-muted-foreground">Pace allows ${campaign.pace_allowance_usd.toFixed(2)} so far · every {campaign.poll_every_minutes} min</p>
          </div>
          <div><p className="text-xs text-muted-foreground">Sent today</p><p className="font-medium">{campaign.sent_today} of {campaign.daily_cap}</p></div>
          <div><p className="text-xs text-muted-foreground">Markets</p><p className="font-medium">{campaign.allowed_markets.join(", ") || "Any"}</p></div>
          <div><p className="text-xs text-muted-foreground">Signup link</p><p className="font-medium truncate">{campaign.link_base || "Not set"}</p></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={size} disabled={busy}><Search className="w-4 h-4 mr-1.5" />Check volume ($0.005)</Button>
          <Button size="sm" variant="outline" onClick={pollNow} disabled={busy || !active}>Search now</Button>
          <Button size="sm" variant="outline" onClick={() => setEditing((v) => !v)}><Pencil className="w-4 h-4 mr-1.5" />Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => setShowTemplates((v) => !v)}>
            Templates {showTemplates ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
          </Button>
        </div>
        {sizing && <p className="text-sm text-muted-foreground bg-muted/50 rounded px-3 py-2">{sizing}</p>}
        {editing && (
          <div className="border-t pt-3">
            <CampaignForm
              initial={campaign}
              submitLabel="Save changes"
              onCancel={() => setEditing(false)}
              onSubmit={async (data) => {
                try {
                  onChange((await listeningApi.updateCampaign(campaign.id, data)).data);
                  setEditing(false);
                  toast.success("Campaign saved");
                } catch (err) {
                  toast.error(errorDetail(err, "Couldn't save"));
                }
              }}
            />
          </div>
        )}
        {showTemplates && <div className="border-t"><TemplatesPanel campaignId={campaign.id} /></div>}
      </CardContent>
    </Card>
  );
}

export default function ListeningPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [campaigns, setCampaigns] = useState<ListeningCampaign[]>([]);
  const [spend, setSpend] = useState({ used: 0, budget: 0, xConfigured: true });
  const [creating, setCreating] = useState(false);

  const load = async () => {
    const r = (await listeningApi.campaigns()).data;
    setCampaigns(r.campaigns);
    setSpend({ used: r.spend_this_month_usd, budget: r.monthly_budget_usd, xConfigured: r.x_configured });
  };

  useEffect(() => {
    usersApi.me().then((r) => {
      setIsAdmin(r.data.is_admin);
      if (r.data.is_admin) void load();
    }).catch(() => setIsAdmin(false));
  }, []);

  const pauseAll = async () => {
    if (!confirm("Pause every campaign? Nothing new will be searched or drafted until you reactivate them.")) return;
    const r = (await listeningApi.pauseAll()).data;
    toast.success(`Paused ${r.paused} campaign${r.paused === 1 ? "" : "s"}`);
    await load();
  };

  if (isAdmin === false) {
    return (
      <div className="p-4 md:p-8">
        <Card><CardContent className="py-12 text-center text-muted-foreground">Listening is available to admins only.</CardContent></Card>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground flex items-center gap-2"><Radar className="w-7 h-7" />Listening</h1>
          <p className="text-muted-foreground mt-1">Find people on X asking for what you offer. A person reviews and sends every reply.</p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted-foreground">X spend: <span className="font-medium text-foreground">${spend.used.toFixed(2)}</span> of ${spend.budget}</p>
          <Button size="sm" variant="outline" className="text-destructive" onClick={pauseAll}><Pause className="w-4 h-4 mr-1.5" />Pause all</Button>
        </div>
      </div>

      {!spend.xConfigured && (
        <p className="text-sm rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 text-amber-800 dark:text-amber-300">
          X API key not set (X_BEARER_TOKEN). Campaigns can be set up, but nothing will be searched yet.
        </p>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Campaigns</CardTitle>
              <CardDescription>New campaigns start paused. Check volume and add an approved template before activating.</CardDescription>
            </div>
            {!creating && <Button size="sm" onClick={() => setCreating(true)}>New campaign</Button>}
          </div>
        </CardHeader>
        {creating && (
          <CardContent className={cn("border-t pt-4")}>
            <CampaignForm
              initial={EMPTY_CAMPAIGN}
              submitLabel="Create campaign"
              onCancel={() => setCreating(false)}
              onSubmit={async (data) => {
                try {
                  const res = await listeningApi.createCampaign(data);
                  setCampaigns((prev) => [...prev, res.data]);
                  setCreating(false);
                  toast.success("Campaign created (paused)");
                } catch (err) {
                  toast.error(errorDetail(err, "Couldn't create campaign"));
                }
              }}
            />
          </CardContent>
        )}
      </Card>

      {campaigns.map((c) => (
        <CampaignCard key={c.id} campaign={c} onChange={(updated) => setCampaigns((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))} />
      ))}
    </div>
  );
}
