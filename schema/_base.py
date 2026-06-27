"""Base model for every canonical DocVerify entity.

The canonical schema is authored here in Pydantic and is the single source of
truth for all four areas (ML, blockchain, backend, frontend). Python attributes
stay idiomatic ``snake_case``; the wire/JSON contract — and therefore the
generated TypeScript — is ``camelCase`` via the alias generator below.

Because FastAPI serialises response models with ``by_alias=True`` by default,
returning any of these models from an endpoint already emits camelCase JSON, and
``model_json_schema(by_alias=True)`` emits a camelCase JSON Schema that the
TypeScript generator consumes. ``populate_by_name=True`` keeps construction by
the snake_case field name working everywhere in the Python codebase (and in the
existing tests).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CanonicalModel(BaseModel):
    """Shared config: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )
