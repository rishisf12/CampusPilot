"""LangGraph state machine orchestrating the agent pipeline."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from .llm.router import LLMRouter
from .schemas.pipeline import PipelineState
from .nodes.plan_queries import plan_queries
from .nodes.search import search
from .nodes.filter_candidates import filter_candidates
from .nodes.trace_source import trace_source
from .nodes.fetch_extract import fetch_extract
from .nodes.verify import verify
from .nodes.generate_template import generate_template
from .nodes.save_draft import save_draft


class AgentPipeline:
    """
    Fixed-stage deterministic pipeline for opportunity discovery.
    Uses a simple sequential graph - no LLM-chosen tool calls.
    """

    STAGES = [
        "plan_queries",
        "search",
        "filter_candidates",
        "trace_source",
        "fetch_extract",
        "verify",
        "generate_template",
        "save_draft",
    ]

    def __init__(self, llm: LLMRouter):
        self.llm = llm

    async def run(
        self,
        run_id: Optional[str] = None,
        mode: str = "manual",
        db: Optional[AsyncSession] = None,
        resume_from: Optional[str] = None,
    ) -> PipelineState:
        """
        Execute the full pipeline.

        Args:
            run_id: Unique run identifier
            mode: Run mode (manual, scheduled, dry_run)
            db: Database session
            resume_from: Stage name to resume from (for checkpoint recovery)
        """
        run_id = run_id or str(uuid.uuid4())
        state = PipelineState(
            run_id=run_id,
            mode=mode,
            current_stage="init",
        )

        # Resume from checkpoint if specified
        if resume_from and resume_from in self.STAGES:
            start_idx = self.STAGES.index(resume_from)
            state.stages_completed = self.STAGES[:start_idx]
            state.current_stage = resume_from
        else:
            start_idx = 0

        # Execute stages sequentially
        stage_methods = [
            ("plan_queries", self._run_stage(plan_queries, state, db)),
            ("search", self._run_stage(search, state, db)),
            ("filter_candidates", self._run_stage(filter_candidates, state, db)),
            ("trace_source", self._run_stage(trace_source, state, db)),
            ("fetch_extract", self._run_stage(fetch_extract, state, db)),
            ("verify", self._run_stage(verify, state, db)),
            ("generate_template", self._run_stage(generate_template, state, db)),
            ("save_draft", self._run_stage(save_draft, state, db)),
        ]

        for i, (stage_name, coro) in enumerate(stage_methods[start_idx:], start_idx):
            try:
                state = await coro
            except Exception as e:
                state.errors.append({
                    "stage": stage_name,
                    "error": str(e),
                })
                state.checkpoint = state.to_checkpoint()
                raise

        return state

    async def _run_stage(self, stage_func, state: PipelineState, db: AsyncSession):
        """Execute a single pipeline stage."""
        state.current_stage = stage_func.__name__
        # Attribute every LLM call made inside this stage to its run/stage on
        # the oppfeed_llm_usage rows the admin status panel reads.
        self.llm.current_run_id = state.run_id
        self.llm.current_step = stage_func.__name__
        try:
            result = await stage_func(state, db=db, llm=self.llm) if "llm" in stage_func.__code__.co_varnames else await stage_func(state, db=db)
            state.checkpoint = state.to_checkpoint()
            return result
        except Exception as e:
            state.errors.append({
                "stage": stage_func.__name__,
                "error": str(e),
            })
            state.checkpoint = state.to_checkpoint()
            raise

    async def run_stage(self, stage_name: str, state: PipelineState, db: AsyncSession) -> PipelineState:
        """Run a single stage by name (for testing/debugging)."""
        stage_methods = {
            "plan_queries": plan_queries,
            "search": search,
            "filter_candidates": filter_candidates,
            "trace_source": trace_source,
            "fetch_extract": fetch_extract,
            "verify": verify,
            "generate_template": generate_template,
            "save_draft": save_draft,
        }

        if stage_name not in stage_methods:
            raise ValueError(f"Unknown stage: {stage_name}")

        stage_func = stage_methods[stage_name]
        return await self._run_stage(stage_func, state, db)
