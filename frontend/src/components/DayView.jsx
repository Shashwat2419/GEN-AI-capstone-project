import { SLOT_ICONS } from "../constants.js";
import { allItems, fmt, moneyStr } from "../util.js";
import MapView from "./MapView.jsx";

export function ActivityCard({ item, fx, partySize }) {
  return (
    <div className="act">
      <b>{item.name}</b> <span className="meta">- {item.area}</span>
      <div className="meta">{item.description}</div>
      <div>{item.tags.slice(0, 4).map((t) => <span className="badge" key={t}>{t}</span>)}</div>
      <div className="cost">
        {moneyStr(item.cost_local * partySize, fx)}{" "}
        <span className="meta">({partySize} traveller{partySize === 1 ? "" : "s"}, ~{fmt(item.duration_hrs)} h)</span>
      </div>
    </div>
  );
}

export default function DayView({ day, itinerary, stats }) {
  const { fx, prefs } = itinerary;
  const pts = allItems(day);
  return (
    <div>
      <p className="meta">
        📅 {day.date} &nbsp;|&nbsp; 🚶 about {stats ? fmt(stats.transit_km) : "?"} km between stops &nbsp;|&nbsp; 💰{" "}
        {stats ? moneyStr(stats.cost_local, fx) : ""}
      </p>
      <div className="grid g32">
        <div>
          {day.slots.map((slot) => (
            <div key={slot.slot}>
              <div className="slot-label">{SLOT_ICONS[slot.slot] || "📍"} {slot.slot}</div>
              {slot.items.map((it) => <ActivityCard key={it.name} item={it} fx={fx} partySize={prefs.party_size} />)}
            </div>
          ))}
        </div>
        <div>
          <MapView points={pts} />
          <p className="meta">{pts.map((p, i) => `${i + 1}. ${p.name}`).join(" → ")}</p>
        </div>
      </div>
    </div>
  );
}
