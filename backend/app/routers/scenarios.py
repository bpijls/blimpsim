from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import ScenarioParams, World
from app.database import get_db
from app.models import Scenario
from app.schemas import ScenarioIn, ScenarioOut, ScenarioSummary
from app.services.worldgen import generate_world

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


async def get_scenario_or_404(scenario_id: str, db: AsyncSession) -> Scenario:
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "Scenario not found")
    return scenario


@router.get("", response_model=list[ScenarioSummary])
async def list_scenarios(db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Scenario).order_by(Scenario.created_at.desc()))).all())


@router.post("", response_model=ScenarioOut, status_code=201)
async def create_scenario(payload: ScenarioIn, db: AsyncSession = Depends(get_db)):
    world = generate_world(payload.params)
    scenario = Scenario(
        name=payload.name, params=payload.params.model_dump(), world=world.model_dump(mode="json")
    )
    db.add(scenario)
    await db.commit()
    return scenario


@router.post("/preview", response_model=World)
async def preview_world(params: ScenarioParams):
    """Generate a world without saving it, for tuning parameters in the monitor."""
    return generate_world(params)


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    return await get_scenario_or_404(scenario_id, db)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    await db.delete(await get_scenario_or_404(scenario_id, db))
    await db.commit()
