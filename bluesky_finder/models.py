from datetime import datetime
from enum import Enum
from typing import List, Optional, Set, Dict, Any
from pydantic import BaseModel, Field

# Core Types
Did = str
Handle = str


class DiscoverySource(str, Enum):
    HASHTAG = "hashtag"
    ANCHOR_FOLLOW = "anchor_follow"


class LlmLabel(str, Enum):
    MATCH = "match"
    MAYBE = "maybe"
    NO = "no"


# Pydantic Models for App Logic
class CandidateFeatures(BaseModel):
    location_keywords_hit: List[str] = []
    tech_keywords_hit: List[str] = []


class LlmEvaluationResult(BaseModel):
    score_location: float = Field(..., ge=0, le=1)
    score_tech: float = Field(..., ge=0, le=1)
    score_overall: float = Field(..., ge=0, le=1)
    label: LlmLabel
    rationale: str
    evidence: List[str]
    uncertainties: List[str]
