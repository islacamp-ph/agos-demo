import { Link } from "react-router-dom";
import { Wordmark } from "@/components/agos/ui";

export default function AuthPage({ children }) {
  return (
    <div className="flex min-h-screen">
      <div className="relative hidden w-[44%] flex-col justify-between overflow-hidden bg-[hsl(var(--navy-ink))] p-12 text-white lg:flex">
        <div className="grain pointer-events-none absolute inset-0" />
        <Link to="/" className="relative"><Wordmark light /></Link>
        <div className="relative">
          <h2 className="font-serif-display text-5xl leading-[1.05]">Business finance,<br /><em className="text-cyan-200">in motion.</em></h2>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-slate-300">Sign in to explore your private Isla Digital Solutions demo workspace, or set up your own business.</p>
        </div>
        <div className="relative text-xs text-slate-400">Demo environment · synthetic data · Stellar Testnet</div>
      </div>
      <div className="flex flex-1 items-center justify-center bg-[#f7f9fb] px-4 py-10">{children}</div>
    </div>
  );
}
