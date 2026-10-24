import { fmt } from "../util.js";
import DayView from "./DayView.jsx";

export default function Itinerary({ itinerary, analytics, onGenerate, busy }) {
  return (
    <div>
      <button className="btn" disabled={!!busy} onClick={onGenerate}>🗺️ Generate optimized itinerary</button>
      {!itinerary && <p className="info">Set your preferences, then press <b>Generate</b>. Use Tab 1 if you have no destination yet.</p>}
      {itinerary && analytics && <Result itinerary={itinerary} a={analytics} />}
    </div>
  );
}

function Result({ itinerary, a }) {
  const { prefs, fx } = itinerary;
  const used = a.target_usd ? a.total_usd / a.target_usd : 0;
  const maxCum = Math.max(...a.rows.map((r) => r["Cumulative (USD)"]), 1);
  return (
    <div className="mt">
      <h2>{itinerary.destination}, {itinerary.country}</h2>
      <p>{itinerary.summary}</p>
      {(itinerary.warnings || []).map((w) => <p className="warn" key={w}>{w}</p>)}
      <div className="grid g4">
        <div className="metric"><span>Days / travellers</span><b>{itinerary.days.length} / {prefs.party_size}</b></div>
        <div className="metric"><span>Estimated total</span><b>{fx.local} {fmt(a.total_local)}</b><small>USD {fmt(a.total_usd)} | INR {fmt(a.total_inr)}</small></div>
        <div className="metric"><span>{prefs.budget} budget target</span><b>USD {fmt(a.target_usd)}</b><small>INR {fmt(a.target_inr)}</small></div>
        <div className="metric"><span>Total transit</span><b>{fmt(a.transit_km)} km</b><small>clustered by area</small></div>
      </div>
      <div className="progress"><div style={{ width: Math.min(100, used * 100) + "%" }} className={used > 1 ? "over" : ""} /></div>
      <p className="meta">Budget used: {Math.round(used * 100)}% of target{used > 1 ? " - over budget" : ""}</p>

      {itinerary.days.map((day, i) => (
        <details key={day.day} open={i === 0} className="day">
          <summary>Day {day.day} - {day.theme}</summary>
          <DayView day={day} itinerary={itinerary} stats={a.days[i]} />
        </details>
      ))}

      <h4>📈 Running budget tracker</h4>
      <div className="tablewrap">
        <table>
          <thead><tr><th>Day</th><th>Day cost ({fx.local})</th><th>Cumulative ({fx.local})</th><th>USD</th><th>INR</th><th></th></tr></thead>
          <tbody>
            {a.rows.map((r) => (
              <tr key={r.Day}>
                <td>{r.Day}</td>
                <td>{fmt(r[`Day cost (${fx.local})`])}</td>
                <td>{fmt(r[`Cumulative (${fx.local})`])}</td>
                <td>{fmt(r["Cumulative (USD)"])}</td>
                <td>{fmt(r["Cumulative (INR)"])}</td>
                <td className="barcell"><div className="bar" style={{ width: (r["Cumulative (USD)"] / maxCum) * 100 + "%" }} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {itinerary.tips && itinerary.tips.length > 0 && (
        <>
          <h4>💡 Local tips</h4>
          <ul>{itinerary.tips.map((t) => <li key={t}>{t}</li>)}</ul>
        </>
      )}
      <p className="meta">Mode: {itinerary.mode}. Costs are estimates per traveller multiplied by party size; confirm opening hours and prices before visiting.</p>
    </div>
  );
}
