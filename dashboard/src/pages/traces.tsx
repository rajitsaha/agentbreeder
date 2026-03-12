import { useQuery } from "@tanstack/react-query";
import { useSearchParams, Link } from "react-router-dom";
import {
  Activity,
  Search,
  Filter,
  Clock,
  Zap,
  DollarSign,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import { api, type Trace, type TraceStatus } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useState, useMemo } from "react";
import { SkeletonTableRows } from "@/components/ui/skeleton-table";
import { EmptyState } from "@/components/ui/empty-state";

const STATUS_VARIANTS: Record<TraceStatus, { label: string; className: string }> = {
  success: {
    label: "Success",
    className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  },
  error: {
    label: "Error",
    className: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
  },
  timeout: {
    label: "Timeout",
    className: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  },
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
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

function timeSince(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function StatsCard({
  label,
  value,
  icon: Icon,
  subValue,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  subValue?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tracking-tight">{value}</div>
      {subValue && (
        <div className="mt-0.5 text-[10px] text-muted-foreground">{subValue}</div>
      )}
    </div>
  );
}

function TraceRow({ trace }: { trace: Trace }) {
  const variant = STATUS_VARIANTS[trace.status] ?? STATUS_VARIANTS.error;

  return (
    <Link
      to={`/traces/${encodeURIComponent(trace.trace_id)}`}
      className="group flex items-center gap-4 border-b border-border/50 px-6 py-3 transition-colors last:border-0 hover:bg-muted/30"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-medium text-foreground group-hover:text-primary">
            {trace.trace_id.length > 24
              ? `${trace.trace_id.slice(0, 12)}...${trace.trace_id.slice(-8)}`
              : trace.trace_id}
          </span>
          <Badge variant="outline" className={cn("text-[10px]", variant.className)}>
            {variant.label}
          </Badge>
        </div>
        <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{trace.agent_name}</span>
          {trace.model_name && (
            <>
              <span className="text-border">|</span>
              <span>{trace.model_name}</span>
            </>
          )}
          {trace.input_preview && (
            <>
              <span className="text-border">|</span>
              <span className="truncate max-w-[200px]">{trace.input_preview}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1 font-mono" title="Duration">
          <Clock className="size-3" />
          {formatDuration(trace.duration_ms)}
        </span>
        <span className="flex items-center gap-1 font-mono" title="Tokens">
          <Zap className="size-3" />
          {formatTokens(trace.total_tokens)}
        </span>
        <span className="flex items-center gap-1 font-mono" title="Cost">
          <DollarSign className="size-3" />
          {formatCost(trace.cost_usd)}
        </span>
        <span className="w-14 text-right font-mono text-[10px]">
          {timeSince(trace.created_at)}
        </span>
        <ChevronRight className="size-3.5 text-muted-foreground/50" />
      </div>
    </Link>
  );
}

export default function TracesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [agentFilter, setAgentFilter] = useState(searchParams.get("agent_name") ?? "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");

  const { data, isLoading, error } = useQuery({
    queryKey: ["traces", { search, agentFilter, statusFilter }],
    queryFn: () =>
      api.traces.list({
        q: search || undefined,
        agent_name: agentFilter || undefined,
        status: (statusFilter as TraceStatus) || undefined,
        per_page: 50,
      }),
    staleTime: 5_000,
  });

  const traces = data?.data ?? [];
  const total = data?.meta?.total ?? 0;

  // Compute stats from current page
  const stats = useMemo(() => {
    if (traces.length === 0) {
      return { total: 0, avgDuration: 0, totalCost: 0, errorRate: 0 };
    }
    const errors = traces.filter((t) => t.status === "error").length;
    const avgDuration = traces.reduce((sum, t) => sum + t.duration_ms, 0) / traces.length;
    const totalCost = traces.reduce((sum, t) => sum + t.cost_usd, 0);
    return {
      total,
      avgDuration: Math.round(avgDuration),
      totalCost,
      errorRate: (errors / traces.length) * 100,
    };
  }, [traces, total]);

  // Extract unique agent names for filter dropdown
  const agentNames = useMemo(() => {
    const names = new Set<string>();
    for (const t of traces) names.add(t.agent_name);
    return [...names].sort();
  }, [traces]);

  const handleSearch = (value: string) => {
    setSearch(value);
    const sp = new URLSearchParams(searchParams);
    if (value) sp.set("q", value);
    else sp.delete("q");
    setSearchParams(sp, { replace: true });
  };

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-lg font-semibold tracking-tight">Traces</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Agent execution traces and observability
        </p>
      </div>

      {/* Stats cards */}
      <div className="mb-6 grid grid-cols-4 gap-4">
        <StatsCard
          label="Total Traces"
          value={String(stats.total)}
          icon={Activity}
        />
        <StatsCard
          label="Avg Duration"
          value={formatDuration(stats.avgDuration)}
          icon={Clock}
        />
        <StatsCard
          label="Total Cost"
          value={formatCost(stats.totalCost)}
          icon={DollarSign}
        />
        <StatsCard
          label="Error Rate"
          value={`${stats.errorRate.toFixed(1)}%`}
          icon={AlertTriangle}
          subValue={`${traces.filter((t) => t.status === "error").length} errors`}
        />
      </div>

      {/* Filters */}
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search traces..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="h-8 pl-9 text-xs"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="size-3.5 text-muted-foreground" />
          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs outline-none"
          >
            <option value="">All agents</option>
            {agentNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs outline-none"
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
            <option value="timeout">Timeout</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-border">
        {/* Column headers */}
        <div className="flex items-center gap-4 border-b border-border bg-muted/30 px-6 py-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          <span className="flex-1">Trace</span>
          <span className="w-16 text-right">Duration</span>
          <span className="w-14 text-right">Tokens</span>
          <span className="w-14 text-right">Cost</span>
          <span className="w-14 text-right">When</span>
          <span className="w-3.5" />
        </div>

        {isLoading ? (
          <SkeletonTableRows rows={8} columns={4} />
        ) : error ? (
          <div className="px-6 py-12 text-center text-sm text-destructive">
            Failed to load traces: {(error as Error).message}
          </div>
        ) : traces.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={search || agentFilter || statusFilter ? "No traces match your filters" : "No traces yet"}
            description={
              search || agentFilter || statusFilter
                ? "Try adjusting your search or filters."
                : "Traces will appear here as agents process requests."
            }
          />
        ) : (
          traces.map((trace) => <TraceRow key={trace.trace_id} trace={trace} />)
        )}
      </div>
    </div>
  );
}
