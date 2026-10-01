import { useEffect, useRef, useState } from "react";
import { telemetrySocketUrl } from "./api.js";

const RETRY_MS = 2000;
const READOUT_MS = 200;

// Streams telemetry to `onMessage` at full rate and returns a copy refreshed a
// few times a second for on-screen numbers, plus whether the link is up.
export default function useTelemetry(onMessage) {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  const [readout, setReadout] = useState(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let socket;
    let retry;
    let closed = false;
    let lastReadout = 0;

    function connect() {
      socket = new WebSocket(telemetrySocketUrl());
      socket.onopen = () => setLive(true);
      socket.onmessage = (event) => {
        const telemetry = JSON.parse(event.data);
        handler.current(telemetry);
        const now = performance.now();
        if (now - lastReadout > READOUT_MS) {
          lastReadout = now;
          setReadout(telemetry);
        }
      };
      socket.onclose = () => {
        setLive(false);
        if (!closed) retry = setTimeout(connect, RETRY_MS);
      };
    }
    connect();

    return () => {
      closed = true;
      clearTimeout(retry);
      socket.close();
    };
  }, []);

  return { readout, live };
}
