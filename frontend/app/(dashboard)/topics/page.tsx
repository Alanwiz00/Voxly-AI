"use client";
import { useEffect, useState } from "react";
import { RefreshCw, Plus, Trash2, Clock, ChevronDown, ChevronUp, Copy, Check, X } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { topicsApi, contentApi, type Topic, type GeneratedContent, type Platform } from "@/lib/api";
import { PLATFORM_LABELS, PLATFORM_COLORS, cn } from "@/lib/utils";
import RatingButtons from "@/components/rating-buttons";

const PLATFORMS: Platform[] = ["twitter", "instagram", "facebook", "telegram"];

type TabKey = "ideas" | "long_form";

export default function CrawlerPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(false);
  const [crawlingId, setCrawlingId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", keywords: "", description: "" });
  const [showForm, setShowForm] = useState(false);

  // Expanded topic content
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [contentMap, setContentMap] = useState<Record<number, GeneratedContent[]>>({});
  const [contentLoading, setContentLoading] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<Record<number, TabKey>>({});

  // Adapt state
  const [adaptingId, setAdaptingId] = useState<number | null>(null);
  const [adapted, setAdapted] = useState<{ contentId: number; result: GeneratedContent } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => topicsApi.list().then((r) => setTopics(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name.trim()) return;
    setLoading(true);
    try {
      await topicsApi.create(form);
      setForm({ name: "", keywords: "", description: "" });
      setShowForm(false);
      await load();
      toast.success("Topic created. Crawl and content generation started.");
    } catch {
      toast.error("Failed to create topic");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: number) => {
    await topicsApi.delete(id);
    setTopics((prev) => prev.filter((t) => t.id !== id));
    if (expandedId === id) setExpandedId(null);
    toast.success("Topic deleted");
  };

  const crawl = async (topic: Topic) => {
    setCrawlingId(topic.id);
    try {
      await topicsApi.crawl(topic.id);
      // Refresh topic list (updated last_crawled_at) and auto-show fresh content
      await load();
      setExpandedId(topic.id);
      const res = await topicsApi.generatedContent(topic.id);
      setContentMap((prev) => ({ ...prev, [topic.id]: res.data }));
      toast.success("Crawl complete. Fresh content is ready.");
    } catch {
      toast.error("Crawl failed");
    } finally {
      setCrawlingId(null);
    }
  };

  const toggleExpand = async (topicId: number) => {
    if (expandedId === topicId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(topicId);
    if (contentMap[topicId]) return;
    setContentLoading(topicId);
    try {
      const res = await topicsApi.generatedContent(topicId);
      setContentMap((prev) => ({ ...prev, [topicId]: res.data }));
    } catch {
      toast.error("Failed to load generated content");
    } finally {
      setContentLoading(null);
    }
  };

  const adaptContent = async (contentId: number, platform: Platform) => {
    setAdaptingId(contentId);
    try {
      const res = await contentApi.adapt(contentId, platform);
      setAdapted({ contentId, result: res.data });
    } catch {
      toast.error("Adaptation failed");
    } finally {
      setAdaptingId(null);
    }
  };

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getTab = (topicId: number): TabKey => activeTab[topicId] ?? "ideas";
  const setTab = (topicId: number, tab: TabKey) =>
    setActiveTab((prev) => ({ ...prev, [topicId]: tab }));

  const [ratings, setRatings] = useState<Record<number, number | null>>({});

  const handleRate = async (id: number, rating: number) => {
    setRatings((prev) => ({ ...prev, [id]: rating === 0 ? null : rating }));
    try {
      await contentApi.rate(id, rating);
    } catch {
      setRatings((prev) => ({ ...prev, [id]: undefined as unknown as null }));
    }
  };

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-4xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">Crawler</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Topics are crawled every 12 hours. Fresh content is auto-generated after each crawl.
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="shrink-0">
          <Plus className="w-4 h-4 mr-2" />
          Add Topic
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader><CardTitle className="text-base">New Topic</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Topic name (e.g. AI in healthcare)"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <Input
              placeholder="Keywords (comma-separated, optional)"
              value={form.keywords}
              onChange={(e) => setForm((f) => ({ ...f, keywords: e.target.value }))}
            />
            <Textarea
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={2}
            />
            <div className="flex gap-2">
              <Button onClick={create} disabled={loading || !form.name.trim()}>
                {loading ? "Creating..." : "Create Topic"}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {topics.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              No topics yet. Add your first topic to start auto-generating content.
            </CardContent>
          </Card>
        )}

        {topics.map((topic) => {
          const isExpanded = expandedId === topic.id;
          const content = contentMap[topic.id] ?? [];
          const ideas = content.filter((c) => c.content_type === "idea");
          const longForms = content.filter((c) => c.content_type === "long_form");
          const tab = getTab(topic.id);

          return (
            <Card key={topic.id} className="overflow-hidden">
              {/* Topic card — stacked for mobile */}
              <CardContent className="py-4 space-y-3">
                {/* Name + badge + delete */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <span className="font-semibold text-foreground leading-snug">{topic.name}</span>
                    {topic.is_active && <Badge variant="secondary">Active</Badge>}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0 -mt-1 -mr-2 h-8 w-8"
                    onClick={() => remove(topic.id)}
                  >
                    <Trash2 className="w-4 h-4 text-destructive" />
                  </Button>
                </div>

                {/* Keywords */}
                {topic.keywords && (
                  <p className="text-sm text-muted-foreground leading-snug">
                    <span className="font-medium">Keywords:</span> {topic.keywords}
                  </p>
                )}

                {/* Last crawled */}
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3 flex-shrink-0" />
                  {topic.last_crawled_at
                    ? `Last crawled: ${new Date(topic.last_crawled_at).toLocaleString()}`
                    : "Not yet crawled"}
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2 pt-0.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 sm:flex-none"
                    onClick={() => crawl(topic)}
                    disabled={crawlingId === topic.id}
                  >
                    <RefreshCw className={cn("w-3 h-3 mr-1.5", crawlingId === topic.id && "animate-spin")} />
                    {crawlingId === topic.id ? "Crawling…" : "Crawl Now"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 sm:flex-none"
                    onClick={() => toggleExpand(topic.id)}
                  >
                    {isExpanded
                      ? <><ChevronUp className="w-3 h-3 mr-1.5" />Hide</>
                      : <><ChevronDown className="w-3 h-3 mr-1.5" />Content</>
                    }
                  </Button>
                </div>
              </CardContent>

              {/* Generated content panel */}
              {isExpanded && (
                <div className="border-t bg-muted/40 p-4 space-y-4">
                  {contentLoading === topic.id ? (
                    <p className="text-sm text-muted-foreground text-center py-4">Loading generated content…</p>
                  ) : content.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No content yet. Content generates automatically after each crawl.
                    </p>
                  ) : (
                    <>
                      {/* Tabs */}
                      <div className="flex gap-2">
                        <button
                          onClick={() => setTab(topic.id, "ideas")}
                          className={cn(
                            "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                            tab === "ideas"
                              ? "bg-foreground text-background border-foreground"
                              : "border-border hover:bg-accent"
                          )}
                        >
                          Short Posts ({ideas.length})
                        </button>
                        <button
                          onClick={() => setTab(topic.id, "long_form")}
                          className={cn(
                            "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                            tab === "long_form"
                              ? "bg-foreground text-background border-foreground"
                              : "border-border hover:bg-accent"
                          )}
                        >
                          Long Form ({longForms.length})
                        </button>
                      </div>

                      {/* Content cards */}
                      <div className="space-y-3">
                        {(tab === "ideas" ? ideas : longForms).map((item) => (
                          <ContentCard
                            key={item.id}
                            item={item}
                            adaptingId={adaptingId}
                            onAdapt={adaptContent}
                            rating={ratings[item.id] ?? item.rating}
                            onRate={handleRate}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Adapt result modal */}
      {adapted && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <span className="font-semibold">Adapted for</span>
                <Badge className={PLATFORM_COLORS[adapted.result.platform as Platform]}>
                  {PLATFORM_LABELS[adapted.result.platform as Platform]}
                </Badge>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyText(adapted.result.content)}
                >
                  {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setAdapted(null)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {adapted.result.title && (
                <p className="font-semibold mb-2">{adapted.result.title}</p>
              )}
              <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                {adapted.result.content}
              </pre>
              {Array.isArray(adapted.result.meta?.hashtags) && (adapted.result.meta.hashtags as string[]).length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {(adapted.result.meta.hashtags as string[]).map((tag) => (
                    <span key={tag} className="text-xs text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ContentCard({
  item,
  adaptingId,
  onAdapt,
  rating,
  onRate,
}: {
  item: GeneratedContent;
  adaptingId: number | null;
  onAdapt: (id: number, platform: Platform) => void;
  rating?: number | null;
  onRate: (id: number, rating: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = item.meta as Record<string, unknown>;
  const score = meta?.score as number | undefined;
  const hook = meta?.hook as string | undefined;
  const cta = meta?.cta as string | undefined;
  const preview = item.content.slice(0, 200);
  const isLong = item.content.length > 200;

  return (
    <div className="bg-card rounded-lg border p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {item.title && <p className="font-medium text-sm">{item.title}</p>}
          {hook && <p className="text-xs text-muted-foreground italic mt-0.5">Hook: {hook}</p>}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <RatingButtons contentId={item.id} rating={rating} onRate={onRate} />
          {score !== undefined && (
            <span
              className={cn(
                "text-xs font-semibold px-2 py-0.5 rounded-full",
                score >= 8 ? "bg-green-100 text-green-700" :
                score >= 6 ? "bg-yellow-100 text-yellow-700" :
                "bg-red-100 text-red-700"
              )}
            >
              {score}/10
            </span>
          )}
        </div>
      </div>

      <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed text-foreground">
        {expanded ? item.content : preview}
        {!expanded && isLong && "…"}
      </pre>

      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-xs text-indigo-600 hover:underline"
        >
          {expanded ? "Show less" : "Show full post"}
        </button>
      )}

      {cta && (
        <p className="text-xs text-indigo-700 bg-indigo-50 rounded px-3 py-1.5">
          <span className="font-semibold">CTA:</span> {cta}
        </p>
      )}

      {/* Platform adapt buttons */}
      <div className="pt-1 border-t flex items-center gap-2 flex-wrap">
        <span className="text-xs text-muted-foreground">Adapt for:</span>
        {PLATFORMS.map((p) => (
          <button
            key={p}
            disabled={adaptingId === item.id}
            onClick={() => onAdapt(item.id, p)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
              PLATFORM_COLORS[p],
              adaptingId === item.id
                ? "opacity-50 cursor-not-allowed"
                : "hover:opacity-80 cursor-pointer"
            )}
          >
            {adaptingId === item.id ? "…" : PLATFORM_LABELS[p]}
          </button>
        ))}
      </div>
    </div>
  );
}
