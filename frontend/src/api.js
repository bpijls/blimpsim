// All fetch() wrappers live here; components never call fetch directly.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().then((body) => body.detail).catch(() => null);
    const error = new Error(
      typeof detail === "string" ? detail : `${options.method ?? "GET"} ${path} → ${res.status}`
    );
    error.status = res.status;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const getHealth = () => request("/health");

export const listScenarios = () => request("/scenarios");
export const getScenario = (id) => request(`/scenarios/${id}`);
export const createScenario = (name, params) => post("/scenarios", { name, params });
export const deleteScenario = (id) => request(`/scenarios/${id}`, { method: "DELETE" });

export const startRun = (scenarioId, mode = "realtime") =>
  post("/runs", { scenario_id: scenarioId, mode });
// Resolves to null when nothing has been run yet.
export const getCurrentRun = () =>
  request("/runs/current").catch((e) => (e.status === 404 ? null : Promise.reject(e)));

export const getBlimpStatus = () => request("/blimp/status");
export const sendCommand = (command) => post("/blimp/command", command);

export const cameraStreamUrl = (runId) => `${BASE}/api/blimp/camera.mjpg?run=${runId}`;

export function telemetrySocketUrl() {
  const origin = BASE || window.location.origin;
  return `${origin.replace(/^http/, "ws")}/api/blimp/telemetry`;
}

export const listDatasets = () => request("/datasets");
export const startRecording = (name, maxFrames) =>
  post("/datasets", { name, max_frames: maxFrames });
export const stopRecording = () => post("/datasets/stop", {});
export const getAnnotations = (name) => request(`/datasets/${name}/annotations`);
export const datasetImageUrl = (name, file) => `${BASE}/api/datasets/${name}/images/${file}`;
