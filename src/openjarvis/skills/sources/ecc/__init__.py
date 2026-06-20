"""ECC-derived skills — adapted from https://github.com/affaan-m/ECC (MIT License).

All items in this package are:
  - Adapted (not wholesale-copied) from ECC
  - Registered INSTALLED_DISABLED by default
  - Require explicit reviewer approval before activation
  - Non-redundant with existing Jarvis capabilities
  - Reachable from Jarvis front door
  - Tested and reversible

Source: https://github.com/affaan-m/ECC
License: MIT
"""

from openjarvis.skills.sources.ecc.eval_context_skill import (
    ECC_EVAL_CONTEXT_CANDIDATE,
    EvalContextSkill,
    get_eval_context_manifest,
    register_eval_context_candidate,
)

__all__ = [
    "ECC_EVAL_CONTEXT_CANDIDATE",
    "EvalContextSkill",
    "get_eval_context_manifest",
    "register_eval_context_candidate",
]
