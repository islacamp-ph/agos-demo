import { useState } from "react";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import http, { useData, errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { php, ROLE_LABEL } from "@/lib/format";
import { PageHeader, StatusBadge, SimBadge } from "@/components/agos/ui";

function AddMember({ open, setOpen, onDone }) {
  const { info } = useWorkspace();
  const [f, setF] = useState({ name: "", email: "", role: "employee", department: info.workspace.departments[0], title: "", spending_limit: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const save = async (e) => {
    e.preventDefault();
    try { await http.post("/team", { ...f, spending_limit: Number(f.spending_limit || 0) }); toast.success("Member invited — they join when they sign in with this email"); setOpen(false); onDone(); } catch (err) { toast.error(errMsg(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add team member</DialogTitle><DialogDescription>They gain access after signing in to AGOS with this verified email.</DialogDescription></DialogHeader>
        <form onSubmit={save} className="grid grid-cols-2 gap-3" data-testid="add-member-form">
          <div className="space-y-1.5"><Label>Name</Label><Input required minLength={2} value={f.name} onChange={set("name")} data-testid="member-name" /></div>
          <div className="space-y-1.5"><Label>Email</Label><Input required type="email" value={f.email} onChange={set("email")} data-testid="member-email" /></div>
          <div className="space-y-1.5"><Label>Role</Label><Select value={f.role} onValueChange={set("role")}><SelectTrigger data-testid="member-role"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(ROLE_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Department</Label><Select value={f.department} onValueChange={set("department")}><SelectTrigger data-testid="member-dept"><SelectValue /></SelectTrigger><SelectContent>{info.workspace.departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Title</Label><Input value={f.title} onChange={set("title")} data-testid="member-title" /></div>
          <div className="space-y-1.5"><Label>Monthly spending limit (PHP)</Label><Input type="number" min="0" value={f.spending_limit} onChange={set("spending_limit")} data-testid="member-limit" /></div>
          <DialogFooter className="col-span-2"><Button type="submit" data-testid="member-save-btn">Add member</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Team() {
  const { isOwner, isManager, info, version } = useWorkspace();
  const { data, reload } = useData("/team", { v: version });
  const [open, setOpen] = useState(false);
  const patch = async (m, body) => { try { await http.patch(`/team/${m.id}`, body); toast.success("Member updated"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div>
      <PageHeader title="Team" subtitle="Roles are enforced on the server for every request: owners control the workspace, finance managers run expense workflows, employees submit and track."
        actions={isOwner && <Button onClick={() => setOpen(true)} data-testid="add-member-btn"><UserPlus className="mr-1.5 h-4 w-4" />Add member</Button>} />
      <div className="overflow-x-auto rounded-xl border bg-card"><Table>
        <TableHeader><TableRow><TableHead>Name</TableHead>{isManager && <TableHead>Email</TableHead>}<TableHead>Department</TableHead><TableHead>Role</TableHead>{isManager && <TableHead>Monthly limit</TableHead>}<TableHead>Status</TableHead>{isOwner && <TableHead />}</TableRow></TableHeader>
        <TableBody>{(data || []).map((m) => (
          <TableRow key={m.id} data-testid={`member-row-${m.id}`}>
            <TableCell><div className="font-medium">{m.name}{m.id === info.real_member_id && <span className="ml-1 text-xs text-muted-foreground">(you)</span>}</div><div className="text-xs text-muted-foreground">{m.title}</div>{m.is_synthetic && <SimBadge label="Fictional demo user" />}</TableCell>
            {isManager && <TableCell className="text-muted-foreground">{m.email}</TableCell>}
            <TableCell>{m.department}</TableCell>
            <TableCell>{isOwner && m.status !== "removed" ? (
              <Select value={m.role} onValueChange={(v) => patch(m, { role: v })}><SelectTrigger className="h-8 w-[180px]" data-testid={`role-select-${m.id}`}><SelectValue /></SelectTrigger><SelectContent>{Object.entries(ROLE_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
            ) : ROLE_LABEL[m.role]}</TableCell>
            {isManager && <TableCell className="tnum">{m.spending_limit ? php(m.spending_limit) : "—"}</TableCell>}
            <TableCell><StatusBadge status={m.status} /></TableCell>
            {isOwner && <TableCell>{m.status !== "removed" && m.id !== info.real_member_id && <Button size="sm" variant="ghost" onClick={() => patch(m, { status: "removed" })} data-testid={`remove-member-${m.id}`}>Remove</Button>}</TableCell>}
          </TableRow>
        ))}</TableBody></Table></div>
      {info.workspace.is_demo && <p className="mt-4 text-xs text-muted-foreground">Fictional demo users cannot sign in. Use "Viewing as" in the top bar to experience their role in your private demo.</p>}
      {open && <AddMember open={open} setOpen={setOpen} onDone={reload} />}
    </div>
  );
}
