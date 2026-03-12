import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  computeDiff,
  groupIntoHunks,
  type DiffLine,
  type DiffHunk,
} from "@/lib/diff";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConfigDiffViewerProps {
  before: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
  contextLines?: number;
}

// ---------------------------------------------------------------------------
// Collapsed section
// ---------------------------------------------------------------------------

function CollapsedSection({
  hunk,
  onExpand,
}: {
  hunk: DiffHunk;
  onExpand: () => void;
}) {
  return (
    <button
      onClick={onExpand}
      className={cn(
        "flex w-full items-center justify-center gap-1.5 py-1",
        "bg-muted/40 text-[11px] text-muted-foreground",
        "border-y border-border/50",
        "transition-colors hover:bg-muted/70 hover:text-foreground",
        "cursor-pointer"
      )}
    >
      <ChevronRight className="size-3" />
      <span>{hunk.lines.length} unchanged lines</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Diff line row (side-by-side)
// ---------------------------------------------------------------------------

function DiffLineRow({ line }: { line: DiffLine }) {
  const bgClass =
    line.type === "added"
      ? "bg-green-500/10 dark:bg-green-500/15"
      : line.type === "removed"
        ? "bg-red-500/10 dark:bg-red-500/15"
        : "";

  const textClass =
    line.type === "added"
      ? "text-green-800 dark:text-green-300"
      : line.type === "removed"
        ? "text-red-800 dark:text-red-300"
        : "text-foreground";

  const lineNumClass =
    line.type === "added"
      ? "text-green-600/50 dark:text-green-400/40"
      : line.type === "removed"
        ? "text-red-600/50 dark:text-red-400/40"
        : "text-muted-foreground/40";

  const prefix =
    line.type === "added" ? "+" : line.type === "removed" ? "-" : " ";

  return (
    <div className={cn("flex hover:brightness-95 dark:hover:brightness-110", bgClass)}>
      {/* Old line number */}
      <span
        className={cn(
          "w-10 shrink-0 select-none text-right font-mono text-[11px] leading-6",
          lineNumClass
        )}
      >
        {line.oldLineNumber ?? ""}
      </span>
      {/* New line number */}
      <span
        className={cn(
          "w-10 shrink-0 select-none text-right font-mono text-[11px] leading-6",
          lineNumClass
        )}
      >
        {line.newLineNumber ?? ""}
      </span>
      {/* Prefix (+/-/space) */}
      <span
        className={cn(
          "w-5 shrink-0 select-none text-center font-mono text-[12px] leading-6 font-bold",
          textClass
        )}
      >
        {prefix}
      </span>
      {/* Content */}
      <span
        className={cn(
          "flex-1 whitespace-pre font-mono text-[13px] leading-6 pr-4",
          textClass
        )}
      >
        {line.content}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main diff viewer component
// ---------------------------------------------------------------------------

export function ConfigDiffViewer({
  before,
  after,
  beforeLabel = "Before",
  afterLabel = "After",
  contextLines = 3,
}: ConfigDiffViewerProps) {
  const diffLines = useMemo(() => computeDiff(before, after), [before, after]);
  const hunks = useMemo(
    () => groupIntoHunks(diffLines, contextLines),
    [diffLines, contextLines]
  );

  // Track which unchanged hunks are expanded
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const toggleExpand = (index: number) => {
    setExpanded((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  // Stats
  const addedCount = diffLines.filter((l) => l.type === "added").length;
  const removedCount = diffLines.filter((l) => l.type === "removed").length;

  const isIdentical = addedCount === 0 && removedCount === 0;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-[#fafafa] dark:bg-[#0d1117]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2">
        <div className="flex items-center gap-4">
          <span className="text-xs font-medium text-muted-foreground">
            {beforeLabel}
          </span>
          <span className="text-muted-foreground/40">vs</span>
          <span className="text-xs font-medium text-muted-foreground">
            {afterLabel}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          {addedCount > 0 && (
            <span className="font-mono text-green-600 dark:text-green-400">
              +{addedCount}
            </span>
          )}
          {removedCount > 0 && (
            <span className="font-mono text-red-600 dark:text-red-400">
              -{removedCount}
            </span>
          )}
          {isIdentical && (
            <span className="text-muted-foreground">No changes</span>
          )}
        </div>
      </div>

      {/* Column headers */}
      <div className="flex border-b border-border/50 bg-muted/20 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        <span className="w-10 shrink-0 py-1 text-right">Old</span>
        <span className="w-10 shrink-0 py-1 text-right">New</span>
        <span className="w-5 shrink-0" />
        <span className="flex-1 py-1 pl-1" />
      </div>

      {/* Diff content */}
      <div className="overflow-x-auto">
        <pre className="font-mono text-[13px]">
          <code>
            {hunks.map((hunk, hunkIdx) => {
              if (hunk.type === "unchanged") {
                const isCollapsible = hunk.lines.length > contextLines * 2;
                const isExpanded = expanded[hunkIdx] ?? false;

                if (isCollapsible && !isExpanded) {
                  // Show context lines at top and bottom, collapse middle
                  const topContext = hunk.lines.slice(0, contextLines);
                  const bottomContext = hunk.lines.slice(-contextLines);
                  const collapsedHunk: DiffHunk = {
                    type: "unchanged",
                    lines: hunk.lines.slice(
                      contextLines,
                      hunk.lines.length - contextLines
                    ),
                  };

                  return (
                    <div key={hunkIdx}>
                      {topContext.map((line, i) => (
                        <DiffLineRow
                          key={`${hunkIdx}-top-${i}`}
                          line={line}
                        />
                      ))}
                      <CollapsedSection
                        hunk={collapsedHunk}
                        onExpand={() => toggleExpand(hunkIdx)}
                      />
                      {bottomContext.map((line, i) => (
                        <DiffLineRow
                          key={`${hunkIdx}-bottom-${i}`}
                          line={line}
                        />
                      ))}
                    </div>
                  );
                }

                // Show all lines (either small section or expanded)
                return (
                  <div key={hunkIdx}>
                    {isCollapsible && isExpanded && (
                      <button
                        onClick={() => toggleExpand(hunkIdx)}
                        className={cn(
                          "flex w-full items-center justify-center gap-1.5 py-1",
                          "bg-muted/40 text-[11px] text-muted-foreground",
                          "border-y border-border/50",
                          "transition-colors hover:bg-muted/70 hover:text-foreground",
                          "cursor-pointer"
                        )}
                      >
                        <ChevronDown className="size-3" />
                        <span>Collapse {hunk.lines.length} unchanged lines</span>
                      </button>
                    )}
                    {hunk.lines.map((line, i) => (
                      <DiffLineRow key={`${hunkIdx}-${i}`} line={line} />
                    ))}
                  </div>
                );
              }

              // Changed lines — always shown
              return (
                <div key={hunkIdx}>
                  {hunk.lines.map((line, i) => (
                    <DiffLineRow key={`${hunkIdx}-${i}`} line={line} />
                  ))}
                </div>
              );
            })}
          </code>
        </pre>
      </div>
    </div>
  );
}
