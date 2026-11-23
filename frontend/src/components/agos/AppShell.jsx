import { useState } from "react";
import { NavLink, Outlet, Navigate, Link } from "react-router-dom";
import { UserButton } from "@clerk/react";
import { LayoutDashboard, Receipt, PieChart, CheckSquare, CreditCard, Send, Orbit, BarChart3, Users, Settings, Menu, Map, ShieldCheck, Loader2 } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Wordmark, SimBadge } from "@/components/agos/ui";
import { ROLE_LABEL } from "@/lib/format";

const NAV = [
  ["overview", "Overview", LayoutDashboard], ["expenses", "Expenses", Receipt], ["budgets", "Budgets", PieChart],
  ["approvals", "Approvals", CheckSquare], ["cards", "Cards", CreditCard], ["payments", "Payments", Send],
  ["stellar", "Stellar", Orbit], ["reports", "Reports", BarChart3], ["team", "Team", Users], ["settings", "Settings", Settings],
];

function NavList({ onNavigate }) {
  const { me } = useWorkspace();
  const item = ([path, label, Icon]) => (
    <NavLink key={path} to={`/app/${path}`} onClick={onNavigate} data-testid={`nav-${path}`}
      className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] transition-colors ${isActive ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}>
      <Icon className="h-4 w-4 shrink-0" /> <span className="flex-1">{label}</span>
      {path === "cards" && <span className="rounded bg-amber-400/15 px-1.5 text-[10px] text-amber-200">Sim</span>}
      {path === "stellar" && <span className="rounded bg-cyan-400/15 px-1.5 text-[10px] text-cyan-200">Testnet</span>}
    </NavLink>
  );
  const admin = me && ["super_admin", "platform_admin"].includes(me.platform_role);
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV.map(item)}
      <div className="my-3 h-px bg-white/10" />
      {item(["roadmap", "Vision & Roadmap", Map])}
      {admin && item(["admin", "Platform Admin", ShieldCheck])}
    </nav>
  );
}

function Sidebar({ onNavigate }) {
  return (
    <div className="flex h-full flex-col bg-[hsl(var(--navy-ink))] px-4 py-5">
      <Link to="/" className="mb-8 px-2" data-testid="sidebar-home-link"><Wordmark light /></Link>
      <NavList onNavigate={onNavigate} />
      <div className="mt-auto rounded-lg border border-white/10 p-3 text-[11px] leading-relaxed text-slate-400">
        AGOS is not a bank or payment institution. Cards and domestic transfers are simulated; Stellar runs on Testnet.
      </div>
    </div>
  );
}

function WorkspaceSwitcher() {
  const { me, wsId, setWsId } = useWorkspace();
  return (
    <Select value={wsId || ""} onValueChange={(v) => (v === "__new" ? (window.location.href = "/app/onboarding") : setWsId(v))}>
      <SelectTrigger className="h-9 w-[220px] bg-white" data-testid="workspace-switcher"><SelectValue placeholder="Workspace" /></SelectTrigger>
      <SelectContent>
        {me.workspaces.map((w) => <SelectItem key={w.id} value={w.id}>{w.name}{w.is_demo ? " · Demo" : ""}</SelectItem>)}
        <SelectItem value="__new">+ New workspace</SelectItem>
      </SelectContent>
    </Select>
  );
}

function PersonaSwitcher() {
  const { info, setActAs } = useWorkspace();
  if (!info?.personas?.length) return null;
  return (
    <div className="hidden items-center gap-2 lg:flex">
      <span className="text-xs text-muted-foreground">Viewing as</span>
      <Select value={info.member.id} onValueChange={setActAs}>
        <SelectTrigger className="h-9 w-[230px] bg-white" data-testid="persona-switcher"><SelectValue /></SelectTrigger>
        <SelectContent>
          {info.personas.map((p) => <SelectItem key={p.id} value={p.id}>{p.name} — {ROLE_LABEL[p.role]}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function AppShell() {
  const { me, info, error } = useWorkspace();
  const [open, setOpen] = useState(false);
  if (error && !me) return <div className="p-10 text-sm text-red-700" data-testid="app-error">{error}</div>;
  if (!me) return <div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  if (!me.workspaces.length) return <Navigate to="/app/onboarding" replace />;
  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 md:block"><Sidebar /></aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-xl md:px-8">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild><Button variant="ghost" size="icon" className="md:hidden" data-testid="mobile-menu-btn"><Menu className="h-5 w-5" /></Button></SheetTrigger>
            <SheetContent side="left" className="w-[260px] border-0 p-0"><Sidebar onNavigate={() => setOpen(false)} /></SheetContent>
          </Sheet>
          <WorkspaceSwitcher />
          {info?.workspace?.is_demo && <SimBadge label="Demo workspace · synthetic data" />}
          <div className="ml-auto flex items-center gap-4">
            <PersonaSwitcher />
            {info && <span className="hidden text-xs text-muted-foreground xl:inline" data-testid="current-role">{ROLE_LABEL[info.role]}</span>}
            <UserButton />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 md:px-8 lg:py-10">
          {info ? <Outlet /> : <div className="flex justify-center py-24"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>}
        </main>
      </div>
    </div>
  );
}
