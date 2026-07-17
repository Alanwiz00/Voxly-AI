"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, BookOpen, History, TrendingUp, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { topicsApi, contentApi, type Topic, type GeneratedContent } from "@/lib/api";
import { PLATFORM_COLORS, PLATFORM_LABELS } from "@/lib/utils";

function StatSkeleton() {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-muted rounded-lg animate-pulse" />
          <div className="space-y-1.5">
            <div className="h-7 w-8 bg-muted rounded animate-pulse" />
            <div className="h-4 w-24 bg-muted rounded animate-pulse" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [recentContent, setRecentContent] = useState<GeneratedContent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      topicsApi.list().then((r) => setTopics(r.data)),
      contentApi.list({ limit: 5 }).then((r) => setRecentContent(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-4 md:p-8 space-y-6 md:space-y-8">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your content generation activity</p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {loading ? (
          <>
            <StatSkeleton />
            <StatSkeleton />
            <StatSkeleton />
          </>
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-indigo-100 dark:bg-indigo-900/40 rounded-lg flex items-center justify-center flex-shrink-0">
                    <BookOpen className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{topics.length}</p>
                    <p className="text-sm text-muted-foreground">Tracked Topics</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-emerald-100 dark:bg-emerald-900/40 rounded-lg flex items-center justify-center flex-shrink-0">
                    <History className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{recentContent.length}</p>
                    <p className="text-sm text-muted-foreground">Recent Pieces</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-orange-100 dark:bg-orange-900/40 rounded-lg flex items-center justify-center flex-shrink-0">
                    <TrendingUp className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{topics.filter((t) => t.last_crawled_at).length}</p>
                    <p className="text-sm text-muted-foreground">Topics with Data</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Quick actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild className="flex-1 sm:flex-none">
            <Link href="/generate">
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Content
            </Link>
          </Button>
          <Button variant="outline" asChild className="flex-1 sm:flex-none">
            <Link href="/settings?tab=topics">
              <BookOpen className="w-4 h-4 mr-2" />
              Manage Topics
            </Link>
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Topics status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Tracked Topics</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/settings?tab=topics">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center justify-between py-1">
                    <div className="h-4 w-32 bg-muted rounded animate-pulse" />
                    <div className="h-3 w-24 bg-muted rounded animate-pulse" />
                  </div>
                ))}
              </div>
            ) : topics.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No topics yet.{" "}
                <Link href="/settings?tab=topics" className="text-indigo-600 dark:text-indigo-400 hover:underline">
                  Add your first topic
                </Link>
              </p>
            ) : (
              topics.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center justify-between py-1 gap-2">
                  <span className="text-sm font-medium truncate">{t.name}</span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">
                    {t.last_crawled_at
                      ? `Crawled ${new Date(t.last_crawled_at).toLocaleDateString()}`
                      : "Not yet crawled"}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Recent content */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Recent Content</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/history">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-2 py-1">
                    <div className="h-5 w-16 bg-muted rounded animate-pulse" />
                    <div className="h-4 flex-1 bg-muted rounded animate-pulse" />
                  </div>
                ))}
              </div>
            ) : recentContent.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No content yet.{" "}
                <Link href="/generate" className="text-indigo-600 dark:text-indigo-400 hover:underline">
                  Generate your first post
                </Link>
              </p>
            ) : (
              recentContent.map((c) => (
                <div key={c.id} className="flex items-center gap-2 py-1">
                  <Badge className={PLATFORM_COLORS[c.platform]}>{PLATFORM_LABELS[c.platform]}</Badge>
                  <span className="text-sm truncate flex-1">{c.title || c.content.slice(0, 50)}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
