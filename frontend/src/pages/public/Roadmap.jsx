import { Link } from "react-router-dom";
import { Check, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";

export const PHASES = [
  { n: 1, title: "AGOS Finance OS", when: "MVP Development · Initial Stage", status: "In development — MVP available", current: true,
    items: ["Business dashboard", "Expense management", "Budgets", "Approval workflows", "Team management", "Simulated corporate cards", "Stellar Testnet payment settlement", "Transaction reconciliation"],
    objective: "Validate demand for unified business finance software." },
  { n: 2, title: "Connected Business Payments", when: "Target: 3–6 months", status: "Planned",
    items: ["Domestic payment integrations", "Regulated financial partner connections", "Business payment orchestration", "Stablecoin-enabled cross-border pilots", "Enhanced reconciliation"],
    objective: "Connect business finance management with regulated payment infrastructure." },
  { n: 3, title: "Corporate Spending Platform", when: "Target: 6–12 months", status: "Planned · subject to partnerships",
    items: ["Authorized card-issuing partnerships", "Visa/Mastercard-enabled corporate card programs (subject to approved partnerships)", "Virtual employee cards", "Card transaction reconciliation", "Advanced financial controls"],
    objective: "Expand AGOS into an integrated corporate spending platform." },
  { n: 4, title: "Intelligent Business Finance", when: "Target: 12–24 months", status: "Planned",
    items: ["AI-powered financial insights", "Cash flow forecasting", "Automated financial workflows", "Partner-enabled business financing", "Regional business payments", "Southeast Asian expansion"],
    objective: "Establish AGOS as a broader financial operating system for growing businesses." },
];

export default function Roadmap({ inApp = false }) {
  return (
    <div className={inApp ? "" : "mx-auto max-w-7xl px-5 py-20 md:px-8"}>
      <div className="eyebrow text-[hsl(var(--stellar))]">Vision & Roadmap</div>
      <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-[hsl(var(--navy-ink))] sm:text-5xl" data-testid="roadmap-title">
        Building the financial operating system for <span className="font-serif-display font-normal italic">Philippine</span> business.
      </h1>
      <p className="mt-5 max-w-2xl text-base text-slate-600">Make business finance simpler, smarter, more accessible and globally connected — starting in the Philippines, expanding to Southeast Asia.</p>

      <div className="relative mt-16 grid gap-6 lg:grid-cols-4">
        <div className="absolute left-0 right-0 top-[22px] hidden h-px bg-gradient-to-r from-[hsl(var(--primary))] via-slate-300 to-slate-200 lg:block" />
        {PHASES.map((p) => (
          <div key={p.n} className="relative" data-testid={`roadmap-phase-${p.n}`}>
            <div className={`relative z-10 flex h-11 w-11 items-center justify-center rounded-full border-2 text-sm font-semibold ${p.current ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-white" : "border-slate-300 bg-white text-slate-500"}`}>{p.n}</div>
            <div className={`mt-5 rounded-2xl border p-6 ${p.current ? "border-[hsl(var(--primary))]/30 bg-white shadow-md" : "bg-white/70"}`}>
              <div className="text-xs text-slate-500">{p.when}</div>
              <div className="mt-1 text-lg font-semibold text-[hsl(var(--navy-ink))]">Phase {p.n} — {p.title}</div>
              <span className={`mt-3 inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${p.current ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-600"}`}>{p.status}</span>
              <ul className="mt-5 space-y-2">
                {p.items.map((i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-600">
                    {p.current ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <Circle className="mt-1 h-3 w-3 shrink-0 text-slate-300" />}{i}
                  </li>
                ))}
              </ul>
              <div className="mt-5 border-t pt-4 text-xs leading-relaxed text-slate-500"><span className="font-medium text-slate-700">Objective:</span> {p.objective}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 rounded-xl border border-amber-200 bg-amber-50/60 p-5 text-sm leading-relaxed text-amber-900" data-testid="roadmap-disclaimer">
        Timelines are strategic targets, not commitments. Domestic payments, card programs, stablecoin services, financing and any other regulated
        financial services depend on licensing, regulatory assessment and approved partnerships, and may change or not become available. AGOS is not a bank,
        lender, payment institution, electronic money issuer or virtual asset service provider.
      </div>
      {!inApp && (
        <div className="mt-10 flex gap-3">
          <Button asChild className="rounded-full" data-testid="roadmap-demo-btn"><Link to="/app">Explore AGOS Demo</Link></Button>
          <Button asChild variant="outline" className="rounded-full" data-testid="roadmap-waitlist-btn"><Link to="/waitlist">Join the Waitlist</Link></Button>
        </div>
      )}
    </div>
  );
}
