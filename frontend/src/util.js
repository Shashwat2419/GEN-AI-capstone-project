export function fmt(x) {
  const n = Number(x) || 0;
  return Math.abs(n) >= 100
    ? n.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : n.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

export function convert(amountLocal, fx) {
  const usd = fx.per_usd ? amountLocal / fx.per_usd : 0;
  return { local: amountLocal, usd, inr: usd * fx.inr_per_usd };
}

export function moneyStr(amountLocal, fx) {
  if (amountLocal <= 0) return "Free";
  const m = convert(amountLocal, fx);
  return `${fx.local} ${fmt(m.local)}  |  USD ${fmt(m.usd)}  |  INR ${fmt(m.inr)}`;
}

export function allItems(day) {
  return day.slots.flatMap((s) => s.items);
}

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}
