import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { DollarSign, Plus, AlertTriangle, CheckCircle2, X } from "lucide-react";
import { api, type Budget } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useState } from "react";

function formatUsd(v: number): string {
  if (v >= 1) return `$${v.toFixed(2)}`;
  if (v >= 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(6)}`;
}

function statusColor(pct: number): string {
  if (pct > 100) return "text-destructive";
  if (pct > 80) return "text-orange-500";
  if (pct > 60) return "text-yellow-500";
  return "text-emerald-500";
}

function barColor(pct: number): string {
  if (pct > 100) return "bg-destructive";
  if (pct > 80) return "bg-orange-500";
  if (pct > 60) return "bg-yellow-500";
  return "bg-emerald-500";
}

function statusBadge(budget: Budget) {
  if (budget.is_exceeded) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
        <AlertTriangle className="size-3" />
        Exceeded
      </span>
    );
  }
  if (budget.pct_used >= budget.alert_threshold_pct) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-orange-500/10 px-2 py-0.5 text-xs font-medium text-orange-600 dark:text-orange-400">
        <AlertTriangle className="size-3" />
        Warning
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
      <CheckCircle2 className="size-3" />
      OK
    </span>
  );
}

function SetBudgetDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [team, setTeam] = useState("");
  const [limit, setLimit] = useState("");
  const [threshold, setThreshold] = useState("80");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.budgets.create({
        team,
        monthly_limit_usd: parseFloat(limit),
        alert_threshold_pct: parseFloat(threshold),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgets"] });
      setTeam("");
      setLimit("");
      setThreshold("80");
      onClose();
    },
  });

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed inset-x-0 top-[20%] z-50 mx-auto w-full max-w-md">
        <div className="rounded-xl border border-border bg-card shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h3 className="text-sm font-semibold">Set Team Budget</h3>
            <button
              onClick={onClose}
              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (team && limit) mutation.mutate();
            }}
            className="space-y-4 p-5"
          >
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Team Name
              </label>
              <input
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                placeholder="e.g. engineering"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-foreground"
                required
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Monthly Limit (USD)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="e.g. 500.00"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-foreground"
                required
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Alert Threshold (%)
              </label>
              <input
                type="number"
                step="1"
                min="1"
                max="100"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-foreground"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Alert when spend reaches this percentage of the limit
              </p>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border px-4 py-2 text-sm transition-colors hover:bg-accent"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {mutation.isPending ? "Saving..." : "Set Budget"}
              </button>
            </div>
            {mutation.isError && (
              <p className="text-xs text-destructive">
                {(mutation.error as Error).message}
              </p>
            )}
          </form>
        </div>
      </div>
    </>
  );
}

export default function BudgetsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: budgetsRes, isLoading } = useQuery({
    queryKey: ["budgets"],
    queryFn: () => api.budgets.list(),
  });

  const budgets: Budget[] = budgetsRes?.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <SetBudgetDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Budgets</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage monthly cost limits per team
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="inline-flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90"
        >
          <Plus className="size-4" />
          Set Budget
        </button>
      </div>

      {/* Budget Table */}
      <div className="rounded-lg border border-border bg-card">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            Loading budgets...
          </div>
        ) : budgets.length === 0 ? (
          <div className="py-12 text-center">
            <DollarSign className="mx-auto size-10 text-muted-foreground/40" />
            <p className="mt-3 text-sm font-medium">No budgets configured</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Set a monthly budget to track team spending
            </p>
            <button
              onClick={() => setDialogOpen(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background"
            >
              <Plus className="size-4" />
              Set First Budget
            </button>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-5 py-3 font-medium">Team</th>
                <th className="px-5 py-3 font-medium">Monthly Limit</th>
                <th className="px-5 py-3 font-medium">Current Spend</th>
                <th className="px-5 py-3 font-medium">Usage</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Alert At</th>
              </tr>
            </thead>
            <tbody>
              {budgets.map((b) => (
                <tr
                  key={b.id}
                  className="border-b border-border/50 last:border-0"
                >
                  <td className="px-5 py-3.5 font-medium">{b.team}</td>
                  <td className="px-5 py-3.5 font-mono text-xs">
                    {formatUsd(b.monthly_limit_usd)}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs">
                    {formatUsd(b.current_month_spend)}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            barColor(b.pct_used)
                          )}
                          style={{
                            width: `${Math.min(b.pct_used, 100)}%`,
                          }}
                        />
                      </div>
                      <span
                        className={cn(
                          "font-mono text-xs font-medium",
                          statusColor(b.pct_used)
                        )}
                      >
                        {b.pct_used.toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">{statusBadge(b)}</td>
                  <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">
                    {b.alert_threshold_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
