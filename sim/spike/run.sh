#!/usr/bin/env bash
# Tries each offscreen rendering route and prints adapter + fps for the ones that work.
set -u
mkdir -p /out
export XDG_RUNTIME_DIR=/tmp/xdg
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"

run() {
  local name=$1; shift
  echo "##### $name"
  SPIKE_OUT="/out/$name.jpg" timeout 90 "$@" > "/out/$name.log" 2>&1
  echo "exit=$?"
  grep -E "SPIKE|ERROR" "/out/$name.log" | head -12
}

XVFB=(xvfb-run -a -s "-screen 0 640x480x24")
GODOT=(godot --path /spike --audio-driver Dummy)

run xvfb-vulkan "${XVFB[@]}" "${GODOT[@]}" --rendering-driver vulkan
run xvfb-opengl "${XVFB[@]}" "${GODOT[@]}" --rendering-driver opengl3

weston --backend=headless --width=640 --height=480 --socket=wl-spike > /out/weston.log 2>&1 &
sleep 2
WAYLAND_DISPLAY=wl-spike run wayland-vulkan "${GODOT[@]}" --display-driver wayland --rendering-driver vulkan

# CPU baseline, in case no GPU route works.
VK_DRIVER_FILES="$(ls /usr/share/vulkan/icd.d/lvp_icd*.json | head -1)" \
  run xvfb-lavapipe "${XVFB[@]}" "${GODOT[@]}" --rendering-driver vulkan
