import { BUDGETS, DIETS, INTERESTS, MAX_DAYS, PACES, PARTIES, VIBES, DEMO_CITIES } from "../constants.js";

export default function Preferences({ prefs, setPrefs, demo }) {
  const set = (k, v) => setPrefs({ ...prefs, [k]: v });
  const toggleInterest = (i) =>
    set("interests", prefs.interests.includes(i) ? prefs.interests.filter((x) => x !== i) : [...prefs.interests, i]);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <section className="panel">
      <h3>🎒 Trip preferences</h3>
      <div className="grid g3">
        <label>
          Destination (leave blank if undecided)
          <input
            value={prefs.destination}
            maxLength={80}
            placeholder={demo ? "Jaipur, Goa, Manali, Paris or Bangkok" : "e.g. Tokyo, Lisbon, Jaipur..."}
            onChange={(e) => set("destination", e.target.value)}
            list="demo-cities"
          />
          <datalist id="demo-cities">{DEMO_CITIES.map((c) => <option key={c} value={c} />)}</datalist>
        </label>
        <label>
          Open-ended vibe
          <select value={prefs.vibe} onChange={(e) => set("vibe", e.target.value)}>
            {VIBES.map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <label>
          Trip duration: <b>{prefs.days}</b> day{prefs.days > 1 ? "s" : ""}
          <input type="range" min="1" max={MAX_DAYS} value={prefs.days} onChange={(e) => set("days", Number(e.target.value))} />
        </label>
      </div>
      <div className="grid g4">
        <label>
          Travel start date
          <input type="date" min={today} value={prefs.start_date} onChange={(e) => set("start_date", e.target.value)} />
        </label>
        <label>
          Budget level
          <select value={prefs.budget} onChange={(e) => set("budget", e.target.value)}>
            {BUDGETS.map((b) => <option key={b}>{b}</option>)}
          </select>
        </label>
        <label>
          Travel party
          <select value={prefs.party} onChange={(e) => set("party", e.target.value)}>
            {Object.keys(PARTIES).map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label>
          Pace
          <select value={prefs.pace} onChange={(e) => set("pace", e.target.value)}>
            {PACES.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
      </div>
      <div className="grid g2">
        <div>
          <span className="lbl">Interests</span>
          <div className="chips">
            {INTERESTS.map((i) => (
              <button type="button" key={i} className={"chip" + (prefs.interests.includes(i) ? " on" : "")} onClick={() => toggleInterest(i)}>
                {i}
              </button>
            ))}
          </div>
        </div>
        <label>
          Dietary needs
          <select value={prefs.diet} onChange={(e) => set("diet", e.target.value)}>
            {DIETS.map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
      </div>
    </section>
  );
}
