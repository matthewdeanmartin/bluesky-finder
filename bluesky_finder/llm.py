import json
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from .config import settings
from .models import LlmEvaluationResult

client = OpenAI(
    api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url
)

SYSTEM_PROMPT = """
You are an expert recruiter and location analyst. 
Your Goal: Identify if a Bluesky user is a "DC-area Tech Professional".

Definitions:
1. Location: DC / Northern VA / Maryland suburbs (DMV).
2. Profession: Software, Data, Security, Product, Design, DevRel, etc.

Input: JSON with "bio" and "posts".
Output: Strict JSON matching the schema.
Rules:
- Be probabilistic but strict on location evidence.
- "Match" = High confidence in BOTH location AND tech.
- "Maybe" = Strong tech but unsure location, or vice versa.
- "No" = Clearly irrelevant.
"""


def preprocess_json(data: str) -> str:
    """
    Extracts the substring between the first '{' and the last '}'.
    Raises ValueError if no such bounds exist.
    """
    if not isinstance(data, str):
        raise TypeError("data must be a string")

    start = data.find("{")
    end = data.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("No valid JSON object found")

    return data[start : end + 1]


def _to_float01(x: Any) -> float:
    """Best-effort conversion to [0,1]."""
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        v = float(x)
    elif isinstance(x, str):
        s = x.strip().lower()
        if s.endswith("%"):
            try:
                v = float(s[:-1]) / 100.0
            except ValueError:
                v = 0.0
        elif s in {"true", "yes", "y"}:
            v = 1.0
        elif s in {"false", "no", "n"}:
            v = 0.0
        else:
            try:
                v = float(s)
            except ValueError:
                v = 0.0
    elif isinstance(x, bool):
        v = 1.0 if x else 0.0
    else:
        v = 0.0
    # clamp
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _label_from_overall(overall: float) -> str:
    if overall >= settings.scoring_thresholds.match_overall:
        return "match"
    if overall >= settings.scoring_thresholds.maybe_overall:
        return "maybe"
    return "no"


def _normalize_llm_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce provider/model output into the exact LlmEvaluationResult shape.
    Accepts common variants like:
      - is_dc_tech / is_dc_tech_professional
      - confidence / overall_confidence
      - location_score / tech_score
      - reasoning / conclusion
    """
    # pull likely fields from many possible keys
    loc = (
        data.get("score_location")
        or data.get("location_score")
        or data.get("dc_location_score")
        or data.get("location_confidence")
    )
    tech = (
        data.get("score_tech")
        or data.get("tech_score")
        or data.get("tech_confidence")
        or data.get("profession_score")
    )
    overall = (
        data.get("score_overall")
        or data.get("overall_score")
        or data.get("confidence")
        or data.get("overall_confidence")
    )

    # boolean-ish verdicts
    verdict = (
        data.get("label")
        or data.get("is_dc_tech")
        or data.get("is_dc_tech_professional")
        or data.get("is_dc_techie")
    )

    # Convert/derive scores
    score_location = _to_float01(loc)
    score_tech = _to_float01(tech)

    # If both missing but verdict present, set conservative defaults
    if score_location == 0.0 and score_tech == 0.0 and verdict is not None:
        v = str(verdict).strip().lower()
        if v in {"yes", "true", "match"}:
            score_location, score_tech = 0.8, 0.8
        elif v in {"maybe"}:
            score_location, score_tech = 0.5, 0.7
        else:
            score_location, score_tech = 0.2, 0.2

    score_overall = _to_float01(overall)
    if score_overall == 0.0:
        # default overall: min() matches your spec’s “strict on both”
        score_overall = min(score_location, score_tech)

    # Label
    label = data.get("label")
    if isinstance(label, str):
        label = label.strip().lower()
    else:
        label = None

    if label not in {"match", "maybe", "no"}:
        # if verdict is yes/no-ish, translate; else derive from overall
        if verdict is not None:
            v = str(verdict).strip().lower()
            if v in {"yes", "true", "match"}:
                label = (
                    "match"
                    if score_overall >= settings.scoring_thresholds.match_overall
                    else "maybe"
                )
            elif v in {"maybe"}:
                label = "maybe"
            else:
                label = "no"
        else:
            label = _label_from_overall(score_overall)

    # Rationale/evidence/uncertainties
    rationale = (
        data.get("rationale")
        or data.get("reasoning")
        or data.get("conclusion")
        or data.get("summary")
        or ""
    )
    evidence = (
        data.get("evidence")
        or data.get("signals")
        or data.get("supporting_evidence")
        or []
    )
    uncertainties = (
        data.get("uncertainties") or data.get("caveats") or data.get("unknowns") or []
    )

    # Normalize list types
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    if isinstance(uncertainties, str):
        uncertainties = [uncertainties]
    if not isinstance(uncertainties, list):
        uncertainties = []

    # Cap sizes (spec-ish)
    evidence = [str(x) for x in evidence][:5]
    uncertainties = [str(x) for x in uncertainties][:3]

    return {
        "score_location": float(score_location),
        "score_tech": float(score_tech),
        "score_overall": float(score_overall),
        "label": label,
        "rationale": str(rationale),
        "evidence": evidence,
        "uncertainties": uncertainties,
    }


def evaluate_candidate(
    profile_data: dict, posts_data: list[dict]
) -> LlmEvaluationResult:
    posts_text = [f"- {p['text']} ({p['created_at']})" for p in posts_data[:30]]
    user_payload = {
        "handle": profile_data.get("handle"),
        "bio": profile_data.get("description"),
        "recent_posts": posts_text,
    }

    resp = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0.0,
    )

    raw = resp.choices[0].message.content or "{}"
    raw = preprocess_json(raw)
    print(raw)
    data = json.loads(raw)

    normalized = _normalize_llm_json(data)
    return LlmEvaluationResult(**normalized)
