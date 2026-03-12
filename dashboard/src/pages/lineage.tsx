import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  GitBranch,
  Bot,
  Wrench,
  Cpu,
  FileText,
  Database,
  Brain,
  Server,
  Search,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api, type LineageNode, type LineageEdge, type AffectedAgent } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESOURCE_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  agent: Bot,
  tool: Wrench,
  model: Cpu,
  prompt: FileText,
  knowledge_base: Database,
  memory: Brain,
  mcp_server: Server,
};

const RESOURCE_TYPE_COLORS: Record<string, string> = {
  agent: "border-sky-500/40 bg-sky-500/5",
  tool: "border-violet-500/40 bg-violet-500/5",
  model: "border-emerald-500/40 bg-emerald-500/5",
  prompt: "border-amber-500/40 bg-amber-500/5",
  knowledge_base: "border-orange-500/40 bg-orange-500/5",
  memory: "border-pink-500/40 bg-pink-500/5",
  mcp_server: "border-indigo-500/40 bg-indigo-500/5",
};

const RESOURCE_BADGE_COLORS: Record<string, string> = {
  agent: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
  tool: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20",
  model: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  prompt: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  knowledge_base: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
  memory: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/20",
  mcp_server: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20",
};

const SEARCHABLE_TYPES = [
  { value: "agent", label: "Agent" },
  { value: "tool", label: "Tool" },
  { value: "model", label: "Model" },
  { value: "prompt", label: "Prompt" },
  { value: "mcp_server", label: "MCP Server" },
  { value: "knowledge_base", label: "Knowledge Base" },
  { value: "memory", label: "Memory" },
] as const;

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function NodeCard({
  node,
  isCenter,
}: {
  node: LineageNode;
  isCenter?: boolean;
}) {
  const Icon = RESOURCE_TYPE_ICONS[node.type] ?? GitBranch;
  const colorClass = RESOURCE_TYPE_COLORS[node.type] ?? "border-border bg-card";

  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-lg border-2 px-3 py-2.5 transition-colors",
        colorClass,
        isCenter && "ring-2 ring-foreground/20 shadow-md"
      )}
    >
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{node.name}</div>
        <div className="flex items-center gap-1.5">
          <Badge
            variant="outline"
            className={cn(
              "text-[9px] capitalize",
              RESOURCE_BADGE_COLORS[node.type]
            )}
          >
            {node.type.replace("_", " ")}
          </Badge>
          <span className="text-[10px] text-muted-foreground">{node.status}</span>
        </div>
      </div>
    </div>
  );
}

function LineageTree({
  nodes,
  edges,
  centerId,
}: {
  nodes: LineageNode[];
  edges: LineageEdge[];
  centerId: string;
}) {
  const centerNode = nodes.find((n) => n.id === centerId);
  if (!centerNode) return null;

  // "depends on" — edges where center is source
  const dependsOnEdges = edges.filter((e) => e.source_id === centerId);
  const dependsOnNodes = dependsOnEdges
    .map((e) => {
      const node = nodes.find((n) => n.id === e.target_id);
      return node ? { node, edge: e } : null;
    })
    .filter(Boolean) as { node: LineageNode; edge: LineageEdge }[];

  // "used by" — edges where center is target
  const usedByEdges = edges.filter((e) => e.target_id === centerId);
  const usedByNodes = usedByEdges
    .map((e) => {
      const node = nodes.find((n) => n.id === e.source_id);
      return node ? { node, edge: e } : null;
    })
    .filter(Boolean) as { node: LineageNode; edge: LineageEdge }[];

  return (
    <div className="flex items-start justify-center gap-8 py-8">
      {/* Left: Depends on */}
      {dependsOnNodes.length > 0 && (
        <div className="flex flex-col items-end gap-3">
          <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Depends on
          </div>
          {dependsOnNodes.map(({ node, edge }) => (
            <div key={node.id} className="flex items-center gap-3">
              <NodeCard node={node} />
              <div className="flex items-center gap-1">
                <div className="h-px w-8 bg-border" />
                <Badge
                  variant="outline"
                  className="text-[9px] whitespace-nowrap text-muted-foreground"
                >
                  {edge.dependency_type.replace("uses_", "")}
                </Badge>
                <ArrowRight className="size-3 text-muted-foreground" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Center node */}
      <div className="flex flex-col items-center gap-2 pt-6">
        <NodeCard node={centerNode} isCenter />
      </div>

      {/* Right: Used by */}
      {usedByNodes.length > 0 && (
        <div className="flex flex-col items-start gap-3">
          <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Used by
          </div>
          {usedByNodes.map(({ node, edge }) => (
            <div key={node.id} className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <ArrowRight className="size-3 text-muted-foreground" />
                <Badge
                  variant="outline"
                  className="text-[9px] whitespace-nowrap text-muted-foreground"
                >
                  {edge.dependency_type.replace("uses_", "")}
                </Badge>
                <div className="h-px w-8 bg-border" />
              </div>
              <NodeCard node={node} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ImpactPanel({
  resourceType,
  resourceName,
}: {
  resourceType: string;
  resourceName: string;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["lineage-impact", resourceType, resourceName],
    queryFn: () => api.lineage.impact(resourceType, resourceName),
    enabled: !!resourceType && !!resourceName,
  });

  const affected: AffectedAgent[] = data?.data?.affected_agents ?? [];

  if (isLoading) return null;
  if (affected.length === 0) return null;

  return (
    <div className="mt-6 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="size-4 text-amber-500" />
        <span className="text-sm font-medium">Impact Analysis</span>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        If you change <strong>{resourceName}</strong> ({resourceType}), these agents are affected:
      </p>
      <div className="space-y-2">
        {affected.map((a, i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2"
          >
            <Bot className="size-3.5 text-muted-foreground" />
            <span className="text-sm">{a.name}</span>
            <Badge variant="outline" className="ml-auto text-[9px]">
              {a.dependency_type.replace("uses_", "")}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LineagePage() {
  const [resourceType, setResourceType] = useState("agent");
  const [resourceId, setResourceId] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const { data, isLoading, isFetched } = useQuery({
    queryKey: ["lineage-graph", resourceType, resourceId],
    queryFn: () => api.lineage.graph(resourceType, resourceId),
    enabled: !!resourceId,
  });

  const nodes: LineageNode[] = data?.data?.nodes ?? [];
  const edges: LineageEdge[] = data?.data?.edges ?? [];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      setResourceId(searchInput.trim());
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6">
        <h1 className="text-lg font-semibold tracking-tight">Lineage</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Explore resource dependencies and impact analysis
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="mb-6 flex items-center gap-3">
        <select
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
        >
          {SEARCHABLE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>

        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Enter resource name or ID..."
            className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
          />
        </div>

        <button
          type="submit"
          className="h-9 rounded-md bg-foreground px-4 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
        >
          View Lineage
        </button>
      </form>

      {/* Graph */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="size-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        </div>
      ) : isFetched && resourceId && nodes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="mb-4 flex size-12 items-center justify-center rounded-xl border border-dashed border-border">
            <GitBranch className="size-5 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium">No dependencies found</h3>
          <p className="mt-1 max-w-xs text-xs text-muted-foreground">
            This resource has no registered dependencies. Dependencies are synced during deployment.
          </p>
        </div>
      ) : nodes.length > 0 ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
            <LineageTree
              nodes={nodes}
              edges={edges}
              centerId={resourceId}
            />
          </div>

          {/* Impact analysis */}
          <ImpactPanel
            resourceType={resourceType}
            resourceName={
              nodes.find((n) => n.id === resourceId)?.name ?? resourceId
            }
          />
        </>
      ) : (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="mb-4 flex size-12 items-center justify-center rounded-xl border border-dashed border-border">
            <GitBranch className="size-5 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium">Explore resource lineage</h3>
          <p className="mt-1 max-w-xs text-xs text-muted-foreground">
            Select a resource type and enter its name or ID to view its dependency graph.
          </p>
        </div>
      )}
    </div>
  );
}
