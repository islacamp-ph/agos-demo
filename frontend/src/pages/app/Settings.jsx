import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { fmtDateTime, ROLE_LABEL } from "@/lib/format";
import { PageHeader, Panel } from "@/components/agos/ui";

export default function Settings() {
  const { info, isOwner, isManager, reloadInfo, reloadMe } = useWorkspace();
  const w = info.workspace;
  const [f, setF] = useState({ name: w.name, category: w.category, industry: w.industry, location: w.location, business_email: w.business_email, default_currency: w.default_currency, approval_threshold: w.approval_threshold, departments: w.departments.join(", ") });
  const { data: logs } = useData(isManager ? "/audit" : null);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const save = async (e) => {
    e.preventDefault();
    try {
      await http.patch("/workspace", { ...f, approval_threshold: Number(f.approval_threshold), departments: f.departments.split(",").map((d) => d.trim()).filter(Boolean) });
      toast.success("Settings saved"); reloadInfo(); reloadMe();
    } catch (err) { toast.error(errMsg(err)); }
  };
  const field = (k, label, props = {}) => <div className="space-y-1.5"><Label>{label}</Label><Input value={f[k]} onChange={set(k)} disabled={!isOwner} data-testid={`settings-${k}`} {...props} /></div>;
  return (
    <div>
      <PageHeader title="Settings" subtitle={`You are signed in as ${ROLE_LABEL[info.role]}${info.acting_as_persona ? " (demo persona)" : ""}.`} />
      <Panel title="Business workspace" testid="settings-workspace">
        <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
          {field("name", "Business name")}{field("category", "Business category")}{field("industry", "Industry")}{field("location", "Location")}{field("business_email", "Business email", { type: "email" })}
          <div className="space-y-1.5"><Label>Default currency</Label><Select value={f.default_currency} onValueChange={set("default_currency")} disabled={!isOwner}><SelectTrigger data-testid="settings-currency"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="PHP">PHP</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent></Select></div>
          {field("approval_threshold", "Finance manager approval threshold (PHP)", { type: "number", min: 0 })}
          {field("departments", "Departments (comma-separated)")}
          {isOwner && <div className="md:col-span-2"><Button type="submit" data-testid="settings-save-btn">Save settings</Button></div>}
        </form>
      </Panel>
      <Panel title="Compliance notice" className="mt-6">
        <p className="text-sm leading-relaxed text-muted-foreground">AGOS is an MVP demonstration. It is not a bank, licensed lender, payment institution, electronic money issuer or virtual asset service provider. Do not enter real banking credentials or sensitive identification documents. Cards and domestic payments are simulated; Stellar transactions run on Testnet with no monetary value.</p>
      </Panel>
      {isManager && <Panel title="Audit log" className="mt-6" testid="audit-log">
        <div className="max-h-[480px] overflow-auto"><Table>
          <TableHeader><TableRow><TableHead>When</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead>Details</TableHead></TableRow></TableHeader>
          <TableBody>{(logs || []).map((l) => <TableRow key={l.id}><TableCell className="whitespace-nowrap text-xs">{fmtDateTime(l.at)}</TableCell><TableCell className="text-sm">{l.actor_name}</TableCell><TableCell className="font-mono-plex text-xs">{l.action}</TableCell><TableCell className="max-w-[360px] truncate text-xs text-muted-foreground">{l.details}</TableCell></TableRow>)}</TableBody>
        </Table></div>
      </Panel>}
    </div>
  );
}
