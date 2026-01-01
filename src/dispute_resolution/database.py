from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


def _coerce_async_dsn(dsn: str) -> str:
    """
    Ensure the DSN uses the async driver.
    """
    if "://" not in dsn:
        return dsn

    scheme, rest = dsn.split("://", 1)
    if "+asyncpg" in scheme:
        return dsn

    if scheme.startswith("postgresql"):
        return f"postgresql+asyncpg://{rest}"

    return dsn


engine = create_async_engine(_coerce_async_dsn(settings.POSTGRES_DSN), echo=False, future=True)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
