class_name HallBuilder
# Builds the hall from a world description (contracts/world.schema.json).
# The browser monitor builds its low-fidelity copy from the same description.

const WALL_THICKNESS := 0.3
const FLOOR_COLOR := Color(0.55, 0.55, 0.58)
const WALL_COLOR := Color(0.82, 0.8, 0.76)
const CEILING_COLOR := Color(0.9, 0.9, 0.9)
const PILLAR_COLOR := Color(0.7, 0.7, 0.72)
const OBSTACLE_COLORS := {
	"kiosk": Color(0.25, 0.4, 0.6),
	"bench": Color(0.45, 0.3, 0.2),
	"planter": Color(0.2, 0.45, 0.25),
}


static func build(world: Dictionary) -> Node3D:
	var root := Node3D.new()
	root.name = "Hall"
	var hall: Dictionary = world.hall
	var w: float = hall.width
	var d: float = hall.depth
	var h: float = hall.height
	var t := WALL_THICKNESS
	var look: Dictionary = world.get("look", {})
	var floor_color := _color(look.get("floor"), FLOOR_COLOR)
	var wall_color := _color(look.get("walls"), WALL_COLOR)
	var light_color := _color(look.get("light"), Color.WHITE)

	_box(root, Vector3(w, t, d), Vector3(0, -t / 2, 0), floor_color)
	_box(root, Vector3(w, t, d), Vector3(0, h + t / 2, 0), CEILING_COLOR)
	_box(root, Vector3(w, h, t), Vector3(0, h / 2, -d / 2 - t / 2), wall_color)
	_box(root, Vector3(w, h, t), Vector3(0, h / 2, d / 2 + t / 2), wall_color)
	_box(root, Vector3(t, h, d), Vector3(-w / 2 - t / 2, h / 2, 0), wall_color)
	_box(root, Vector3(t, h, d), Vector3(w / 2 + t / 2, h / 2, 0), wall_color)

	for p: Dictionary in world.pillars:
		_box(root, Vector3(p.size, h, p.size), Vector3(p.x, h / 2, p.z), PILLAR_COLOR)

	for o: Dictionary in world.obstacles:
		var color: Color = OBSTACLE_COLORS.get(o.kind, Color.GRAY)
		_box(root, Vector3(o.width, o.height, o.depth), Vector3(o.x, o.height / 2, o.z), color, o.yaw)

	for l: Dictionary in world.lights:
		var light := OmniLight3D.new()
		light.position = Vector3(l.position[0], l.position[1], l.position[2])
		light.light_energy = l.energy * 0.9
		light.omni_range = h * 2.0
		light.light_color = light_color
		root.add_child(light)

	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.1, 0.1, 0.12)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.WHITE
	env.ambient_light_energy = world.ambient
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	root.add_child(world_env)
	return root


static func _color(rgb: Variant, fallback: Color) -> Color:
	return Color(rgb[0], rgb[1], rgb[2]) if rgb is Array else fallback


static func _box(parent: Node3D, size: Vector3, pos: Vector3, color: Color, yaw := 0.0) -> void:
	var body := StaticBody3D.new()
	body.position = pos
	body.rotation.y = yaw

	var mesh := BoxMesh.new()
	mesh.size = size
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.9
	mesh.material = material
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	body.add_child(instance)

	var shape := BoxShape3D.new()
	shape.size = size
	var collider := CollisionShape3D.new()
	collider.shape = shape
	body.add_child(collider)
	parent.add_child(body)
