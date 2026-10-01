class_name NetClient
extends Node
# WebSocket client to the gateway. Reconnects forever; the sim is useless alone.

signal connected
signal message(data: Dictionary)

const RETRY_SECONDS := 2.0
const BUFFER_BYTES := 8 * 1024 * 1024

var _url: String
var _socket: WebSocketPeer
var _open := false
var _retry_at_msec := 0


func _init(url: String) -> void:
	_url = url
	process_mode = Node.PROCESS_MODE_ALWAYS


func _process(_delta: float) -> void:
	if _socket == null:
		if Time.get_ticks_msec() >= _retry_at_msec:
			_connect()
		return

	_socket.poll()
	match _socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _open:
				_open = true
				print("gateway connected")
				connected.emit()
			while _socket.get_available_packet_count() > 0:
				var packet := _socket.get_packet()
				if _socket.was_string_packet():
					var data: Variant = JSON.parse_string(packet.get_string_from_utf8())
					if data is Dictionary:
						message.emit(data)
		WebSocketPeer.STATE_CLOSED:
			if _open:
				print("gateway disconnected")
			_open = false
			_socket = null
			_retry_at_msec = Time.get_ticks_msec() + int(RETRY_SECONDS * 1000)


func send_json(data: Dictionary) -> void:
	if _open:
		_socket.send_text(JSON.stringify(data))


func send_bytes(data: PackedByteArray) -> void:
	if _open:
		_socket.send(data)


func _connect() -> void:
	_socket = WebSocketPeer.new()
	# Defaults are 64 KiB: too small for a world description or a JPEG frame.
	_socket.inbound_buffer_size = BUFFER_BYTES
	_socket.outbound_buffer_size = BUFFER_BYTES
	if _socket.connect_to_url(_url) != OK:
		_socket = null
		_retry_at_msec = Time.get_ticks_msec() + int(RETRY_SECONDS * 1000)
