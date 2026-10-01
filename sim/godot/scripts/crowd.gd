class_name Crowd
extends Node3D
# The people in the hall: navigation mesh, spawning, and ground-truth labels.

const WALL_MARGIN := 1.0
const CLEARANCE := 0.6
const PLACEMENT_ATTEMPTS := 30

var people: Array[Person] = []

var _world: Dictionary
var _blockers: Array = []  # [x, z, radius] of pillars and obstacles
var _map_iteration_at_setup := 0


func setup(world: Dictionary, hall: Node3D) -> void:
	_world = world
	for p: Dictionary in world.pillars:
		_blockers.append([p.x, p.z, p.size])
	for o: Dictionary in world.obstacles:
		_blockers.append([o.x, o.z, Vector2(o.width, o.depth).length() / 2])

	var navmesh := NavigationMesh.new()
	navmesh.cell_size = 0.25
	navmesh.cell_height = 0.25
	navmesh.agent_radius = 0.5  # a whole number of cells, or the baker warns
	navmesh.agent_height = 1.8
	navmesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(navmesh, source, hall)
	NavigationServer3D.bake_from_source_geometry_data(navmesh, source)
	var region := NavigationRegion3D.new()
	region.navigation_mesh = navmesh
	add_child(region)
	_map_iteration_at_setup = NavigationServer3D.map_get_iteration_id(get_world_3d().navigation_map)

	var rng := RandomNumberGenerator.new()
	rng.seed = world.seed
	var crowd: Dictionary = world.crowd
	var count: int = crowd.count
	var total: float = maxf(crowd.wander + crowd.transit + crowd.stand, 0.001)
	var wanderers := roundi(count * crowd.wander / total)
	var transits := roundi(count * crowd.transit / total)
	for i in count:
		var kind := "wander" if i < wanderers else ("transit" if i < wanderers + transits else "stand")
		var start: Vector3
		match kind:
			"transit":
				start = zone_point(rng, "entrance")
			"stand":
				start = zone_point(rng, "attraction")
			_:
				start = random_floor_point(rng)
		var person := Person.new()
		add_child(person)
		person.setup(self, i, kind, start, rng.randi())
		people.append(person)


func navigation_ready() -> bool:
	# The navigation map only contains this hall after the server's next sync.
	var map := get_world_3d().navigation_map
	return NavigationServer3D.map_get_iteration_id(map) != _map_iteration_at_setup


func next_target(person: Person, rng: RandomNumberGenerator) -> Vector3:
	if person.behaviour == "transit":
		return zone_point(rng, "")
	return random_floor_point(rng)


func random_floor_point(rng: RandomNumberGenerator) -> Vector3:
	var half_w: float = _world.hall.width / 2 - WALL_MARGIN
	var half_d: float = _world.hall.depth / 2 - WALL_MARGIN
	var point := Vector3.ZERO
	for attempt in PLACEMENT_ATTEMPTS:
		point = Vector3(rng.randf_range(-half_w, half_w), 0, rng.randf_range(-half_d, half_d))
		if _is_clear(point):
			break
	return point


func zone_point(rng: RandomNumberGenerator, kind: String) -> Vector3:
	# A point inside a random zone of `kind`; "" means any zone.
	var zones: Array = _world.zones.filter(func(z): return kind == "" or z.kind == kind)
	if zones.is_empty():
		return random_floor_point(rng)
	var zone: Dictionary = zones[rng.randi() % zones.size()]
	var reach: float = zone.radius * sqrt(rng.randf())
	var offset := Vector2.from_angle(rng.randf_range(0, TAU)) * reach
	return Vector3(zone.x + offset.x, 0, zone.z + offset.y)


func states() -> Array:
	return people.map(func(p: Person): return p.state())


func labels(camera: Camera3D, size: Vector2i, exclude: Array[RID]) -> Array:
	# One entry per person with any joint in view. The box covers the visible
	# joints only; visibility is the fraction of joints that are in frame and
	# not hidden behind the hall, an obstacle or another person.
	var space := get_world_3d().direct_space_state
	var eye := camera.global_position
	var focal := size.y / 2.0 / tan(deg_to_rad(camera.fov) / 2.0)
	var frame := Rect2(Vector2.ZERO, size)
	var out := []
	for person in people:
		var points := person.keypoints()
		var visible := 0
		var box := Rect2()
		for point in points:
			if camera.is_position_behind(point):
				continue
			var pixel := camera.unproject_position(point)
			if not frame.has_point(pixel):
				continue
			# Stop just short of the joint, so a surface it touches does not count as cover.
			var short := point.move_toward(eye, 0.03)
			var ray := PhysicsRayQueryParameters3D.create(eye, short, 3, exclude + [person.get_rid()])
			if not space.intersect_ray(ray).is_empty():
				continue
			var margin := Person.LIMB_RADIUS * focal / eye.distance_to(point)
			var around := Rect2(pixel - Vector2(margin, margin), Vector2(margin, margin) * 2)
			box = around if visible == 0 else box.merge(around)
			visible += 1
		if visible == 0:
			continue
		box = box.intersection(frame)
		out.append({
			"id": person.id,
			"bbox": [
				snappedf(box.position.x, 0.1), snappedf(box.position.y, 0.1),
				snappedf(box.size.x, 0.1), snappedf(box.size.y, 0.1),
			],
			"visibility": snappedf(float(visible) / points.size(), 0.01),
		})
	return out


func _is_clear(point: Vector3) -> bool:
	for b: Array in _blockers:
		if Vector2(point.x - b[0], point.z - b[1]).length() < b[2] + CLEARANCE:
			return false
	return true
