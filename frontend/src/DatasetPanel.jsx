import { useState } from "react";

export default function DatasetPanel({ datasets, canRecord, onStart, onStop, onOpen }) {
  const [name, setName] = useState("");
  const [maxFrames, setMaxFrames] = useState(300);
  const recording = datasets.find((d) => d.recording);

  function submit(event) {
    event.preventDefault();
    onStart(name, maxFrames);
    setName("");
  }

  return (
    <section className="panel">
      <h2>Datasets</h2>
      <ul className="scenarios">
        {datasets.length === 0 && <li className="muted">No recordings yet.</li>}
        {datasets.map((d) => (
          <li key={d.name}>
            <span>
              {d.name}
              <small>{d.recording ? `recording, ${d.frames} frames` : `${d.frames} frames`}</small>
            </span>
            {d.recording ? (
              <button onClick={onStop}>Stop</button>
            ) : (
              <button onClick={() => onOpen(d.name)}>Inspect</button>
            )}
          </li>
        ))}
      </ul>

      {!recording && (
        <form onSubmit={submit}>
          <label>
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="walk-01"
              pattern="[a-z0-9][a-z0-9_\-]{0,63}"
              title="Lowercase letters, digits, - and _"
              required
            />
          </label>
          <label>
            Frames
            <input
              type="number"
              min={1}
              max={100000}
              value={maxFrames}
              onChange={(e) => setMaxFrames(Number(e.target.value))}
            />
          </label>
          <button type="submit" disabled={!canRecord}>
            Record labelled frames
          </button>
        </form>
      )}
    </section>
  );
}
