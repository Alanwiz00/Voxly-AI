"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { contentApi, type GeneratedContent, type Platform } from "@/lib/api";
import { PLATFORM_LABELS } from "@/lib/utils";

const PLATFORMS: Platform[] = ["twitter", "instagram", "facebook", "telegram"];

interface SummarizePanelProps {
  contentId: number;
  onSummarized: (summary: GeneratedContent) => void;
  onClose: () => void;
}

// Pick a platform and get the post condensed into that platform's short-post format.
export default function SummarizePanel({ contentId, onSummarized, onClose }: SummarizePanelProps) {
  const [loading, setLoading] = useState<Platform | null>(null);

  const summarize = async (platform: Platform) => {
    setLoading(platform);
    try {
      const res = await contentApi.summarize(contentId, platform);
      onSummarized(res.data);
      toast.success(`Summary for ${PLATFORM_LABELS[platform]} created`);
    } catch {
      toast.error("Summarize failed");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-2 pt-3">
      <p className="text-sm font-medium">Summarize for</p>
      <div className="flex flex-wrap gap-2">
        {PLATFORMS.map((p) => (
          <Button key={p} size="sm" variant="outline" onClick={() => summarize(p)} disabled={loading !== null}>
            {loading === p ? "Summarizing..." : PLATFORM_LABELS[p]}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={onClose} disabled={loading !== null}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
