from functools import lru_cache

from app.config import settings
from app.services.drivers.base import BlimpDriver, DriverUnavailable
from app.services.drivers.real import RealDriver
from app.services.drivers.sim import SimDriver

__all__ = ["BlimpDriver", "DriverUnavailable", "get_driver"]

DRIVERS: dict[str, type[BlimpDriver]] = {"sim": SimDriver, "real": RealDriver}


@lru_cache
def get_driver() -> BlimpDriver:
    """FastAPI dependency: the driver selected by BLIMP_DRIVER."""
    if settings.blimp_driver not in DRIVERS:
        raise RuntimeError(f"BLIMP_DRIVER must be one of {sorted(DRIVERS)}")
    return DRIVERS[settings.blimp_driver]()
