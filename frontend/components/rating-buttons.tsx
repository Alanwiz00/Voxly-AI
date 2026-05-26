"use client";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface RatingButtonsProps {
  contentId: number;
  rating: number | null | undefined;
  onRate: (id: number, rating: number) => void;
}

export default function RatingButtons({ contentId, rating, onRate }: RatingButtonsProps) {
  const handleRate = (value: number) => {
    // clicking same button toggles off (rating = 0 = remove)
    onRate(contentId, rating === value ? 0 : value);
  };

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleRate(1)}
        aria-label="Thumbs up"
        className={cn(
          "p-1.5 rounded-md transition-colors",
          rating === 1
            ? "text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400"
            : "text-muted-foreground hover:text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20"
        )}
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => handleRate(-1)}
        aria-label="Thumbs down"
        className={cn(
          "p-1.5 rounded-md transition-colors",
          rating === -1
            ? "text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400"
            : "text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
        )}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
