from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import BlimpProfile, ScenarioParams, World


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    params: ScenarioParams = ScenarioParams()


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    params: ScenarioParams
    created_at: datetime


class ScenarioOut(ScenarioSummary):
    world: World


class RunIn(BaseModel):
    scenario_id: str
    mode: Literal["realtime", "lockstep"] = "realtime"
    profile: BlimpProfile = BlimpProfile()
    profile_spread: float = Field(
        0.0, ge=0, le=0.9, description="Random variation of the airframe parameters, 0.2 = ±20%"
    )
    profile_seed: int = 0


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_id: str
    mode: str
    profile: BlimpProfile
    started_at: datetime


class CurrentRun(RunOut):
    """The latest run with its world, so the monitor can redraw after a reload."""

    world: World
