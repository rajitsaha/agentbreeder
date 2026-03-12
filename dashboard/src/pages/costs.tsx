import { useQuery } from "@tanstack/react-query";
import { DollarSign, Coins, Activity, TrendingUp, AlertTriangle } from "lucide-react";
import {
  api,
  type CostSummary,
  type CostBreakdown,
  type CostTrendResponse,
  type TopSpender,
  type Budget,
  type CostBreakdownItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useState } from "react";

function formatUsd(v: number): string {
  if (v >= 1) return `$${v.toFixed(2)}`;
  if (v >= 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(6)}`;
}

function formatTokens(t: number): string {
  if (t >= 1_000_000) return `${(t / 1_000_000).toFixed(1)}M`;
  if (t >= 1_000) return `${(t / 1_000).toFixed(1)}K`;
  return String(t);
}

function SummaryCard({
  title,
  value,
  sub,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{title}</span>
        <div className={cn("rounded-md p-2", color)}>
          <Icon className="size-4" />
        </div>
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function TrendChart({ points }: { points: CostTrendResponse["points"] }) {
  if (!points.length) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        No cost data yet
      </div>
    );
  }

  const maxCost = Math.max(...points.map((p) => p.cost), 0.001);

  return (
    <div className="flex h-48 items-end gap-0.5">
      {points.map((p) => {
        const heightPct = Math.max((p.cost / maxCost) * 100, 1);
        return (
          <div
            key={p.date}
            className="group relative flex-1"
            title={`${p.date}: ${formatUsd(p.cost)} | ${formatTokens(p.tokens)} tokens | ${p.requests} req`}
          >
            <div
              className="w-full rounded-t bg-emerald-500/70 transition-colors group-hover:bg-emerald-500"
              style={{ height: `${heightPct}%` }}
            />
            {/* Tooltip on hover */}
            <div className="pointer-events-none absolute -top-16 left-1/2 z-10 hidden -translate-x-1/2 rounded border border-border bg-card px-2 py-1 text-xs shadow-lg group-hover:block">
              <div className="font-medium">{p.date}</div>
              <div>{formatUsd(p.cost)}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BreakdownTable({
  items,
  totalCost,
}: {
  items: CostBreakdownItem[];
  totalCost: number;
}) {
  if (!items.length) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No data available
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-muted-foreground">
          <th className="pb-2 font-medium">Name</th>
          <th className="pb-2 text-right font-medium">Cost</th>
          <th className="pb-2 text-right font-medium">Tokens</th>
          <th className="pb-2 text-right font-medium">Requests</th>
          <th className="pb-2 text-right font-medium">% of Total</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => {
          const pct = totalCost > 0 ? (item.cost / totalCost) * 100 : 0;
          return (
            <tr
              key={item.name}
              className="border-b border-border/50 last:border-0"
            >
              <td className="py-2.5 font-medium">{item.name}</td>
              <td className="py-2.5 text-right font-mono text-xs">
                {formatUsd(item.cost)}
              </td>
              <td className="py-2.5 text-right font-mono text-xs text-muted-foreground">
                {formatTokens(item.tokens)}
              </td>
              <td className="py-2.5 text-right font-mono text-xs text-muted-foreground">
                {item.requests.toLocaleString()}
              </td>
              <td className="py-2.5 text-right">
                <div className="flex items-center justify-end gap-2">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                  <span className="w-10 text-right font-mono text-xs text-muted-foreground">
                    {pct.toFixed(1)}%
                  </span>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function TopSpendersList({ spenders }: { spenders: TopSpender[] }) {
  if (!spenders.length) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        No data yet
      </div>
    );
  }

  const maxCost = Math.max(...spenders.map((s) => s.cost), 0.001);

  return (
    <div className="space-y-3">
      {spenders.slice(0, 5).map((s, i) => (
        <div key={s.agent_name} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span className="flex size-5 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground">
                {i + 1}
              </span>
              <span className="font-medium">{s.agent_name}</span>
              <span className="text-xs text-muted-foreground">{s.team}</span>
            </div>
            <span className="font-mono text-xs">{formatUsd(s.cost)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-amber-500"
              style={{ width: `${(s.cost / maxCost) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function BudgetStatusCard({ budget }: { budget: Budget }) {
  const colorClass =
    budget.pct_used > 100
      ? "text-destructive"
      : budget.pct_used > 80
        ? "text-orange-500"
        : budget.pct_used > 60
          ? "text-yellow-500"
          : "text-emerald-500";

  const barColor =
    budget.pct_used > 100
      ? "bg-destructive"
      : budget.pct_used > 80
        ? "bg-orange-500"
        : budget.pct_used > 60
          ? "bg-yellow-500"
          : "bg-emerald-500";

  return (
    <div className="flex items-center gap-4 rounded-lg border border-border/50 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{budget.team}</span>
          {budget.is_exceeded && (
            <AlertTriangle className="size-3.5 text-destructive" />
          )}
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full transition-all", barColor)}
            style={{ width: `${Math.min(budget.pct_used, 100)}%` }}
          />
        </div>
      </div>
      <div className="text-right">
        <span className={cn("text-sm font-mono font-medium", colorClass)}>
          {budget.pct_used.toFixed(1)}%
        </span>
        <div className="text-xs text-muted-foreground">
          {formatUsd(budget.current_month_spend)} / {formatUsd(budget.monthly_limit_usd)}
        </div>
      </div>
    </div>
  );
}

type BreakdownTab = "agent" | "model" | "team";

export default function CostsPage() {
  const [breakdownTab, setBreakdownTab] = useState<BreakdownTab>("agent");
  const days = 30;

  const { data: summaryRes, isLoading: loadingSummary } = useQuery({
    queryKey: ["cost-summary", days],
    queryFn: () => api.costs.summary({ days }),
  });

  const { data: breakdownRes, isLoading: loadingBreakdown } = useQuery({
    queryKey: ["cost-breakdown", days],
    queryFn: () => api.costs.breakdown({ days }),
  });

  const { data: trendRes, isLoading: loadingTrend } = useQuery({
    queryKey: ["cost-trend", days],
    queryFn: () => api.costs.trend({ days }),
  });

  const { data: spendersRes } = useQuery({
    queryKey: ["cost-top-spenders", days],
    queryFn: () => api.costs.topSpenders({ days, limit: 5 }),
  });

  const { data: budgetsRes } = useQuery({
    queryKey: ["budgets"],
    queryFn: () => api.budgets.list(),
  });

  const summary: CostSummary = summaryRes?.data ?? {
    total_cost: 0,
    total_tokens: 0,
    request_count: 0,
    period: "30d",
  };

  const breakdown: CostBreakdown = breakdownRes?.data ?? {
    by_agent: [],
    by_model: [],
    by_team: [],
  };

  const trend: CostTrendResponse = trendRes?.data ?? {
    points: [],
    total_cost: 0,
    period: "30d",
  };

  const spenders: TopSpender[] = spendersRes?.data ?? [];
  const budgets: Budget[] = budgetsRes?.data ?? [];

  const breakdownItems =
    breakdownTab === "agent"
      ? breakdown.by_agent
      : breakdownTab === "model"
        ? breakdown.by_model
        : breakdown.by_team;

  // Budget status for summary card
  const exceededBudgets = budgets.filter((b) => b.is_exceeded).length;
  const budgetStatus =
    exceededBudgets > 0
      ? `${exceededBudgets} exceeded`
      : budgets.length > 0
        ? "All within limit"
        : "No budgets set";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cost Tracking</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor LLM costs across agents, models, and teams
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Total Spend"
          value={loadingSummary ? "--" : formatUsd(summary.total_cost)}
          sub="This month"
          icon={DollarSign}
          color="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
        />
        <SummaryCard
          title="Total Tokens"
          value={loadingSummary ? "--" : formatTokens(summary.total_tokens)}
          sub={`${summary.request_count.toLocaleString()} requests`}
          icon={Coins}
          color="bg-blue-500/10 text-blue-600 dark:text-blue-400"
        />
        <SummaryCard
          title="Avg Cost / Request"
          value={
            loadingSummary || summary.request_count === 0
              ? "--"
              : formatUsd(summary.total_cost / summary.request_count)
          }
          sub="Last 30 days"
          icon={Activity}
          color="bg-violet-500/10 text-violet-600 dark:text-violet-400"
        />
        <SummaryCard
          title="Budget Status"
          value={budgetStatus}
          sub={`${budgets.length} team budget${budgets.length !== 1 ? "s" : ""}`}
          icon={exceededBudgets > 0 ? AlertTriangle : TrendingUp}
          color={
            exceededBudgets > 0
              ? "bg-destructive/10 text-destructive"
              : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
          }
        />
      </div>

      {/* Trend Chart */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-medium">Daily Cost Trend</h2>
        {loadingTrend ? (
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : (
          <TrendChart points={trend.points} />
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Breakdown */}
        <div className="rounded-lg border border-border bg-card p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-medium">Cost Breakdown</h2>
            <div className="flex gap-1 rounded-md border border-border p-0.5">
              {(["agent", "model", "team"] as BreakdownTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setBreakdownTab(tab)}
                  className={cn(
                    "rounded px-3 py-1 text-xs font-medium transition-colors",
                    breakdownTab === tab
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  By {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
          </div>
          {loadingBreakdown ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Loading...
            </div>
          ) : (
            <BreakdownTable
              items={breakdownItems}
              totalCost={summary.total_cost}
            />
          )}
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Top Spenders */}
          <div className="rounded-lg border border-border bg-card p-5">
            <h2 className="mb-4 text-sm font-medium">Top Spenders</h2>
            <TopSpendersList spenders={spenders} />
          </div>

          {/* Budget Status */}
          {budgets.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="mb-4 text-sm font-medium">Budget Status</h2>
              <div className="space-y-2">
                {budgets.map((b) => (
                  <BudgetStatusCard key={b.id} budget={b} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
