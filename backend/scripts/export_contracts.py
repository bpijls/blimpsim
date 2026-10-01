"""Regenerate /contracts/*.schema.json from app/contracts.py.

    cd backend && ../.venv/bin/python scripts/export_contracts.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts import SCHEMAS  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "contracts"


def render(name: str) -> str:
    return json.dumps(SCHEMAS[name].model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name in SCHEMAS:
        (OUT / f"{name}.schema.json").write_text(render(name))
        print(f"wrote contracts/{name}.schema.json")
