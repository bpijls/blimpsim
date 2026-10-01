class_name Person
extends CharacterBody3D
# One simulated pedestrian: a procedural mannequin that walks the navmesh.
#
# The body is built from primitives so the sim needs no downloaded assets.
# To use rigged characters instead, replace _build() and keep keypoints()
# returning the same joints: labelling only depends on those.

const COLLISION_LAYER := 2
const LIMB_RADIUS := 0.12  # metres added around each joint when boxing a person
const ARRIVE_DISTANCE := 0.6
const SKIN_TONES := ["f1c9a5", "d9a377", "a86e45", "6b4428"]

var id := 0
var behaviour := "wander"

var _crowd: Crowd
var _rng := RandomNumberGenerator.new()
var _agent: NavigationAgent3D
var _speed := 1.2
var _wait := 0.0
var _has_target := false
var _phase := 0.0
var _stride := 0.0  # 0 standing, 1 walking; eased so limbs do not snap
var _limbs: Array[Node3D] = []  # left leg, right leg, left arm, right arm
var _keypoints: Array[Node3D] = []


func setup(crowd: Crowd, person_id: int, kind: String, start: Vector3, random_seed: int) -> void:
	_crowd = crowd
	id = person_id
	behaviour = kind
	_rng.seed = random_seed
	position = start
	rotation.y = _rng.randf_range(-PI, PI)
	_speed = _rng.randf_range(0.8, 1.5)
	collision_layer = COLLISION_LAYER
	collision_mask = 0

	var height := _rng.randf_range(1.55, 1.95)
	_build(height / 1.75)

	var shape := CapsuleShape3D.new()
	shape.radius = 0.25
	shape.height = height
	var collider := CollisionShape3D.new()
	collider.shape = shape
	collider.position.y = height / 2
	add_child(collider)

	_agent = NavigationAgent3D.new()
	_agent.radius = 0.3
	_agent.height = height
	_agent.max_speed = _speed
	_agent.path_desired_distance = 0.5
	_agent.target_desired_distance = ARRIVE_DISTANCE
	_agent.avoidance_enabled = true
	_agent.neighbor_distance = 5.0
	_agent.time_horizon_agents = 1.5
	_agent.velocity_computed.connect(_on_velocity_computed)
	add_child(_agent)

	if behaviour == "stand":
		_wait = INF
	else:
		_wait = _rng.randf_range(0.0, 2.0)  # so the crowd does not set off in step


func keypoints() -> PackedVector3Array:
	var points := PackedVector3Array()
	for marker in _keypoints:
		points.append(marker.global_position)
	return points


func state() -> Dictionary:
	return {
		"id": id,
		"x": snappedf(position.x, 0.01),
		"z": snappedf(position.z, 0.01),
		"heading": snappedf(rotation.y, 0.01),
	}


func _physics_process(delta: float) -> void:
	if _wait > 0.0:
		_wait -= delta
		_agent.velocity = Vector3.ZERO  # still registers with avoidance, so others walk around
		_animate(0.0, delta)
		if _wait <= 0.0:
			_has_target = false
		return
	if not _crowd.navigation_ready():
		return
	if not _has_target:
		_agent.target_position = _crowd.next_target(self, _rng)
		_has_target = true
		return
	if _agent.is_navigation_finished():
		_arrive()
		return
	var step := _agent.get_next_path_position() - global_position
	step.y = 0
	_agent.velocity = step.normalized() * _speed


func _on_velocity_computed(safe_velocity: Vector3) -> void:
	if _wait > 0.0:
		return
	var delta := get_physics_process_delta_time()
	safe_velocity.y = 0
	position += safe_velocity * delta
	position.y = 0
	var speed := safe_velocity.length()
	if speed > 0.1:
		var heading := atan2(-safe_velocity.x, -safe_velocity.z)
		rotation.y = wrapf(lerp_angle(rotation.y, heading, minf(1.0, 8.0 * delta)), -PI, PI)
	_animate(speed, delta)


func _arrive() -> void:
	if behaviour == "transit":
		_wait = _rng.randf_range(5.0, 20.0)  # linger at the zone
	else:
		_wait = _rng.randf_range(0.5, 4.0)


func _animate(speed: float, delta: float) -> void:
	_stride = move_toward(_stride, 1.0 if speed > 0.1 else 0.0, 4.0 * delta)
	_phase += speed * delta * 4.0
	var swing := sin(_phase) * 0.55 * _stride
	_limbs[0].rotation.x = swing
	_limbs[1].rotation.x = -swing
	_limbs[2].rotation.x = -swing * 0.7
	_limbs[3].rotation.x = swing * 0.7


func _build(scale_factor: float) -> void:
	var body := Node3D.new()
	body.scale = Vector3.ONE * scale_factor
	add_child(body)

	var skin := Color(SKIN_TONES[_rng.randi() % SKIN_TONES.size()])
	var shirt := Color.from_hsv(_rng.randf(), _rng.randf_range(0.2, 0.8), _rng.randf_range(0.3, 0.9))
	var trousers := Color.from_hsv(_rng.randf(), _rng.randf_range(0.0, 0.4), _rng.randf_range(0.1, 0.5))

	_capsule(body, 0.17, 0.62, Vector3(0, 1.17, 0), shirt)
	var head := SphereMesh.new()
	head.radius = 0.115
	head.height = 0.23
	_mesh(body, head, Vector3(0, 1.62, 0), skin)

	for side: float in [-1.0, 1.0]:
		var hip := _pivot(body, Vector3(side * 0.09, 0.9, 0))
		_capsule(hip, 0.075, 0.9, Vector3(0, -0.45, 0), trousers)
		_limbs.append(hip)
		_keypoints.append(_pivot(hip, Vector3(0, -0.84, 0)))  # ankle; a point on the floor itself is hidden by it
	for side: float in [-1.0, 1.0]:
		var shoulder := _pivot(body, Vector3(side * 0.24, 1.42, 0))
		_capsule(shoulder, 0.05, 0.62, Vector3(0, -0.31, 0), shirt)
		_limbs.append(shoulder)
		_keypoints.append(shoulder)
		_keypoints.append(_pivot(shoulder, Vector3(0, -0.62, 0)))  # hand

	_keypoints.append(_pivot(body, Vector3(0, 1.74, 0)))  # top of head
	_keypoints.append(_pivot(body, Vector3(0, 1.2, 0)))  # chest
	_keypoints.append(_pivot(body, Vector3(0, 0.9, 0)))  # pelvis


func _pivot(parent: Node3D, at: Vector3) -> Node3D:
	var node := Node3D.new()
	node.position = at
	parent.add_child(node)
	return node


func _capsule(parent: Node3D, radius: float, height: float, at: Vector3, color: Color) -> void:
	var mesh := CapsuleMesh.new()
	mesh.radius = radius
	mesh.height = height
	_mesh(parent, mesh, at, color)


func _mesh(parent: Node3D, mesh: PrimitiveMesh, at: Vector3, color: Color) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.8
	mesh.material = material
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.position = at
	parent.add_child(instance)
