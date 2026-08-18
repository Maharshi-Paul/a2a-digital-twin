"""Domain-agnostic simulation configuration models.

These Pydantic models describe *what* to seed and *how fast* events arrive,
without coupling to any specific domain.  A warehouse, airport, or hospital
can each provide its own ``SimulationConfig`` instance and the generic
``SimulationEngine`` will use it without modification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityProfile(BaseModel):
    """Describes a single category of entities to seed.

    Attributes:
        entity_type: Logical type key (e.g. ``"zone"``, ``"worker"``).
                     Must match a factory registered with ``SimulationEngine``.
        count:       Number of instances to create.
        attributes:  Arbitrary dict passed to the domain factory function so
                     it can set names, defaults, ranges, etc.
    """

    entity_type: str
    count: int = 1
    attributes: dict = Field(default_factory=dict)


class ArrivalRateConfig(BaseModel):
    """Poisson arrival-rate parameters for event generation.

    Attributes:
        lambda_per_minute: Default λ (events / minute).
        min_lambda:        Lower bound for dynamic rate adjustment.
        max_lambda:        Upper bound for dynamic rate adjustment.
        sla_window_minutes: (min, max) SLA deadline range in minutes.
        items_per_event:    (min, max) number of sub-items per event.
        max_interval_seconds: Cap on the exponential inter-arrival interval
                              to prevent long idle periods.
    """

    lambda_per_minute: float = 3.0
    min_lambda: float = 0.5
    max_lambda: float = 10.0
    sla_window_minutes: tuple[int, int] = (15, 60)
    items_per_event: tuple[int, int] = (1, 5)
    max_interval_seconds: float = 30.0


class ResourceConstraints(BaseModel):
    """Global resource bounds that apply to the entire simulation.

    Attributes:
        max_concurrent_tasks: Soft ceiling on in-flight work items.
        capacity_limits:      Domain-specific limits keyed by resource name.
    """

    max_concurrent_tasks: int = 50
    capacity_limits: dict[str, int] = Field(default_factory=dict)


class SimulationConfig(BaseModel):
    """Top-level simulation configuration.

    Combines entity definitions, arrival rates, and resource constraints
    into a single portable config object.

    Attributes:
        domain:    Logical domain name (``"warehouse"``, ``"airport"``, …).
        seed:      Random seed for reproducibility.
        entities:  List of entity profiles to seed.
        arrival_rate: Poisson arrival-rate configuration.
        resources: Global resource constraint configuration.
    """

    domain: str = "warehouse"
    seed: int = 42
    entities: list[EntityProfile] = Field(default_factory=list)
    arrival_rate: ArrivalRateConfig = Field(default_factory=ArrivalRateConfig)
    resources: ResourceConstraints = Field(default_factory=ResourceConstraints)
