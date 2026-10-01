import { useCallback, useEffect, useRef, useState } from "react";
import {
  cameraStreamUrl,
  createScenario,
  deleteScenario,
  getBlimpStatus,
  getCurrentRun,
  listDatasets,
  listScenarios,
  startRecording,
  startRun,
  stopRecording,
} from "./api.js";
import DatasetPanel from "./DatasetPanel.jsx";
import DatasetViewer from "./DatasetViewer.jsx";
import Monitor from "./monitor/Monitor.jsx";
import ScenarioPanel from "./ScenarioPanel.jsx";
import useKeyboardSteering from "./useKeyboardSteering.js";
import useTelemetry from "./useTelemetry.js";

const fixed = (value, digits = 1) => value.toFixed(digits);

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [run, setRun] = useState(null); // current run, including its world
  const [status, setStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [inspecting, setInspecting] = useState(null); // dataset name
  const [error, setError] = useState(null);
  const monitor = useRef(null);

  const { readout, live } = useTelemetry((telemetry) => monitor.current?.setTelemetry(telemetry));
  const { command } = useKeyboardSteering(run !== null, setError);

  const refresh = useCallback(async () => {
    try {
      const [list, current, blimp] = await Promise.all([
        listScenarios(),
        getCurrentRun(),
        getBlimpStatus(),
      ]);
      setScenarios(list);
      setRun(current);
      setStatus(blimp);
      // Datasets live on the simulator host; without it the rest still works.
      setDatasets(await listDatasets().catch(() => []));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // While recording, keep the frame count moving.
  const recording = datasets.some((d) => d.recording);
  useEffect(() => {
    if (!recording) return undefined;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [recording, refresh]);

  async function act(action) {
    setError(null);
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  const simUp = status?.reachable && status?.sim_connected !== false;
  const blimp = readout?.blimp;

  return (
    <div className="app">
      <header>
        <h1>blimpsim</h1>
        <span className={`pill ${simUp ? "ok" : "down"}`}>
          {status ? `${status.driver}: ${simUp ? "connected" : "not connected"}` : "…"}
        </span>
        <span className={`pill ${live ? "ok" : "down"}`}>telemetry {live ? "live" : "off"}</span>
        {error && <span className="error">{error}</span>}
        <button
          className="open-remote"
          onClick={() => window.open("/remote.html", "blimp-remote", "width=960,height=760")}
        >
          Remote control
        </button>
      </header>

      <aside>
        <ScenarioPanel
          scenarios={scenarios}
          activeId={run?.scenario_id}
          onCreate={(name, params) => act(() => createScenario(name, params))}
          onRun={(id) => act(() => startRun(id))}
          onDelete={(id) => act(() => deleteScenario(id))}
        />
        <DatasetPanel
          datasets={datasets}
          canRecord={run !== null}
          onStart={(name, maxFrames) => act(() => startRecording(name, maxFrames))}
          onStop={() => act(stopRecording)}
          onOpen={setInspecting}
        />
      </aside>

      <main>
        <Monitor ref={monitor} world={run?.world ?? null} profile={run?.profile ?? null} />
        {!run && <p className="empty">Generate a hall and press Run to start the simulator.</p>}

        {inspecting && (
          <DatasetViewer name={inspecting} onClose={() => setInspecting(null)} onError={setError} />
        )}

        {run && !inspecting && (
          <div className="hud">
            <img src={cameraStreamUrl(run.id)} alt="Onboard camera" />
            <dl>
              <dt>Time</dt>
              <dd>{readout ? `${fixed(readout.t)} s` : "–"}</dd>
              <dt>Position</dt>
              <dd>{blimp ? blimp.position.map((v) => fixed(v)).join(", ") : "–"}</dd>
              <dt>Speed</dt>
              <dd>{blimp ? `${fixed(Math.hypot(...blimp.velocity), 2)} m/s` : "–"}</dd>
              <dt>Heading</dt>
              <dd>{blimp ? `${fixed((blimp.yaw * 180) / Math.PI, 0)}°` : "–"}</dd>
              <dt>People</dt>
              <dd>{readout ? readout.people.length : "–"}</dd>
              <dt>Command</dt>
              <dd>
                surge {command.surge}, yaw {command.yaw}, heave {command.heave}
              </dd>
            </dl>
            <p className="muted">W/S forward and back · A/D turn · R/F up and down</p>
          </div>
        )}
      </main>
    </div>
  );
}
