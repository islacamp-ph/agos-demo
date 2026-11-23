import { Link } from "react-router-dom";
import { ArrowRight, Wallet, ShieldCheck, Send, Orbit, BarChart3, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const PILLARS = [
  ["Manage", "Track business expenses and financial activity in one place.", Wallet, "Live in MVP", "live"],
  ["Control", "Set budgets, manage teams and approve spending.", ShieldCheck, "Live in MVP · cards simulated", "live"],
  ["Pay", "Organize domestic and international business payment workflows.", Send, "Domestic simulated · Stellar Testnet live", "sim"],
  ["Connect", "Explore blockchain-enabled settlement and verification through Stellar.", Orbit, "Live on Stellar Testnet", "chain"],
  ["Understand", "Gain visibility through financial dashboards and reporting.", BarChart3, "Live in MVP · AI insights planned", "live"],
];
const TONE = { live: "bg-emerald-50 text-emerald-800 border-emerald-200", sim: "bg-amber-50 text-amber-800 border-amber-200", chain: "bg-cyan-50 text-cyan-800 border-cyan-200" };

function FlowLines() {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1200 600" preserveAspectRatio="none" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <path key={i} className="flow-line" d={`M-50 ${380 + i * 26} C 250 ${300 + i * 20}, 450 ${520 - i * 14}, 700 ${400 + i * 10} S 1100 ${300 + i * 22}, 1260 ${360 + i * 18}`}
          fill="none" stroke={i % 2 ? "#7dd3e0" : "#ffffff"} strokeOpacity={0.08 + i * 0.03} strokeWidth="1.2" style={{ animationDelay: `${i * -0.8}s` }} />
      ))}
    </svg>
  );
}

function PreviewCard() {
  const bars = [42, 58, 49, 71, 64, 83];
  return (
    <div className="fade-up relative rounded-2xl border border-white/10 bg-white/[0.06] p-5 shadow-2xl backdrop-blur-xl" style={{ animationDelay: "0.25s" }}>
      <div className="flex items-center justify-between text-xs text-slate-300"><span>Isla Digital Solutions · Overview</span><span className="rounded-full bg-amber-300/15 px-2 py-0.5 text-amber-200">Synthetic demo data</span></div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {[["Recorded spend", "₱1.24M"], ["Pending approvals", "7"], ["Budget used", "68%"]].map(([l, v]) => (
          <div key={l} className="rounded-xl bg-white/[0.06] p-3"><div className="text-[10px] text-slate-400">{l}</div><div className="tnum mt-1 text-lg font-semibold text-white">{v}</div></div>
        ))}
      </div>
      <div className="mt-4 flex h-28 items-end gap-2 rounded-xl bg-white/[0.04] p-3">
        {bars.map((h, i) => <div key={i} className="flex-1 rounded-t bg-gradient-to-t from-cyan-300/40 to-cyan-200/80" style={{ height: `${h}%` }} />)}
      </div>
      <div className="mt-4 flex items-center gap-3 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.07] p-3 text-xs">
        <Orbit className="h-4 w-4 text-cyan-200" />
        <div className="flex-1 text-slate-200">Contractor payment · 25 XLM<div className="font-mono-plex text-[10px] text-slate-400">Testnet ledger confirmation · hash recorded</div></div>
        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div>
      <section className="relative overflow-hidden bg-[hsl(var(--navy-ink))] text-white">
        <div className="grain pointer-events-none absolute inset-0" />
        <FlowLines />
        <div className="relative mx-auto grid max-w-7xl gap-14 px-5 pb-24 pt-20 md:px-8 lg:grid-cols-[1.1fr_0.9fr] lg:pb-32 lg:pt-28">
          <div className="fade-up">
            <div className="eyebrow mb-6 text-cyan-200">A venture of ISLA Ventures Inc. · Philippines</div>
            <h1 className="text-4xl font-semibold leading-[1.02] tracking-tight sm:text-5xl lg:text-6xl" data-testid="hero-headline">
              Business Finance <span className="font-serif-display font-normal italic text-cyan-200">in Motion.</span>
            </h1>
            <p className="mt-7 max-w-xl text-base leading-relaxed text-slate-300 md:text-lg">
              One intelligent platform to manage spending, control payments and connect your business to modern financial infrastructure.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <Button asChild size="lg" className="rounded-full bg-white text-[hsl(var(--navy-ink))] hover:bg-cyan-50" data-testid="hero-demo-btn">
                <Link to="/app">Explore AGOS Demo <ArrowRight className="ml-1 h-4 w-4" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="rounded-full border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white" data-testid="hero-waitlist-btn">
                <Link to="/waitlist">Join the Waitlist</Link>
              </Button>
            </div>
            <p className="mt-8 text-xs text-slate-400">MVP demonstration · synthetic business data · simulated cards · real Stellar Testnet transactions</p>
          </div>
          <PreviewCard />
        </div>
      </section>

      <section id="product" className="mx-auto max-w-7xl px-5 py-24 md:px-8">
        <div className="eyebrow text-[hsl(var(--stellar))]">One platform</div>
        <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-[hsl(var(--navy-ink))] md:text-4xl">Complete control over your business finances.</h2>
        <p className="mt-4 max-w-2xl text-base text-slate-600">Every capability below is labeled honestly: what is live in the MVP, what is simulated, and what is planned.</p>
        <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border bg-slate-200 md:grid-cols-2 lg:grid-cols-5">
          {PILLARS.map(([t, d, Icon, s, tone], i) => (
            <div key={t} className="fade-up flex flex-col bg-white p-7 transition-colors hover:bg-slate-50" style={{ animationDelay: `${i * 0.06}s` }} data-testid={`pillar-${t.toLowerCase()}`}>
              <Icon className="h-5 w-5 text-[hsl(var(--primary))]" />
              <div className="mt-6 text-lg font-semibold text-[hsl(var(--navy-ink))]">{t}</div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-600">{d}</p>
              <span className={`mt-6 w-fit rounded-full border px-2.5 py-1 text-[11px] font-medium ${TONE[tone]}`}>{s}</span>
            </div>
          ))}
        </div>
        <div className="mt-6 text-xs text-slate-500">Planned (not in MVP): regulated domestic payment rails, partner-issued corporate cards, licensed fiat on/off-ramps, AI insights, forecasting and financing.</div>
      </section>

      <section id="technology" className="border-y bg-white">
        <div className="mx-auto grid max-w-7xl gap-14 px-5 py-24 md:px-8 lg:grid-cols-2">
          <div>
            <div className="eyebrow text-[hsl(var(--stellar))]">Technology</div>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[hsl(var(--navy-ink))] md:text-4xl">Settlement you can independently verify.</h2>
            <p className="mt-5 text-base leading-relaxed text-slate-600">
              AGOS uses the Stellar network as a settlement and verification layer for international payment workflows. In this MVP,
              approved payments are signed server-side and submitted as genuine transactions on the Stellar Testnet. Each record stores the
              transaction hash and ledger number, so anyone can verify it on a public explorer.
            </p>
            <p className="mt-4 text-sm leading-relaxed text-slate-500">
              Future cross-border capabilities, including Stellar-issued stablecoins, depend on supported assets, licensed on/off-ramp partners and
              compliance approvals. AGOS is an independent venture; it is not endorsed, funded or approved by the Stellar Development Foundation.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[["Payment settlement", "Approved requests settle as real Testnet XLM transfers with idempotent submission."],
              ["Transaction verification", "Verify any payment against Horizon: hash, ledger, destination and amount."],
              ["Reconciliation", "On-chain references flow into AGOS reconciliation alongside expenses and card records."],
              ["Cross-border, later", "A modular asset registry is ready for partner-supported stablecoins in future phases."]].map(([t, d]) => (
              <div key={t} className="rounded-xl border bg-[#f7f9fb] p-6">
                <div className="text-sm font-semibold text-[hsl(var(--navy-ink))]">{t}</div>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="about" className="mx-auto grid max-w-7xl gap-12 px-5 py-24 md:px-8 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <div className="eyebrow text-[hsl(var(--stellar))]">About AGOS</div>
          <h2 className="mt-3 font-serif-display text-5xl leading-none text-[hsl(var(--navy-ink))]">agos <span className="text-2xl italic text-slate-400">/ˈa.ɡos/ · flow</span></h2>
        </div>
        <div className="space-y-5 text-base leading-relaxed text-slate-600">
          <p>AGOS is a fintech venture being developed under ISLA Ventures Inc., focused on making business financial operations simpler and more accessible for Philippine enterprises.</p>
          <p>Our vision is to make business finance simpler, smarter, more accessible and globally connected, starting with Philippine startups and MSMEs and expanding to Southeast Asia.</p>
          <div className="flex flex-wrap gap-3 pt-3">
            <Button asChild className="rounded-full" data-testid="about-roadmap-btn"><Link to="/roadmap">See the Vision & Roadmap</Link></Button>
            <Button asChild variant="outline" className="rounded-full" data-testid="about-waitlist-btn"><Link to="/waitlist">Join the Waitlist</Link></Button>
          </div>
        </div>
      </section>
    </div>
  );
}
