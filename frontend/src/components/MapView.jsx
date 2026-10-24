import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Numbered pins joined by a dashed line, so you can see the day's route and how compact it is.
export default function MapView({ points }) {
  const ref = useRef(null);
  const key = JSON.stringify(points.map((p) => [p.lat, p.lon, p.name]));

  useEffect(() => {
    if (!ref.current || points.length === 0) return undefined;
    const map = L.map(ref.current, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    const latlngs = points.map((p) => [p.lat, p.lon]);
    L.polyline(latlngs, { color: "#F97316", weight: 3, dashArray: "6 6" }).addTo(map);
    points.forEach((p, i) => {
      const marker = L.marker([p.lat, p.lon], {
        icon: L.divIcon({ className: "pin", html: `<span>${i + 1}</span>`, iconSize: [26, 26] }),
      }).addTo(map);
      const tip = document.createElement("span"); // textContent keeps AI-written names safe
      tip.textContent = `${i + 1}. ${p.name}`;
      marker.bindTooltip(tip);
    });
    map.fitBounds(L.latLngBounds(latlngs).pad(0.25), { maxZoom: 15 });
    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return <div ref={ref} className="map" />;
}
