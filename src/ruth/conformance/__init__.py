"""Reusable conformance suites for Ruth extension implementations."""

from ruth.runtime_dependencies import activate_runtime_dependencies


activate_runtime_dependencies()

from our_ark_provider_kit.conformance import (
    CONFORMANCE_API_VERSION,
    AgentRuntimeConformanceMixin,
    ProviderContractConformanceMixin,
    RepositoryProviderConformanceMixin,
    ReviewProviderConformanceMixin,
)

from ruth.conformance.profile import ProfileCommandCase, ProfileConformanceMixin
from ruth.conformance.application import ApplicationCompositionConformanceMixin
from ruth.conformance.extension import (
    AgentExtensionConformanceMixin,
    ExtensionCommandCase,
)
from ruth.conformance.notification import DurableNotificationConformanceMixin
from ruth.conformance.schedule import ExtensionScheduleConformanceMixin
from ruth.conformance.workflow import WorkflowEngineConformanceMixin


__all__ = [
    "CONFORMANCE_API_VERSION",
    "AgentRuntimeConformanceMixin",
    "ApplicationCompositionConformanceMixin",
    "AgentExtensionConformanceMixin",
    "DurableNotificationConformanceMixin",
    "ExtensionCommandCase",
    "ExtensionScheduleConformanceMixin",
    "ProfileCommandCase",
    "ProfileConformanceMixin",
    "ProviderContractConformanceMixin",
    "RepositoryProviderConformanceMixin",
    "ReviewProviderConformanceMixin",
    "WorkflowEngineConformanceMixin",
]
