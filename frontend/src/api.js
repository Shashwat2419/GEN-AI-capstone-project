const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

// Anonymous browser id so each visitor only sees their own saved trips.
export function clientId() {
  try {
    let id = localStorage.getItem("tp_client_id");
    if (!id) {
      id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2));
      localStorage.setItem("tp_client_id", id);
    }
    return id;
  } catch {
    return "anon-session-" + Math.random().toString(36).slice(2, 12);
  }
}
const CID = clientId();

function errorText(data, status) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d[0].msg ? `${d[0].msg} (${(d[0].loc || []).slice(1).join(".")})` : "Invalid request.";
  return `Request failed (${status}).`;
}

async function request(path, { method = "GET", body, blob = false } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { "Content-Type": "application/json", "X-Client-Id": CID },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    throw new Error(
      e.name === "AbortError"
        ? "The server took too long to respond. Please try again."
        : "Cannot reach the server. If it was idle, it may take about a minute to wake up - try again shortly."
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { /* not json */ }
    throw new Error(errorText(data, res.status));
  }
  return blob ? res.blob() : res.json();
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const api = {
  health: () => request("/health"),
  recommend: (prefs, llm) => request("/api/recommend", { method: "POST", body: { prefs, llm } }),
  createItinerary: (prefs, llm) => request("/api/itinerary", { method: "POST", body: { prefs, llm } }),
  summary: (itinerary) => request("/api/summary", { method: "POST", body: { itinerary } }),
  swap: (itinerary, day_index, slot, item_index, instruction, llm) =>
    request("/api/swap", { method: "POST", body: { itinerary, day_index, slot, item_index, instruction, llm } }),
  regenerateDay: (itinerary, day_index, instruction, llm) =>
    request("/api/regenerate-day", { method: "POST", body: { itinerary, day_index, instruction, llm } }),
  listTrips: () => request("/api/trips"),
  saveTrip: (name, itinerary, trip_id) => request("/api/trips", { method: "POST", body: { name, itinerary, trip_id } }),
  loadTrip: (id) => request(`/api/trips/${id}`),
  deleteTrip: (id) => request(`/api/trips/${id}`, { method: "DELETE" }),
  async downloadPdf(itinerary) {
    const blob = await request("/api/pdf", { method: "POST", body: { itinerary }, blob: true });
    saveBlob(blob, `${itinerary.destination.replace(/\W+/g, "_")}_itinerary.pdf`);
  },
  async downloadTripPdf(id, name) {
    const blob = await request(`/api/trips/${id}/pdf`, { blob: true });
    saveBlob(blob, `${(name || "trip").replace(/\W+/g, "_")}_itinerary.pdf`);
  },
};
