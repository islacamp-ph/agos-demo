import { Badge } from "@/components/ui/badge";
import { FlaskConical, Link2, Clock, CheckCircle2, XCircle, CircleDashed, Send, Loader2 } from "lucide-react";

export const AgosMark = ({ className = "h-7 w-7", light = false }) => (
  <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
    <rect width="32" height="32" rx="8" fill={light ? "#ffffff" : "#14263d"} />
    <path d="M6 20c4-6 7-6 10 0s6 6 10 0" fill="none" stroke={light ? "#14263d" : "#7dd3e0"} strokeWidth="2.6" strokeLinecap="round" />
    <path d="M6 13c4-6 7-6 10 0s6 6 10 0" fill="none" stroke={light ? "#14263d" : "#ffffff"} strokeOpacity="0.55" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

export const Wordmark = ({ light = false }) => (
  <span className="flex items-center gap-2.5" data-testid="agos-wordmark">
    <AgosMark light={light} />
    <span className={`text-[17px] font-semibold tracking-[0.18em] ${light ? "text-white" : "text-[hsl(var(--navy-ink))]"}`}>AGOS</span>
  </span>
);

export const SimBadge = ({ label = "Simulated" }) => (
  <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800" data-testid="simulated-badge">
    <FlaskConical className="h-3 w-3" /> {label}
  </span>
);

export const ChainBadge = ({ label = "On-chain · Testnet" }) => (
  <span className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-[hsl(var(--stellar-subtle))] px-2 py-0.5 text-[11px] font-medium text-[hsl(var(--stellar))]" data-testid="chain-badge">
    <Link2 className="h-3 w-3" /> {label}
  </span>
);

const STATUS = {
  draft: ["Draft", "bg-slate-100 text-slate-700 border-slate-200", CircleDashed],
  submitted: ["Submitted", "bg-sky-50 text-sky-800 border-sky-200", Send],
  pending_approval: ["Pending Approval", "bg-amber-50 text-amber-800 border-amber-200", Clock],
  approved: ["Approved", "bg-emerald-50 text-emerald-800 border-emerald-200", CheckCircle2],
  rejected: ["Rejected", "bg-red-50 text-red-700 border-red-200", XCircle],
  paid: ["Recorded as Paid", "bg-indigo-50 text-indigo-800 border-indigo-200", CheckCircle2],
  recorded_as_paid: ["Recorded (Demo)", "bg-indigo-50 text-indigo-800 border-indigo-200", CheckCircle2],
  submitting: ["Submitting", "bg-cyan-50 text-cyan-800 border-cyan-200", Loader2],
  pending_verification: ["Awaiting Verification", "bg-cyan-50 text-cyan-800 border-cyan-200", Clock],
  confirmed: ["Confirmed on Ledger", "bg-emerald-50 text-emerald-800 border-emerald-200", CheckCircle2],
  failed: ["Failed", "bg-red-50 text-red-700 border-red-200", XCircle],
  active: ["Active", "bg-emerald-50 text-emerald-800 border-emerald-200", CheckCircle2],
  frozen: ["Frozen", "bg-sky-50 text-sky-800 border-sky-200", CircleDashed],
  invited: ["Invited", "bg-slate-100 text-slate-700 border-slate-200", Send],
  removed: ["Removed", "bg-slate-100 text-slate-500 border-slate-200", XCircle],
  posted: ["Posted", "bg-emerald-50 text-emerald-800 border-emerald-200", CheckCircle2],
  declined: ["Declined", "bg-red-50 text-red-700 border-red-200", XCircle],
};

export const StatusBadge = ({ status }) => {
  const [label, cls, Icon] = STATUS[status] || [String(status || "").replace(/_/g, " "), "bg-slate-100 text-slate-700 border-slate-200", CircleDashed];
  return (
    <Badge variant="outline" className={`gap-1 whitespace-nowrap rounded-full font-medium capitalize ${cls}`} data-testid={`status-${status}`}>
      <Icon className={`h-3 w-3 ${status === "submitting" ? "animate-spin" : ""}`} /> {label}
    </Badge>
  );
};

export const PageHeader = ({ title, subtitle, actions, eyebrow }) => (
  <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between fade-up">
    <div>
      {eyebrow && <div className="eyebrow mb-2 text-[hsl(var(--stellar))]">{eyebrow}</div>}
      <h1 className="text-2xl font-semibold tracking-tight text-[hsl(var(--navy-ink))] md:text-[28px]" data-testid="page-title">{title}</h1>
      {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

export const Kpi = ({ label, value, sub, tone, testid, icon: Icon }) => (
  <div className="rounded-xl border bg-card p-5 shadow-[0_1px_2px_rgba(15,23,42,0.05)] transition-shadow hover:shadow-md" data-testid={testid}>
    <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
      <span>{label}</span>{Icon && <Icon className="h-4 w-4 opacity-60" />}
    </div>
    <div className="tnum mt-3 text-[26px] font-semibold tracking-tight text-[hsl(var(--navy-ink))]">{value}</div>
    {sub && <div className={`mt-1 text-xs ${tone === "warn" ? "text-amber-700" : tone === "stellar" ? "text-[hsl(var(--stellar))]" : "text-muted-foreground"}`}>{sub}</div>}
  </div>
);

export const Empty = ({ title, hint, action }) => (
  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/60 px-6 py-14 text-center" data-testid="empty-state">
    <div className="text-sm font-medium text-[hsl(var(--navy-ink))]">{title}</div>
    {hint && <div className="mt-1 max-w-md text-sm text-muted-foreground">{hint}</div>}
    {action && <div className="mt-5">{action}</div>}
  </div>
);

export const Panel = ({ title, actions, children, className = "", testid }) => (
  <section className={`rounded-xl border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.05)] ${className}`} data-testid={testid}>
    {title && (
      <div className="flex items-center justify-between gap-3 border-b px-5 py-3.5">
        <h2 className="text-sm font-semibold text-[hsl(var(--navy-ink))]">{title}</h2>
        {actions}
      </div>
    )}
    <div className="p-5">{children}</div>
  </section>
);

export const Meter = ({ pct, state }) => {
  const color = state === "over" ? "bg-red-600" : state === "warning" ? "bg-amber-500" : "bg-[hsl(var(--primary))]";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full transition-[width] duration-700 ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
};
