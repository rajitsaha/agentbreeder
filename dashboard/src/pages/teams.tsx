import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Shield, Users, Plus, ChevronRight } from "lucide-react";
import { api, type TeamResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";

function CreateTeamDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      api.teams.create({ name, display_name: displayName, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      onOpenChange(false);
      setName("");
      setDisplayName("");
      setDescription("");
    },
  });

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      <div className="fixed inset-x-0 top-[20%] z-50 mx-auto w-full max-w-md">
        <div className="rounded-xl border border-border bg-card p-6 shadow-2xl">
          <h2 className="mb-4 text-lg font-semibold">Create Team</h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Slug Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="engineering"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Display Name
              </label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Engineering Team"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional team description..."
                rows={2}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!name.trim() || !displayName.trim() || createMut.isPending}
              onClick={() => createMut.mutate()}
            >
              {createMut.isPending ? "Creating..." : "Create Team"}
            </Button>
          </div>
          {createMut.isError && (
            <p className="mt-2 text-xs text-destructive">
              {(createMut.error as Error).message}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function TeamCard({ team }: { team: TeamResponse }) {
  return (
    <Link
      to={`/teams/${team.id}`}
      className="group flex items-center gap-4 rounded-lg border border-border/50 bg-card p-4 transition-all hover:border-border hover:shadow-sm"
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <Users className="size-5 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium group-hover:text-primary">
            {team.display_name}
          </span>
          <Badge variant="outline" className="text-[10px]">
            {team.name}
          </Badge>
        </div>
        {team.description && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {team.description}
          </p>
        )}
        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Users className="size-3" />
            {team.member_count} member{team.member_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>
      <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

export default function TeamsPage() {
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["teams"],
    queryFn: () => api.teams.list(),
  });

  const teams = data?.data ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10">
            <Shield className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Teams</h1>
            <p className="text-sm text-muted-foreground">
              Manage teams, roles, and API key access
            </p>
          </div>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 size-3.5" />
          Create Team
        </Button>
      </div>

      <CreateTeamDialog open={createOpen} onOpenChange={setCreateOpen} />

      {/* Content */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-lg border border-border/50 bg-muted/30"
            />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
          Failed to load teams: {(error as Error).message}
        </div>
      )}

      {!isLoading && !error && teams.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <Users className="mb-3 size-10 text-muted-foreground/50" />
          <h3 className="text-sm font-medium">No teams yet</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Create your first team to start managing access
          </p>
          <Button
            size="sm"
            className="mt-4"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="mr-1.5 size-3.5" />
            Create Team
          </Button>
        </div>
      )}

      {!isLoading && teams.length > 0 && (
        <div className="space-y-2">
          {teams.map((team) => (
            <TeamCard key={team.id} team={team} />
          ))}
        </div>
      )}
    </div>
  );
}
