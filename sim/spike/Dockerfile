# Milestone 0 spike: can Godot 4 render offscreen on the GPU host (ARM64 + GB10)?
# Godot's own --headless flag uses a dummy renderer and produces no frames, so
# the candidates here are a virtual X server and a headless Wayland compositor.
FROM ubuntu:24.04

ARG GODOT_VERSION=4.5-stable
ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates wget unzip xvfb xauth weston vulkan-tools \
      libvulkan1 mesa-vulkan-drivers libgl1 libegl1 libgles2 \
      libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 libxext6 libxrender1 \
      libxkbcommon0 libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libfontconfig1 libasound2t64 libpulse0 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/Godot_v${GODOT_VERSION}_linux.arm64.zip" -O /tmp/godot.zip \
    && unzip -q /tmp/godot.zip -d /opt \
    && mv "/opt/Godot_v${GODOT_VERSION}_linux.arm64" /usr/local/bin/godot \
    && rm /tmp/godot.zip

COPY project /spike
COPY run.sh /run.sh
CMD ["/run.sh"]
