class_name Blimp
extends CharacterBody3D
# Blimp dynamics, integrated by hand: a near-neutrally-buoyant body with weak
# thrusters, strong drag and no pitch or roll. Every number comes from the
# profile (contracts/blimp_profile.schema.json), because the real airframe's
# parameters are not known yet.

const RENDER_LAYER := 2  # hidden from the onboard camera, which sits inside the hull
const BOUNCE := 0.3

var yaw_rate := 0.0
var camera_tilt_deg := 0.0

var _profile: Dictionary
var _thrust := Vector3.ZERO  # actuator state: x surge, y yaw, z heave, each in [-1, 1]
var _target := Vector3.ZERO
var _pending: Array = []  # [apply_at_tick, target, tilt-or-null], oldest first
var _tick := 0


func setup(profile: Dictionary, start: Dictionary) -> void:
	_profile = profile
	camera_tilt_deg = profile.camera.tilt_deg
	position = Vector3(start.position[0], start.position[1], start.position[2])
	rotation.y = start.yaw

	var length: float = profile.length
	var diameter: float = profile.diameter

	var shape := CapsuleShape3D.new()
	shape.radius = diameter / 2
	shape.height = length
	var collider := CollisionShape3D.new()
	collider.shape = shape
	collider.rotation.x = PI / 2  # capsule axis along Z, the direction of travel
	add_child(collider)

	var hull_mesh := SphereMesh.new()
	hull_mesh.radius = diameter / 2
	hull_mesh.height = diameter
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.9, 0.35, 0.1)
	hull_mesh.material = material
	var hull := MeshInstance3D.new()
	hull.mesh = hull_mesh
	hull.scale.z = length / diameter
	hull.layers = RENDER_LAYER
	add_child(hull)


func command(cmd: Dictionary) -> void:
	var target := Vector3(
		clampf(cmd.get("surge", 0.0), -1, 1),
		clampf(cmd.get("yaw", 0.0), -1, 1),
		clampf(cmd.get("heave", 0.0), -1, 1),
	)
	# Not Engine.physics_ticks_per_second: lockstep raises that to run faster
	# than real time, while a tick stays 1/60 s of simulated time.
	var latency_ticks := roundi(_profile.command_latency / get_physics_process_delta_time())
	_pending.append([_tick + latency_ticks, target, cmd.get("camera_tilt")])


func camera_transform() -> Transform3D:
	var m: Array = _profile.camera.mount
	var mount := Transform3D(
		Basis(Vector3.RIGHT, -deg_to_rad(camera_tilt_deg)), Vector3(m[0], m[1], m[2])
	)
	return global_transform * mount


func state() -> Dictionary:
	return {
		"position": _vec(position),
		"yaw": snappedf(rotation.y, 0.0001),
		"velocity": _vec(velocity),
		"yaw_rate": snappedf(yaw_rate, 0.0001),
		"camera_tilt": camera_tilt_deg,
		"battery": null,
	}


func _physics_process(delta: float) -> void:
	_tick += 1
	while not _pending.is_empty() and _pending[0][0] <= _tick:
		var due: Array = _pending.pop_front()
		_target = due[1]
		if due[2] != null:
			camera_tilt_deg = clampf(due[2], 0, 90)

	var p := _profile
	var lag: float = p.actuator_lag
	_thrust += (_target - _thrust) * (1.0 if lag <= 0.0 else 1.0 - exp(-delta / lag))

	var forward := -global_transform.basis.z
	var right := global_transform.basis.x
	var u := velocity.dot(forward)
	var v := velocity.dot(right)
	var w := velocity.y
	var damping: float = p.linear_damping
	var surge: float = _thrust.x * p.max_surge_thrust - p.drag_surge * absf(u) * u - damping * u
	var sway: float = -p.drag_sway * absf(v) * v - damping * v
	var heave: float = (
		_thrust.z * p.max_heave_thrust + p.buoyancy_trim - p.drag_heave * absf(w) * w - damping * w
	)
	var effective_mass: float = p.mass * (1.0 + p.added_mass)
	velocity += (forward * surge + right * sway + Vector3.UP * heave) / effective_mass * delta

	var torque: float = (
		_thrust.y * p.max_yaw_torque
		- p.yaw_drag * absf(yaw_rate) * yaw_rate
		- p.yaw_damping * yaw_rate
	)
	var yaw_inertia: float = p.yaw_inertia
	yaw_rate += torque / yaw_inertia * delta
	rotation.y = wrapf(rotation.y + yaw_rate * delta, -PI, PI)

	var hit := move_and_collide(velocity * delta)
	if hit:
		velocity = velocity.bounce(hit.get_normal()) * BOUNCE


static func _vec(v: Vector3) -> Array:
	return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)]
