"""Declarative base for the tables the agent owns.

The agent ships in the same repository as the FastAPI backend, which maps its
own ``oppfeed_llm_cache`` / ``oppfeed_search_query`` / ``oppfeed_source_rule`` /
``oppfeed_feedback`` tables.  SQLModel puts every model on one global metadata
by default, so importing the agent inside the backend process (which it does to
run a pipeline) would collide with those definitions.

Registering the agent's tables on their own registry keeps both packages
independently importable in either order: the agent still never imports the web
layer, and the backend only needs the package directory on ``sys.path``.
"""

from sqlalchemy.orm import registry as sa_registry
from sqlmodel import MetaData, SQLModel

#: Registry holding the agent-owned tables (drafts, verifications, LLM cache,
#: search queries, source rules, feedback).
agent_registry = sa_registry(metadata=MetaData())


class AgentBase(SQLModel, registry=agent_registry):
    """Base class for agent-owned SQLModel tables."""

    pass
