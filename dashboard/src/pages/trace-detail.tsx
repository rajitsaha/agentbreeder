import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Clock,
  Zap,
  DollarSign,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Timer,
  Cpu,
  Wrench,
  Bot,
  Database,
  Code,
} from "lucide-react";
import { api, type Span, type SpanType } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useState } from "react";

const SPAN_TYPE_CONFIG: Record<
  SpanType | string,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  llm: {
    label: "LLM",
    color: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20",
    icon: Cpu,
  },
  tool: {
    label: "Tool",
    color: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
    icon: Wrench,
  },
  agent: {
    label: "Agent",
    color: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
    icon: Bot,
  },
  retrieval: {
    label: "Retrieval",
    color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    icon: Database,
  },
  custom: {
    label: "Custom",
    color: "bg-muted text-muted-foreground border-border",
    icon: Code,
  },
};

const BAR_COLORS: Record<SpanType | string, string> = {
  llm: "bg-violet-500",
  tool: "bg-sky-500",
  agent: "bg-orange-500",
  retrieval: "bg-emerald-500",
  custom: "bg-muted-foreground",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  if (usd < 1) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  return `${(n / 1000).toFixed(1)}k`;
}

function JsonViewer({ data, label }: { data: Record<string, unknown> | null; label: string }) {
  if (!data || Object.keys(data).length === 0) return null;

  return (
    <div className="mt-2">
      <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted/50 p-3 font-mono text-[11px] leading-relaxed text-foreground">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function SpanRow({
  span,
  traceDuration,
  depth,
}: {
  span: Span;
  traceDuration: number;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showData, setShowData] = useState(false);
  const config = SPAN_TYPE_CONFIG[span.span_type] ?? SPAN_TYPE_CONFIG.custom;
  const barColor = BAR_COLORS[span.span_type] ?? BAR_COLORS.custom;
  const Icon = config.icon;

  const barWidth = traceDuration > 0 ? Math.max(2, (span.duration_ms / traceDuration) * 100) : 0;
  const hasChildren = span.children && span.children.length > 0;
  const hasData =
    (span.input_data && Object.keys(span.input_data).length > 0) ||
    (span.output_data && Object.keys(span.output_data).length > 0);

  return (
    <>
      <div
        className={cn(
          "group flex items-center gap-2 border-b border-border/30 px-4 py-2 transition-colors hover:bg-muted/20",
          showData && "bg-muted/10"
        )}
        style={{ paddingLeft: `${16 + depth * 24}px` }}
      >
        {/* Expand toggle for children */}
        <button
          onClick={() => hasChildren && setExpanded(!expanded)}
          className={cn(
            "flex size-4 items-center justify-center rounded-sm",
            hasChildren
              ? "text-muted-foreground hover:text-foreground"
              : "invisible"
          )}
        >
          {expanded ? (
            <ChevronDown className="size-3" />
          ) : (
            <ChevronRight className="size-3" />
          )}
        </button>

        {/* Status icon */}
        {span.status === "error" ? (
          <AlertCircle className="size-3.5 text-red-500" />
        ) : (
          <CheckCircle2 className="size-3.5 text-emerald-500" />
        )}

        {/* Span name + type */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Icon className="size-3.5 shrink-0 text-muted-foreground" />
          <button
            onClick={() => hasData && setShowData(!showData)}
            className={cn(
              "truncate text-xs font-medium",
              hasData && "cursor-pointer hover:text-primary"
            )}
            title={span.name}
          >
            {span.name}
          </button>
          <Badge variant="outline" className={cn("text-[9px] px-1.5 py-0 h-4", config.color)}>
            {config.label}
          </Badge>
          {span.model_name && (
            <span className="text-[10px] text-muted-foreground">{span.model_name}</span>
          )}
        </div>

        {/* Duration bar */}
        <div className="w-32 shrink-0">
          <div className="h-2 w-full rounded-full bg-muted/50">
            <div
              className={cn("h-2 rounded-full", barColor)}
              style={{ width: `${barWidth}%` }}
            />
          </div>
        </div>

        {/* Metrics */}
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-0.5 font-mono" title="Duration">
            <Timer className="size-2.5" />
            {formatDuration(span.duration_ms)}
          </span>
          {(span.input_tokens > 0 || span.output_tokens > 0) && (
            <span className="flex items-center gap-0.5 font-mono" title="Tokens">
              <Zap className="size-2.5" />
              {formatTokens(span.input_tokens + span.output_tokens)}
            </span>
          )}
          {span.cost_usd > 0 && (
            <span className="flex items-center gap-0.5 font-mono" title="Cost">
              <DollarSign className="size-2.5" />
              {formatCost(span.cost_usd)}
            </span>
          )}
        </div>
      </div>

      {/* Expanded data panel */}
      {showData && (
        <div
          className="border-b border-border/30 bg-muted/5 px-4 py-3"
          style={{ paddingLeft: `${40 + depth * 24}px` }}
        >
          <JsonViewer data={span.input_data} label="Input" />
          <JsonViewer data={span.output_data} label="Output" />
          {span.metadata && Object.keys(span.metadata).length > 0 && (
            <JsonViewer data={span.metadata} label="Metadata" />
          )}
        </div>
      )}

      {/* Children */}
      {expanded &&
        hasChildren &&
        span.children.map((child) => (
          <SpanRow
            key={child.span_id}
            span={child}
            traceDuration={traceDuration}
            depth={depth + 1}
          />
        ))}
    </>
  );
}

function buildSpanTree(spans: Span[]): Span[] {
  const lookup = new Map<string, Span>();
  const roots: Span[] = [];

  // First pass: index all spans and reset children
  for (const span of spans) {
    lookup.set(span.span_id, { ...span, children: [] });
  }

  // Second pass: build tree
  for (const span of spans) {
    const node = lookup.get(span.span_id)!;
    if (span.parent_span_id && lookup.has(span.parent_span_id)) {
      lookup.get(span.parent_span_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

export default function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ["trace-detail", traceId],
    queryFn: () => api.traces.get(traceId!),
    enabled: !!traceId,
    staleTime: 10_000,
  });

  const trace = data?.data?.trace;
  const spans = data?.data?.spans ?? [];
  const spanTree = buildSpanTree(spans);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 rounded bg-muted" />
          <div className="h-32 rounded-lg bg-muted" />
          <div className="h-64 rounded-lg bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <div className="text-center text-sm text-destructive">
          {error ? `Failed to load trace: ${(error as Error).message}` : "Trace not found"}
        </div>
      </div>
    );
  }

  const isError = trace.status === "error";

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Back link */}
      <Link
        to="/traces"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3" />
        Back to Traces
      </Link>

      {/* Header */}
      <div className="mb-6 rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-sm font-semibold">{trace.trace_id}</h1>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px]",
                  isError
                    ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                    : trace.status === "timeout"
                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                )}
              >
                {trace.status}
              </Badge>
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
              <span>Agent: {trace.agent_name}</span>
              {trace.model_name && (
                <>
                  <span className="text-border">|</span>
                  <span>Model: {trace.model_name}</span>
                </>
              )}
              <span className="text-border">|</span>
              <span>{new Date(trace.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>

        {/* Metrics row */}
        <div className="mt-4 flex items-center gap-6 text-xs">
          <div className="flex items-center gap-1.5">
            <Clock className="size-3.5 text-muted-foreground" />
            <span className="font-mono font-medium">{formatDuration(trace.duration_ms)}</span>
            <span className="text-muted-foreground">duration</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Zap className="size-3.5 text-muted-foreground" />
            <span className="font-mono font-medium">{formatTokens(trace.total_tokens)}</span>
            <span className="text-muted-foreground">
              tokens ({formatTokens(trace.input_tokens)} in / {formatTokens(trace.output_tokens)} out)
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <DollarSign className="size-3.5 text-muted-foreground" />
            <span className="font-mono font-medium">{formatCost(trace.cost_usd)}</span>
            <span className="text-muted-foreground">cost</span>
          </div>
        </div>

        {/* Error message */}
        {trace.error_message && (
          <div className="mt-4 rounded-md bg-red-500/5 border border-red-500/20 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-red-600 dark:text-red-400">
              <AlertCircle className="size-3.5" />
              Error
            </div>
            <pre className="mt-1 font-mono text-[11px] text-red-600/80 dark:text-red-400/80 whitespace-pre-wrap">
              {trace.error_message}
            </pre>
          </div>
        )}

        {/* Input/Output preview */}
        {(trace.input_preview || trace.output_preview) && (
          <div className="mt-4 grid grid-cols-2 gap-4">
            {trace.input_preview && (
              <div>
                <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Input
                </div>
                <div className="mt-1 rounded-md bg-muted/30 p-2 text-xs text-muted-foreground">
                  {trace.input_preview}
                </div>
              </div>
            )}
            {trace.output_preview && (
              <div>
                <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Output
                </div>
                <div className="mt-1 rounded-md bg-muted/30 p-2 text-xs text-muted-foreground">
                  {trace.output_preview}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spans timeline */}
      <div className="rounded-lg border border-border">
        <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Span Timeline
          </h2>
          <span className="text-[10px] text-muted-foreground">
            {spans.length} span{spans.length !== 1 ? "s" : ""}
          </span>
        </div>

        {spans.length === 0 ? (
          <div className="px-6 py-12 text-center text-xs text-muted-foreground">
            No spans recorded for this trace.
          </div>
        ) : (
          <div>
            {/* Span type legend */}
            <div className="flex items-center gap-4 border-b border-border/50 px-4 py-2">
              {Object.entries(SPAN_TYPE_CONFIG).map(([type, cfg]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <div
                    className={cn(
                      "size-2 rounded-full",
                      BAR_COLORS[type] ?? BAR_COLORS.custom
                    )}
                  />
                  <span className="text-[10px] text-muted-foreground">{cfg.label}</span>
                </div>
              ))}
            </div>

            {/* Span rows */}
            {spanTree.map((span) => (
              <SpanRow
                key={span.span_id}
                span={span}
                traceDuration={trace.duration_ms}
                depth={0}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
