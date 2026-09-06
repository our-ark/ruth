from __future__ import annotations

from contextvars import ContextVar

from ruth.app.models import WorkStatusMessage
from ruth.prompt_append import TaskRegressionSignal


CURRENT_WORK_STATUS: ContextVar[WorkStatusMessage | None] = ContextVar(
    "ruth_work_status",
    default=None,
)
CURRENT_TASK_ID: ContextVar[int | None] = ContextVar("ruth_task_id", default=None)
CURRENT_TASK_WORKER_ID: ContextVar[str] = ContextVar(
    "ruth_task_worker_id",
    default="",
)
CURRENT_REGRESSION_SIGNALS: ContextVar[tuple[TaskRegressionSignal, ...]] = ContextVar(
    "ruth_regression_signals",
    default=(),
)
