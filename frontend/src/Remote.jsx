import { useEffect, useState } from "react";
import { cameraStreamUrl, getCurrentRun } from "./api.js";
import useKeyboardSteering, { KEYS } from "./useKeyboardSteering.js";
import useTelemetry from "./useTelemetry.js";

const RUN_POLL_MS = 3000;
const BUTTONS = [
  ["a", "⟲", "Turn left", "left"],
  ["w", "▲", "Forward", "forward"],
  ["d", "⟳", "Turn right", "right"],
  ["s", "▼", "Back", "back"],
  ["r", "⤒", "Up", "up"],
  ["f", "⤓", "Down", "down"],
];
const noop = () => {};

// Remote control in its own window: the onboard camera, and steering by
// keyboard or by holding the on-screen buttons. It only uses the blimp
// endpoints, so it works for whichever blimp the api is driving.
export default function Remote() {
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const { readout, live } = useTelemetry(noop);
  const { command, press, release } = useKeyboardSteering(run !== null, setError);

  // A run started or restarted from the monitor changes the camera stream.
  useEffect(() => {
    let stopped = false;
    const load = () =>
      getCurrentRun()
        .then((current) => {
          if (!stopped) setRun((old) => (old?.id === current?.id ? old : current));
        })
        .catch((e) => setError(e.message));
    load();
    const timer = setInterval(load, RUN_POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, []);

  const blimp = readout?.blimp;

  return (
    <div className="remote">
      <div className="remote-feed">
        {run ? (
          <img src={cameraStreamUrl(run.id)} alt="Onboard camera" />
        ) : (
          <p className="muted">Nothing is running. Start a run from the monitor.</p>
        )}
      </div>

      <div className="remote-bar">
        <div className="remote-pad">
          {BUTTONS.map(([key, symbol, label, area]) => {
            const [axis, direction] = KEYS[key];
            return (
              <button
                key={key}
                style={{ gridArea: area }}
                className={command[axis] === direction ? "held" : ""}
                disabled={!run}
                aria-label={label}
                title={`${label} (${key.toUpperCase()})`}
                onPointerDown={() => press(key)}
                onPointerUp={() => release(key)}
                onPointerLeave={() => release(key)}
                onPointerCancel={() => release(key)}
                onContextMenu={(e) => e.preventDefault()}
              >
                {symbol}
                <small>{key.toUpperCase()}</small>
              </button>
            );
          })}
        </div>

        <dl>
          <dt>Link</dt>
          <dd className={live ? "" : "error"}>{live ? "live" : "no telemetry"}</dd>
          <dt>Altitude</dt>
          <dd>{blimp ? `${blimp.position[1].toFixed(1)} m` : "–"}</dd>
          <dt>Speed</dt>
          <dd>{blimp ? `${Math.hypot(...blimp.velocity).toFixed(2)} m/s` : "–"}</dd>
          <dt>Heading</dt>
          <dd>{blimp ? `${((blimp.yaw * 180) / Math.PI).toFixed(0)}°` : "–"}</dd>
        </dl>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
