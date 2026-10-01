// Low-fidelity live view of the hall, the blimp and the people. It draws state
// and simulates nothing, so it works the same whether telemetry comes from the
// simulator or from the real blimp. Coordinates match Godot's: metres, Y up,
// yaw about +Y with 0 facing -Z.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const MAX_PEOPLE = 500;
const OBSTACLE_COLORS = { kiosk: 0x40669a, bench: 0x735033, planter: 0x337340 };
const ZONE_COLORS = { entrance: 0x3fa66a, attraction: 0xd9a441 };

export function createMonitor(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x15161a);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x333340, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2);
  sun.position.set(20, 40, 10);
  scene.add(sun);

  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
  camera.position.set(0, 45, 55);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.maxPolarAngle = Math.PI / 2 - 0.02;

  let hall = new THREE.Group();
  scene.add(hall);

  // Blimp: hull, a line down to the floor (height is hard to read otherwise),
  // and the camera's view rays with their footprint on the floor.
  const blimp = new THREE.Group();
  const hull = new THREE.Mesh(
    new THREE.SphereGeometry(1, 24, 16),
    new THREE.MeshStandardMaterial({ color: 0xe65a1a })
  );
  blimp.add(hull);
  blimp.visible = false;
  scene.add(blimp);

  const overlayMaterial = new THREE.LineBasicMaterial({ color: 0xffd24a });
  const dropLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineDashedMaterial({ color: 0xe65a1a, dashSize: 0.4, gapSize: 0.3 })
  );
  // 4 rays from the lens plus the 4 edges of the footprint: 8 segments.
  const view = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(8 * 2 * 3), 3)
    ),
    overlayMaterial
  );
  view.frustumCulled = false;
  dropLine.frustumCulled = false;
  dropLine.visible = view.visible = false;
  scene.add(dropLine, view);

  const people = new THREE.InstancedMesh(
    new THREE.CapsuleGeometry(0.25, 1.3, 4, 8),
    new THREE.MeshStandardMaterial({ color: 0x8fc5ff }),
    MAX_PEOPLE
  );
  people.count = 0;
  people.frustumCulled = false;
  scene.add(people);

  let profile = null;
  let bounds = null; // half-extents of the hall, for clipping the camera's view rays

  function setWorld(world) {
    scene.remove(hall);
    hall.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
    hall = new THREE.Group();
    scene.add(hall);
    blimp.visible = dropLine.visible = view.visible = false;
    people.count = 0;
    bounds = null;
    if (!world) return;

    const { width, depth, height } = world.hall;
    bounds = { x: width / 2, y: height, z: depth / 2 };
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ color: 0x3a3c44 })
    );
    floor.rotation.x = -Math.PI / 2;
    hall.add(floor);

    // Walls and ceiling as an outline only, so the inside stays visible.
    const shell = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(width, height, depth)),
      new THREE.LineBasicMaterial({ color: 0x8a8d99 })
    );
    shell.position.y = height / 2;
    hall.add(shell);

    const pillarMaterial = new THREE.MeshStandardMaterial({
      color: 0xb3b3b8,
      transparent: true,
      opacity: 0.45,
    });
    for (const p of world.pillars) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(p.size, height, p.size), pillarMaterial);
      mesh.position.set(p.x, height / 2, p.z);
      hall.add(mesh);
    }

    for (const o of world.obstacles) {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(o.width, o.height, o.depth),
        new THREE.MeshStandardMaterial({ color: OBSTACLE_COLORS[o.kind] ?? 0x808080 })
      );
      mesh.position.set(o.x, o.height / 2, o.z);
      mesh.rotation.y = o.yaw;
      hall.add(mesh);
    }

    for (const z of world.zones) {
      const disc = new THREE.Mesh(
        new THREE.CircleGeometry(z.radius, 32),
        new THREE.MeshBasicMaterial({
          color: ZONE_COLORS[z.kind] ?? 0xffffff,
          transparent: true,
          opacity: 0.35,
        })
      );
      disc.rotation.x = -Math.PI / 2;
      disc.position.set(z.x, 0.02, z.z);
      hall.add(disc);
    }

    const reach = Math.max(width, depth);
    camera.position.set(0, reach * 0.75, reach * 0.9);
    controls.target.set(0, 0, 0);
  }

  function setProfile(next) {
    profile = next;
    if (profile) hull.scale.set(profile.diameter / 2, profile.diameter / 2, profile.length / 2);
  }

  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const one = new THREE.Vector3(1, 1, 1);
  const position = new THREE.Vector3();

  function setTelemetry(telemetry) {
    const [x, y, z] = telemetry.blimp.position;
    blimp.position.set(x, y, z);
    blimp.rotation.y = telemetry.blimp.yaw;
    blimp.visible = dropLine.visible = true;

    dropLine.geometry.setFromPoints([new THREE.Vector3(x, y, z), new THREE.Vector3(x, 0, z)]);
    dropLine.computeLineDistances();
    if (profile && bounds) updateView(telemetry.blimp);

    const list = telemetry.people ?? [];
    people.count = Math.min(list.length, MAX_PEOPLE);
    for (let i = 0; i < people.count; i++) {
      quaternion.setFromAxisAngle(up, list[i].heading);
      matrix.compose(position.set(list[i].x, 0.9, list[i].z), quaternion, one);
      people.setMatrixAt(i, matrix);
    }
    people.instanceMatrix.needsUpdate = true;
  }

  function updateView(state) {
    const cam = profile.camera;
    const yaw = new THREE.Matrix4().makeRotationY(state.yaw);
    const lens = new THREE.Vector3(...cam.mount).applyMatrix4(yaw).add(blimp.position);
    const tilt = new THREE.Matrix4().makeRotationX(-THREE.MathUtils.degToRad(state.camera_tilt));
    const halfV = Math.tan(THREE.MathUtils.degToRad(cam.fov_y_deg) / 2);
    const halfH = halfV * (cam.width / cam.height);

    const corners = [[-1, 1], [1, 1], [1, -1], [-1, -1]].map(([sx, sy]) => {
      const ray = new THREE.Vector3(sx * halfH, sy * halfV, -1)
        .normalize()
        .applyMatrix4(tilt)
        .applyMatrix4(yaw);
      return lens.clone().addScaledVector(ray, distanceToHall(lens, ray));
    });

    const points = view.geometry.attributes.position;
    let i = 0;
    const segment = (a, b) => {
      points.setXYZ(i++, a.x, a.y, a.z);
      points.setXYZ(i++, b.x, b.y, b.z);
    };
    corners.forEach((corner, n) => {
      segment(lens, corner);
      segment(corner, corners[(n + 1) % 4]);
    });
    points.needsUpdate = true;
    view.visible = true;
  }

  // How far a ray from inside the hall travels before it meets the floor, a wall or the ceiling.
  function distanceToHall(from, ray) {
    const along = (origin, direction, min, max) =>
      direction > 0 ? (max - origin) / direction : direction < 0 ? (min - origin) / direction : Infinity;
    return Math.max(
      0,
      Math.min(
        along(from.x, ray.x, -bounds.x, bounds.x),
        along(from.y, ray.y, 0, bounds.y),
        along(from.z, ray.z, -bounds.z, bounds.z)
      )
    );
  }

  function resize() {
    const { clientWidth, clientHeight } = container;
    if (clientWidth === 0 || clientHeight === 0) return;
    renderer.setSize(clientWidth, clientHeight);
    camera.aspect = clientWidth / clientHeight;
    camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  return {
    setWorld,
    setProfile,
    setTelemetry,
    dispose() {
      observer.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
