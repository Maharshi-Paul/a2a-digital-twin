"""Generic simulation engine — seeds databases from config using domain factories.

Domains register *factory functions* for each ``entity_type`` they support.
The engine iterates ``SimulationConfig.entities`` and delegates creation to
the matching factory, making the seeding loop entirely domain-agnostic.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable, Coroutine
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from core.simulation.config import EntityProfile, SimulationConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class EntityFactory(Protocol):
    """Protocol for domain-specific entity factory functions.

    A factory receives an ``AsyncSession`` and an ``EntityProfile`` and
    creates the corresponding ORM objects, returning a count of created
    entities.
    """

    async def __call__(
        self, session: AsyncSession, profile: EntityProfile
    ) -> int: ...


# Global registry: ``entity_type`` → factory callable
_factory_registry: dict[str, Callable[..., Coroutine[Any, Any, int]]] = {}


def register_entity_factory(entity_type: str, factory: Callable[..., Coroutine[Any, Any, int]]) -> None:
    """Register a factory function for a given entity type.

    Args:
        entity_type: Key that matches ``EntityProfile.entity_type``.
        factory:     Async callable ``(session, profile) -> int``.
    """
    _factory_registry[entity_type] = factory
    logger.debug("Registered entity factory for type: %s", entity_type)


def get_registered_factories() -> dict[str, Callable[..., Coroutine[Any, Any, int]]]:
    """Return a snapshot of all registered factories."""
    return dict(_factory_registry)


class SimulationEngine:
    """Domain-agnostic simulation engine.

    Usage::

        # 1. Domain registers its factories at import time
        register_entity_factory("zone", create_zones)
        register_entity_factory("sku", create_skus)

        # 2. At startup, build a config and seed
        engine = SimulationEngine(config)
        counts = await engine.seed(session)
    """

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config

    async def seed(self, session: AsyncSession) -> dict[str, int]:
        """Seed the database using the configured entity profiles.

        Sets the random seed for reproducibility, then iterates each
        ``EntityProfile`` and invokes the registered factory.

        Returns:
            Mapping of ``entity_type`` → number of entities created.
        """
        random.seed(self.config.seed)
        counts: dict[str, int] = {}

        for profile in self.config.entities:
            factory = _factory_registry.get(profile.entity_type)
            if factory is None:
                logger.warning(
                    "No factory registered for entity type '%s' — skipping",
                    profile.entity_type,
                )
                continue

            try:
                created = await factory(session, profile)
                counts[profile.entity_type] = created
                logger.info(
                    "Seeded %d × %s (domain=%s)",
                    created,
                    profile.entity_type,
                    self.config.domain,
                )
            except Exception:
                logger.exception(
                    "Failed to seed entity type '%s'", profile.entity_type
                )

        await session.flush()
        logger.info(
            "Simulation seed complete (domain=%s): %s",
            self.config.domain,
            counts,
        )
        return counts
