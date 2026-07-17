"use client";
import { useEffect, useState } from "react";
import { Copy, Check, Pencil, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import RatingButtons from "@/components/rating-buttons";
import { toast } from "sonner";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { contentApi, type GeneratedContent, type Platform, type ContentType } from "@/lib/api";
import { PLATFORM_LABELS, PLATFORM_COLORS, CONTENT_TYPE_LABELS, cn } from "@/lib/utils";

const SELECT_CLS =
  "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring";

export default function HistoryPage() {
  const [items, setItems] = useState<GeneratedContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [platformFilter, setPlatformFilter] = useState<Platform | "">("");
  const [typeFilter, setTypeFilter] = useState<ContentType | "">("");
  const [copied, setCopied] = useState<number | null>(null);
  const [ratings, setRatings] = useState<Record<number, number | null>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    contentApi
      .list({ platform: platformFilter || undefined, content_type: typeFilter || undefined, limit: 50 })
      .then((r) => setItems(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [platformFilter, typeFilter]);

  const copy = async (id: number, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleRate = async (id: number, rating: number) => {
    setRatings((prev) => ({ ...prev, [id]: rating === 0 ? null : rating }));
    try {
      await contentApi.rate(id, rating);
    } catch {
      setRatings((prev) => ({ ...prev, [id]: undefined as unknown as null }));
    }
  };

  const reEdit = async (item: GeneratedContent) => {
    if (!editInstruction.trim()) return;
    setEditLoading(true);
    try {
      const res = await contentApi.reEdit(item.id, editInstruction);
      setItems((prev) => [res.data, ...prev]);
      setEditingId(null);
      setEditInstruction("");
      toast.success("New version created");
    } catch {
      toast.error("Re-edit failed");
    } finally {
      setEditLoading(false);
    }
  };

  const remove = async (id: number) => {
    await contentApi.delete(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
    toast.success("Deleted");
  };

  return (
    <div className="p-4 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">Content History</h1>
        <p className="text-muted-foreground mt-1">All generated content. Re-edit any piece with a plain instruction.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value as Platform | "")}
          className={SELECT_CLS}
        >
          <option value="">All Platforms</option>
          {(["twitter", "instagram", "facebook", "telegram"] as Platform[]).map((p) => (
            <option key={p} value={p}>{PLATFORM_LABELS[p]}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as ContentType | "")}
          className={SELECT_CLS}
        >
          <option value="">All Types</option>
          {(["idea", "long_form", "thread", "article"] as ContentType[]).map((t) => (
            <option key={t} value={t}>{CONTENT_TYPE_LABELS[t]}</option>
          ))}
        </select>
      </div>

      <div className="space-y-3">
        {loading ? (
          [...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 space-y-2">
                    <div className="flex gap-2">
                      <div className="h-5 w-16 bg-muted rounded animate-pulse" />
                      <div className="h-5 w-14 bg-muted rounded animate-pulse" />
                    </div>
                    <div className="h-4 w-48 bg-muted rounded animate-pulse" />
                    <div className="h-3 w-32 bg-muted rounded animate-pulse" />
                  </div>
                  <div className="flex gap-1">
                    {[...Array(4)].map((_, j) => (
                      <div key={j} className="h-8 w-8 bg-muted rounded animate-pulse" />
                    ))}
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))
        ) : items.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              No content yet. Head to <strong>Generate</strong> to create your first post.
            </CardContent>
          </Card>
        ) : (
          items.map((item) => (
            <Card key={item.id}>
              <CardHeader className="pb-2">
                {/* Info + actions: stacked on mobile, side-by-side on sm+ */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className={PLATFORM_COLORS[item.platform]}>{PLATFORM_LABELS[item.platform]}</Badge>
                      <Badge variant="outline">{CONTENT_TYPE_LABELS[item.content_type]}</Badge>
                      {item.version > 1 && <Badge variant="secondary">v{item.version}</Badge>}
                      {item.parent_id && <Badge variant="outline" className="text-indigo-600 dark:text-indigo-400">Re-edit</Badge>}
                    </div>
                    {item.title && <p className="font-medium mt-1 truncate text-foreground">{item.title}</p>}
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex gap-1 items-center self-start sm:self-auto flex-shrink-0">
                    <RatingButtons
                      contentId={item.id}
                      rating={ratings[item.id] ?? item.rating}
                      onRate={handleRate}
                    />
                    <Button variant="ghost" size="icon" onClick={() => copy(item.id, item.content)}>
                      {copied === item.id ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => { setEditingId(editingId === item.id ? null : item.id); setEditInstruction(""); }}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}>
                      {expandedId === item.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => remove(item.id)}>
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardHeader>

              {expandedId === item.id && (
                <CardContent className="pt-0">
                  <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed text-foreground bg-muted/50 rounded-md p-4">
                    {item.content}
                  </pre>
                </CardContent>
              )}

              {editingId === item.id && (
                <CardContent className="pt-0 border-t">
                  <div className="space-y-2 pt-3">
                    <p className="text-sm font-medium">Re-edit instruction</p>
                    <Textarea
                      placeholder="e.g. Make it shorter and more casual, add a CTA at the end..."
                      rows={2}
                      value={editInstruction}
                      onChange={(e) => setEditInstruction(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => reEdit(item)} disabled={editLoading || !editInstruction.trim()}>
                        {editLoading ? "Editing..." : "Apply Edit"}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
