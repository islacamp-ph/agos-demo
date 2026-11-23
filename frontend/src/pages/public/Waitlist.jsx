import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import http, { errMsg } from "@/lib/api";
import { BUSINESS_CATEGORIES } from "@/lib/format";

const EMPTY = { name: "", business_name: "", email: "", category: "", challenge: "", consent: false, website: "" };

export default function Waitlist() {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });

  const submit = async (e) => {
    e.preventDefault();
    if (!f.category) return toast.error("Choose a business category");
    if (!f.consent) return toast.error("Please accept the privacy notice");
    setBusy(true);
    try {
      await http.post("/waitlist", f);
      setDone(true);
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-6xl gap-14 px-5 py-20 md:px-8 lg:grid-cols-[0.9fr_1.1fr]">
      <div>
        <div className="eyebrow text-[hsl(var(--stellar))]">Early access</div>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-[hsl(var(--navy-ink))] sm:text-5xl">Join the AGOS waitlist.</h1>
        <p className="mt-5 text-base leading-relaxed text-slate-600">Tell us about your business and the finance problem you most want solved. We will reach out about pilots for Philippine startups and MSMEs.</p>
        <p className="mt-6 text-sm text-slate-500">Please do not include bank credentials, IDs or other sensitive information.</p>
      </div>
      <div className="rounded-2xl border bg-white p-7 shadow-sm md:p-9">
        {done ? (
          <div className="py-10 text-center" data-testid="waitlist-success">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
            <div className="mt-4 text-lg font-semibold text-[hsl(var(--navy-ink))]">You're on the list.</div>
            <p className="mt-2 text-sm text-slate-600">Thank you — the AGOS team will be in touch.</p>
            <Button asChild variant="outline" className="mt-6 rounded-full"><Link to="/app">Explore the demo meanwhile</Link></Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-5" data-testid="waitlist-form">
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Name</Label><Input required minLength={2} value={f.name} onChange={set("name")} data-testid="waitlist-name" /></div>
              <div className="space-y-1.5"><Label>Business name</Label><Input required minLength={2} value={f.business_name} onChange={set("business_name")} data-testid="waitlist-business" /></div>
            </div>
            <div className="space-y-1.5"><Label>Business email</Label><Input required type="email" value={f.email} onChange={set("email")} data-testid="waitlist-email" /></div>
            <div className="space-y-1.5">
              <Label>Business category</Label>
              <Select value={f.category} onValueChange={set("category")}>
                <SelectTrigger data-testid="waitlist-category"><SelectValue placeholder="Select a category" /></SelectTrigger>
                <SelectContent>{BUSINESS_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5"><Label>Primary financial challenge</Label><Textarea required minLength={3} rows={4} value={f.challenge} onChange={set("challenge")} placeholder="e.g. Tracking employee spending across departments" data-testid="waitlist-challenge" /></div>
            <input type="text" tabIndex={-1} autoComplete="off" className="hidden" value={f.website} onChange={set("website")} aria-hidden="true" />
            <label className="flex items-start gap-3 text-sm text-slate-600">
              <Checkbox checked={f.consent} onCheckedChange={(v) => setF({ ...f, consent: !!v })} data-testid="waitlist-consent" className="mt-0.5" />
              <span>I consent to ISLA Ventures Inc. storing these details to contact me about AGOS, as described in the <Link to="/privacy" className="underline">privacy notice</Link>. I can ask for deletion at any time.</span>
            </label>
            <Button type="submit" disabled={busy} className="w-full rounded-full" data-testid="waitlist-submit">{busy ? "Submitting…" : "Join the Waitlist"}</Button>
          </form>
        )}
      </div>
    </div>
  );
}
