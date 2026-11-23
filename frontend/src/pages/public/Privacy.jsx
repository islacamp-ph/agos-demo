import { CONTACT_EMAIL } from "@/pages/public/PublicLayout";

export default function Privacy() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-20 md:px-8" data-testid="privacy-page">
      <h1 className="text-4xl font-semibold tracking-tight text-[hsl(var(--navy-ink))]">Privacy notice</h1>
      <div className="mt-8 space-y-5 text-sm leading-relaxed text-slate-600">
        <p>This notice covers the AGOS MVP demonstration operated by ISLA Ventures Inc. It is a summary for the demo and will be replaced by a full policy before any live service.</p>
        <p><b>What we collect.</b> Waitlist details you submit (name, business name, business email, category and challenge), and account information from sign-in. Demo workspaces contain synthetic business data.</p>
        <p><b>What we do not collect.</b> Banking credentials, government IDs or real customer funds. Please do not upload sensitive documents.</p>
        <p><b>How we use it.</b> To contact you about AGOS pilots and to operate the demo. Waitlist data is visible only to authorized ISLA Ventures / AGOS platform administrators.</p>
        <p><b>Your choices.</b> You may request access or deletion by writing to {CONTACT_EMAIL}. We aim to align with the Philippine Data Privacy Act of 2012.</p>
      </div>
    </div>
  );
}
