import { useState } from "react";
import { toast } from "sonner";
import { Plus, Snowflake, Play, Zap, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { php, fmtDate, CATEGORIES } from "@/lib/format";
import { PageHeader, Meter, StatusBadge, Empty } from "@/components/agos/ui";

function CardVisual({ c }) {
  const frozen = c.status === "frozen";
  return (
    <div className={`relative aspect-[1.586/1] overflow-hidden rounded-2xl p-5 text-white shadow-lg transition-[filter] ${frozen ? "grayscale" : ""}`}
      style={{ background: "linear-gradient(135deg, #14263d 0%, #1d3a5c 55%, #1f6f7f 120%)" }} data-testid={`card-visual-${c.id}`}>
      <div className="grain pointer-events-none absolute inset-0" />
      <div className="relative flex items-start justify-between"><span className="text-sm font-semibold tracking-[0.2em]">AGOS</span><span className="rounded bg-white/15 px-2 py-0.5 text-[10px]">{c.nickname}</span></div>
      <div className="relative mt-[12%] font-mono-plex text-lg tracking-[0.2em]">•••• •••• •••• {c.last4}</div>
      <div className="relative mt-3 flex items-end justify-between text-xs"><div><div className="text-[10px] text-white/60">Cardholder</div>{c.member_name}</div><div className="text-right"><div className="text-[10px] text-white/60">Exp</div>{c.expiry}</div></div>
      <div className="absolute inset-x-0 bottom-0 bg-amber-300/90 py-1 text-center text-[10px] font-semibold uppercase tracking-wider text-amber-950" data-testid="demo-card-label">Demo Card — Not Valid for Payment</div>
      {frozen && <div className="absolute inset-0 flex items-center justify-center bg-slate-900/30 text-sm font-medium"><Snowflake className="mr-1.5 h-4 w-4" />Frozen</div>}
    </div>
  );
}

function SimulateDialog({ card, onClose, onDone }) {
  const [f, setF] = useState({ merchant: "", category: "Software & SaaS", amount: "" });
  const [busy, setBusy] = useState(false);
  const run = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await http.post(`/cards/${card.id}/simulate`, { ...f, amount: Number(f.amount) });
      if (data.status === "declined") toast.error(`Declined: ${data.decline_reason}`); else toast.success("Simulated transaction posted — expense created for approval");
      onDone();
      onClose();
    } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={!!card} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Simulate a card transaction</DialogTitle><DialogDescription>No real payment occurs. AGOS checks card status and limit, then creates a linked expense.</DialogDescription></DialogHeader>
        <form onSubmit={run} className="grid gap-3" data-testid="simulate-form">
          <div className="space-y-1.5"><Label>Merchant</Label><Input required value={f.merchant} onChange={(e) => setF({ ...f, merchant: e.target.value })} data-testid="sim-merchant" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Amount (PHP)</Label><Input required type="number" min="0.01" step="0.01" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="sim-amount" /></div>
            <div className="space-y-1.5"><Label>Category</Label><Select value={f.category} onValueChange={(v) => setF({ ...f, category: v })}><SelectTrigger data-testid="sim-category"><SelectValue /></SelectTrigger><SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
          </div>
          <DialogFooter><Button type="submit" disabled={busy} data-testid="sim-submit-btn">Run simulation</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function IssueDialog({ open, setOpen, onDone }) {
  const { data: team } = useData(open ? "/team" : null);
  const [f, setF] = useState({ member_id: "", nickname: "", spending_limit: "" });
  const save = async (e) => {
    e.preventDefault();
    try { await http.post("/cards", { ...f, spending_limit: Number(f.spending_limit) }); toast.success("Simulated card issued"); setOpen(false); onDone(); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader><DialogTitle>Issue simulated card</DialogTitle><DialogDescription>Generates a mock card with no real card number or payment credentials.</DialogDescription></DialogHeader>
        <form onSubmit={save} className="grid gap-3" data-testid="issue-card-form">
          <div className="space-y-1.5"><Label>Employee</Label><Select value={f.member_id} onValueChange={(v) => setF({ ...f, member_id: v })}><SelectTrigger data-testid="card-member"><SelectValue placeholder="Select" /></SelectTrigger><SelectContent>{(team || []).filter((m) => m.status === "active").map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Card nickname</Label><Input required value={f.nickname} onChange={(e) => setF({ ...f, nickname: e.target.value })} data-testid="card-nickname" /></div>
          <div className="space-y-1.5"><Label>Monthly limit (PHP)</Label><Input required type="number" min="1" value={f.spending_limit} onChange={(e) => setF({ ...f, spending_limit: e.target.value })} data-testid="card-limit" /></div>
          <DialogFooter><Button type="submit" disabled={!f.member_id} data-testid="issue-card-submit">Issue card</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TxnSheet({ card, onClose }) {
  const { data } = useData(card ? `/cards/${card.id}/transactions` : null);
  return (
    <Sheet open={!!card} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-[480px]" data-testid="card-txn-sheet">
        <SheetHeader><SheetTitle>{card?.nickname} · simulated transactions</SheetTitle></SheetHeader>
        <div className="mt-6 divide-y">{(data || []).map((t) => (
          <div key={t.id} className="flex items-center justify-between gap-3 py-3 text-sm"><div><div className="font-medium">{t.merchant}</div><div className="text-xs text-muted-foreground">{fmtDate(t.date)} · {t.decline_reason || (t.expense_id ? "Linked expense created" : "")}</div></div>
            <div className="text-right"><div className="tnum font-medium">{php(t.amount)}</div><StatusBadge status={t.status} /></div></div>
        ))}{data && !data.length && <Empty title="No transactions yet" />}</div>
      </SheetContent>
    </Sheet>
  );
}

export default function Cards() {
  const { isManager, version } = useWorkspace();
  const { data, reload } = useData("/cards", { v: version });
  const [sim, setSim] = useState(null);
  const [txns, setTxns] = useState(null);
  const [issue, setIssue] = useState(false);
  const toggle = async (c) => {
    try { await http.post(`/cards/${c.id}/status`, { action: c.status === "frozen" ? "unfreeze" : "freeze" }); toast.success(c.status === "frozen" ? "Card unfrozen" : "Card frozen"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader title="Corporate cards" eyebrow="Simulated module"
        subtitle="Mock virtual cards that demonstrate spending controls. They carry no real card numbers and cannot make payments. Real card programs require an authorized issuing partner."
        actions={isManager && <Button onClick={() => setIssue(true)} data-testid="issue-card-btn"><Plus className="mr-1.5 h-4 w-4" />Issue simulated card</Button>} />
      {data && !data.length && <Empty title="No cards yet" hint={isManager ? "Issue a simulated card to an employee." : "No card is assigned to you."} />}
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {(data || []).map((c) => (
          <div key={c.id} className="fade-up" data-testid={`card-${c.id}`}>
            <CardVisual c={c} />
            <div className="mt-4 rounded-xl border bg-card p-4">
              <div className="flex items-center justify-between text-sm"><StatusBadge status={c.status} /><span className="tnum text-muted-foreground">{php(c.spent_this_month)} / {php(c.spending_limit)}</span></div>
              <div className="mt-3"><Meter pct={(c.spent_this_month / c.spending_limit) * 100} state={c.available <= 0 ? "over" : c.spent_this_month / c.spending_limit > 0.8 ? "warning" : "ok"} /></div>
              <div className="tnum mt-2 text-xs text-muted-foreground">{php(c.available)} available this month</div>
              <div className="mt-4 flex flex-wrap gap-2">
                {(isManager || c.status === "active") && <Button size="sm" variant="outline" onClick={() => toggle(c)} data-testid={`toggle-freeze-${c.id}`}>{c.status === "frozen" ? <><Play className="mr-1 h-3.5 w-3.5" />Unfreeze</> : <><Snowflake className="mr-1 h-3.5 w-3.5" />Freeze</>}</Button>}
                <Button size="sm" variant="outline" onClick={() => setSim(c)} data-testid={`simulate-${c.id}`}><Zap className="mr-1 h-3.5 w-3.5" />Simulate spend</Button>
                <Button size="sm" variant="ghost" onClick={() => setTxns(c)} data-testid={`txns-${c.id}`}><List className="mr-1 h-3.5 w-3.5" />Transactions</Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-10 max-w-3xl text-xs text-muted-foreground">Roadmap: Visa/Mastercard-enabled corporate card programs are planned for Phase 3, subject to approved card-issuing partnerships. The card module is designed so an authorized issuer can be connected later.</p>
      <SimulateDialog card={sim} onClose={() => setSim(null)} onDone={reload} />
      <TxnSheet card={txns} onClose={() => setTxns(null)} />
      <IssueDialog open={issue} setOpen={setIssue} onDone={reload} />
    </div>
  );
}
