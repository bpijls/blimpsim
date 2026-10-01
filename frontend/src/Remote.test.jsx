import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import Remote from "./Remote.jsx";

vi.mock("./useTelemetry.js", () => ({ default: () => ({ readout: null, live: false }) }));

function respond(currentRun) {
  globalThis.fetch = vi.fn((url) =>
    Promise.resolve(
      url.endsWith("/runs/current") && !currentRun
        ? { ok: false, status: 404, json: () => Promise.resolve({ detail: "Nothing run" }) }
        : { ok: true, status: 200, json: () => Promise.resolve(currentRun ?? {}) }
    )
  );
}

const commands = () =>
  fetch.mock.calls.filter(([url]) => url.endsWith("/blimp/command")).map(([, o]) => JSON.parse(o.body));

beforeEach(() => respond({ id: "r1" }));

test("shows the camera of the current run", async () => {
  render(<Remote />);
  const feed = await screen.findByAltText("Onboard camera");
  expect(feed.getAttribute("src")).toContain("/api/blimp/camera.mjpg?run=r1");
});

test("holding a button steers and letting go stops", async () => {
  render(<Remote />);
  const forward = await screen.findByLabelText("Forward");
  await waitFor(() => expect(forward.disabled).toBe(false));

  fireEvent.pointerDown(forward);
  fireEvent.pointerUp(forward);
  expect(commands()).toEqual([
    { surge: 1, yaw: 0, heave: 0 },
    { surge: 0, yaw: 0, heave: 0 },
  ]);
});

test("says so when nothing is running, and disables steering", async () => {
  respond(null);
  render(<Remote />);
  await screen.findByText(/Nothing is running/);
  expect(screen.getByLabelText("Forward").disabled).toBe(true);
});
