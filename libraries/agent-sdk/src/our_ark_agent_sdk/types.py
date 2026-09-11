"""UAAP messages and bidirectional context exchanged with an application.

Context contents belong to the application domain. The SDK defines the envelope;
the agent and app separately enforce authorization and disclosure policies.
"""
from typing import Any, NotRequired, TypedDict


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
