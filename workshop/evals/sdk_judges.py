"""Compatibility adapter for the pinned azure-ai-evaluation 1.18.6 SDK.

Its reasoning option replaces native output budgets with 60,000 tokens. Keep the
native budgets instead, with reasoning disabled for the workshop deployments.
The SDK has no evaluator-level parameter override, so isolate its private flow
access here. The setter also handles GroundednessEvaluator reloading its prompt.
"""

from __future__ import annotations

from typing import Any

from azure.ai.evaluation import (
    GroundednessEvaluator as _GroundednessEvaluator,
    IntentResolutionEvaluator as _IntentResolutionEvaluator,
    RelevanceEvaluator as _RelevanceEvaluator,
    TaskAdherenceEvaluator as _TaskAdherenceEvaluator,
    ToolCallAccuracyEvaluator as _ToolCallAccuracyEvaluator,
)
from azure.ai.evaluation._legacy.prompty import AsyncPrompty


class _NativeBudgetMixin:
    def __init__(self, *args: Any, is_reasoning_model: bool = False, **kwargs: Any) -> None:
        self._workshop_reasoning = is_reasoning_model
        super().__init__(*args, is_reasoning_model=False, **kwargs)

    @property
    def _flow(self) -> AsyncPrompty:
        return self._workshop_flow

    @_flow.setter
    def _flow(self, flow: AsyncPrompty) -> None:
        if self._workshop_reasoning:
            parameters = flow._model.parameters
            budget = parameters.get("max_tokens", parameters.get("max_completion_tokens"))
            if not isinstance(budget, int) or budget <= 0 or budget > 5000:
                raise RuntimeError(
                    "Unexpected SDK judge output budget; check the azure-ai-evaluation 1.18.6 pin."
                )
            parameters.pop("max_tokens", None)
            parameters["max_completion_tokens"] = budget
            parameters["reasoning_effort"] = "none"
            for key in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
                parameters.pop(key, None)
        self._workshop_flow = flow


class IntentResolutionEvaluator(_NativeBudgetMixin, _IntentResolutionEvaluator):
    pass


class TaskAdherenceEvaluator(_NativeBudgetMixin, _TaskAdherenceEvaluator):
    pass


class ToolCallAccuracyEvaluator(_NativeBudgetMixin, _ToolCallAccuracyEvaluator):
    pass


class GroundednessEvaluator(_NativeBudgetMixin, _GroundednessEvaluator):
    pass


class RelevanceEvaluator(_NativeBudgetMixin, _RelevanceEvaluator):
    pass
