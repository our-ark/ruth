"""UAAP messages and bidirectional context exchanged with an application.

Context contents belong to the application domain. The SDK defines the envelope;
the agent and app separately enforce authorization and disclosure policies.
"""
from typing import Any, Literal, NotRequired, TypedDict


class ActivityEvent(TypedDict):
    event_id: str
    app_id: str
    session_id: str
    type: Literal["context.updated", "presence.updated"]
    sequence: int
    cursor: int
    received_at: float
    context: NotRequired[dict[str, Any]]
    state: NotRequired[Literal["active", "inactive"]]
    expires_at: NotRequired[float]


class ActivityBatch(TypedDict):
    events: list[ActivityEvent]
    cursor: int
    server_time: float


class UserMessage(TypedDict):
    id: str
    text: str


class AppEvent(TypedDict):
    """App -> agent: a user message and its app-provided context snapshot."""

    event_id: str
    session_id: str
    message: UserMessage
    context: dict[str, Any]
    created_at: float
    cursor: int


class EventBatch(TypedDict):
    events: list[AppEvent]
    cursor: int


class AgentOutput(TypedDict):
    """Agent -> app: a reply and selected user context authorized for this app."""

    id: str
    in_reply_to: str
    text: str
    shared_context: NotRequired[dict[str, Any]]
