import { useState } from "react";
import { toast } from "sonner";
import { Download, ExternalLink } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg, downloadFile } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { php, money, compact, monthLabel, fmtDate, shortKey } from "@/lib/format";
import { PageHeader, Panel, Kpi, StatusBadge, SimBadge, Empty } from "@/components/agos/ui";

const tip = { contentStyle: { borderRadius: 10, fontSize: 12 } };

function ExportBtn({ kind, params }) {
  return <Button size="sm" variant="ghost" onClick={() => downloadFile(`/reports/export/${kind}`, params, `agos-${kind}.csv`).catch((e) => toast.error(errMsg(e)))} data-testid={`export-${kind}-btn`}><Download className="mr-1 h-3.5 w-3.5" />CSV</Button>;
}

function SimpleTable({ cols, rows, render }) {
  return <div className="overflow-x-auto"><Table><TableHeader><TableRow>{cols.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader><TableBody>{rows.map(render)}</TableBody></Table>{!rows.length && <Empty title="No records in range" />}</div>;
}

function ReportsTab() {
  const [range, setRange] = useState({ date_from: "", date_to: "" });
  const params = Object.fromEntries(Object.entries(range).filter(([, v]) => v));
  const { data: d } = useData("/reports", params);
  if (!d) return <div className="h-96 animate-pulse rounded-xl bg-slate-100" />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-muted-foreground">Date range</span>
        <Input type="date" value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} className="w-[160px] bg-white" data-testid="report-date-from" />
        <Input type="date" value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} className="w-[160px] bg-white" data-testid="report-date-to" /></div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Kpi testid="report-total" label="Recorded expenses" value={compact(d.totals.recorded_php)} sub={`${d.totals.expense_count} records`} />
        <Kpi label="Payments" value={d.totals.payment_count} sub="All rails" />
        <Kpi label="Stellar transactions" value={d.totals.stellar_count} sub="With on-chain hash" tone="stellar" />
        <Kpi label="Pending approvals" value={d.pending.length} sub="Expenses + payments" />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Monthly expenses" actions={<ExportBtn kind="monthly" params={params} />} testid="report-monthly">
          <div className="h-60"><ResponsiveContainer><BarChart data={d.monthly}><CartesianGrid vertical={false} stroke="hsl(214 16% 92%)" /><XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis tickFormatter={compact} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} width={60} /><Tooltip {...tip} formatter={(v) => php(v)} labelFormatter={monthLabel} /><Bar dataKey="amount" fill="hsl(212 52% 28%)" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Panel>
        <Panel title="Department spending" actions={<ExportBtn kind="departments" params={params} />} testid="report-departments">
          <div className="h-60"><ResponsiveContainer><BarChart data={d.departments}><CartesianGrid vertical={false} stroke="hsl(214 16% 92%)" /><XAxis dataKey="name" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis tickFormatter={compact} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} width={60} /><Tooltip {...tip} formatter={(v) => php(v)} /><Bar dataKey="amount" fill="hsl(190 55% 38%)" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Panel>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Employee spending" actions={<ExportBtn kind="employees" params={params} />} testid="report-employees">
          <SimpleTable cols={["Employee", "Recorded"]} rows={d.employees} render={(r) => <TableRow key={r.name}><TableCell>{r.name}</TableCell><TableCell className="tnum">{php(r.amount)}</TableCell></TableRow>} />
        </Panel>
        <Panel title="Pending approvals" actions={<ExportBtn kind="pending" params={params} />} testid="report-pending">
          <SimpleTable cols={["Date", "Item", "Requester", "Amount"]} rows={d.pending} render={(r) => <TableRow key={r.id}><TableCell>{fmtDate(r.date)}</TableCell><TableCell>{r.merchant}</TableCell><TableCell>{r.member_name}</TableCell><TableCell className="tnum">{r.currency === "XLM" ? money(r.amount, "XLM") : php(r.amount_php)}</TableCell></TableRow>} />
        </Panel>
      </div>
      <Panel title="Budget vs actual" actions={<ExportBtn kind="budget_vs_actual" params={params} />} testid="report-bva">
        <SimpleTable cols={["Budget", "Month", "Budget", "Actual", "Variance", "Used"]} rows={d.budget_vs_actual} render={(r, i) => <TableRow key={i}><TableCell>{r.name}</TableCell><TableCell>{monthLabel(r.period)}</TableCell><TableCell className="tnum">{php(r.budget)}</TableCell><TableCell className="tnum">{php(r.actual)}</TableCell><TableCell className={`tnum ${r.variance < 0 ? "text-red-700" : ""}`}>{php(r.variance)}</TableCell><TableCell className="tnum">{r.utilization}%</TableCell></TableRow>} />
      </Panel>
      <Panel title="Payment history" actions={<ExportBtn kind="payments" params={params} />} testid="report-payments">
        <SimpleTable cols={["Date", "Recipient", "Rail", "Status", "Amount"]} rows={d.payments} render={(r) => <TableRow key={r.id}><TableCell>{fmtDate(r.date)}</TableCell><TableCell>{r.recipient} {r.is_synthetic && <SimBadge />}</TableCell><TableCell className="text-xs">{r.rail === "stellar_testnet" ? "Stellar Testnet" : "Domestic (demo)"}</TableCell><TableCell><StatusBadge status={r.status} /></TableCell><TableCell className="tnum">{money(r.amount, r.currency)}</TableCell></TableRow>} />
      </Panel>
      <Panel title="Stellar settlement & verification records" actions={<ExportBtn kind="stellar" params={params} />} testid="report-stellar">
        <SimpleTable cols={["Recipient", "Amount", "Status", "Hash", "Ledger", "Verified", ""]} rows={d.stellar} render={(r) => <TableRow key={r.id}><TableCell>{r.recipient}</TableCell><TableCell className="tnum">{r.amount} XLM</TableCell><TableCell><StatusBadge status={r.status} /></TableCell><TableCell className="font-mono-plex text-xs">{shortKey(r.tx_hash, 8)}</TableCell><TableCell className="tnum">{r.ledger || "—"}</TableCell><TableCell className="text-xs">{r.verified_at ? (r.matches_request ? "Matches" : "Mismatch") : "Not yet"}</TableCell><TableCell><a href={r.explorer} target="_blank" rel="noreferrer" className="text-xs text-[hsl(var(--stellar))] underline">Explorer</a></TableCell></TableRow>} />
        <p className="mt-3 text-xs text-muted-foreground">{d.disclaimer}</p>
      </Panel>
    </div>
  );
}

const RS_LABEL = { reconciled: "Reconciled", ready_to_reconcile: "Ready", missing_receipt: "Missing receipt", awaiting_approval: "Awaiting approval", not_applicable: "Not applicable", matched_to_expense: "Matched to expense", unmatched: "Unmatched", declined: "Declined", demo_record: "Demo record", open: "Open", verified_on_chain: "Verified on-chain", confirmed_unverified: "Confirmed · verify", awaiting_settlement: "Awaiting settlement" };
const RS_TONE = { reconciled: "bg-emerald-50 text-emerald-800", verified_on_chain: "bg-cyan-50 text-cyan-800", matched_to_expense: "bg-emerald-50 text-emerald-800", missing_receipt: "bg-amber-50 text-amber-800", unmatched: "bg-amber-50 text-amber-800" };

function ReconTab() {
  const { data, reload } = useData("/reconciliation");
  const [kind, setKind] = useState("all");
  const [status, setStatus] = useState("all");
  if (!data) return <div className="h-96 animate-pulse rounded-xl bg-slate-100" />;
  const rows = data.rows.filter((r) => (kind === "all" || r.kind === kind) && (status === "all" || r.reconciliation_status === status));
  const toggle = async (r, v) => { try { await http.post(`/reconciliation/${r.id}`, { kind: r.kind, reconciled: v }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select value={kind} onValueChange={setKind}><SelectTrigger className="w-[180px] bg-white" data-testid="recon-kind-filter"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All sources</SelectItem><SelectItem value="expense">Expenses</SelectItem><SelectItem value="card_txn">Card transactions</SelectItem><SelectItem value="payment">Payments</SelectItem></SelectContent></Select>
        <Select value={status} onValueChange={setStatus}><SelectTrigger className="w-[200px] bg-white" data-testid="recon-status-filter"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All statuses</SelectItem>{Object.keys(data.summary).map((s) => <SelectItem key={s} value={s}>{RS_LABEL[s] || s} ({data.summary[s]})</SelectItem>)}</SelectContent></Select>
        <Button variant="outline" className="ml-auto" onClick={() => downloadFile("/reconciliation/export", {}, "agos-reconciliation.csv")} data-testid="export-recon-btn"><Download className="mr-1.5 h-4 w-4" />Export CSV</Button>
      </div>
      <div className="overflow-x-auto rounded-xl border bg-card"><Table>
        <TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Date</TableHead><TableHead>Description</TableHead><TableHead>Method</TableHead><TableHead>Category</TableHead><TableHead>Approval</TableHead><TableHead>Payment</TableHead><TableHead>Reconciliation</TableHead><TableHead>Evidence</TableHead><TableHead className="text-right">Amount</TableHead><TableHead>Done</TableHead></TableRow></TableHeader>
        <TableBody>{rows.map((r) => (
          <TableRow key={r.kind + r.id} data-testid={`recon-row-${r.id}`}>
            <TableCell className="font-mono-plex text-xs">{r.reference}</TableCell><TableCell className="whitespace-nowrap text-xs">{fmtDate(r.date)}</TableCell>
            <TableCell><div className="font-medium">{r.description}</div>{r.is_synthetic && <SimBadge />}</TableCell><TableCell className="text-xs">{r.method}</TableCell>
            <TableCell className="max-w-[140px] truncate text-xs text-muted-foreground">{r.category}</TableCell>
            <TableCell><StatusBadge status={r.approval_status} /></TableCell><TableCell className="text-xs capitalize">{String(r.payment_status).replace(/_/g, " ")}</TableCell>
            <TableCell><span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${RS_TONE[r.reconciliation_status] || "bg-slate-100 text-slate-700"}`}>{RS_LABEL[r.reconciliation_status] || r.reconciliation_status}</span></TableCell>
            <TableCell className="max-w-[170px] text-xs">{r.explorer ? <a href={r.explorer} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono-plex text-[hsl(var(--stellar))] underline">{shortKey(r.evidence, 6)}<ExternalLink className="h-3 w-3" /></a> : <span className="block max-w-[170px] truncate text-muted-foreground" title={r.evidence}>{r.evidence}</span>}</TableCell>
            <TableCell className="tnum whitespace-nowrap text-right">{money(r.amount, r.currency)}</TableCell>
            <TableCell>{r.can_toggle && <Switch checked={r.reconciliation_status === "reconciled"} onCheckedChange={(v) => toggle(r, v)} data-testid={`recon-toggle-${r.id}`} />}</TableCell>
          </TableRow>
        ))}</TableBody></Table></div>
      <p className="mt-3 text-xs text-muted-foreground">{data.disclaimer}</p>
    </div>
  );
}

export default function Reports() {
  const { isManager } = useWorkspace();
  if (!isManager) return <Empty title="Reports are available to owners and finance managers" />;
  return (
    <div>
      <PageHeader title="Reports & reconciliation" subtitle="Built from persisted workspace records. Synthetic demo data is labeled throughout." />
      <Tabs defaultValue="reports"><TabsList className="mb-6"><TabsTrigger value="reports" data-testid="tab-reports">Reports</TabsTrigger><TabsTrigger value="recon" data-testid="tab-reconciliation">Reconciliation</TabsTrigger></TabsList>
        <TabsContent value="reports"><ReportsTab /></TabsContent><TabsContent value="recon"><ReconTab /></TabsContent></Tabs>
    </div>
  );
}
