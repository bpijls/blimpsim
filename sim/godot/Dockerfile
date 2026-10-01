# The simulator. Runs on the GPU host (ARM64 + NVIDIA GB10).
# Godot's --headless flag uses a dummy renderer and produces no frames, so it
# runs against a virtual X server instead; Vulkan still renders on the GPU.
# (Measured in sim/spike: ~285 fps at 640x480 this way, ~7 fps on the CPU.)
FROM ubuntu:24.04

ARG GODOT_VERSION=4.5-stable
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates wget unzip xvfb \
      libvulkan1 libgl1 libegl1 \
      libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 libxext6 libxrender1 \
      libxkbcommon0 libfontconfig1 libasound2t64 libpulse0 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/Godot_v${GODOT_VERSION}_linux.arm64.zip" -O /tmp/godot.zip \
    && unzip -q /tmp/godot.zip -d /opt \
    && mv "/opt/Godot_v${GODOT_VERSION}_linux.arm64" /usr/local/bin/godot \
    && rm /tmp/godot.zip

COPY . /sim
# Builds .godot/: the class_name registry (and, later, imported assets). Without
# it scripts cannot see each other's classes. This step needs no renderer.
# Godot exits 0 on script errors, so the log is checked to fail the build.
RUN godot --headless --path /sim --import 2>&1 | tee /tmp/import.log \
    && ! grep -q "SCRIPT ERROR" /tmp/import.log

CMD ["/sim/entrypoint.sh"]
