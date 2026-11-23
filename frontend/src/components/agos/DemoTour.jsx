import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Check, Play, X, ExternalLink, Presentation, Loader2, Link2, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import http, { errMsg, downloadFile } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { signWithFreighter, ensureFreighter } from "@/lib/wallet";
import { today, newKey, shortKey } from "@/lib/format";

const STEPS = [
  { title: "One view of the business", body: "The dashboard is calculated live from stored records: spending, budgets, approvals and Stellar activity.", path: "/app/overview", cta: "Start tour" },
  { title: "An employee submits an expense", body: "Paolo (Engineering) submits a ₱2,450 design-tool expense. It is routed for approval automatically.", path: "/app/expenses", cta: "Submit expense" },
  { title: "Finance approves — budgets update", body: "The approval is recorded with actor and timestamp, and the Engineering budget utilization moves.", path: "/app/budgets", cta: "Approve expense" },
  { title: "Request a cross-border payment", body: "A 5 XLM contractor payment is requested to a fresh Stellar Testnet address and enters the approval queue.", path: "/app/payments", cta: "Create payment" },
  { title: "Approve and settle on Stellar", body: "After approval and explicit confirmation, a genuine Stellar Testnet transaction is signed and submitted.", path: "/app/payments", cta: "Approve & settle" },
  { title: "Verify independently", body: "AGOS re-checks the transaction on Horizon. Anyone can confirm it on the public explorer.", path: "/app/stellar", cta: "Verify on ledger" },
];

function useElapsed(start, stopped) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!start || stopped) return undefined; setNow(Date.now()); const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [start, stopped]);
  if (!start) return "0:00";
  const s = Math.max(0, Math.floor((now - start) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export const TOUR_URL = () => `${window.location.origin}/tour`;

export function copyTourLink() {
  navigator.clipboard?.writeText(TOUR_URL()).then(
    () => toast.success("Tour link copied — anyone who opens it gets their own private demo"),
    () => toast.message(TOUR_URL()),
  );
}

export function TourLauncher() {
  const { info } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const eligible = info?.workspace?.is_demo && !info.acting_as_persona && info.role === "owner";
  useEffect(() => {
    if (params.get("tour") !== "1" || !info) return;
    if (eligible) setOpen(true);
    params.delete("tour");
    setParams(params, { replace: true });
  }, [params, setParams, info, eligible]);
  if (!eligible) return null;
  return (
    <>
      <Button size="icon" variant="outline" className="h-9 w-9 rounded-full sm:hidden" onClick={() => setOpen(true)} data-testid="investor-tour-btn-mobile"><Presentation className="h-4 w-4" /></Button>
      <div className="hidden items-center sm:flex">
        <Button size="sm" variant="outline" className="rounded-l-full rounded-r-none border-r-0" onClick={() => setOpen(true)} data-testid="investor-tour-btn"><Presentation className="mr-1.5 h-4 w-4" />Investor tour</Button>
        <Button size="sm" variant="outline" className="rounded-l-none rounded-r-full px-2.5" onClick={copyTourLink} title="Copy shareable tour link" data-testid="copy-tour-link-btn"><Link2 className="h-4 w-4" /></Button>
      </div>
      {open && createPortal(<DemoTour onClose={() => setOpen(false)} />, document.body)}
    </>
  );
}

function DemoTour({ onClose }) {
  const { info, bump } = useWorkspace();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [ctx, setCtx] = useState({});
  const [start, setStart] = useState(null);
  const elapsed = useElapsed(start, step >= STEPS.length);
  const shownTime = step >= STEPS.length && ctx.duration ? `${Math.floor(ctx.duration / 60)}:${String(ctx.duration % 60).padStart(2, "0")}` : elapsed;
  const s = STEPS[step];

  const actions = [
    async () => { setStart(Date.now()); },
    async () => {
      const paolo = info.personas.find((p) => p.name === "Paolo Mendoza") || info.personas.find((p) => p.role === "employee");
      const { data } = await http.post("/expenses", { merchant: "Figma (investor tour)", category: "Software & SaaS", amount: 2450, currency: "PHP", date: today(), description: "Investor tour — design tooling", member_id: paolo?.id, submit: true });
      return { expenseId: data.id };
    },
    async (c) => { await http.post(`/expenses/${c.expenseId}/decision`, { action: "approve", note: "Approved during investor tour" }); },
    async () => {
      let { data: acct } = await http.get("/stellar/account");
      if (!acct.account) { await http.post("/stellar/account"); await new Promise((r) => setTimeout(r, 2500)); ({ data: acct } = await http.get("/stellar/account")); }
      const { data: rec } = await http.post("/stellar/demo-recipient");
      const { data: pay } = await http.post("/payments", { type: "international", recipient_name: "Investor tour — Singapore contractor", destination_address: rec.public_key, asset_code: "XLM", amount: "5", purpose: "Investor tour settlement demo" });
      return { paymentId: pay.id, walletMode: acct.account.mode === "wallet" };
    },
    async (c) => {
      if (c.walletMode) await ensureFreighter();
      await http.post(`/payments/${c.paymentId}/decision`, { action: "approve", note: "Approved during investor tour" });
      const key = newKey();
      let pay;
      if (c.walletMode) {
        const { data: prep } = await http.post(`/payments/${c.paymentId}/stellar/prepare`, { confirm: true, idempotency_key: key });
        const signed = await signWithFreighter(prep.xdr, prep.network_passphrase, prep.address);
        pay = (await http.post(`/payments/${c.paymentId}/stellar/submit-signed`, { signed_xdr: signed })).data.payment;
      } else {
        pay = (await http.post(`/payments/${c.paymentId}/stellar/submit`, { confirm: true, idempotency_key: key })).data.payment;
      }
      if (pay.status === "failed") throw new Error(pay.stellar?.last_error || "Stellar submission failed");
      return { txHash: pay.stellar?.tx_hash, ledger: pay.stellar?.ledger, explorer: pay.stellar?.links?.explorer };
    },
    async (c) => {
      const { data } = await http.post(`/payments/${c.paymentId}/stellar/verify`);
      return { verified: data.status === "confirmed" && data.stellar?.verification?.matches_request, ledger: data.stellar?.ledger, duration: Math.max(1, Math.round((Date.now() - start) / 1000)) };
    },
  ];

  const run = async () => {
    setBusy(true);
    try {
      const out = await actions[step](ctx);
      setCtx((c) => ({ ...c, ...(out || {}) }));
      nav(STEPS[step].path);
      bump();
      setStep(step + 1);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const done = step >= STEPS.length;
  const [pdfBusy, setPdfBusy] = useState(false);
  const downloadPdf = async () => {
    setPdfBusy(true);
    try {
      await downloadFile(`/payments/${ctx.paymentId}/pitch-summary`, { expense_id: ctx.expenseId, duration: ctx.duration }, "agos-pitch-summary.pdf");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setPdfBusy(false);
    }
  };
  return (
    <div className="fixed bottom-5 right-5 z-50 w-[380px] max-w-[calc(100vw-2.5rem)] rounded-2xl border bg-white shadow-2xl fade-up" data-testid="investor-tour-panel">
      <div className="flex items-center justify-between rounded-t-2xl bg-[hsl(var(--navy-ink))] px-5 py-3 text-white">
        <div className="text-sm font-semibold">Investor tour · expense to settlement</div>
        <div className="flex items-center gap-3"><span className="tnum text-xs text-slate-300" data-testid="tour-timer">{shownTime}</span><button onClick={copyTourLink} title="Copy shareable tour link" data-testid="tour-panel-copy-link"><Link2 className="h-4 w-4" /></button><button onClick={onClose} data-testid="tour-close-btn"><X className="h-4 w-4" /></button></div>
      </div>
      <ol className="flex gap-1 px-5 pt-4">{STEPS.map((st, i) => <li key={st.title} className={`h-1 flex-1 rounded-full ${i < step ? "bg-emerald-500" : i === step ? "bg-[hsl(var(--primary))]" : "bg-slate-200"}`} />)}</ol>
      <div className="px-5 pb-5 pt-4">
        {done ? (
          <div data-testid="tour-complete">
            <div className="flex items-center gap-2 font-semibold text-[hsl(var(--navy-ink))]"><Check className="h-4 w-4 text-emerald-600" />Settled and verified in {shownTime}</div>
            <p className="mt-2 text-sm text-slate-600">Expense submitted, approved and counted in budgets; a payment approved and settled on Stellar Testnet{ctx.ledger ? ` at ledger ${ctx.ledger}` : ""}{ctx.verified ? ", verified against Horizon" : ""}.</p>
            {ctx.explorer && <a href={ctx.explorer} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm text-[hsl(var(--stellar))] underline" data-testid="tour-explorer-link">{shortKey(ctx.txHash, 8)} on explorer <ExternalLink className="h-3.5 w-3.5" /></a>}
            <p className="mt-3 text-[11px] text-muted-foreground">Testnet XLM has no monetary value; ledger confirmation does not prove fiat delivery. Expense data is synthetic.</p>
            <Button className="mt-4 w-full" disabled={pdfBusy} onClick={downloadPdf} data-testid="tour-download-pdf-btn">{pdfBusy ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Preparing PDF…</> : <><FileDown className="mr-1.5 h-4 w-4" />Download pitch summary (PDF)</>}</Button>
            <Button className="mt-2 w-full" variant="outline" onClick={onClose}>Close tour</Button>
          </div>
        ) : (
          <div>
            <div className="text-xs text-muted-foreground">Step {step + 1} of {STEPS.length}</div>
            <div className="mt-1 font-semibold text-[hsl(var(--navy-ink))]" data-testid="tour-step-title">{s.title}</div>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.body}</p>
            {step === 5 && ctx.txHash && <div className="mt-2 font-mono-plex text-xs text-muted-foreground">tx {shortKey(ctx.txHash, 8)} · ledger {ctx.ledger || "pending"}</div>}
            <Button className="mt-4 w-full" disabled={busy} onClick={run} data-testid="tour-next-btn">{busy ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Working…</> : <><Play className="mr-1.5 h-4 w-4" />{s.cta}</>}</Button>
          </div>
        )}
      </div>
    </div>
  );
}
