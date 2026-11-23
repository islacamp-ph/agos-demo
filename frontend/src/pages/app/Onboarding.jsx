import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { Building2, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import http, { errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Wordmark, SimBadge } from "@/components/agos/ui";
import { BUSINESS_CATEGORIES } from "@/lib/format";

const SEL = (label, value, onChange, options, testid) => (
  <div className="space-y-1.5"><Label>{label}</Label>
    <Select value={value} onValueChange={onChange}><SelectTrigger data-testid={testid}><SelectValue placeholder="Select" /></SelectTrigger>
      <SelectContent>{options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent></Select></div>
);

export default function Onboarding() {
  const { me, reloadMe, setWsId } = useWorkspace();
  const nav = useNavigate();
  const [busy, setBusy] = useState(null);
  const [f, setF] = useState({ name: "", category: "", industry: "", location: "", business_email: "", admin_name: "", team_size: "1-10", default_currency: "PHP" });
  if (!me) return <div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });

  const go = async (fn, which) => {
    setBusy(which);
    try {
      const { data } = await fn();
      await reloadMe();
      setWsId(data.id);
      nav("/app/overview");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };
  const create = (e) => {
    e.preventDefault();
    if (!f.category) return toast.error("Choose a business category");
    go(() => http.post("/workspaces", { ...f, admin_name: f.admin_name || me.name }), "new");
  };
  if (me.workspaces.length && window.location.search.includes("auto")) return <Navigate to="/app/overview" replace />;

  return (
    <div className="min-h-screen bg-[#f7f9fb]">
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8">
        <Wordmark />
        <h1 className="mt-14 text-4xl font-semibold tracking-tight text-[hsl(var(--navy-ink))]" data-testid="onboarding-title">Welcome to AGOS, {me.name.split(" ")[0]}.</h1>
        <p className="mt-3 text-slate-600">Choose how you'd like to start. You can have both and switch any time.</p>
        <div className="mt-10 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="flex flex-col rounded-2xl bg-[hsl(var(--navy-ink))] p-8 text-white">
            <Sparkles className="h-6 w-6 text-cyan-200" />
            <div className="mt-6 text-xl font-semibold">Explore the Isla Digital Solutions demo</div>
            <p className="mt-3 flex-1 text-sm leading-relaxed text-slate-300">A private, pre-filled copy just for you: a Metro Manila technology services company with an owner (you), a finance manager and three employees, plus expenses, budgets, simulated cards and payment requests. Edit anything — nobody else sees it.</p>
            <div className="mt-4"><SimBadge label="Synthetic data · simulated cards" /></div>
            <Button className="mt-8 rounded-full bg-white text-[hsl(var(--navy-ink))] hover:bg-cyan-50" disabled={!!busy} onClick={() => go(() => http.post("/workspaces/demo"), "demo")} data-testid="create-demo-btn">
              {busy === "demo" ? "Preparing your demo…" : "Open my demo workspace"}
            </Button>
          </div>
          <form onSubmit={create} className="rounded-2xl border bg-white p-8" data-testid="onboarding-form">
            <div className="flex items-center gap-2 text-[hsl(var(--navy-ink))]"><Building2 className="h-5 w-5" /><span className="text-xl font-semibold">Set up your business</span></div>
            <p className="mt-2 text-sm text-slate-500">An empty workspace for real onboarding and pilots. No regulatory verification is required in this MVP.</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><Label>Business name</Label><Input required minLength={2} value={f.name} onChange={set("name")} data-testid="ob-name" /></div>
              {SEL("Business category", f.category, set("category"), BUSINESS_CATEGORIES, "ob-category")}
              <div className="space-y-1.5"><Label>Industry</Label><Input required minLength={2} value={f.industry} onChange={set("industry")} placeholder="e.g. Food & Beverage" data-testid="ob-industry" /></div>
              <div className="space-y-1.5"><Label>Registered / operating location</Label><Input required minLength={2} value={f.location} onChange={set("location")} placeholder="e.g. Cebu City, Philippines" data-testid="ob-location" /></div>
              <div className="space-y-1.5"><Label>Business email</Label><Input required type="email" value={f.business_email} onChange={set("business_email")} data-testid="ob-email" /></div>
              <div className="space-y-1.5"><Label>Administrator name</Label><Input value={f.admin_name} onChange={set("admin_name")} placeholder={me.name} data-testid="ob-admin" /></div>
              {SEL("Team size", f.team_size, set("team_size"), ["1-10", "11-50", "51-200", "200+"], "ob-team-size")}
              {SEL("Default currency", f.default_currency, set("default_currency"), ["PHP", "USD"], "ob-currency")}
            </div>
            <Button type="submit" className="mt-7 w-full rounded-full" disabled={!!busy} data-testid="ob-submit">{busy === "new" ? "Creating…" : "Create workspace"}</Button>
          </form>
        </div>
      </div>
    </div>
  );
}
