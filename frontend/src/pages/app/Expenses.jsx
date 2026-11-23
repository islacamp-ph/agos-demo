import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Download, Search, Upload, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg, downloadFile } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { money, php, fmtDate, fmtDateTime, today, CATEGORIES } from "@/lib/format";
import { PageHeader, StatusBadge, SimBadge, Empty } from "@/components/agos/ui";
import DecideButtons from "@/components/agos/DecideButtons";

const STATUSES = ["draft", "submitted", "pending_approval", "approved", "rejected", "paid"];

function NewExpense({ open, setOpen, onSaved }) {
  const { isManager, info } = useWorkspace();
  const { data: team } = useData(isManager && open ? "/team" : null);
  const blank = { merchant: "", category: "Software & SaaS", amount: "", currency: "PHP", date: today(), description: "", notes: "", member_id: "", submit: true };
  const [f, setF] = useState(blank);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await http.post("/expenses", { ...f, amount: Number(f.amount), member_id: f.member_id || undefined });
      toast.success(data.status === "draft" ? "Saved as draft" : "Submitted for approval");
      data.warnings?.forEach((w) => toast.warning(w));
      setF(blank);
      setOpen(false);
      onSaved();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>New expense</DialogTitle></DialogHeader>
        <form onSubmit={save} className="grid gap-4" data-testid="expense-form">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 space-y-1.5"><Label>Merchant</Label><Input required value={f.merchant} onChange={set("merchant")} data-testid="exp-merchant" /></div>
            <div className="space-y-1.5"><Label>Amount</Label><Input required type="number" step="0.01" min="0.01" value={f.amount} onChange={set("amount")} data-testid="exp-amount" /></div>
            <div className="space-y-1.5"><Label>Currency</Label><Select value={f.currency} onValueChange={set("currency")}><SelectTrigger data-testid="exp-currency"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PHP">PHP</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent></Select></div>
            <div className="space-y-1.5"><Label>Category</Label><Select value={f.category} onValueChange={set("category")}><SelectTrigger data-testid="exp-category"><SelectValue /></SelectTrigger><SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
            <div className="space-y-1.5"><Label>Date</Label><Input type="date" required value={f.date} onChange={set("date")} data-testid="exp-date" /></div>
            {isManager && (
              <div className="col-span-2 space-y-1.5"><Label>Assign to employee</Label>
                <Select value={f.member_id || info.member.id} onValueChange={set("member_id")}><SelectTrigger data-testid="exp-member"><SelectValue /></SelectTrigger>
                  <SelectContent>{(team || []).filter((m) => m.status !== "removed").map((m) => <SelectItem key={m.id} value={m.id}>{m.name} · {m.department}</SelectItem>)}</SelectContent></Select></div>
            )}
            <div className="col-span-2 space-y-1.5"><Label>Description</Label><Input value={f.description} onChange={set("description")} data-testid="exp-description" /></div>
            <div className="col-span-2 space-y-1.5"><Label>Notes</Label><Textarea rows={2} value={f.notes} onChange={set("notes")} data-testid="exp-notes" /></div>
          </div>
          {f.currency === "USD" && <p className="text-xs text-muted-foreground">USD is converted at a fixed demo rate of ₱58.00 for reporting.</p>}
          <label className="flex items-center gap-3 text-sm"><Switch checked={f.submit} onCheckedChange={set("submit")} data-testid="exp-submit-toggle" /> Submit for approval now</label>
          <DialogFooter><Button type="submit" disabled={busy} data-testid="exp-save-btn">{busy ? "Saving…" : f.submit ? "Submit expense" : "Save draft"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Receipt({ r }) {
  const view = async () => {
    try {
      const res = await http.get(`/files/${r.id}`, { responseType: "blob" });
      window.open(URL.createObjectURL(res.data), "_blank");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return <button onClick={view} className="flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm hover:bg-slate-50" data-testid={`receipt-${r.id}`}><FileText className="h-4 w-4 text-slate-400" /><span className="flex-1 truncate">{r.filename}</span><span className="text-xs text-muted-foreground">{Math.ceil(r.size / 1024)} KB</span></button>;
}

function ExpenseDrawer({ exp, onClose, onChanged }) {
  const { isManager, info } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const act = async (fn, msg) => {
    setBusy(true);
    try { await fn(); toast.success(msg); onChanged(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const upload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    act(() => http.post(`/expenses/${exp.id}/receipts`, fd), "Receipt uploaded");
    e.target.value = "";
  };
  if (!exp) return null;
  const blocked = exp.member_id === info.member.id && info.role !== "owner" ? "You cannot approve your own request" :
    info.role === "finance_manager" && exp.amount_php > info.workspace.approval_threshold ? "Above your approval threshold — owner approval required" : null;
  return (
    <Sheet open={!!exp} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-[480px]" data-testid="expense-drawer">
        <SheetHeader><SheetTitle>{exp.merchant}</SheetTitle></SheetHeader>
        <div className="mt-2 flex flex-wrap gap-2"><StatusBadge status={exp.status} />{exp.is_synthetic && <SimBadge />}{exp.card_id && <SimBadge label="Simulated card spend" />}</div>
        <div className="tnum mt-6 text-3xl font-semibold">{money(exp.amount, exp.currency)}</div>
        {exp.currency !== "PHP" && <div className="text-xs text-muted-foreground">{php(exp.amount_php)} at demo rate</div>}
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          {[["Employee", exp.member_name], ["Department", exp.department], ["Category", exp.category], ["Date", fmtDate(exp.date)]].map(([k, v]) => <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="mt-0.5">{v}</dd></div>)}
          {exp.description && <div className="col-span-2"><dt className="text-xs text-muted-foreground">Description</dt><dd>{exp.description}</dd></div>}
          {exp.notes && <div className="col-span-2"><dt className="text-xs text-muted-foreground">Notes</dt><dd>{exp.notes}</dd></div>}
        </dl>
        <div className="mt-6 flex flex-wrap gap-2">
          {["draft", "rejected"].includes(exp.status) && <Button size="sm" disabled={busy} onClick={() => act(() => http.post(`/expenses/${exp.id}/submit`), "Submitted")} data-testid="drawer-submit-btn">Submit for approval</Button>}
          {exp.status === "pending_approval" && isManager && <DecideButtons kind="expense" id={exp.id} blockedReason={blocked} onDone={onChanged} />}
          {exp.status === "approved" && isManager && <Button size="sm" variant="outline" disabled={busy} onClick={() => act(() => http.post(`/expenses/${exp.id}/mark-paid`), "Recorded as paid")} data-testid="drawer-mark-paid-btn">Record as paid</Button>}
        </div>
        <div className="mt-8">
          <div className="mb-2 flex items-center justify-between"><div className="text-sm font-semibold">Receipts</div>
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-[hsl(var(--primary))]"><Upload className="h-3.5 w-3.5" />Upload<input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="hidden" onChange={upload} data-testid="receipt-upload-input" /></label></div>
          <div className="space-y-2">{exp.receipts?.length ? exp.receipts.map((r) => <Receipt key={r.id} r={r} />) : <div className="text-xs text-muted-foreground">No receipts yet. JPG, PNG, WEBP or PDF up to 10 MB.</div>}</div>
        </div>
        <div className="mt-8"><div className="mb-3 text-sm font-semibold">Status history</div>
          <ol className="space-y-3 border-l pl-4" data-testid="expense-history">{exp.history.map((h) => (
            <li key={`${h.at}-${h.status}-${h.actor_name}`} className="relative text-sm"><span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-[hsl(var(--primary))]" />
              <div className="flex items-center gap-2"><StatusBadge status={h.status} /></div>
              <div className="mt-1 text-xs text-muted-foreground">{h.actor_name} · {fmtDateTime(h.at)}</div>{h.note && <div className="mt-0.5 text-xs">{h.note}</div>}</li>
          ))}</ol></div>
      </SheetContent>
    </Sheet>
  );
}

export default function Expenses() {
  const { info, version } = useWorkspace();
  const [filters, setFilters] = useState({ q: "", status: "all", department: "all", date_from: "", date_to: "" });
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(null);
  useEffect(() => { const t = setTimeout(() => setFilters((f) => ({ ...f, q })), 300); return () => clearTimeout(t); }, [q]);
  const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v && v !== "all"));
  const { data, reload } = useData("/expenses", { ...params, v: version });
  const refresh = async () => { await reload(); if (sel) { const { data: e } = await http.get("/expenses", { params: {} }); setSel(e.find((x) => x.id === sel.id) || null); } };
  const set = (k) => (v) => setFilters({ ...filters, [k]: v?.target ? v.target.value : v });
  return (
    <div>
      <PageHeader title="Expenses" subtitle="Create, categorize and submit business expenses. Every status change records who did it and when."
        actions={<>
          <Button variant="outline" onClick={() => downloadFile("/expenses/export", params, "agos-expenses.csv")} data-testid="export-expenses-btn"><Download className="mr-1.5 h-4 w-4" />Export CSV</Button>
          <Button onClick={() => setOpen(true)} data-testid="new-expense-btn"><Plus className="mr-1.5 h-4 w-4" />New expense</Button>
        </>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search merchant, category, employee" className="bg-white pl-9" data-testid="expense-search" /></div>
        <Select value={filters.status} onValueChange={set("status")}><SelectTrigger className="w-[170px] bg-white" data-testid="expense-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All statuses</SelectItem>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s === "paid" ? "Recorded as Paid" : s.replace("_", " ")}</SelectItem>)}</SelectContent></Select>
        <Select value={filters.department} onValueChange={set("department")}><SelectTrigger className="w-[160px] bg-white" data-testid="expense-dept-filter"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All departments</SelectItem>{info.workspace.departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent></Select>
        <Input type="date" value={filters.date_from} onChange={set("date_from")} className="w-[150px] bg-white" data-testid="expense-date-from" />
        <Input type="date" value={filters.date_to} onChange={set("date_to")} className="w-[150px] bg-white" data-testid="expense-date-to" />
      </div>
      <div className="overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Merchant</TableHead><TableHead>Employee</TableHead><TableHead>Department</TableHead><TableHead>Category</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Amount</TableHead></TableRow></TableHeader>
          <TableBody>{(data || []).map((e) => (
            <TableRow key={e.id} className="cursor-pointer" onClick={() => setSel(e)} data-testid={`expense-row-${e.id}`}>
              <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDate(e.date)}</TableCell>
              <TableCell><div className="font-medium">{e.merchant}</div><div className="mt-0.5 flex gap-1">{e.is_synthetic && <SimBadge />}{!e.receipts?.length && e.status !== "draft" && <span className="text-[11px] text-amber-700">No receipt</span>}</div></TableCell>
              <TableCell>{e.member_name}</TableCell><TableCell>{e.department}</TableCell><TableCell className="text-muted-foreground">{e.category}</TableCell>
              <TableCell><StatusBadge status={e.status} /></TableCell><TableCell className="tnum whitespace-nowrap text-right font-medium">{money(e.amount, e.currency)}</TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
        {data && !data.length && <div className="p-6"><Empty title="No expenses match these filters" hint="Create an expense or clear the filters." /></div>}
      </div>
      <NewExpense open={open} setOpen={setOpen} onSaved={reload} />
      <ExpenseDrawer exp={sel} onClose={() => setSel(null)} onChanged={refresh} />
    </div>
  );
}
