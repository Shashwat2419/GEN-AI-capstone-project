import { useEffect, useState } from "react";
import { formatDate } from "../util.js";

export default function Trips({ itinerary, trips, tripId, onSave, onLoad, onDelete, onPdf, onTripPdf, onRefresh, busy }) {
  const [name, setName] = useState("");
  useEffect(() => {
    if (itinerary) setName(`${itinerary.destination} - ${itinerary.days.length} days`);
  }, [itinerary && itinerary.destination, itinerary && itinerary.days.length]); // eslint-disable-line

  return (
    <div>
      <h4>💾 Save the current plan</h4>
      {itinerary ? (
        <>
          <label>Trip name<input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></label>
          <div className="row mt">
            <button className="btn" disabled={!!busy || !name.trim()} onClick={() => onSave(name.trim(), false)}>Save as new trip</button>
            {tripId && <button className="btn" disabled={!!busy} onClick={() => onSave(name.trim(), true)}>Update saved trip</button>}
            <button className="btn accent" disabled={!!busy} onClick={onPdf}>📄 Export offline PDF guide</button>
          </div>
        </>
      ) : (
        <p className="info">No active itinerary yet - generate one in Tab 2.</p>
      )}

      <div className="row between mt">
        <h4>🗂️ Trip history</h4>
        <button className="btn ghost small" onClick={onRefresh}>Refresh</button>
      </div>
      {trips.length === 0 && <p className="meta">No saved trips yet.</p>}
      {trips.map((t) => (
        <div className="card row between" key={t.id}>
          <div>
            <b>{t.name}</b>
            <div className="meta">{t.destination} · {t.num_days} days · updated {formatDate(t.updated_at)}</div>
          </div>
          <div className="row">
            <button className="btn small" disabled={!!busy} onClick={() => onLoad(t.id)}>Load</button>
            <button className="btn small accent" disabled={!!busy} onClick={() => onTripPdf(t.id, t.name)}>PDF</button>
            <button className="btn small ghost" disabled={!!busy} onClick={() => onDelete(t.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}
