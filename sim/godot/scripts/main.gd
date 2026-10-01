extends Node3D
# Owns the simulation clock and the link to the gateway.
#
# Real-time mode: physics runs at 60 Hz wall-clock; telemetry goes out at 20 Hz
# and camera frames at the profile's fps.
# Lockstep mode: the tree stays paused until a "step" message asks for N ticks,
# then pauses again and answers with one frame. Same commands, same ticks,
# same result, and it runs faster than real time.

const TICKS_PER_SECOND := 60
const TELEMETRY_EVERY := 3
const JPEG_QUALITY := 0.85
const LOCKSTEP_SPEEDUP := 20

var _net: NetClient
var _viewport: SubViewport
var _camera: Camera3D
var _scene: Node3D  # everything that is simulated; pausable
var _blimp: Blimp
var _crowd: Crowd
var _load_message: Dictionary

var _tick := 0
var _frame := 0
var _frame_every := 4
var _lockstep := false
var _steps_left := 0
var _capture_pending := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	# Run after the blimp and the crowd, so a tick is counted once it is complete.
	process_physics_priority = 100

	_viewport = SubViewport.new()
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)
	_camera = Camera3D.new()
	_camera.cull_mask &= ~Blimp.RENDER_LAYER
	_viewport.add_child(_camera)

	var url := OS.get_environment("GATEWAY_WS_URL")
	if url == "":
		push_error("GATEWAY_WS_URL is not set")
		get_tree().quit(1)
		return
	url += "?secret=" + OS.get_environment("SIM_SECRET").uri_encode()
	_net = NetClient.new(url)
	_net.connected.connect(_on_connected)
	_net.message.connect(_on_message)
	add_child(_net)

	RenderingServer.frame_post_draw.connect(_after_draw)
	_set_lockstep(false)


func _on_connected() -> void:
	_net.send_json({
		"type": "hello",
		"godot": Engine.get_version_info().string,
		"adapter": RenderingServer.get_video_adapter_name(),
	})


func _on_message(msg: Dictionary) -> void:
	match msg.get("type"):
		"load":
			_load(msg)
		"reset":
			if not _load_message.is_empty():
				_load(_load_message)
		"command":
			if _blimp:
				_blimp.command(msg)
		"step":
			if _blimp and _lockstep:
				if msg.has("command"):
					_blimp.command(msg.command)
				_steps_left = maxi(1, int(msg.get("ticks", 1)))
				_set_paused(false)


func _load(msg: Dictionary) -> void:
	_load_message = msg
	if _scene:
		remove_child(_scene)
		_scene.queue_free()
	_scene = Node3D.new()
	_scene.process_mode = Node.PROCESS_MODE_PAUSABLE
	add_child(_scene)
	var hall := HallBuilder.build(msg.world)
	_scene.add_child(hall)
	_crowd = Crowd.new()
	_scene.add_child(_crowd)
	_crowd.setup(msg.world, hall)

	_blimp = Blimp.new()
	_scene.add_child(_blimp)
	_blimp.setup(msg.profile, msg.world.blimp_start)

	var cam: Dictionary = msg.profile.camera
	_viewport.size = Vector2i(cam.width, cam.height)
	_camera.fov = cam.fov_y_deg
	_frame_every = maxi(1, roundi(TICKS_PER_SECOND / cam.fps))
	_camera.global_transform = _blimp.camera_transform()

	_tick = 0
	_frame = 0
	_steps_left = 0
	_set_lockstep(msg.get("mode", "realtime") == "lockstep")
	_capture_pending = _lockstep  # lockstep answers the load with the first observation
	_net.send_json({"type": "loaded", "mode": "lockstep" if _lockstep else "realtime"})
	print("loaded world seed=%d mode=%s" % [msg.world.seed, msg.get("mode", "realtime")])


func _set_lockstep(enabled: bool) -> void:
	_lockstep = enabled
	_set_paused(enabled)
	# Scaling time and tick rate together keeps the physics delta at 1/60 s
	# while running that many more ticks per wall-clock second.
	var speedup := LOCKSTEP_SPEEDUP if enabled else 1
	Engine.time_scale = speedup
	Engine.physics_ticks_per_second = TICKS_PER_SECOND * speedup
	Engine.max_physics_steps_per_frame = 8 * speedup
	Engine.max_fps = 0 if enabled else TICKS_PER_SECOND


func _set_paused(paused: bool) -> void:
	get_tree().paused = paused
	# The navigation server ignores the tree's pause: left running, crowd
	# avoidance keeps evolving between steps and episodes stop being repeatable.
	NavigationServer3D.set_active(not paused)


func _physics_process(_delta: float) -> void:
	if _blimp == null or get_tree().paused:
		return
	_tick += 1
	if _lockstep:
		_steps_left -= 1
		if _steps_left <= 0:
			_set_paused(true)
			_capture_pending = true
		return
	if _tick % TELEMETRY_EVERY == 0:
		_net.send_json({"type": "telemetry", "telemetry": _telemetry()})
	if _tick % _frame_every == 0:
		_capture_pending = true


func _process(_delta: float) -> void:
	if _blimp:
		_camera.global_transform = _blimp.camera_transform()


func _after_draw() -> void:
	if not _capture_pending:
		return
	_capture_pending = false
	var jpeg := _viewport.get_texture().get_image().save_jpg_to_buffer(JPEG_QUALITY)
	# The gateway pairs each binary message with the frame header before it.
	_net.send_json({
		"type": "frame",
		"frame": _frame,
		"tick": _tick,
		"telemetry": _telemetry(),
		"labels": _labels(),
	})
	_net.send_bytes(jpeg)
	_frame += 1


func _telemetry() -> Dictionary:
	return {
		"t": snappedf(float(_tick) / TICKS_PER_SECOND, 0.001),
		"blimp": _blimp.state(),
		"people": _crowd.states(),
	}


func _labels() -> Dictionary:
	var q := _camera.global_transform.basis.get_rotation_quaternion()
	var at := _camera.global_position
	return {
		"frame": _frame,
		"t": snappedf(float(_tick) / TICKS_PER_SECOND, 0.001),
		"camera": {
			"width": _viewport.size.x,
			"height": _viewport.size.y,
			"fov_y_deg": _camera.fov,
			"position": [snappedf(at.x, 0.001), snappedf(at.y, 0.001), snappedf(at.z, 0.001)],
			"rotation": [q.x, q.y, q.z, q.w],
		},
		"people": _crowd.labels(_camera, _viewport.size, [_blimp.get_rid()]),
	}
