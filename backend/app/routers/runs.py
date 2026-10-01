from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import World
from app.database import get_db
from app.models import Run, Scenario
from app.routers.scenarios import get_scenario_or_404
from app.schemas import CurrentRun, RunIn, RunOut
from app.services.drivers import BlimpDriver, DriverUnavailable, get_driver
from app.services.profile import jitter_profile

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def start_run(
    payload: RunIn,
    db: AsyncSession = Depends(get_db),
    driver: BlimpDriver = Depends(get_driver),
):
    """Load a scenario into the simulator, replacing whatever was running."""
    scenario = await get_scenario_or_404(payload.scenario_id, db)
    profile = jitter_profile(payload.profile, payload.profile_spread, payload.profile_seed)
    try:
        await driver.load(World.model_validate(scenario.world), profile, payload.mode)
    except DriverUnavailable as e:
        raise HTTPException(503, str(e)) from e
    run = Run(scenario_id=scenario.id, mode=payload.mode, profile=profile.model_dump())
    db.add(run)
    await db.commit()
    return run


@router.get("", response_model=list[RunOut])
async def list_runs(db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Run).order_by(Run.started_at.desc()).limit(100))).all())


@router.get("/current", response_model=CurrentRun)
async def current_run(db: AsyncSession = Depends(get_db)):
    run = await db.scalar(select(Run).order_by(Run.started_at.desc()).limit(1))
    if run is None:
        raise HTTPException(404, "Nothing has been run yet")
    scenario = await db.get(Scenario, run.scenario_id)
    return {**RunOut.model_validate(run).model_dump(), "world": scenario.world}
