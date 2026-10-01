import { useCallback, useEffect, useRef, useState } from "react";
import { sendCommand } from "./api.js";

// key → [axis, direction]
export const KEYS = {
  w: ["surge", 1],
  s: ["surge", -1],
  a: ["yaw", 1],
  d: ["yaw", -1],
  r: ["heave", 1],
  f: ["heave", -1],
};
const IDLE = { surge: 0, yaw: 0, heave: 0 };

export function commandFor(held) {
  const command = { ...IDLE };
  for (const key of held) {
    const [axis, direction] = KEYS[key];
    command[axis] += direction;
  }
  return command;
}

// Holding a key applies full thrust on its axis; releasing it returns to idle.
// The blimp keeps the last command it was given, so every change is sent.
// `press` and `release` let on-screen buttons act as the same keys.
export default function useKeyboardSteering(enabled, onError) {
  const [command, setCommand] = useState(IDLE);
  const held = useRef(new Set());

  const setKey = useCallback(
    (key, down) => {
      if (!enabled || !(key in KEYS) || down === held.current.has(key)) return;
      if (down) held.current.add(key);
      else held.current.delete(key);
      const next = commandFor(held.current);
      setCommand(next);
      sendCommand(next).catch((e) => onError?.(e.message));
    },
    [enabled, onError]
  );
  const press = useCallback((key) => setKey(key, true), [setKey]);
  const release = useCallback((key) => setKey(key, false), [setKey]);

  useEffect(() => {
    if (!enabled) return undefined;

    function onKey(event) {
      if (event.target.closest("input, select, textarea")) return;
      setKey(event.key.toLowerCase(), event.type === "keydown");
    }
    function releaseAll() {
      for (const key of [...held.current]) setKey(key, false);
    }

    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    window.addEventListener("blur", releaseAll);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKey);
      window.removeEventListener("blur", releaseAll);
    };
  }, [enabled, setKey]);

  return { command, press, release };
}
