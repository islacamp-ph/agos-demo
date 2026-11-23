import { useState } from "react";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import http, { errMsg } from "@/lib/api";

export default function DecideButtons({ kind, id, blockedReason, onDone, size = "sm" }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const decide = async (action) => {
    setBusy(true);
    try {
      await http.post(`/${kind === "expense" ? "expenses" : "payments"}/${id}/decision`, { action, note });
      toast.success(action === "approve" ? "Approved" : "Rejected");
      setOpen(false);
      setNote("");
      onDone?.();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  if (blockedReason) return <span className="text-xs text-muted-foreground" data-testid={`blocked-${id}`}>{blockedReason}</span>;
  return (
    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
      <Button size={size} disabled={busy} onClick={() => decide("approve")} className="bg-emerald-700 hover:bg-emerald-800" data-testid={`approve-${id}`}><Check className="mr-1 h-3.5 w-3.5" />Approve</Button>
      <Button size={size} variant="outline" disabled={busy} onClick={() => setOpen(true)} data-testid={`reject-${id}`}><X className="mr-1 h-3.5 w-3.5" />Reject</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reject request</DialogTitle><DialogDescription>The reason is recorded in the approval history.</DialogDescription></DialogHeader>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason for rejection" data-testid="reject-reason-input" />
          <DialogFooter><Button variant="destructive" disabled={busy || !note.trim()} onClick={() => decide("reject")} data-testid="reject-confirm-btn">Reject</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
