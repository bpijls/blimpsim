import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App.jsx";

beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([{ id: "1", title: "Existing" }]) })
  );
});

test("renders items loaded from the API", async () => {
  render(<App />);
  await waitFor(() => expect(screen.getByText("Existing")).toBeDefined());
});
