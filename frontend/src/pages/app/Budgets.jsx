import { useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { php, thisMonth, monthLabel } from "@/lib/format";
import { PageHeader, Meter, SimBadge, Empty } from "@/components/agos/ui";

function BudgetDialog({ budget, open, setOpen, onSaved }) {
  const { info } = useWorkspace();
  const { data: team } = useData(open ? "/team" : null);
  const init = budget || { name: "", scope: "department", department: info.workspace.departments[0], member_id: null, amount: "", period: thisMonth(), alert_pct: 80, assigned_member_ids: [] };
  const [f, setF] = useState(init);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const toggle = (id) => setF({ ...f, assigned_member_ids: f.assigned_member_ids.includes(id) ? f.assigned_member_ids.filter((x) => x !== id) : [...f.assigned_member_ids, id] });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body = { ...f, amount: Number(f.amount), alert_pct: Number(f.alert_pct) };
      await (budget ? http.put(`/budgets/${budget.id}`, body) : http.post("/budgets", body));
      toast.success("Budget saved");
      setOpen(false);
      onSaved();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  const active = (team || []).filter((m) => m.status !== "removed");
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>{budget ? "Edit budget" : "New budget"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="grid grid-cols-2 gap-4" data-testid="budget-form">
          <div className="col-span-2 space-y-1.5"><Label>Name</Label><Input required value={f.name} onChange={set("name")} data-testid="budget-name" /></div>
          <div className="space-y-1.5"><Label>Scope</Label><Select value={f.scope} onValueChange={set("scope")}><SelectTrigger data-testid="budget-scope"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="business">Business-wide</SelectItem><SelectItem value="department">Department</SelectItem><SelectItem value="employee">Employee limit</SelectItem></SelectContent></Select></div>
          {f.scope === "department" && <div className="space-y-1.5"><Label>Department</Label><Select value={f.department || ""} onValueChange={set("department")}><SelectTrigger data-testid="budget-dept"><SelectValue /></SelectTrigger><SelectContent>{info.workspace.departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent></Select></div>}
          {f.scope === "employee" && <div className="space-y-1.5"><Label>Employee</Label><Select value={f.member_id || ""} onValueChange={set("member_id")}><SelectTrigger data-testid="budget-member"><SelectValue placeholder="Select" /></SelectTrigger><SelectContent>{active.map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent></Select></div>}
          {f.scope === "business" && <div />}
          <div className="space-y-1.5"><Label>Amount (PHP)</Label><Input required type="number" min="1" step="0.01" value={f.amount} onChange={set("amount")} data-testid="budget-amount" /></div>
          <div className="space-y-1.5"><Label>Month</Label><Input required type="month" value={f.period} onChange={set("period")} data-testid="budget-period" /></div>
          <div className="space-y-1.5"><Label>Warn at (%)</Label><Input type="number" min="10" max="100" value={f.alert_pct} onChange={set("alert_pct")} data-testid="budget-alert" /></div>
          {f.scope !== "employee" && (
            <div className="col-span-2"><Label>Assigned employees (can view this budget)</Label>
              <div className="mt-2 grid max-h-36 grid-cols-2 gap-2 overflow-y-auto">{active.map((m) => (
                <label key={m.id} className="flex items-center gap-2 text-sm"><Checkbox checked={f.assigned_member_ids.includes(m.id)} onCheckedChange={() => toggle(m.id)} data-testid={`budget-assign-${m.id}`} />{m.name}</label>
              ))}</div></div>
          )}
          <DialogFooter className="col-span-2"><Button type="submit" disabled={busy} data-testid="budget-save-btn">{busy ? "Saving…" : "Save budget"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Budgets() {
  const { isOwner, version } = useWorkspace();
  const [period, setPeriod] = useState(thisMonth());
  const { data, reload } = useData("/budgets", { period, v: version });
  const [edit, setEdit] = useState(null);
  const [open, setOpen] = useState(false);
  const del = async (b) => {
    if (!window.confirm(`Delete budget "${b.name}"?`)) return;
    try { await http.delete(`/budgets/${b.id}`); toast.success("Budget deleted"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader title="Budgets & spending controls" subtitle="Utilization counts approved and recorded-as-paid expenses in the budget's month, in PHP. Card transactions count once, through their linked expense."
        actions={<>
          <Input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} className="w-[170px] bg-white" data-testid="budget-period-filter" />
          {isOwner && <Button onClick={() => { setEdit(null); setOpen(true); }} data-testid="new-budget-btn"><Plus className="mr-1.5 h-4 w-4" />New budget</Button>}
        </>} />
      {data && !data.length && <Empty title={`No budgets for ${monthLabel(period)}`} hint={isOwner ? "Create a business, department or employee budget." : "Budgets assigned to you will appear here."} />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(data || []).map((b) => (
          <div key={b.id} className="fade-up rounded-xl border bg-card p-5 transition-shadow hover:shadow-md" data-testid={`budget-card-${b.id}`}>
            <div className="flex items-start justify-between gap-2">
              <div><div className="font-semibold text-[hsl(var(--navy-ink))]">{b.name}</div><div className="mt-0.5 text-xs capitalize text-muted-foreground">{b.scope === "employee" ? "Employee limit" : b.scope}{b.department ? ` · ${b.department}` : ""} · {monthLabel(b.period)}</div></div>
              <div className="flex gap-1">{b.is_synthetic && <SimBadge />}{isOwner && <>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => { setEdit(b); setOpen(true); }} data-testid={`edit-budget-${b.id}`}><Pencil className="h-3.5 w-3.5" /></Button>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => del(b)} data-testid={`delete-budget-${b.id}`}><Trash2 className="h-3.5 w-3.5" /></Button></>}</div>
            </div>
            <div className="tnum mt-5 flex items-baseline justify-between"><span className="text-2xl font-semibold" data-testid={`budget-used-${b.id}`}>{php(b.used)}</span><span className="text-sm text-muted-foreground">of {php(b.amount)}</span></div>
            <div className="mt-3"><Meter pct={b.utilization} state={b.state} /></div>
            <div className="mt-2 flex justify-between text-xs"><span className="tnum text-muted-foreground">{b.utilization}% used</span><span className="tnum">{php(b.remaining)} left</span></div>
            {b.state !== "ok" && <div className={`mt-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${b.state === "over" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`} data-testid={`budget-warning-${b.id}`}><AlertTriangle className="h-3.5 w-3.5" />{b.state === "over" ? "Over budget" : `Above ${b.alert_pct}% warning threshold`}</div>}
          </div>
        ))}
      </div>
      {open && <BudgetDialog key={edit?.id || "new"} budget={edit} open={open} setOpen={setOpen} onSaved={reload} />}
    </div>
  );
}
