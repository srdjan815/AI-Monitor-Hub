from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from app.core.config import settings

# Create async engine with database configuration
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.database_echo,
)
