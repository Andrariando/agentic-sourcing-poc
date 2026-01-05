"""
Tasks module - Sub-tasks for each agent.

Sub-tasks implement the decision logic hierarchy:
1. Deterministic rules/policy checks first
2. Retrieval second (ChromaDB + SQLite)
3. Analytics third (scoring/normalization/comparison)
4. LLM narration/packaging ONLY after 1-3

These are internal to agents and NOT exposed separately in UI.
"""
from backend.tasks.registry import TaskRegistry, get_task_registry
from backend.tasks.base_task import BaseTask, TaskResult

__all__ = [
    "TaskRegistry",
    "get_task_registry",
    "BaseTask",
    "TaskResult",
]



