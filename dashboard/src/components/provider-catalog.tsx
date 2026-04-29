/**
 * Provider catalog — surfaces the OpenAI-compatible presets shipped in
 * `engine/providers/catalog.yaml` (Nvidia, Groq, Together, OpenRouter, …) so
 * users can connect a provider with a single click.
 *
 * Backed by `GET /api/v1/providers/catalog` (Track F / issue #160). The
 * "Configure" button currently surfaces the env-var that needs to be set —
 * wiring it to a secrets-entry modal lands with Track K.
 */

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Plug, Server } from "lucide-react";

import { api, type CatalogProvider } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface ProviderCatalogProps {
  onConfigure?: (provider: CatalogProvider) => void;
}

export function ProviderCatalog({ onConfigure }: ProviderCatalogProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["providers", "catalog"],
    queryFn: () => api.providers.catalog(),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-muted/20 p-4 text-xs text-muted-foreground">
        Loading provider catalog...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive">
        Failed to load catalog: {(error as Error).message}
      </div>
    );
  }

  const presets = data?.data ?? [];
  if (presets.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <Server className="size-3.5 text-muted-foreground" />
          <h3 className="text-sm font-semibold">OpenAI-Compatible Catalog</h3>
          <Badge variant="outline" className="text-[10px]">
            {presets.length} providers
          </Badge>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Click Configure to connect — keys live in your environment, never the database
        </span>
      </div>

      <div className="divide-y divide-border/50">
        {presets.map((preset) => (
          <CatalogRow
            key={preset.name}
            preset={preset}
            onConfigure={onConfigure}
          />
        ))}
      </div>
    </div>
  );
}

function CatalogRow({
  preset,
  onConfigure,
}: {
  preset: CatalogProvider;
  onConfigure?: (preset: CatalogProvider) => void;
}) {
  const isUserLocal = preset.source === "user-local";

  return (
    <div className="flex items-center gap-4 px-4 py-3">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="font-medium text-sm capitalize">{preset.name}</div>
        {isUserLocal && (
          <Badge variant="secondary" className="text-[10px]">
            user-local
          </Badge>
        )}
        <span className="truncate text-[11px] text-muted-foreground">
          {preset.base_url}
        </span>
      </div>

      <code className="rounded bg-muted/50 px-2 py-0.5 text-[10px] text-muted-foreground">
        {preset.api_key_env}
      </code>

      {preset.docs && (
        <a
          href={preset.docs}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
        >
          Docs
          <ExternalLink className="size-3" />
        </a>
      )}

      <Button
        size="sm"
        variant="outline"
        onClick={() => onConfigure?.(preset)}
        className="h-7 text-xs"
        data-testid={`catalog-configure-${preset.name}`}
      >
        <Plug className="mr-1 size-3" />
        Configure
      </Button>
    </div>
  );
}
