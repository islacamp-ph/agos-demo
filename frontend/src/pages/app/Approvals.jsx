import { useData } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { money, php, fmtDate, fmtDateTime } from "@/lib/format";
import { PageHeader, Panel, StatusBadge, SimBadge, ChainBadge, Empty } from "@/components/agos/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import DecideButtons from "@/components/agos/DecideButtons";

export default function Approvals() {
  const { isManager, version } = useWorkspace();
  const { data, reload } = useData("/approvals", { v: version });
  if (!data) return <div className="h-96 animate-pulse rounded-xl bg-slate-100" />;
  return (
    <div>
      <PageHeader title="Approvals" subtitle={isManager ? `Finance managers approve up to ${php(data.threshold)}; larger amounts need the owner. Nobody but the owner approves their own request.` : "Track the status of your submitted expenses and payment requests."} />
      <Panel title={`Pending (${data.pending.length})`} testid="pending-approvals">
        {data.pending.length ? <div className="divide-y">{data.pending.map((i) => (
          <div key={i.kind + i.id} className="flex flex-wrap items-center gap-4 py-4" data-testid={`approval-item-${i.id}`}>
            <div className="min-w-[200px] flex-1">
              <div className="flex items-center gap-2 font-medium">{i.title}{i.is_synthetic && <SimBadge />}{i.rail === "stellar_testnet" && <ChainBadge label="Stellar Testnet" />}</div>
              <div className="mt-0.5 text-xs capitalize text-muted-foreground">{i.kind} · {i.requester} · {i.department} · {fmtDate(i.date)}</div>
            </div>
            <div className="tnum w-36 text-right font-semibold">{money(i.amount, i.currency)}</div>
            {isManager ? <DecideButtons kind={i.kind} id={i.id} blockedReason={i.blocked_reason} onDone={reload} /> : <StatusBadge status="pending_approval" />}
          </div>
        ))}</div> : <Empty title="No pending approvals" hint="Your team is fully unblocked." />}
      </Panel>
      <Panel title="Approval & rejection history" className="mt-6" testid="approval-history">
        <div className="overflow-x-auto"><Table>
          <TableHeader><TableRow><TableHead>When</TableHead><TableHead>Item</TableHead><TableHead>Decision</TableHead><TableHead>By</TableHead><TableHead>Note</TableHead><TableHead className="text-right">Amount</TableHead></TableRow></TableHeader>
          <TableBody>{data.history.map((h) => (
            <TableRow key={`${h.kind}-${h.id}-${h.at}-${h.status}`}><TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(h.at)}</TableCell><TableCell><span className="capitalize text-muted-foreground">{h.kind}</span> · {h.title}</TableCell>
              <TableCell><StatusBadge status={h.status} /></TableCell><TableCell>{h.actor_name}</TableCell><TableCell className="max-w-[240px] truncate text-muted-foreground">{h.note}</TableCell>
              <TableCell className="tnum text-right">{money(h.amount, h.currency)}</TableCell></TableRow>
          ))}</TableBody>
        </Table></div>
        {!data.history.length && <Empty title="No decisions yet" />}
      </Panel>
    </div>
  );
}
