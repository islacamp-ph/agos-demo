# AGOS — PRD

## Original problem statement
"AGOS — MASTER EMERGENT BUILD PROMPT — Business Finance in Motion, MVP Version 1.0, ISLA Ventures Inc." Build AGOS, a full-stack business financial operating platform for Philippine startups and MSMEs: public website (landing, product sections with Live/Simulated/Planned labels, About, Technology/Stellar, Vision & Roadmap with 4 phases and disclaimers, waitlist with consent + admin view); secure auth and business workspaces with onboarding (name, category, industry, location, business email, admin name, team size, currency PHP/USD); roles Owner/Administrator, Finance Manager, Employee with server-side authorization and workspace isolation; dashboard from stored records; expense management (Draft, Submitted, Pending Approval, Approved, Rejected, Recorded as Paid, actor + timestamp, receipts, search/filter, CSV); budgets and spending controls; simulated corporate cards ("Demo Card — Not Valid for Payment", no Visa/Mastercard branding); business payments (domestic demo-only records, international via genuine Stellar Testnet with approval, explicit confirmation, signing, hash, ledger, verification, idempotency, failure/retry); stablecoin-ready asset registry; reconciliation; reports with charts, date filters, CSV; security (audit logs, validation, secure uploads, env secrets, rate limiting); demo business Isla Digital Solutions (Metro Manila, PHP) with owner, finance manager and three employees. No pricing/billing. Do not claim AGOS is a bank/payment institution/EMI/VASP.

User choices: Emergent-managed sign-in (Google + email/password); each signed-in user gets a private pre-populated Isla Digital Solutions demo workspace and can also create an empty real workspace; demo workspaces isolated; synthetic data and cards labeled simulated; Stellar Testnet records must be genuine and distinct from sample data; Emergent object storage for receipts. Platform admins: lumbresnelson@gmail.com, barschia@gmail.com, chris.icalla@gmail.com — kept private; separate ISLA Ventures Super Admin and AGOS Platform Admin roles; public uses a separate contact email.

## Architecture
- Backend FastAPI (/app/backend): server.py (app, indexes, rate limit, safe errors), core.py (db, Clerk user → platform role, workspace context + role deps, X-Act-As personas for demo owners), routes_workspace.py, routes_finance.py (expenses, receipts, budgets, approvals, cards), routes_payments.py (payments + Stellar), routes_insights.py (dashboard, reports, reconciliation, CSV), routes_public.py (waitlist, admin), stellar_service.py (stellar-sdk 17, Horizon testnet, Fernet-encrypted secrets, asset registry), storage.py (Emergent object storage), seed.py (demo data).
- Frontend React + Clerk (@clerk/react), shadcn, recharts. Public pages under src/pages/public, app under src/pages/app, shell in components/agos.
- MongoDB collections: users, workspaces, members, expenses, budgets, cards, card_transactions, payments (stellar sub-doc), stellar_accounts, stellar_recipients, files, audit_logs, waitlist.

## Implemented (2026-11-23, iteration 5)
- Pitch summary PDF (reportlab, one A4 page): GET /api/payments/{id}/pitch-summary?expense_id&duration — re-verifies on Horizon, shows snapshot KPIs (synthetic), timeline, full transaction details, QR + explorer link, disclaimers. Download button at tour end and in Payments drawer for confirmed payments.

## Implemented (2026-11-23, iteration 4)
- Tour share link: /tour (protected; signed-out visitors go to sign-in and return) finds or creates the visitor's private demo, clears personas and opens the investor tour automatically. Copy-link buttons in header and tour panel; hero link on landing page; mobile tour icon.

## Implemented (2026-11-23, iteration 2)
- Wallet Connect: Freighter (@stellar/freighter-api 6.0.1). Ownership proven by signing a non-submittable challenge tx; workspace account mode "wallet" (no secret stored). Payments: prepare (unsigned XDR, status awaiting_signature) → wallet signs → submit-signed (hash + signature verified) → confirmed; cancel-signature; owner disconnect archives the account. Managed mode unchanged.
- Investor tour: 6-step guided panel (demo workspaces, real owner) — expense submit → approve → budgets → Stellar payment → settle → verify with explorer link and timer.
- Tested: iteration_2 backend 8/8; wallet path tested with local keypairs (real Freighter extension not testable in automation).

## Implemented (2026-11-23)
- All modules above; real Stellar Testnet payments verified (confirmed ledger, idempotent resubmit, Verify vs Horizon, startup refresh of pending tx).
- Testing iteration 1: backend 35/35 core + edge findings fixed (FM limit 100 XLM for Stellar payments, card budget_id validation, invited-owner removal, submit requires approval), frontend core flows pass; admin reachable without a workspace; reports nav hidden for employees.

## Assumptions / placeholders
- SUPER_ADMIN_EMAIL = lumbresnelson@gmail.com; PLATFORM_ADMIN_EMAIL = barschia@gmail.com, chris.icalla@gmail.com (assumed split).
- Public contact email placeholder: hello@agos.example.
- Fixed demo FX rate USD→PHP 58.00.

## Backlog
- P1: shadcn date pickers instead of native inputs; empty-state charts for new workspaces; public mobile menu.
- P1: connect an existing Stellar account via wallet signing (Freighter); Testnet demo asset.
- P2: regulated domestic payment provider, card-issuer integration, AI insights, forecasting.

## Next tasks
- User review of demo; decide on Phase 2 integrations.
