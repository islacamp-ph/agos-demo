const phpFmt = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", minimumFractionDigits: 2 });
const usdFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const compactFmt = new Intl.NumberFormat("en-PH", { notation: "compact", maximumFractionDigits: 1 });

export function money(amount, currency = "PHP") {
  const n = Number(amount || 0);
  if (currency === "USD") return usdFmt.format(n);
  if (currency === "XLM") return `${n.toLocaleString("en-US", { maximumFractionDigits: 7 })} XLM`;
  return phpFmt.format(n);
}

export const php = (n) => money(n, "PHP");
export const compact = (n) => `₱${compactFmt.format(Number(n || 0))}`;

export function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s.length === 10 ? `${s}T00:00:00` : s);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(s) {
  if (!s) return "—";
  return new Date(s).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const monthLabel = (m) => {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1, 1).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
};

export const shortKey = (k, n = 6) => (k ? `${k.slice(0, n)}…${k.slice(-n)}` : "—");
export const today = () => new Date().toISOString().slice(0, 10);
export const thisMonth = () => new Date().toISOString().slice(0, 7);

export const ROLE_LABEL = { owner: "Owner / Administrator", finance_manager: "Finance Manager", employee: "Employee" };
export const CATEGORIES = ["Software & SaaS", "Cloud & Hosting", "Advertising", "Travel", "Transportation", "Meals & Entertainment",
  "Office Supplies", "Utilities & Internet", "Professional Services", "Logistics", "Events", "Other"];
export const BUSINESS_CATEGORIES = ["Startup", "MSME", "Digital Agency", "Service Business", "Freelancer (registered business)", "Ecommerce", "Other"];
export const newKey = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
