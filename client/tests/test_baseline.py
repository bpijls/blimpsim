import pytest

from blimpsim_client import VisualServo, tracking_reward

W, H = 640, 480


def box(cx: float, cy: float, visibility: float = 1.0) -> dict:
    return {"id": 1, "bbox": [cx - 10, cy - 30, 20, 60], "visibility": visibility}


def test_searches_by_turning_when_target_is_not_in_view():
    surge, yaw, heave = VisualServo().act(None, W, H)
    assert (surge, heave) == (0, 0)
    assert yaw > 0


def test_turns_towards_the_target():
    servo = VisualServo()
    assert servo.act(box(500, 240), W, H)[1] < 0  # target on the right: turn right
    assert servo.act(box(100, 240), W, H)[1] > 0


def test_closes_in_when_far_and_backs_off_when_close():
    servo = VisualServo()
    assert servo.act(box(320, 80), W, H)[0] > 0  # high in the frame: far away
    assert servo.act(box(320, 440), W, H)[0] < 0


def test_holds_still_when_target_is_where_it_should_be():
    assert list(VisualServo().act(box(320, 240), W, H)) == [0, 0, 0]


def test_does_not_advance_while_the_target_is_far_off_to_the_side():
    assert VisualServo().act(box(635, 80), W, H)[0] == pytest.approx(0, abs=0.05)


def test_commands_stay_in_range():
    for cx, cy in [(0, 0), (640, 480), (0, 480), (640, 0)]:
        assert all(-1 <= value <= 1 for value in VisualServo().act(box(cx, cy), W, H))


def test_reward_is_highest_when_centred_and_scales_with_visibility():
    assert tracking_reward(box(320, 240), W, H) == pytest.approx(1.0)
    assert tracking_reward(box(320, 240, 0.5), W, H) == pytest.approx(0.5)
    assert tracking_reward(box(600, 240), W, H) < tracking_reward(box(400, 240), W, H)
    assert tracking_reward(None, W, H) == 0


def test_brakes_when_the_target_is_sweeping_across_the_frame():
    servo = VisualServo()
    servo.act(box(120, 240), W, H)
    # Still left of centre, but closing fast: steer against the swing, not into it.
    assert servo.act(box(280, 240), W, H)[1] < 0


def test_losing_the_target_forgets_its_motion():
    servo = VisualServo()
    servo.act(box(120, 240), W, H)
    servo.act(None, W, H)
    assert servo.act(box(280, 240), W, H)[1] > 0
