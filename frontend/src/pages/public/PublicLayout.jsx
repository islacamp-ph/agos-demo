import { Link, NavLink, Outlet } from "react-router-dom";
import { Show } from "@clerk/react";
import { Button } from "@/components/ui/button";
import { Wordmark } from "@/components/agos/ui";

export const CONTACT_EMAIL = "hello@agos.example";

export default function PublicLayout() {
  const link = (to, label, id) => (
    <NavLink to={to} data-testid={id} className={({ isActive }) => `text-sm transition-colors ${isActive ? "text-[hsl(var(--navy-ink))]" : "text-slate-500 hover:text-[hsl(var(--navy-ink))]"}`}>{label}</NavLink>
  );
  return (
    <div className="min-h-screen bg-[#f7f9fb]">
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-[#f7f9fb]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-8 px-5 md:px-8">
          <Link to="/" data-testid="public-home-link"><Wordmark /></Link>
          <nav className="hidden items-center gap-7 md:flex">
            <a href="/#product" className="text-sm text-slate-500 hover:text-[hsl(var(--navy-ink))]" data-testid="nav-product">Product</a>
            <a href="/#technology" className="text-sm text-slate-500 hover:text-[hsl(var(--navy-ink))]" data-testid="nav-technology">Technology</a>
            {link("/roadmap", "Vision & Roadmap", "nav-roadmap")}
            <a href="/#about" className="text-sm text-slate-500 hover:text-[hsl(var(--navy-ink))]" data-testid="nav-about">About</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/roadmap" className="text-sm text-slate-600 md:hidden" data-testid="mobile-nav-roadmap">Roadmap</Link>
            <Link to="/waitlist" className="hidden" data-testid="mobile-nav-waitlist">Waitlist</Link>
            <Show when="signed-out"><Link to="/sign-in" className="hidden text-sm text-slate-600 hover:text-slate-900 sm:block" data-testid="nav-sign-in">Sign in</Link></Show>
            <Button asChild variant="outline" className="hidden rounded-full sm:inline-flex" data-testid="nav-waitlist-btn"><Link to="/waitlist">Join the Waitlist</Link></Button>
            <Button asChild className="rounded-full" data-testid="nav-demo-btn"><Link to="/app">Explore Demo</Link></Button>
          </div>
        </div>
      </header>
      <Outlet />
      <footer className="border-t bg-[hsl(var(--navy-ink))] text-slate-300">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 md:grid-cols-4 md:px-8">
          <div className="md:col-span-2">
            <Wordmark light />
            <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
              AGOS is a fintech venture in development under ISLA Ventures Inc. AGOS is not a bank, lender, payment institution,
              electronic money issuer or virtual asset service provider. Live financial services will require separate regulatory and partner assessment.
            </p>
          </div>
          <div className="space-y-2 text-sm">
            <div className="eyebrow text-slate-500">Explore</div>
            <Link to="/roadmap" className="block hover:text-white">Vision & Roadmap</Link>
            <Link to="/waitlist" className="block hover:text-white">Waitlist</Link>
            <Link to="/privacy" className="block hover:text-white" data-testid="footer-privacy">Privacy notice</Link>
          </div>
          <div className="space-y-2 text-sm">
            <div className="eyebrow text-slate-500">Contact</div>
            <a href={`mailto:${CONTACT_EMAIL}`} className="block hover:text-white" data-testid="footer-contact-email">{CONTACT_EMAIL}</a>
            <div className="text-slate-500">Metro Manila, Philippines</div>
          </div>
        </div>
        <div className="border-t border-white/10 py-5 text-center text-xs text-slate-500">© {new Date().getFullYear()} ISLA Ventures Inc. · AGOS — Business Finance in Motion</div>
      </footer>
    </div>
  );
}
