extends Node3D
# Renders a hall-sized scene with ~200 capsule "people", reads every frame back
# from the GPU as JPEG, and reports the achieved frame rate.

const WARMUP := 30
const FRAMES := 150

var _count := 0
var _start_usec := 0
var _jpeg_bytes := 0


func _ready() -> void:
	var cam := Camera3D.new()
	cam.position = Vector3(0, 8, 20)
	add_child(cam)
	cam.look_at(Vector3.ZERO)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	add_child(sun)

	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60, 40)
	ground.mesh = plane
	add_child(ground)

	var rng := RandomNumberGenerator.new()
	rng.seed = 1
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.25
	capsule.height = 1.8
	for i in 200:
		var person := MeshInstance3D.new()
		person.mesh = capsule
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color.from_hsv(rng.randf(), 0.6, 0.8)
		person.material_override = mat
		person.position = Vector3(rng.randf_range(-28, 28), 0.9, rng.randf_range(-18, 18))
		add_child(person)

	print("SPIKE adapter=%s vendor=%s api=%s driver=%s" % [
		RenderingServer.get_video_adapter_name(),
		RenderingServer.get_video_adapter_vendor(),
		RenderingServer.get_video_adapter_api_version(),
		RenderingServer.get_current_rendering_driver_name(),
	])
	RenderingServer.frame_post_draw.connect(_on_frame)


func _on_frame() -> void:
	var img := get_viewport().get_texture().get_image()
	var jpg := img.save_jpg_to_buffer(0.8)
	_count += 1
	if _count == WARMUP:
		_start_usec = Time.get_ticks_usec()
	elif _count > WARMUP:
		_jpeg_bytes += jpg.size()
	if _count < WARMUP + FRAMES:
		return
	RenderingServer.frame_post_draw.disconnect(_on_frame)

	var secs := (Time.get_ticks_usec() - _start_usec) / 1e6
	print("SPIKE fps=%.1f size=%dx%d jpeg_avg=%d" % [
		FRAMES / secs, img.get_width(), img.get_height(), _jpeg_bytes / FRAMES,
	])
	var out := OS.get_environment("SPIKE_OUT")
	if out != "":
		var f := FileAccess.open(out, FileAccess.WRITE)
		f.store_buffer(jpg)
		f.close()
	get_tree().quit()
