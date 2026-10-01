import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import SCHEMAS, BlimpCommand

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_contracts import OUT, render  # noqa: E402


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_exported_schema_is_current(name):
    """If this fails, rerun scripts/export_contracts.py and commit the result."""
    assert (OUT / f"{name}.schema.json").read_text() == render(name)


def test_command_defaults_to_idle():
    assert BlimpCommand().model_dump() == {
        "surge": 0.0, "yaw": 0.0, "heave": 0.0, "camera_tilt": None,
    }


def test_command_clamps_out_of_range_thrust():
    command = BlimpCommand(surge=3.5, yaw=-9, heave=0.25)
    assert (command.surge, command.yaw, command.heave) == (1.0, -1.0, 0.25)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "fast"])
def test_command_rejects_non_finite_thrust(bad):
    with pytest.raises(ValidationError):
        BlimpCommand(surge=bad)
