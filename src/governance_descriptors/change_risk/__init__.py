"""PR-level governance-change-risk study.

The package keeps extraction, feature construction, outcome adjudication, and
evaluation separate. That separation is deliberate: graph descriptors must not
influence the human outcome label, and preprocessing must be fitted inside each
held-out project or temporal split.
"""

from .features import extract_change_features
from .manifest import ManifestSnapshot, load_manifest
from .study import build_study_dataset

__all__ = [
    "ManifestSnapshot",
    "build_study_dataset",
    "extract_change_features",
    "load_manifest",
]
