import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { fmtDateTime } from "@/lib/format";
import { PageHeader, Panel, Kpi, Empty } from "@/components/agos/ui";

const ROLE = { super_admin: "ISLA Ventures Super Admin", platform_admin: "AGOS Platform Admin" };

function Overview() {
  const { data } = useData("/admin/overview");
  if (!data) return null;
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-3 xl:grid-cols-6" data-testid="admin-overview">
      <Kpi label="Users" value={data.users} /><Kpi label="Workspaces" value={data.workspaces} sub={`${data.demo_workspaces} demo · ${data.real_workspaces} real`} />
      <Kpi label="Waitlist" value={data.waitlist} /><Kpi label="Stellar confirmed" value={data.stellar_confirmed} tone="stellar" /><Kpi label="Platform admins" value={data.platform_admins} />
    </div>
  );
}

export default function AdminPanel() {
  const { me } = useWorkspace();
  const allowed = ["super_admin", "platform_admin"].includes(me.platform_role);
  const { data, reload } = useData(allowed ? "/admin/waitlist" : null);
  if (!allowed) return <Empty title="Not available" hint="This area is restricted to platform administrators." />;
  const update = async (id, status) => { try { await http.patch(`/admin/waitlist/${id}`, { status }); toast.success("Updated"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div>
      <PageHeader eyebrow={ROLE[me.platform_role]} title="Platform administration" subtitle="Waitlist submissions across AGOS. Handle personal data according to the privacy notice." />
      {me.platform_role === "super_admin" && <Overview />}
      <Panel title={`Waitlist (${data?.length || 0})`} testid="admin-waitlist">
        <div className="overflow-x-auto"><Table>
          <TableHeader><TableRow><TableHead>Submitted</TableHead><TableHead>Name</TableHead><TableHead>Business</TableHead><TableHead>Email</TableHead><TableHead>Category</TableHead><TableHead>Challenge</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
          <TableBody>{(data || []).map((w) => (
            <TableRow key={w.id} data-testid={`waitlist-row-${w.id}`}>
              <TableCell className="whitespace-nowrap text-xs">{fmtDateTime(w.created_at)}</TableCell><TableCell>{w.name}</TableCell><TableCell>{w.business_name}</TableCell>
              <TableCell className="text-muted-foreground">{w.email}</TableCell><TableCell>{w.category}</TableCell><TableCell className="max-w-[260px] text-xs text-muted-foreground">{w.challenge}</TableCell>
              <TableCell><Select value={w.status} onValueChange={(v) => update(w.id, v)}><SelectTrigger className="h-8 w-[170px]" data-testid={`waitlist-status-${w.id}`}><SelectValue /></SelectTrigger>
                <SelectContent>{["new", "contacted", "approved_for_pilot", "archived"].map((s) => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></TableCell>
            </TableRow>
          ))}</TableBody></Table></div>
        {data && !data.length && <Empty title="No submissions yet" />}
      </Panel>
    </div>
  );
}
