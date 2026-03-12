import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ScrollText,
  Rocket,
  Plus,
  Pencil,
  Trash2,
  CheckCircle2,
  XCircle,
  LogIn,
  Settings,
  Shield,
  ChevronDown,
  ChevronRight,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { RelativeTime } from "@/components/ui/relative-time";
import { cn } from "@/lib/utils";
import { api, type AuditEvent } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTION_BADGE_COLORS: Record<string, string> = {
  deploy: "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/20",
  create: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  update: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/20",
  delete: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/20",
  approve: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  reject: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/20",
  login: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  config_change: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/20",
  access_change: "bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/20",
};

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  deploy: Rocket,
  create: Plus,
  update: Pencil,
  delete: Trash2,
  approve: CheckCircle2,
  reject: XCircle,
  login: LogIn,
  config_change: Settings,
  access_change: Shield,
};

const RESOURCE_TYPES = [
  "all",
  "agent",
  "tool",
  "prompt",
  "model",
  "team",
  "mcp_server",
  "knowledge_base",
] as const;

const ACTIONS = [
  "all",
  "deploy",
  "create",
  "update",
  "delete",
  "approve",
  "reject",
  "login",
  "config_change",
  "access_change",
] as const;

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function SummaryCard({
  label,
  value,
  icon: Icon,
  className,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-card p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const [expanded, setExpanded] = useState(false);
  const ActionIcon = ACTION_ICONS[event.action] ?? ScrollText;
  const badgeColor =
    ACTION_BADGE_COLORS[event.action] ??
    "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20";

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/20"
      >
        <ActionIcon className="size-4 shrink-0 text-muted-foreground" />
        <RelativeTime
          date={event.created_at}
          className="w-28 shrink-0 text-xs text-muted-foreground"
        />
        <span className="w-32 shrink-0 truncate text-sm">{event.actor}</span>
        <Badge variant="outline" className={cn("text-[10px] capitalize", badgeColor)}>
          {event.action}
        </Badge>
        <span className="w-24 shrink-0 text-xs text-muted-foreground capitalize">
          {event.resource_type}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm">{event.resource_name}</span>
        <span className="w-24 shrink-0 truncate text-xs text-muted-foreground">
          {event.team ?? "-"}
        </span>
        {expanded ? (
          <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div className="border-t border-border/30 bg-muted/10 px-4 py-3">
          <div className="text-xs font-medium text-muted-foreground mb-1">Details</div>
          <pre className="max-h-48 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
            {JSON.stringify(event.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AuditPage() {
  const [actorFilter, setActorFilter] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>("all");
  const [page] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: [
      "audit-events",
      actorFilter,
      actionFilter,
      resourceTypeFilter,
      page,
    ],
    queryFn: () =>
      api.audit.list({
        actor: actorFilter || undefined,
        action: actionFilter === "all" ? undefined : actionFilter,
        resource_type: resourceTypeFilter === "all" ? undefined : resourceTypeFilter,
        page,
        per_page: 50,
      }),
    refetchInterval: 15_000,
  });

  const events: AuditEvent[] = data?.data ?? [];
  const total = data?.meta?.total ?? 0;

  // Summary cards: count today's events by type
  const summaryStats = useMemo(() => {
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const todayEvents = events.filter(
      (e) => new Date(e.created_at) >= todayStart
    );
    return {
      total: todayEvents.length,
      deploys: todayEvents.filter((e) => e.action === "deploy").length,
      configChanges: todayEvents.filter(
        (e) => e.action === "config_change" || e.action === "update"
      ).length,
      accessChanges: todayEvents.filter(
        (e) => e.action === "access_change"
      ).length,
    };
  }, [events]);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6">
        <h1 className="text-lg font-semibold tracking-tight">Audit Log</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {total} event{total !== 1 ? "s" : ""} recorded
        </p>
      </div>

      {/* Summary cards */}
      <div className="mb-6 grid grid-cols-4 gap-4">
        <SummaryCard
          label="Events today"
          value={summaryStats.total}
          icon={ScrollText}
        />
        <SummaryCard
          label="Deploys today"
          value={summaryStats.deploys}
          icon={Rocket}
        />
        <SummaryCard
          label="Config changes today"
          value={summaryStats.configChanges}
          icon={Settings}
        />
        <SummaryCard
          label="Access changes today"
          value={summaryStats.accessChanges}
          icon={Shield}
        />
      </div>

      {/* Filter bar */}
      <div className="mb-4 flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            placeholder="Filter by actor..."
            className="h-8 w-48 rounded-md border border-input bg-background pl-8 pr-3 text-xs outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
          />
        </div>

        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs outline-none"
        >
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a === "all" ? "All actions" : a.replace("_", " ")}
            </option>
          ))}
        </select>

        <select
          value={resourceTypeFilter}
          onChange={(e) => setResourceTypeFilter(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs outline-none"
        >
          {RESOURCE_TYPES.map((rt) => (
            <option key={rt} value={rt}>
              {rt === "all" ? "All resources" : rt.replace("_", " ")}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="size-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="mb-4 flex size-12 items-center justify-center rounded-xl border border-dashed border-border">
            <ScrollText className="size-5 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium">No audit events</h3>
          <p className="mt-1 max-w-xs text-xs text-muted-foreground">
            Audit events will appear here as actions are performed across the platform.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-4 py-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            <span className="w-4" />
            <span className="w-28">Time</span>
            <span className="w-32">Actor</span>
            <span className="w-20">Action</span>
            <span className="w-24">Resource</span>
            <span className="min-w-0 flex-1">Name</span>
            <span className="w-24">Team</span>
            <span className="w-4" />
          </div>

          {events.map((event) => (
            <AuditRow key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
