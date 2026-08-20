"""Provider-neutral external metadata and resilient network access for MusicArk."""

from .models import Confidence, ExternalMetadataCandidate, MetadataEvidence
from .resolver import ExternalMetadataResolver

__all__ = [
    "Confidence",
    "ExternalMetadataCandidate",
    "MetadataEvidence",
    "ExternalMetadataResolver",
]
