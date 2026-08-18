"""Core simulation framework — domain-agnostic config and engine."""

from core.simulation.config import (
    ArrivalRateConfig,
    EntityProfile,
    ResourceConstraints,
    SimulationConfig,
)
from core.simulation.engine import EntityFactory, SimulationEngine

__all__ = [
    "ArrivalRateConfig",
    "EntityFactory",
    "EntityProfile",
    "ResourceConstraints",
    "SimulationConfig",
    "SimulationEngine",
]
