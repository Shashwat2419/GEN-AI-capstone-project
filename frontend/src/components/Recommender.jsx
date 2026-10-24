export default function Recommender({ recs, onRecommend, onPick, busy }) {
  return (
    <div>
      <h4>Not sure where to go?</h4>
      <p>Choose a vibe, budget, travel date and interests above and we will match your top 3 destinations.</p>
      <button className="btn" disabled={!!busy} onClick={onRecommend}>✨ Recommend destinations</button>
      <div className="grid g3 mt">
        {(recs || []).map((r) => (
          <article className="card" key={r.city}>
            <span className="score">{r.match}% match</span>
            <h3>{r.city}</h3>
            <div className="meta">{r.country}</div>
            <p>{r.why}</p>
            <div>{(r.tags || []).map((t) => <span className="badge warm" key={t}>{t}</span>)}</div>
            <p className="meta">🌤️ {r.weather}<br />💵 ~USD {Math.round(r.daily_usd)} per person/day</p>
            <button className="btn small" onClick={() => onPick(r.city)}>Plan this trip</button>
          </article>
        ))}
      </div>
    </div>
  );
}
