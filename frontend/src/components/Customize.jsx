import { useState } from "react";
import { SWAP_SUGGESTIONS } from "../constants.js";
import DayView from "./DayView.jsx";

export default function Customize({ itinerary, analytics, onSwap, onRegenerate, onUndo, canUndo, busy }) {
  const [dayIdx, setDayIdx] = useState(0);
  const [slotName, setSlotName] = useState("");
  const [itemIdx, setItemIdx] = useState(0);
  const [text, setText] = useState("");

  if (!itinerary) return <p className="info">Generate an itinerary first (Tab 2), then come back to customize it.</p>;

  const di = Math.min(dayIdx, itinerary.days.length - 1);
  const day = itinerary.days[di];
  const slot = day.slots.find((s) => s.slot === slotName) || day.slots[0];
  const ii = Math.min(itemIdx, slot.items.length - 1);

  return (
    <div>
      <h4>Change one slot - or rebuild one day - without touching the rest of your plan</h4>
      <div className="grid g3">
        <label>Day
          <select value={di} onChange={(e) => { setDayIdx(Number(e.target.value)); setSlotName(""); setItemIdx(0); }}>
            {itinerary.days.map((d, i) => <option key={d.day} value={i}>Day {d.day} - {d.theme}</option>)}
          </select>
        </label>
        <label>Time slot
          <select value={slot.slot} onChange={(e) => { setSlotName(e.target.value); setItemIdx(0); }}>
            {day.slots.map((s) => <option key={s.slot}>{s.slot}</option>)}
          </select>
        </label>
        <label>Activity
          <select value={ii} onChange={(e) => setItemIdx(Number(e.target.value))}>
            {slot.items.map((it, i) => <option key={it.name} value={i}>{it.name}</option>)}
          </select>
        </label>
      </div>
      <span className="lbl">Quick vibes</span>
      <div className="chips">
        {SWAP_SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => setText(s)}>{s}</button>)}
      </div>
      <label>Or describe what you want
        <input value={text} maxLength={300} placeholder="e.g. Swap museum for outdoor market" onChange={(e) => setText(e.target.value)} />
      </label>
      <div className="row mt">
        <button className="btn" disabled={!!busy} onClick={() => onSwap(di, slot.slot, ii, text)}>🔄 Swap this activity</button>
        <button className="btn" disabled={!!busy} onClick={() => onRegenerate(di, text)}>♻️ Regenerate whole day</button>
        <button className="btn ghost" disabled={!canUndo || !!busy} onClick={onUndo}>↩️ Undo last change</button>
      </div>
      <hr />
      <h4>Current plan for Day {day.day}</h4>
      <DayView day={day} itinerary={itinerary} stats={analytics && analytics.days[di]} />
    </div>
  );
}
