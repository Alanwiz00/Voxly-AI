"use client";
import { useEffect, useState, useRef } from "react";
import { Sparkles, Upload, Globe, FileText, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { topicsApi, generateApi, type Topic, type GeneratedContent, type Platform, type ContentType } from "@/lib/api";
import { PLATFORM_LABELS, PLATFORM_COLORS, CONTENT_TYPE_LABELS, cn } from "@/lib/utils";

const PLATFORMS: Platform[] = ["twitter", "instagram", "facebook", "telegram"];
const CONTENT_TYPES: ContentType[] = ["idea", "long_form", "thread", "article"];
type SourceMode = "topic" | "text" | "url" | "file";

export default function GeneratePage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [platform, setPlatform] = useState<Platform>("twitter");
  const [contentType, setContentType] = useState<ContentType>("idea");
  const [sourceMode, setSourceMode] = useState<SourceMode>("topic");
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null);
  const [customTopicName, setCustomTopicName] = useState("");
  const [textInput, setTextInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [ideaCount, setIdeaCount] = useState(4);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<GeneratedContent[]>([]);
  const [copied, setCopied] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { topicsApi.list().then((r) => setTopics(r.data)); }, []);

  const copy = async (id: number, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const generate = async () => {
    setLoading(true);
    setResults([]);
    try {
      if (sourceMode === "topic") {
        const res = await generateApi.generate({
          topic_id: selectedTopic || undefined,
          topic_name: !selectedTopic ? customTopicName : undefined,
          platform,
          content_type: contentType,
          idea_count: ideaCount,
        });
        setResults(res.data.results);
      } else {
        const form = new FormData();
        form.append("platform", platform);
        form.append("content_type", contentType);
        form.append("idea_count", String(ideaCount));
        if (sourceMode === "text") form.append("text", textInput);
        if (sourceMode === "url") form.append("url", urlInput);
        if (sourceMode === "file" && file) form.append("file", file);
        const res = await generateApi.fromSource(form);
        setResults(res.data.results);
      }
      toast.success("Content generated!");
    } catch {
      toast.error("Generation failed. Check your settings.");
    } finally {
      setLoading(false);
    }
  };

  const canGenerate =
    sourceMode === "topic"
      ? selectedTopic !== null || customTopicName.trim().length > 0
      : sourceMode === "text"
      ? textInput.trim().length > 0
      : sourceMode === "url"
      ? urlInput.trim().length > 0
      : file !== null;

  return (
    <div className="p-8 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Generate Content</h1>
        <p className="text-slate-500 mt-1">Create platform-ready content from topics or your own source</p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Config panel */}
        <div className="col-span-1 space-y-4">
          {/* Platform */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm">Platform</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPlatform(p)}
                  className={cn(
                    "px-3 py-2 rounded-md text-xs font-medium border transition-colors",
                    platform === p ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-border hover:bg-accent"
                  )}
                >
                  {PLATFORM_LABELS[p]}
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Content type */}
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-sm">Content Type</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {CONTENT_TYPES.map((ct) => (
                <button
                  key={ct}
                  onClick={() => setContentType(ct)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-md text-sm border transition-colors",
                    contentType === ct ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-border hover:bg-accent"
                  )}
                >
                  {CONTENT_TYPE_LABELS[ct]}
                </button>
              ))}
              {contentType === "idea" && (
                <div className="pt-1">
                  <label className="text-xs text-muted-foreground">Number of ideas</label>
                  <Input
                    type="number"
                    min={1}
                    max={8}
                    value={ideaCount}
                    onChange={(e) => setIdeaCount(Number(e.target.value))}
                    className="mt-1 h-8"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Source panel */}
        <div className="col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Source</CardTitle>
              <div className="flex gap-2 mt-2">
                {(["topic", "text", "url", "file"] as SourceMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setSourceMode(m)}
                    className={cn(
                      "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                      sourceMode === m ? "bg-slate-900 text-white border-slate-900" : "border-border hover:bg-accent"
                    )}
                  >
                    {m === "topic" ? "Topic" : m === "text" ? "Paste Text" : m === "url" ? "URL" : "Upload File"}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {sourceMode === "topic" && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    {topics.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setSelectedTopic(selectedTopic === t.id ? null : t.id)}
                        className={cn(
                          "w-full text-left px-4 py-3 rounded-lg border transition-colors",
                          selectedTopic === t.id ? "border-indigo-500 bg-indigo-50" : "border-border hover:bg-accent"
                        )}
                      >
                        <span className="font-medium text-sm">{t.name}</span>
                        {t.last_crawled_at && (
                          <span className="text-xs text-muted-foreground ml-2">
                            · crawled {new Date(t.last_crawled_at).toLocaleDateString()}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-white px-2 text-muted-foreground">or type a topic</span>
                    </div>
                  </div>
                  <Input
                    placeholder="Enter any topic..."
                    value={customTopicName}
                    onChange={(e) => { setCustomTopicName(e.target.value); setSelectedTopic(null); }}
                  />
                </div>
              )}

              {sourceMode === "text" && (
                <Textarea
                  placeholder="Paste your article, notes, or reference content here..."
                  rows={8}
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                />
              )}

              {sourceMode === "url" && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-muted-foreground" />
                    <Input
                      placeholder="https://example.com/article"
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">We'll extract and analyze the content at this URL.</p>
                </div>
              )}

              {sourceMode === "file" && (
                <div
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => fileRef.current?.click()}
                >
                  <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                  <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                  {file ? (
                    <p className="text-sm font-medium">{file.name}</p>
                  ) : (
                    <>
                      <p className="text-sm font-medium">Drop PDF or DOCX here</p>
                      <p className="text-xs text-muted-foreground mt-1">or click to browse</p>
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Button className="w-full" size="lg" onClick={generate} disabled={loading || !canGenerate}>
            <Sparkles className="w-4 h-4 mr-2" />
            {loading ? "Generating..." : "Generate Content"}
          </Button>
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Generated Content</h2>
          {results.map((item) => {
            const meta = item.meta as Record<string, unknown>;
            const score = meta?.score as number | undefined;
            const scoreReason = meta?.score_reason as string | undefined;
            const hook = meta?.hook as string | undefined;
            const cta = meta?.cta as string | undefined;
            const hashtags = Array.isArray(meta?.hashtags) ? (meta.hashtags as string[]) : [];
            return (
              <Card key={item.id}>
                <CardHeader className="pb-2 flex flex-row items-start justify-between">
                  <div className="flex-1 min-w-0">
                    {item.title && <CardTitle className="text-base">{item.title}</CardTitle>}
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <Badge className={PLATFORM_COLORS[item.platform]}>{PLATFORM_LABELS[item.platform]}</Badge>
                      <Badge variant="outline">{CONTENT_TYPE_LABELS[item.content_type]}</Badge>
                      {score !== undefined && (
                        <span
                          className={cn(
                            "text-xs font-semibold px-2 py-0.5 rounded-full",
                            score >= 8 ? "bg-green-100 text-green-700" :
                            score >= 6 ? "bg-yellow-100 text-yellow-700" :
                            "bg-red-100 text-red-700"
                          )}
                          title={scoreReason}
                        >
                          Score {score}/10
                        </span>
                      )}
                    </div>
                    {hook && (
                      <p className="text-xs text-muted-foreground mt-1 italic">Hook: {hook}</p>
                    )}
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => copy(item.id, item.content)}>
                    {copied === item.id ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </CardHeader>
                <CardContent className="space-y-3">
                  <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed bg-slate-50 rounded-md p-3">
                    {item.content}
                  </pre>
                  {cta && (
                    <p className="text-xs text-indigo-700 bg-indigo-50 rounded px-3 py-1.5">
                      <span className="font-semibold">CTA:</span> {cta}
                    </p>
                  )}
                  {hashtags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {hashtags.map((tag) => (
                        <span key={tag} className="text-xs text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {scoreReason && (
                    <p className="text-xs text-muted-foreground border-t pt-2">
                      <span className="font-medium">Why this works:</span> {scoreReason}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
