"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, ExternalLink, Send, SkipForward, Ban, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { listeningApi, type OutreachDraft } from "@/lib/api";

const errorDetail = (err: unknown, fallback: string) =>
  (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

// X's own reply box, pre-filled. Nothing is posted until the reviewer presses Post on X.
const replyIntentUrl = (postId: string, text: string) =>
  `https://x.com/intent/tweet?in_reply_to=${postId}&text=${encodeURIComponent(text)}`;

function DraftCard({ draft, onDone }: { draft: OutreachDraft; onDone: () => void }) {
  const [text, setText] = useState(draft.text ?? "");
  const [savedText, setSavedText] = useState(draft.text ?? "");
  const [confirming, setConfirming] = useState(false);
  const [replyUrl, setReplyUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const post = draft.post;
  const verdict = post.verdict ?? {};
  const postUrl = `https://x.com/${post.author_handle ?? "i"}/status/${post.id}`;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); }
  };

  const save = () => run(async () => {
    try {
      const res = await listeningApi.editDraft(draft.id, text);
      setSavedText(res.data.text ?? text);
      toast.success("Draft updated");
    } catch (err) {
      toast.error(errorDetail(err, "Edit rejected"));
    }
  });

  const markSent = () => run(async () => {
    try {
      await listeningApi.markSent(draft.id, replyUrl.trim() || undefined);
      toast.success("Marked as sent");
      onDone();
    } catch (err) {
      toast.error(errorDetail(err, "Couldn't mark as sent"));
    }
  });

  const skip = (doNotContact: boolean) => run(async () => {
    await listeningApi.skip(draft.id, doNotContact);
    toast.success(doNotContact ? "Skipped and added to do-not-contact" : "Skipped");
    onDone();
  });

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <a href={postUrl} target="_blank" rel="noreferrer" className="font-medium hover:underline">@{post.author_handle ?? post.author_id}</a>
          {post.posted_at && <span className="text-xs text-muted-foreground">{new Date(post.posted_at).toLocaleString()}</span>}
          {verdict.intent && <Badge variant="outline">{verdict.intent.replace(/_/g, " ")}</Badge>}
          {verdict.market && verdict.market !== "UNKNOWN" && <Badge variant="outline">{verdict.market}</Badge>}
          {typeof verdict.confidence === "number" && <Badge variant="secondary">{Math.round(verdict.confidence * 100)}% sure</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <blockquote className="border-l-2 pl-3 text-sm text-foreground whitespace-pre-wrap">{post.text}</blockquote>
        {post.matched_terms.length > 0 && (
          <p className="text-xs text-muted-foreground">Matched: {post.matched_terms.join(", ")}</p>
        )}
        {draft.proof && (
          <p className="text-xs flex items-center gap-1.5 rounded bg-green-50 dark:bg-green-950/30 text-green-800 dark:text-green-300 px-2 py-1.5">
            <Trophy className="w-3.5 h-3.5 flex-shrink-0" />
            Proof: {draft.proof.match} · {draft.proof.alertType.replace(/_/g, " ").toLowerCase()} at {draft.proof.minuteAtFire}&apos; · {draft.proof.outcome}
            {draft.proof.proofUrl && <a className="underline ml-1" href={draft.proof.proofUrl} target="_blank" rel="noreferrer">view</a>}
          </p>
        )}

        <div className="space-y-1">
          <Textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{text.length} chars{text.length > 280 && " · long for a reply"}</span>
            {text !== savedText && (
              <Button size="sm" variant="ghost" onClick={save} disabled={busy}>Save edit</Button>
            )}
          </div>
        </div>

        {confirming ? (
          <div className="rounded-md border p-3 space-y-2">
            <p className="text-sm font-medium">Posted it on X?</p>
            <Input
              placeholder="Paste your reply's URL to track replies (optional)"
              value={replyUrl}
              onChange={(e) => setReplyUrl(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={markSent} disabled={busy}>Confirm sent</Button>
              <Button size="sm" variant="outline" onClick={() => setConfirming(false)}>Back</Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <a href={replyIntentUrl(post.id, savedText)} target="_blank" rel="noreferrer">
              <Button size="sm" disabled={text !== savedText} title={text !== savedText ? "Save your edit first" : undefined}>
                <ExternalLink className="w-4 h-4 mr-1.5" />Open in X
              </Button>
            </a>
            <Button size="sm" variant="outline" onClick={() => setConfirming(true)}><Send className="w-4 h-4 mr-1.5" />Mark sent</Button>
            <Button size="sm" variant="outline" onClick={() => skip(false)} disabled={busy}><SkipForward className="w-4 h-4 mr-1.5" />Skip</Button>
            <Button size="sm" variant="ghost" className="text-destructive" onClick={() => skip(true)} disabled={busy}>
              <Ban className="w-4 h-4 mr-1.5" />Skip & never contact
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function QueuePage() {
  const { id } = useParams<{ id: string }>();
  const campaignId = Number(id);
  const [data, setData] = useState<Awaited<ReturnType<typeof listeningApi.queue>>["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listeningApi.queue(campaignId).then((r) => setData(r.data)).catch((err) => setError(errorDetail(err, "Couldn't load the queue")));
  }, [campaignId]);

  // Reload after each action so the sent-today count stays accurate
  const reload = async () => setData((await listeningApi.queue(campaignId)).data);

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-3xl">
      <div className="space-y-2">
        <Link href="/listening" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />Listening
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{data?.campaign.name ?? "Review queue"}</h1>
            <p className="text-muted-foreground mt-1">Read the post, check the draft, then send it yourself from X.</p>
          </div>
          {data && (
            <Badge className={data.sent_today >= data.daily_cap ? "bg-red-100 text-red-800" : "bg-slate-100 text-slate-700"}>
              Sent today: {data.sent_today} of {data.daily_cap}
            </Badge>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {data && data.drafts.length === 0 && (
        <Card><CardContent className="py-12 text-center text-muted-foreground">Nothing to review right now.</CardContent></Card>
      )}
      {data?.drafts.map((d) => <DraftCard key={d.id} draft={d} onDone={() => void reload()} />)}
    </div>
  );
}
