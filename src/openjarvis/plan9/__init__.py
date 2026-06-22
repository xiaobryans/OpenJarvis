"""Plan 9 — Full Cross-Device Jarvis Parity / Mobile-Cloud-MacBook Operator Completion.

Canonical machine-readable architecture for Plan 9. Every module here is
importable and testable. Extends existing systems — does not duplicate them.

Sections implemented:
  2.  All Managers / All Teams inventory + future-proof inheritance
  3.  Jarvis internal operating rules
  4.  Jarvis PA vs Brain layer
  5.  Role-based model routing matrix
  6.  Jarvis skills and commands manifests
  7.  Capability inventory matrix (CLOUD_LIVE / LOCAL_LIVE / CROSS_DEVICE_LIVE / …)
  8.  Retrieval / reader worker policy per team
  9.  Safe parallel execution / DAG policy
  10. Elastic same-role worker pools policy
  11. Same-file batch integration protocol
  12-15. Cloud operator (coding / test / commit / deploy)
  16-18. Cloud memory / connector / file-mirror parity
  19. Mac worker queue
  20. Capability-aware UI/API status
  21. Authority / approval / audit / rollback

Accepted permanent exceptions (§ Plan 9 scope):
  - Rebuilding/reinstalling /Applications/OpenJarvis.app → MacBook-only, not Plan 9.
  - Voice/wake/TTS → PARKED until Plan 10.
  - Apple signing/updater → PARKED until Plan 11.
  - Cursor rules → not part of Plan 9. Future roadmap.
"""

from openjarvis.plan9.capability_matrix import (
    CapabilityStatus,
    Plan9CapabilityEntry,
    Plan9CapabilityMatrix,
    get_plan9_capability_matrix,
)
from openjarvis.plan9.model_routing import (
    ModelTier,
    ModelRoutingEntry,
    RoleModelRoutingMatrix,
    get_role_routing_matrix,
)
from openjarvis.plan9.rules import PLAN9_INTERNAL_RULES, Plan9Rule
from openjarvis.plan9.pa_brain_layer import (
    JarvisLayer,
    JarvisPAConfig,
    JarvisBrainLayerConfig,
    get_pa_config,
    get_brain_layer_config,
)
from openjarvis.plan9.skills_manifest import (
    Plan9SkillStatus,
    Plan9SkillEntry,
    PLAN9_SKILLS_MANIFEST,
    get_skills_manifest,
)
from openjarvis.plan9.commands_manifest import (
    Plan9CommandStatus,
    Plan9CommandEntry,
    PLAN9_COMMANDS_MANIFEST,
    get_commands_manifest,
)
from openjarvis.plan9.orchestration_policy import (
    RetrievalWorkerPolicy,
    ParallelDAGPolicy,
    ElasticPoolPolicy,
    BatchIntegrationPolicy,
    PLAN9_ORCHESTRATION_POLICIES,
    get_orchestration_policy,
)
from openjarvis.plan9.mac_worker_queue import (
    MacTaskType,
    MacWorkerTask,
    MacWorkerQueue,
    get_mac_worker_queue,
)
from openjarvis.plan9.future_inheritance import (
    DefaultInheritancePolicy,
    PLAN9_DEFAULT_INHERITANCE,
    validate_manager_inheritance,
    validate_worker_inheritance,
)

__all__ = [
    # Capability matrix
    "CapabilityStatus",
    "Plan9CapabilityEntry",
    "Plan9CapabilityMatrix",
    "get_plan9_capability_matrix",
    # Model routing
    "ModelTier",
    "ModelRoutingEntry",
    "RoleModelRoutingMatrix",
    "get_role_routing_matrix",
    # Rules
    "PLAN9_INTERNAL_RULES",
    "Plan9Rule",
    # PA vs Brain layer
    "JarvisLayer",
    "JarvisPAConfig",
    "JarvisBrainLayerConfig",
    "get_pa_config",
    "get_brain_layer_config",
    # Skills
    "Plan9SkillStatus",
    "Plan9SkillEntry",
    "PLAN9_SKILLS_MANIFEST",
    "get_skills_manifest",
    # Commands
    "Plan9CommandStatus",
    "Plan9CommandEntry",
    "PLAN9_COMMANDS_MANIFEST",
    "get_commands_manifest",
    # Orchestration
    "RetrievalWorkerPolicy",
    "ParallelDAGPolicy",
    "ElasticPoolPolicy",
    "BatchIntegrationPolicy",
    "PLAN9_ORCHESTRATION_POLICIES",
    "get_orchestration_policy",
    # Mac worker queue
    "MacTaskType",
    "MacWorkerTask",
    "MacWorkerQueue",
    "get_mac_worker_queue",
    # Future inheritance
    "DefaultInheritancePolicy",
    "PLAN9_DEFAULT_INHERITANCE",
    "validate_manager_inheritance",
    "validate_worker_inheritance",
]
