"""OMNIX Front Door Adapter.

OMNIX is ONE project under Jarvis — not the default, not the root.
This adapter enriches requests that target the OMNIX project with
OMNIX-specific project context (memory namespace, repo path, etc.).

The JarvisFrontDoor works completely without this adapter. It is
optional enrichment for OMNIX-specific routing decisions.
"""

from __future__ import annotations

from openjarvis.frontdoor.frontdoor import FrontDoorAdapter, FrontDoorResult, UniversalTaskRequest
from openjarvis.orchestrator.contracts import ProjectContext, TASK_TYPE_CODING


class OmnixFrontDoorAdapter(FrontDoorAdapter):
    """Optional adapter that enriches requests targeting the OMNIX project.

    Provides OMNIX-specific ProjectContext (repo path, memory namespace,
    deploy gates) when the request targets OMNIX.

    This adapter does NOT make OMNIX the default or global entry point.
    """

    @property
    def adapter_id(self) -> str:
        return "omnix"

    def can_handle(self, request: UniversalTaskRequest) -> bool:
        """Return True if this request targets OMNIX."""
        ctx = request.project_context
        if ctx and ctx.project_id == "omnix":
            return True
        # Also handle intent-based routing
        intent_lower = request.intent.lower()
        return "omnix" in intent_lower

    def enrich(self, request: UniversalTaskRequest) -> UniversalTaskRequest:
        """Attach OMNIX ProjectContext if not already present."""
        if request.project_context is not None:
            return request  # already has context

        try:
            from openjarvis.governance.constitution import OMNIX_PROJECT
            ctx = ProjectContext.for_project(
                project_id=OMNIX_PROJECT.project_id,
                display_name=OMNIX_PROJECT.display_name,
                task_type=TASK_TYPE_CODING,
                repo_path=OMNIX_PROJECT.repo_path,
                memory_namespace=OMNIX_PROJECT.memory_namespace,
            )
        except Exception:
            ctx = ProjectContext.for_project(
                project_id="omnix",
                display_name="OMNIX",
                task_type=TASK_TYPE_CODING,
            )

        # Return a new request with OMNIX context attached
        import dataclasses
        return dataclasses.replace(request, project_context=ctx)

    def post_process(
        self,
        request: UniversalTaskRequest,
        result: FrontDoorResult,
    ) -> FrontDoorResult:
        """Tag OMNIX-specific metadata into result."""
        import dataclasses
        updated_meta = dict(result.metadata)
        updated_meta["omnix_adapter_applied"] = True
        return dataclasses.replace(result, metadata=updated_meta)
