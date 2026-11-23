import { useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Wallet, CalendarDays, PieChart, Clock, Orbit } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useData } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { php, compact, money, monthLabel, fmtDate, shortKey } from "@/lib/format";
import { PageHeader, Kpi, Panel, Meter, StatusBadge, SimBadge, ChainBadge, Empty } from "@/components/agos/ui";

const tip = { contentStyle: { borderRadius: 10, border: "1px solid hsl(214 16% 89%)", fontSize: 12 } };
const TICK = { fontSize: 12 };
const H_BAR_RADIUS = [0, 6, 6, 0];
const BAR_MARGIN = { left: 10 };

export default function Overview() {
  const { info, version } = useWorkspace();
  const [months, setMonths] = useState("6");
  const [dept, setDept] = useState("all");
  const { data: d } = useData("/dashboard", { months, department: dept === "all" ? undefined : dept, v: version });
  if (!d) return <div className="h-96 animate-pulse rounded-xl bg-slate-100" />;
  const k = d.kpis;
  const util = k.budget_total ? Math.round((k.budget_used / k.budget_total) * 100) : 0;
  return (
    <div>
      <PageHeader eyebrow={info.workspace.name} title="Financial overview"
        subtitle="Every figure is calculated from records stored in this workspace. Recorded expenses are not bank balances."
        actions={<>
          <Select value={dept} onValueChange={setDept}><SelectTrigger className="w-[170px] bg-white" data-testid="overview-dept-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All departments</SelectItem>{d.departments_list.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
          <Select value={months} onValueChange={setMonths}><SelectTrigger className="w-[140px] bg-white" data-testid="overview-months-filter"><SelectValue /></SelectTrigger>
            <SelectContent>{["3", "6", "12"].map((m) => <SelectItem key={m} value={m}>Last {m} months</SelectItem>)}</SelectContent></Select>
        </>} />
      {d.synthetic_records > 0 && <div className="mb-6 flex items-center gap-2 text-xs text-muted-foreground"><SimBadge /> {d.synthetic_records} expense records in view are synthetic demo data.</div>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi testid="kpi-total-recorded" label="Total recorded expenses" value={compact(k.total_recorded)} sub="Approved + recorded as paid" icon={Wallet} />
        <Kpi testid="kpi-month-spend" label="This month" value={compact(k.month_spend)} sub={`Card spend ${compact(k.card_spend_month)} (simulated)`} icon={CalendarDays} />
        <Kpi testid="kpi-budget-util" label="Budget utilization" value={`${util}%`} sub={`${compact(k.budget_used)} of ${compact(k.budget_total)}`} tone={util >= 80 ? "warn" : ""} icon={PieChart} />
        <Kpi testid="kpi-pending" label="Pending approvals" value={k.pending_approvals} sub={`${k.pending_expenses} expenses · ${k.pending_payments} payments`} icon={Clock} />
        <Kpi testid="kpi-stellar" label="Stellar settlements" value={d.stellar.confirmed} sub={`${money(d.stellar.xlm_settled, "XLM")} confirmed on Testnet`} tone="stellar" icon={Orbit} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title="Monthly spending" className="xl:col-span-2" testid="chart-monthly">
          <div className="h-64">
            <ResponsiveContainer><AreaChart data={d.monthly}>
              <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(212 52% 28%)" stopOpacity={0.25} /><stop offset="100%" stopColor="hsl(212 52% 28%)" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid stroke="hsl(214 16% 92%)" vertical={false} />
              <XAxis dataKey="month" tickFormatter={monthLabel} tick={TICK} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={compact} tick={TICK} axisLine={false} tickLine={false} width={60} />
              <Tooltip {...tip} formatter={(v) => php(v)} labelFormatter={monthLabel} />
              <Area dataKey="amount" stroke="hsl(212 52% 28%)" strokeWidth={2} fill="url(#g)" />
            </AreaChart></ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Department spending" testid="chart-departments">
          <div className="h-64">
            <ResponsiveContainer><BarChart data={d.departments} layout="vertical" margin={BAR_MARGIN}>
              <XAxis type="number" hide /><YAxis type="category" dataKey="name" width={90} tick={TICK} axisLine={false} tickLine={false} />
              <Tooltip {...tip} formatter={(v) => php(v)} /><Bar dataKey="amount" fill="hsl(190 55% 38%)" radius={H_BAR_RADIUS} />
            </BarChart></ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title={`Budgets · ${monthLabel(d.month)}`} actions={<Link to="/app/budgets" className="text-xs text-[hsl(var(--primary))]">View all</Link>} testid="overview-budgets">
          {d.budgets.length ? <div className="space-y-4">{d.budgets.slice(0, 5).map((b) => (
            <div key={b.id}><div className="mb-1.5 flex justify-between text-sm"><span className="truncate">{b.name}</span><span className="tnum text-muted-foreground">{b.utilization}%</span></div><Meter pct={b.utilization} state={b.state} /></div>
          ))}</div> : <Empty title="No budgets this month" />}
        </Panel>
        <Panel title="Employee spending" testid="overview-employees">
          <div className="space-y-3">{d.employees.map((e) => (
            <div key={e.name} className="flex items-center justify-between text-sm"><span>{e.name}</span><span className="tnum font-medium">{php(e.amount)}</span></div>
          ))}{!d.employees.length && <Empty title="No recorded spending yet" />}</div>
        </Panel>
        <Panel title="Payments" testid="overview-payments">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-muted-foreground">Domestic (demo records)</div><div className="tnum mt-1 font-semibold">{d.domestic.recorded_demo} recorded · {d.domestic.pending} pending</div><div className="tnum text-xs text-muted-foreground">{php(d.domestic.total_php)} — no funds moved</div></div>
            <div className="rounded-lg bg-[hsl(var(--stellar-subtle))] p-3"><div className="text-xs text-[hsl(var(--stellar))]">Stellar Testnet</div><div className="tnum mt-1 font-semibold">{d.stellar.confirmed} of {d.stellar.count} confirmed</div></div>
          </div>
          <div className="mt-4 space-y-2">{d.stellar.latest.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-2 text-xs"><span className="truncate">{s.recipient}</span>
              {s.tx_hash ? <span className="font-mono-plex text-muted-foreground">{shortKey(s.tx_hash, 5)}</span> : null}<StatusBadge status={s.status} /></div>
          ))}</div>
        </Panel>
      </div>

      <Panel title="Recent transactions" className="mt-6" testid="overview-recent">
        <div className="divide-y">{d.recent.map((r) => (
          <div key={r.kind + r.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
            <div className="w-24 text-xs text-muted-foreground">{fmtDate(r.date)}</div>
            <div className="min-w-[160px] flex-1"><div className="font-medium">{r.title}</div><div className="text-xs text-muted-foreground">{r.kind === "payment" ? (r.rail === "stellar_testnet" ? "Stellar payment" : "Domestic payment (demo)") : "Expense"} · {r.who}</div></div>
            {r.is_synthetic ? <SimBadge /> : r.rail === "stellar_testnet" ? <ChainBadge /> : null}
            <StatusBadge status={r.status} /><div className="tnum w-32 text-right font-medium">{money(r.amount, r.currency)}</div>
          </div>
        ))}</div>
      </Panel>
    </div>
  );
}
