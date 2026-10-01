import { useState } from "react";

const FIELDS = [
  ["seed", "Seed", 0, 999999, 1],
  ["width", "Width (m)", 10, 300, 1],
  ["depth", "Depth (m)", 10, 300, 1],
  ["height", "Height (m)", 3, 40, 0.5],
  ["pillar_spacing", "Pillar spacing (m)", 0, 100, 1],
  ["obstacles", "Obstacles", 0, 200, 1],
  ["people", "People", 0, 500, 1],
];
const DEFAULTS = {
  seed: 0, width: 60, depth: 40, height: 12, pillar_spacing: 12, obstacles: 12, people: 40,
};

export default function ScenarioPanel({ scenarios, activeId, onCreate, onRun, onDelete }) {
  const [name, setName] = useState("");
  const [params, setParams] = useState(DEFAULTS);

  function submit(event) {
    event.preventDefault();
    onCreate(name.trim() || `Hall ${params.width}×${params.depth} #${params.seed}`, params);
    setName("");
  }

  return (
    <section className="panel">
      <h2>Scenarios</h2>
      <ul className="scenarios">
        {scenarios.length === 0 && <li className="muted">None yet. Generate a hall below.</li>}
        {scenarios.map((s) => (
          <li key={s.id} className={s.id === activeId ? "active" : ""}>
            <span>
              {s.name}
              <small>
                {s.params.width}×{s.params.depth} m, {s.params.people} people
              </small>
            </span>
            <button onClick={() => onRun(s.id)}>{s.id === activeId ? "Restart" : "Run"}</button>
            <button className="quiet" onClick={() => onDelete(s.id)} aria-label={`Delete ${s.name}`}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <h2>New hall</h2>
      <form onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" />
        </label>
        {FIELDS.map(([key, label, min, max, step]) => (
          <label key={key}>
            {label}
            <input
              type="number"
              min={min}
              max={max}
              step={step}
              value={params[key]}
              onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })}
            />
          </label>
        ))}
        <button type="submit">Generate</button>
      </form>
    </section>
  );
}
