import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import { commandFor } from "./useKeyboardSteering.js";

// WebGL and WebSockets do not exist in jsdom; the monitor is verified in a browser.
vi.mock("./monitor/Monitor.jsx", async () => {
  const { forwardRef } = await import("react");
  return { default: forwardRef(() => <div data-testid="monitor" />) };
});
vi.mock("./useTelemetry.js", () => ({ default: () => ({ readout: null, live: false }) }));

const SCENARIO = {
  id: "s1",
  name: "Atrium",
  params: { width: 60, depth: 40, people: 40 },
};

function respond(routes) {
  globalThis.fetch = vi.fn((url) => {
    const [, body] = Object.entries(routes).find(([path]) => url.endsWith(path)) ?? [];
    return Promise.resolve(
      body === undefined
        ? { ok: false, status: 404, json: () => Promise.resolve({ detail: "Not found" }) }
        : { ok: true, status: 200, json: () => Promise.resolve(body) }
    );
  });
}

beforeEach(() => {
  respond({
    "/scenarios": [SCENARIO],
    "/blimp/status": { driver: "sim", reachable: true, sim_connected: true },
  });
});

test("lists scenarios and shows the simulator as connected", async () => {
  render(<App />);
  await waitFor(() => expect(screen.getByText("Atrium")).toBeDefined());
  expect(screen.getByText("sim: connected")).toBeDefined();
});

test("prompts to start a run when nothing is running", async () => {
  render(<App />);
  await waitFor(() => expect(screen.getByText(/press Run/)).toBeDefined());
});

test("opposite keys cancel out and axes combine", () => {
  expect(commandFor(new Set(["w", "s", "a", "r"]))).toEqual({ surge: 0, yaw: 1, heave: 1 });
});
