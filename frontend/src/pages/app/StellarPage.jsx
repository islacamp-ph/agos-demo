import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Copy, ExternalLink, Droplets, Orbit, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { fmtDateTime, shortKey } from "@/lib/format";
import { PageHeader, Panel, ChainBadge, Empty, StatusBadge } from "@/components/agos/ui";

export default function StellarPage() {
  const { isManager, version } = useWorkspace();
  const acct = useData("/stellar/account", { v: version });
  const txs = useData(acct.data?.account ? "/stellar/transactions" : null, { v: version });
  const pays = useData("/payments", { type: "international", v: version });
  const [busy, setBusy] = useState(false);
  const a = acct.data?.account;
  const run = async (fn, msg) => {
    setBusy(true);
    try { await fn(); toast.success(msg); await acct.reload(); txs.reload(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const copy = () => { navigator.clipboard?.writeText(a.public_key); toast.success("Address copied"); };
  const xlm = a?.balances?.find((b) => b.asset === "XLM");
  const records = (pays.data || []).filter((p) => p.stellar?.tx_hash);
  return (
    <div>
      <PageHeader eyebrow="Stellar Testnet" title="Stellar settlement" subtitle="Genuine Stellar Testnet infrastructure. Secret keys are encrypted server-side and never sent to the browser. Testnet XLM has no monetary value."
        actions={<Button variant="outline" onClick={() => { acct.reload(); txs.reload(); pays.reload(); }} data-testid="stellar-refresh-btn"><RefreshCw className="mr-1.5 h-4 w-4" />Refresh</Button>} />
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="Workspace account" testid="stellar-account-panel">
          {!acct.data ? <div className="h-32 animate-pulse rounded bg-slate-100" /> : !a ? (
            <Empty title="No Stellar Testnet account yet" hint="Create a Testnet account for this workspace. It is funded automatically by Stellar's Friendbot."
              action={isManager ? <Button disabled={busy} onClick={() => run(() => http.post("/stellar/account"), "Testnet account created")} data-testid="create-stellar-account-btn">{busy ? "Creating…" : "Create Testnet account"}</Button> : <span className="text-xs text-muted-foreground">Ask an owner or finance manager to create it.</span>} />
          ) : (
            <div>
              <div className="flex flex-wrap items-center gap-2"><ChainBadge label={`Network: ${acct.data.network}`} />{a.exists === false && <StatusBadge status="unfunded" />}</div>
              <div className="mt-5 text-xs text-muted-foreground">Public address</div>
              <div className="mt-1 flex items-start gap-2"><code className="break-all font-mono-plex text-sm" data-testid="stellar-public-key">{a.public_key}</code><button onClick={copy} className="text-slate-400 hover:text-slate-700" data-testid="copy-address-btn"><Copy className="h-4 w-4" /></button></div>
              <div className="mt-6 flex items-end gap-3"><div className="tnum text-4xl font-semibold" data-testid="stellar-balance">{xlm ? Number(xlm.balance).toLocaleString("en-US", { maximumFractionDigits: 7 }) : "0"}</div><div className="pb-1 text-sm text-muted-foreground">Testnet XLM available</div></div>
              {a.error && <div className="mt-2 text-xs text-red-700">{a.error}</div>}
              <div className="mt-6 flex flex-wrap gap-2">
                <Button asChild variant="outline" size="sm"><a href={a.explorer} target="_blank" rel="noreferrer" data-testid="account-explorer-link">View on explorer <ExternalLink className="ml-1 h-3.5 w-3.5" /></a></Button>
                {isManager && a.exists === false && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => http.post("/stellar/account/fund"), "Funded by Friendbot")} data-testid="fund-account-btn"><Droplets className="mr-1 h-3.5 w-3.5" />Fund with Friendbot</Button>}
                <Button asChild size="sm"><Link to="/app/payments" data-testid="goto-payments-btn">Create Stellar payment</Link></Button>
              </div>
            </div>
          )}
        </Panel>
        <Panel title="How the workflow runs" testid="stellar-howto">
          <ol className="space-y-3 text-sm text-slate-600">
            {["Request an international payment with a destination G… address", "An authorized approver approves it internally", "An owner or finance manager explicitly confirms", "AGOS signs server-side and submits to Stellar Testnet", "Hash and ledger are stored; Verify re-checks Horizon at any time"].map((s, i) => (
              <li key={s} className="flex gap-3"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--stellar-subtle))] text-[11px] font-semibold text-[hsl(var(--stellar))]">{i + 1}</span>{s}</li>
            ))}
          </ol>
          <p className="mt-5 text-xs text-muted-foreground">Supported assets: {(acct.data?.assets || []).map((x) => x.label).join(", ")}. Stablecoins (e.g. USDC) are planned only with real supported assets and regulated partners. AGOS is not affiliated with or endorsed by the Stellar Development Foundation.</p>
        </Panel>
      </div>

      <Panel title="Transaction verification records" className="mt-6" testid="stellar-records">
        {records.length ? <div className="overflow-x-auto"><Table>
          <TableHeader><TableRow><TableHead>Recipient</TableHead><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead>Hash</TableHead><TableHead>Ledger</TableHead><TableHead>Confirmed</TableHead><TableHead /></TableRow></TableHeader>
          <TableBody>{records.map((p) => (
            <TableRow key={p.id}><TableCell>{p.recipient_name}</TableCell><TableCell className="tnum">{p.amount} XLM</TableCell><TableCell><StatusBadge status={p.status} /></TableCell>
              <TableCell className="font-mono-plex text-xs">{shortKey(p.stellar.tx_hash, 8)}</TableCell><TableCell className="tnum">{p.stellar.ledger || "—"}</TableCell><TableCell className="text-xs">{fmtDateTime(p.stellar.confirmed_at)}</TableCell>
              <TableCell><a href={p.stellar.links.explorer} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-[hsl(var(--stellar))] underline">Explorer <ExternalLink className="h-3 w-3" /></a></TableCell></TableRow>
          ))}</TableBody></Table></div> : <Empty title="No on-chain payments yet" hint="Approve and confirm an international payment to create the first real Testnet record." />}
      </Panel>

      {a && <Panel title="Recent account activity (live from Horizon)" className="mt-6" testid="stellar-horizon-activity">
        {txs.error ? <div className="text-sm text-red-700">{txs.error}</div> : (txs.data || []).length ? <div className="divide-y">{txs.data.map((t) => (
          <div key={t.id} className="flex flex-wrap items-center gap-3 py-3 text-sm"><Orbit className="h-4 w-4 text-[hsl(var(--stellar))]" />
            <div className="min-w-[200px] flex-1"><div className="capitalize">{t.type.replace(/_/g, " ")} · {t.to === a.public_key ? "received" : "sent"}</div><div className="font-mono-plex text-xs text-muted-foreground">{shortKey(t.tx_hash, 8)} · {fmtDateTime(t.created_at)}</div></div>
            <div className="tnum font-medium">{t.amount} {t.asset}</div><a href={t.explorer} target="_blank" rel="noreferrer" className="text-xs text-[hsl(var(--stellar))] underline">Explorer</a></div>
        ))}</div> : <Empty title="No activity yet" />}
      </Panel>}
    </div>
  );
}
