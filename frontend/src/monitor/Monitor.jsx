import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { createMonitor } from "./scene.js";

// Telemetry arrives 20 times a second, so it is pushed in through the ref
// (`ref.current.setTelemetry(...)`) instead of through props and a re-render.
const Monitor = forwardRef(function Monitor({ world, profile }, ref) {
  const container = useRef(null);
  const monitor = useRef(null);

  useEffect(() => {
    monitor.current = createMonitor(container.current);
    return () => monitor.current.dispose();
  }, []);

  useEffect(() => monitor.current.setWorld(world), [world]);
  useEffect(() => monitor.current.setProfile(profile), [profile]);

  useImperativeHandle(ref, () => ({
    setTelemetry: (telemetry) => monitor.current?.setTelemetry(telemetry),
  }));

  return <div className="monitor" ref={container} />;
});

export default Monitor;
