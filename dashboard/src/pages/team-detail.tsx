import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Shield,
  Users,
  Key,
  Bot,
  Plus,
  Trash2,
  ArrowLeft,
  TestTube,
} from "lucide-react";
import { api, type TeamDetailResponse, type TeamMemberResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";

type Tab = "members" | "api-keys" | "agents";

function AddMemberDialog({
  open,
  onOpenChange,
  teamId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  teamId: string;
}) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");

  const addMut = useMutation({
    mutationFn: () =>
      api.teams.addMember(teamId, { user_email: email, role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", teamId] });
      onOpenChange(false);
      setEmail("");
      setRole("viewer");
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
          <h2 className="mb-4 text-lg font-semibold">Add Member</h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Email
              </label>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@company.com"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="viewer">Viewer</option>
                <option value="deployer">Deployer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!email.trim() || addMut.isPending}
              onClick={() => addMut.mutate()}
            >
              {addMut.isPending ? "Adding..." : "Add Member"}
            </Button>
          </div>
          {addMut.isError && (
            <p className="mt-2 text-xs text-destructive">
              {(addMut.error as Error).message}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function AddApiKeyDialog({
  open,
  onOpenChange,
  teamId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  teamId: string;
}) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");

  const addMut = useMutation({
    mutationFn: () =>
      api.teams.setApiKey(teamId, { provider, api_key: apiKey }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-api-keys", teamId] });
      onOpenChange(false);
      setProvider("openai");
      setApiKey("");
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
          <h2 className="mb-4 text-lg font-semibold">Add API Key</h2>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Provider
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="ollama">Ollama</option>
                <option value="openrouter">OpenRouter</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!apiKey.trim() || addMut.isPending}
              onClick={() => addMut.mutate()}
            >
              {addMut.isPending ? "Saving..." : "Save Key"}
            </Button>
          </div>
          {addMut.isError && (
            <p className="mt-2 text-xs text-destructive">
              {(addMut.error as Error).message}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function MembersTab({ teamId, members }: { teamId: string; members: TeamMemberResponse[] }) {
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);

  const removeMut = useMutation({
    mutationFn: (userId: string) => api.teams.removeMember(teamId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", teamId] }),
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.teams.updateMemberRole(teamId, userId, { role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", teamId] }),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium">
          Members ({members.length})
        </h3>
        <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
          <Plus className="mr-1.5 size-3.5" />
          Add Member
        </Button>
      </div>

      <AddMemberDialog open={addOpen} onOpenChange={setAddOpen} teamId={teamId} />

      <div className="rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Name</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Email</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Role</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className="border-b border-border/50 last:border-0">
                <td className="px-4 py-2.5 font-medium">{m.user_name}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{m.user_email}</td>
                <td className="px-4 py-2.5">
                  <select
                    value={m.role}
                    onChange={(e) =>
                      updateRoleMut.mutate({ userId: m.user_id, role: e.target.value })
                    }
                    className="rounded border border-border bg-background px-2 py-0.5 text-xs"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="deployer">Deployer</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => removeMut.mutate(m.user_id)}
                    className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    title="Remove member"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </td>
              </tr>
            ))}
            {members.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                  No members yet. Add the first member.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ApiKeysTab({ teamId }: { teamId: string }) {
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["team-api-keys", teamId],
    queryFn: () => api.teams.listApiKeys(teamId),
  });

  const deleteMut = useMutation({
    mutationFn: (keyId: string) => api.teams.deleteApiKey(teamId, keyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team-api-keys", teamId] }),
  });

  const testMut = useMutation({
    mutationFn: (keyId: string) => api.teams.testApiKey(teamId, keyId),
  });

  const keys = data?.data ?? [];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium">
          API Keys ({keys.length})
        </h3>
        <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
          <Plus className="mr-1.5 size-3.5" />
          Add Key
        </Button>
      </div>

      <AddApiKeyDialog open={addOpen} onOpenChange={setAddOpen} teamId={teamId} />

      {isLoading ? (
        <div className="h-32 animate-pulse rounded-lg border border-border/50 bg-muted/30" />
      ) : (
        <div className="rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Provider</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Key</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Created By</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5">
                    <Badge variant="outline" className="text-xs capitalize">
                      {k.provider}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                    {k.key_hint}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{k.created_by}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => testMut.mutate(k.id)}
                        className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                        title="Test key"
                      >
                        <TestTube className="size-3.5" />
                      </button>
                      <button
                        onClick={() => deleteMut.mutate(k.id)}
                        className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        title="Delete key"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {keys.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    No API keys configured. Add a key for a provider.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {testMut.data && (
        <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3 text-xs">
          <strong>Test result:</strong>{" "}
          {testMut.data.data.success ? (
            <span className="text-emerald-600">Success</span>
          ) : (
            <span className="text-destructive">
              Failed: {testMut.data.data.error}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function AgentsTab({ teamName }: { teamName: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["agents", { team: teamName }],
    queryFn: () => api.agents.list({ team: teamName }),
  });

  const agents = data?.data ?? [];

  if (isLoading) {
    return <div className="h-32 animate-pulse rounded-lg border border-border/50 bg-muted/30" />;
  }

  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
        <Bot className="mb-3 size-8 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">
          No agents owned by this team yet.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <Link
          key={agent.id}
          to={`/agents/${agent.id}`}
          className="flex items-center gap-3 rounded-lg border border-border/50 p-3 transition-colors hover:bg-muted/30"
        >
          <Bot className="size-4 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <span className="text-sm font-medium">{agent.name}</span>
            <span className="ml-2 text-xs text-muted-foreground">v{agent.version}</span>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] capitalize"
          >
            {agent.status}
          </Badge>
        </Link>
      ))}
    </div>
  );
}

export default function TeamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("members");

  const { data, isLoading, error } = useQuery({
    queryKey: ["team", id],
    queryFn: () => api.teams.get(id!),
    enabled: !!id,
  });

  const deleteMut = useMutation({
    mutationFn: () => api.teams.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      navigate("/teams");
    },
  });

  const team = data?.data as TeamDetailResponse | undefined;

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="h-48 animate-pulse rounded-lg bg-muted/30" />
      </div>
    );
  }

  if (error || !team) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
          Team not found
        </div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: typeof Users }[] = [
    { key: "members", label: `Members (${team.member_count})`, icon: Users },
    { key: "api-keys", label: "API Keys", icon: Key },
    { key: "agents", label: "Agents", icon: Bot },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Back */}
      <button
        onClick={() => navigate("/teams")}
        className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3" />
        Back to Teams
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <Shield className="size-5 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold">{team.display_name}</h1>
              <Badge variant="outline" className="text-xs">
                {team.name}
              </Badge>
            </div>
            {team.description && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                {team.description}
              </p>
            )}
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:bg-destructive/10"
          onClick={() => {
            if (confirm("Are you sure you want to delete this team?")) {
              deleteMut.mutate();
            }
          }}
        >
          <Trash2 className="mr-1.5 size-3.5" />
          Delete
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors ${
              tab === key
                ? "border-primary font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === "members" && (
        <MembersTab teamId={team.id} members={team.members} />
      )}
      {tab === "api-keys" && <ApiKeysTab teamId={team.id} />}
      {tab === "agents" && <AgentsTab teamName={team.name} />}
    </div>
  );
}
