"""Shared pytest fixtures: in-memory DB, app instance, HTTP clients, user factory."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only-x")
os.environ.setdefault("ML_ENABLED", "false")

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import app.models  # noqa: F401  (populate metadata)
import pytest
import pytest_asyncio
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models.enums import UserRole
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_PASSWORD = "Sup3r-Secret-Passphrase!"


@pytest_asyncio.fixture
async def engine() -> AsyncIterator:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


UserFactory = Callable[..., Awaitable[User]]


@pytest_asyncio.fixture
async def make_user(db_session: AsyncSession) -> UserFactory:
    counter = {"n": 0}

    async def _make(
        *,
        role: UserRole = UserRole.VIEWER,
        email: str | None = None,
        password: str = DEFAULT_PASSWORD,
        is_active: bool = True,
        full_name: str = "Test User",
    ) -> User:
        counter["n"] += 1
        user = User(
            email=email or f"user{counter['n']}@test.local",
            full_name=full_name,
            role=role,
            is_active=is_active,
            hashed_password=hash_password(password),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make


@pytest_asyncio.fixture
async def admin(make_user: UserFactory) -> User:
    return await make_user(role=UserRole.ADMIN, email="admin@test.local")


@pytest_asyncio.fixture
async def analyst(make_user: UserFactory) -> User:
    return await make_user(role=UserRole.ANALYST, email="analyst@test.local")


@pytest_asyncio.fixture
async def auditor(make_user: UserFactory) -> User:
    return await make_user(role=UserRole.AUDITOR, email="auditor@test.local")


@pytest_asyncio.fixture
async def viewer(make_user: UserFactory) -> User:
    return await make_user(role=UserRole.VIEWER, email="viewer@test.local")


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def as_user(client: AsyncClient) -> Callable[[User], AsyncClient]:
    """Return the shared client with the Authorization header bound to a user."""

    def _bind(user: User) -> AsyncClient:
        client.headers.update(auth_headers(user))
        return client

    return _bind


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


# ---- demo PKI (shared across crypto + detection tests) ----


@pytest.fixture(scope="session")
def demo_pki():
    from gen_test_pki import build_demo_pki

    return build_demo_pki()


def sign_bytes(
    key, message: bytes, *, hash_name: str = "sha256", rsa_padding: str = "pss"
) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

    halg = {
        "sha256": hashes.SHA256(),
        "sha384": hashes.SHA384(),
        "sha512": hashes.SHA512(),
    }[hash_name]
    if isinstance(key, rsa.RSAPrivateKey):
        pad = (
            padding.PSS(mgf=padding.MGF1(halg), salt_length=padding.PSS.DIGEST_LENGTH)
            if rsa_padding == "pss"
            else padding.PKCS1v15()
        )
        return key.sign(message, pad, halg)
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return key.sign(message, ec.ECDSA(halg))
    if isinstance(key, ed25519.Ed25519PrivateKey):
        return key.sign(message)
    raise TypeError(f"unsupported key type {type(key)}")
