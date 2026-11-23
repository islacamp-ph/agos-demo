import { useState } from "react";
import { toast } from "sonner";
import { Plus, ExternalLink, ShieldCheck, Send, RefreshCw, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { money, fmtDate, fmtDateTime, shortKey, newKey } from "@/lib/format";
import { PageHeader, StatusBadge, SimBadge, ChainBadge, Empty } from "@/components/agos/ui";
import DecideButtons from "@/components/agos/DecideButtons";

function NewPayment({ open, setOpen, type, onSaved }) {
  const blank = { recipient_name: "", recipient_bank: "", recipient_account_last4: "", destination_address: "", asset_code: "XLM", amount: "", purpose: "" };
  const [f, setF] = useState(blank);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const intl = type === "international";
  const genRecipient = async () => {
    setBusy(true);
    try { const { data } = await http.post("/stellar/demo-recipient"); setF((x) => ({ ...x, destination_address: data.public_key })); toast.success(data.funded ? "Funded Testnet recipient generated" : "Recipient address generated"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const save = async (e) => {
    e.preventDefault();
    if (intl && !/^G[A-Z2-7]{55}$/.test(f.destination_address)) return toast.error("Enter a valid Stellar public key (G…, 56 characters)");
    setBusy(true);
    try {
      await http.post("/payments", { ...f, type, recipient_account_last4: f.recipient_account_last4 || undefined, recipient_bank: f.recipient_bank || undefined, destination_address: intl ? f.destination_address : undefined });
      toast.success("Payment request submitted for approval");
      setF(blank); setOpen(false); onSaved();
    } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>{intl ? "International payment · Stellar Testnet" : "Domestic payment · demo record"}</DialogTitle>
          <DialogDescription>{intl ? "Settles as a genuine Stellar Testnet XLM transaction after approval and explicit confirmation. Testnet XLM has no monetary value." : "Creates a PHP bank-transfer record for workflow demonstration. AGOS does not move any funds."}</DialogDescription></DialogHeader>
        <form onSubmit={save} className="grid gap-3" data-testid="payment-form">
          <div className="space-y-1.5"><Label>Recipient name</Label><Input required minLength={2} value={f.recipient_name} onChange={set("recipient_name")} data-testid="pay-recipient" /></div>
          {intl ? (
            <div className="space-y-1.5"><div className="flex items-center justify-between"><Label>Destination Stellar address</Label>
              <button type="button" onClick={genRecipient} disabled={busy} className="inline-flex items-center gap-1 text-xs text-[hsl(var(--stellar))]" data-testid="gen-recipient-btn"><Wand2 className="h-3 w-3" />Generate Testnet recipient</button></div>
              <Input required value={f.destination_address} onChange={set("destination_address")} className="font-mono-plex text-xs" placeholder="G…" data-testid="pay-destination" /></div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Bank (demo)</Label><Input value={f.recipient_bank} onChange={set("recipient_bank")} placeholder="e.g. BPI" data-testid="pay-bank" /></div>
              <div className="space-y-1.5"><Label>Account last 4 digits</Label><Input value={f.recipient_account_last4} onChange={set("recipient_account_last4")} maxLength={4} pattern="\d{4}" data-testid="pay-last4" /></div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Amount ({intl ? "Testnet XLM" : "PHP"})</Label><Input required type="number" step={intl ? "0.0000001" : "0.01"} min={intl ? "0.0000001" : "0.01"} max={intl ? "1000" : undefined} value={f.amount} onChange={set("amount")} data-testid="pay-amount" /></div>
            <div className="space-y-1.5"><Label>Asset / currency</Label><Input disabled value={intl ? "XLM (Testnet)" : "PHP"} /></div>
          </div>
          <div className="space-y-1.5"><Label>Purpose / description</Label><Input required minLength={3} value={f.purpose} onChange={set("purpose")} data-testid="pay-purpose" /></div>
          <DialogFooter><Button type="submit" disabled={busy} data-testid="pay-submit-btn">Submit for approval</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function StellarActions({ p, onChanged }) {
  const { isManager } = useWorkspace();
  const [confirm, setConfirm] = useState(false);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [key] = useState(newKey());
  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await http.post(`/payments/${p.id}/stellar/submit`, { confirm: true, idempotency_key: key });
      const s = data.payment.status;
      if (s === "confirmed") toast.success("Confirmed on the Stellar Testnet ledger"); else if (s === "failed") toast.error(data.payment.stellar?.last_error || "Submission failed"); else toast.message("Submitted — verify to reconcile");
      setConfirm(false); onChanged();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const verify = async () => {
    setBusy(true);
    try { const { data } = await http.post(`/payments/${p.id}/stellar/verify`); toast.success(`Verified · status ${data.status.replace("_", " ")}`); onChanged(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {isManager && ["approved", "failed"].includes(p.status) && <Button size="sm" onClick={() => { setAck(false); setConfirm(true); }} className="bg-[hsl(var(--stellar))] hover:bg-[hsl(190_60%_28%)]" data-testid="stellar-submit-btn"><Send className="mr-1 h-3.5 w-3.5" />{p.status === "failed" ? "Retry on Stellar" : "Confirm & submit to Stellar"}</Button>}
      {p.stellar?.tx_hash && <Button size="sm" variant="outline" disabled={busy} onClick={verify} data-testid="stellar-verify-btn"><ShieldCheck className="mr-1 h-3.5 w-3.5" />Verify transaction</Button>}
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogHeader><DialogTitle>Confirm Stellar Testnet payment</DialogTitle><DialogDescription>This signs and submits a real transaction to the Stellar Testnet from your workspace account.</DialogDescription></DialogHeader>
          <div className="space-y-2 rounded-lg bg-slate-50 p-4 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">Amount</span><span className="tnum font-semibold">{money(p.amount, "XLM")}</span></div>
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">To</span><span className="break-all text-right font-mono-plex text-xs">{p.destination_address}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Network</span><span>Stellar Testnet</span></div>
          </div>
          <label className="flex items-start gap-2 text-sm"><Checkbox checked={ack} onCheckedChange={(v) => setAck(!!v)} data-testid="stellar-ack-checkbox" className="mt-0.5" />I authorize this payment. I understand Testnet XLM has no monetary value and ledger confirmation does not prove fiat delivery.</label>
          <DialogFooter><Button disabled={!ack || busy} onClick={submit} data-testid="stellar-confirm-btn">{busy ? "Signing & submitting…" : "Sign and submit"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PaymentDrawer({ id, onClose, onChanged }) {
  const { isManager } = useWorkspace();
  const { data: p, reload } = useData(id ? `/payments/${id}` : null);
  const changed = () => { reload(); onChanged(); };
  const record = async () => { try { await http.post(`/payments/${id}/record-paid`); toast.success("Recorded (demo — no funds moved)"); changed(); } catch (e) { toast.error(errMsg(e)); } };
  const st = p?.stellar;
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-[520px]" data-testid="payment-drawer">
        {p && <>
          <SheetHeader><SheetTitle>{p.recipient_name}</SheetTitle></SheetHeader>
          <div className="mt-2 flex flex-wrap gap-2"><StatusBadge status={p.status} />{p.rail === "stellar_testnet" ? <ChainBadge label="Stellar Testnet" /> : <SimBadge label="Demo record · no funds move" />}{p.is_synthetic && <SimBadge />}</div>
          <div className="tnum mt-6 text-3xl font-semibold">{money(p.amount, p.currency)}</div>
          <div className="mt-1 text-sm text-muted-foreground">{p.purpose} · requested by {p.requested_by_name}</div>
          {p.destination_address && <div className="mt-4 rounded-lg bg-slate-50 p-3"><div className="text-xs text-muted-foreground">Destination</div><div className="break-all font-mono-plex text-xs">{p.destination_address}</div></div>}
          <div className="mt-5 flex flex-wrap gap-2">
            {p.status === "pending_approval" && isManager && <DecideButtons kind="payment" id={p.id} onDone={changed} />}
            {p.type === "domestic" && p.status === "approved" && isManager && <Button size="sm" variant="outline" onClick={record} data-testid="record-paid-btn">Record as paid (demo)</Button>}
            {p.type === "international" && <StellarActions p={p} onChanged={changed} />}
          </div>
          {st?.tx_hash && (
            <div className="mt-6 rounded-xl border border-cyan-200 bg-[hsl(var(--stellar-subtle))] p-4 text-sm" data-testid="stellar-details">
              <div className="mb-3 flex items-center justify-between font-semibold text-[hsl(var(--stellar))]">Stellar transaction {st.links && <a href={st.links.explorer} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-normal underline" data-testid="explorer-link">Open in explorer <ExternalLink className="h-3 w-3" /></a>}</div>
              <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-2 text-xs">
                <dt className="text-muted-foreground">Hash</dt><dd className="break-all font-mono-plex" data-testid="stellar-tx-hash">{st.tx_hash || "—"}</dd>
                <dt className="text-muted-foreground">Ledger</dt><dd className="tnum" data-testid="stellar-ledger">{st.ledger || "—"}</dd>
                <dt className="text-muted-foreground">Network</dt><dd>{st.network}</dd>
                <dt className="text-muted-foreground">Source</dt><dd className="break-all font-mono-plex">{st.source}</dd>
                <dt className="text-muted-foreground">Operation</dt><dd>{st.operation} · {st.asset_code}{st.asset_issuer ? ` (${shortKey(st.asset_issuer)})` : " (native)"}</dd>
                <dt className="text-muted-foreground">Submitted</dt><dd>{fmtDateTime(st.submitted_at)}</dd>
                <dt className="text-muted-foreground">Confirmed</dt><dd>{fmtDateTime(st.confirmed_at)}</dd>
                <dt className="text-muted-foreground">Attempts</dt><dd>{st.attempts}</dd>
                {st.last_error && <><dt className="text-muted-foreground">Last error</dt><dd className="text-red-700">{st.last_error}</dd></>}
                {st.verification && <><dt className="text-muted-foreground">Last verified</dt><dd data-testid="stellar-verification">{fmtDateTime(st.verification.checked_at)} · {st.verification.found === false ? "not found on ledger" : `${st.verification.successful ? "successful" : "failed"}, ${st.verification.matches_request ? "matches request" : "does not match request"}`}</dd></>}
              </dl>
              <p className="mt-3 text-[11px] text-muted-foreground">Ledger confirmation verifies Testnet settlement only; it does not prove fiat delivery to a beneficiary.</p>
            </div>
          )}
          <div className="mt-8"><div className="mb-3 text-sm font-semibold">History</div>
            <ol className="space-y-3 border-l pl-4">{p.history.map((h, i) => (
              <li key={i} className="relative text-sm"><span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-[hsl(var(--primary))]" /><StatusBadge status={h.status} />
                <div className="mt-1 text-xs text-muted-foreground">{h.actor_name} · {fmtDateTime(h.at)}</div>{h.note && <div className="text-xs">{h.note}</div>}</li>
            ))}</ol></div>
        </>}
      </SheetContent>
    </Sheet>
  );
}

export default function Payments() {
  const { version } = useWorkspace();
  const [type, setType] = useState("international");
  const { data, reload } = useData("/payments", { type, v: version });
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(null);
  return (
    <div>
      <PageHeader title="Business payments" subtitle="Request, approve and track payments. Domestic transfers are demo-only records; international payments settle on the Stellar Testnet."
        actions={<><Button variant="outline" onClick={reload} data-testid="refresh-payments-btn"><RefreshCw className="mr-1.5 h-4 w-4" />Refresh</Button><Button onClick={() => setOpen(true)} data-testid="new-payment-btn"><Plus className="mr-1.5 h-4 w-4" />New {type} payment</Button></>} />
      <Tabs value={type} onValueChange={setType} className="mb-4"><TabsList>
        <TabsTrigger value="international" data-testid="tab-international">International · Stellar Testnet</TabsTrigger>
        <TabsTrigger value="domestic" data-testid="tab-domestic">Domestic · demo records</TabsTrigger>
      </TabsList></Tabs>
      <div className="mb-4 rounded-lg border bg-white px-4 py-3 text-xs text-muted-foreground">{type === "domestic" ? "No actual domestic fund movement. Future integration pathway: regulated Philippine payment providers." : "Real Testnet transactions with stored hash and ledger. Future: licensed fiat on/off-ramps and partner-supported stablecoins."}</div>
      <div className="overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader><TableRow><TableHead>Created</TableHead><TableHead>Recipient</TableHead><TableHead>Purpose</TableHead><TableHead>Requested by</TableHead><TableHead>Status</TableHead>{type === "international" && <TableHead>Tx hash</TableHead>}<TableHead className="text-right">Amount</TableHead></TableRow></TableHeader>
          <TableBody>{(data || []).map((p) => (
            <TableRow key={p.id} className="cursor-pointer" onClick={() => setSel(p.id)} data-testid={`payment-row-${p.id}`}>
              <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDate(p.created_at)}</TableCell>
              <TableCell><div className="font-medium">{p.recipient_name}</div>{p.is_synthetic && <SimBadge />}</TableCell>
              <TableCell className="max-w-[220px] truncate text-muted-foreground">{p.purpose}</TableCell><TableCell>{p.requested_by_name}</TableCell>
              <TableCell><StatusBadge status={p.status} /></TableCell>
              {type === "international" && <TableCell className="font-mono-plex text-xs">{p.stellar?.tx_hash ? shortKey(p.stellar.tx_hash) : "—"}</TableCell>}
              <TableCell className="tnum whitespace-nowrap text-right font-medium">{money(p.amount, p.currency)}</TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
        {data && !data.length && <div className="p-6"><Empty title={`No ${type} payments yet`} /></div>}
      </div>
      <NewPayment open={open} setOpen={setOpen} type={type} onSaved={reload} />
      <PaymentDrawer id={sel} onClose={() => setSel(null)} onChanged={reload} />
    </div>
  );
}
