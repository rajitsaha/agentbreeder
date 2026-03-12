import { useState, useEffect, useMemo } from "react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";

/**
 * Formats a Date as a human-friendly relative time string.
 *
 * - "just now"       (< 60 seconds)
 * - "2 minutes ago"  (< 60 minutes)
 * - "3 hours ago"    (< 24 hours)
 * - "yesterday"      (24-48 hours)
 * - "Mar 9, 2026"    (>= 48 hours)
 */
export function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return "just now";

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return diffMin === 1 ? "1 minute ago" : `${diffMin} minutes ago`;
  }

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    return diffHr === 1 ? "1 hour ago" : `${diffHr} hours ago`;
  }

  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "yesterday";

  // For anything older than 48 hours, use an absolute date
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Formats a Date as a full absolute string for the tooltip. */
function formatAbsoluteTime(date: Date): string {
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

interface RelativeTimeProps {
  /** The date to display. Accepts a Date object or an ISO string. */
  date: string | Date;
  /** Additional CSS class names for the outer element. */
  className?: string;
}

/**
 * Displays a relative timestamp that auto-updates every minute.
 * Hovering shows the exact absolute time in a tooltip.
 */
export function RelativeTime({ date, className }: RelativeTimeProps) {
  const dateObj = useMemo(
    () => (date instanceof Date ? date : new Date(date)),
    [date],
  );

  const [, setTick] = useState(0);

  useEffect(() => {
    // Re-render every 60 seconds so "X minutes ago" stays current.
    const id = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  const relative = formatRelativeTime(dateObj);
  const absolute = formatAbsoluteTime(dateObj);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          className={className}
          render={<time dateTime={dateObj.toISOString()} />}
        >
          {relative}
        </TooltipTrigger>
        <TooltipContent>{absolute}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
