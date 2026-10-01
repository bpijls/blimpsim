#!/usr/bin/env bash
# Starts a virtual X server, then the simulator. xvfb-run is not used: as PID 1
# it never receives Xvfb's ready signal and hangs before launching Godot.
set -euo pipefail

export DISPLAY=:99
rm -f /tmp/.X99-lock
Xvfb "$DISPLAY" -screen 0 640x480x24 -nolisten tcp &

for _ in $(seq 50); do
  [ -S /tmp/.X11-unix/X99 ] && break
  sleep 0.1
done

exec godot --path /sim --rendering-driver vulkan --audio-driver Dummy
