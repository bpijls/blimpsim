"""Tests run against SQLite in memory — no Docker, no postgres, no simulator."""
import os

# Set before importing anything from app/: config and database read these at
# import time. Unconditional, so a DATABASE_URL in your shell can never point
# the suite at a real database.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("SIM_SECRET", "test-secret")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401 — registers ORM tables
from app.contracts import BlimpCommand  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.drivers import BlimpDriver, DriverUnavailable, get_driver  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    await engine.dispose()


class FakeDriver(BlimpDriver):
    """Records what the api asks of the blimp; no simulator involved."""

    name = "fake"

    def __init__(self) -> None:
        self.loaded: list[tuple] = []
        self.commands: list[BlimpCommand] = []
        self.unavailable = False
        self.telemetry_messages: list[dict] = []

    def _check(self) -> None:
        if self.unavailable:
            raise DriverUnavailable("simulator is not connected")

    async def status(self) -> dict:
        return {"driver": self.name, "reachable": not self.unavailable}

    async def load(self, world, profile, mode) -> None:
        self._check()
        self.loaded.append((world, profile, mode))

    async def send(self, command) -> None:
        self._check()
        self.commands.append(command)

    async def telemetry(self):
        self._check()
        for message in self.telemetry_messages:
            yield message

    async def camera(self):
        self._check()
        yield b"--frame\r\n"


@pytest.fixture
def driver():
    fake = FakeDriver()
    app.dependency_overrides[get_driver] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_driver, None)


@pytest_asyncio.fixture
async def client(db_session, driver):
    """HTTP client with the DB and the blimp driver pointed at test doubles."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
