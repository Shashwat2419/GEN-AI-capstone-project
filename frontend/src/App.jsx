import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { DEFAULT_MODELS, PROVIDERS, defaultPrefs } from "./constants.js";
import Preferences from "./components/Preferences.jsx";
import Recommender from "./components/Recommender.jsx";
import Itinerary from "./components/Itinerary.jsx";
import Customize from "./components/Customize.jsx";
import Trips from "./components/Trips.jsx";

const TABS = ["🌍 Destination Recommender", "🗺️ Day-by-Day Itinerary", "🎨 Vibe Customization", "🧳 Trips & PDF Export"];

export default function App() {
  const [prefs, setPrefs] = useState(defaultPrefs());
  const [provider, setProvider] = useState("Demo");
  const [apiKey, setApiKey] = useState(""); // kept in memory only - never stored
  const [model, setModel] = useState("");
  const [tab, setTab] = useState(0);
  const [recs, setRecs] = useState(null);
  const [itinerary, setItinerary] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [undo, setUndo] = useState([]);
  const [trips, setTrips] = useState([]);
  const [tripId, setTripId] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [health, setHealth] = useState(null);

  const llm = { provider, api_key: apiKey, model: model || DEFAULT_MODELS[provider] || "" };
  const payloadPrefs = { ...prefs, days: Number(prefs.days) };
  const demo = provider === "Demo" || (!apiKey && !(health && health.server_ai_keys && health.server_ai_keys[provider]));

  const toast = (msg) => { setNotice(msg); setTimeout(() => setNotice(""), 4000); };

  // Wake the server (free hosting sleeps) and learn which storage it uses.
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "offline" }));
  }, []);

  const refreshTrips = useCallback(async () => {
    try { setTrips((await api.listTrips()).trips); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { if (health && health.status === "ok") refreshTrips(); }, [health, refreshTrips]);

  async function run(label, fn) {
    setBusy(label);
    setError("");
    try { return await fn(); } catch (e) { setError(e.message); return undefined; } finally { setBusy(""); }
  }
  const apply = (res) => { setItinerary(res.itinerary); setAnalytics(res.analytics); };

  const onRecommend = () => run("Matching destinations...", async () => setRecs((await api.recommend(payloadPrefs, llm)).recommendations));
  const onPick = (city) => { setPrefs({ ...prefs, destination: city }); setTab(1); toast(`${city} selected - press Generate.`); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const onGenerate = () => run("Clustering attractions and building your days...", async () => {
    apply(await api.createItinerary(payloadPrefs, llm));
    setUndo([]); setTripId(null);
  });

  const pushUndo = () => setUndo((u) => [...u.slice(-9), { itinerary, analytics }]);
  const onSwap = (di, slot, ii, text) => run("Finding a better fit...", async () => {
    const res = await api.swap(itinerary, di, slot, ii, text, llm);
    pushUndo(); apply(res); toast(`Swapped ${res.old.name} → ${res.new.name}`);
  });
  const onRegenerate = (di, text) => run(`Rebuilding Day ${di + 1}...`, async () => {
    const res = await api.regenerateDay(itinerary, di, text, llm);
    pushUndo(); apply(res); toast(`Day ${di + 1} regenerated - other days untouched.`);
  });
  const onUndo = () => {
    const last = undo[undo.length - 1];
    if (!last) return;
    setUndo(undo.slice(0, -1)); apply(last); toast("Reverted the last change.");
  };

  const onSave = (name, update) => run("Saving trip...", async () => {
    const res = await api.saveTrip(name, itinerary, update ? tripId : null);
    setTripId(res.id); await refreshTrips(); toast("Trip saved.");
  });
  const onLoad = (id) => run("Loading trip...", async () => {
    apply(await api.loadTrip(id)); setTripId(id); setUndo([]); setTab(1); toast("Trip loaded.");
  });
  const onDelete = (id) => run("Deleting...", async () => {
    await api.deleteTrip(id); if (tripId === id) setTripId(null); await refreshTrips(); toast("Trip deleted.");
  });

  // exchange-rate edits: update the itinerary locally, then let the server recompute totals
  const applyFx = (changes) => run("Updating totals...", async () => {
    const next = { ...itinerary, fx: { ...itinerary.fx, ...changes } };
    const res = await api.summary(next);
    apply({ itinerary: next, analytics: res.analytics });
  });

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>⚙️ AI Settings</h2>
        <label>AI provider
          <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(""); }}>
            {PROVIDERS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        {provider === "Demo" ? (
          <p className="side-note">Demo mode has built-in data for Jaipur, Goa, Manali, Paris and Bangkok. Choose Gemini or Groq and paste a key to plan any destination.</p>
        ) : (
          <>
            <label>{provider} API key
              <input type="password" autoComplete="off" value={apiKey} placeholder="paste key" onChange={(e) => setApiKey(e.target.value)} />
            </label>
            <label>Model
              <input value={model} placeholder={DEFAULT_MODELS[provider]} onChange={(e) => setModel(e.target.value)} />
            </label>
            <p className="side-note">{demo ? "No key yet - running in demo mode." : `${provider} connected. Your key is sent only with your requests and never stored.`}</p>
          </>
        )}
        <p className="side-note">
          Server: {!health ? "connecting..." : health.status === "ok" ? `online · storage: ${health.storage}` : "offline (may be waking up)"}
        </p>
        {itinerary && (
          <>
            <h2>💱 Exchange rates</h2>
            <p className="side-note">Approximate - edit to match today&apos;s rate.</p>
            <FxInputs fx={itinerary.fx} onApply={applyFx} />
          </>
        )}
      </aside>

      <main className="main">
        <header className="hero">
          <h1>🧭 Personalized Travel Itinerary Planner</h1>
          <p>Day-by-day plans that cluster nearby attractions, so you spend your trip exploring - not commuting.</p>
        </header>
        {notice && <div className="toast">{notice}</div>}
        {error && <div className="error" role="alert">{error} <button onClick={() => setError("")}>×</button></div>}
        {busy && <div className="busy"><span className="spin" /> {busy}</div>}

        <Preferences prefs={prefs} setPrefs={setPrefs} demo={demo} />

        <nav className="tabs">
          {TABS.map((t, i) => <button key={t} className={"tab" + (tab === i ? " active" : "")} onClick={() => setTab(i)}>{t}</button>)}
        </nav>
        <section className="tabpanel">
          {tab === 0 && <Recommender recs={recs} onRecommend={onRecommend} onPick={onPick} busy={busy} />}
          {tab === 1 && <Itinerary itinerary={itinerary} analytics={analytics} onGenerate={onGenerate} busy={busy} />}
          {tab === 2 && <Customize itinerary={itinerary} analytics={analytics} onSwap={onSwap} onRegenerate={onRegenerate} onUndo={onUndo} canUndo={undo.length > 0} busy={busy} />}
          {tab === 3 && (
            <Trips itinerary={itinerary} trips={trips} tripId={tripId} busy={busy} onSave={onSave} onLoad={onLoad}
              onDelete={onDelete} onRefresh={refreshTrips}
              onPdf={() => run("Building PDF...", () => api.downloadPdf(itinerary))}
              onTripPdf={(id, name) => run("Building PDF...", () => api.downloadTripPdf(id, name))} />
          )}
        </section>
      </main>
    </div>
  );
}

function FxInputs({ fx, onApply }) {
  const [local, setLocal] = useState(fx.per_usd);
  const [inr, setInr] = useState(fx.inr_per_usd);
  useEffect(() => { setLocal(fx.per_usd); setInr(fx.inr_per_usd); }, [fx.per_usd, fx.inr_per_usd, fx.local]);
  const ok = Number(local) > 0 && Number(inr) > 0;
  return (
    <>
      {fx.local !== "USD" && (
        <label>1 USD = ? {fx.local}
          <input type="number" step="any" min="0" value={local} onChange={(e) => setLocal(e.target.value)} />
        </label>
      )}
      <label>1 USD = ? INR
        <input type="number" step="any" min="0" value={inr} onChange={(e) => setInr(e.target.value)} />
      </label>
      <button className="btn small" disabled={!ok} onClick={() => onApply({ per_usd: Number(local), inr_per_usd: Number(inr) })}>Apply rates</button>
    </>
  );
}
