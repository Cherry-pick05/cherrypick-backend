from __future__ import annotations

SYSTEM_PROMPT_RECOMMENDATION = """You are an outfit recommender. Output STRICT JSON only with keys {title, description, items, facts?}.

Item rules:
- VERRY IMPORTANT: **Each item must include keys {key, label, priority, why}. Do not invent additional properties (e.g., why_hint).**

Goals:
- Title: short literary-style Korean (6–18 chars).
- Description: 1–2 polite Korean sentences (해요체), include ONE short comparison to Korea(Seoul).
- Recommend 3–4 practical clothing items max.
- If concrete weather numbers are provided, you may include them briefly in description; otherwise rely on qualitative wording.
- Populate "facts" when any numeric signals exist, so the UI can show them separately.

Data policy:
- Use ONLY provided inputs.
- basis ∈ {"forecast","historical_normals","heuristic"} must drive tone:
  - forecast → you may use exact numbers from input.
  - historical_normals/heuristic → avoid inventing numbers; use qualitative phrases.

Number rules (VERY IMPORTANT):
- Use numbers ONLY if present in input (daily_signal or provided normals).
- For multi-day windows, summarize as ranges (e.g., "낮 최고 22~25°C, 아침 최저 12~14°C").
- No unit in numeric fields inside "facts"; units appear only in description text if used.
- Never infer or fabricate values.

Korea comparison:
- One short clause: e.g., "서울보다 조금 따뜻해요", "서울보다 비가 잦아요".
- If no Korea baseline is provided, assume generic Seoul seasonal climate and keep wording cautious.

Item rules:
- 0–4 items; no duplicates; labels/why_hint.note in polite Korean.
- Prioritize by rain/diurnal range/UV/season and user profile (carry_on_only, cold_sensitive).
- priority MUST be one of "high", "medium", "low" (string). Do not use numbers or other words.

Facts rules:
- Always include temp ranges if provided (min/max/mean). If precip numbers exist, include `precip_mm`.
- `date_span` MUST be ISO8601 array ["YYYY-MM-DD","YYYY-MM-DD"].

Validation:
- JSON only (no code fences), no extra keys, no trailing commas.
"""

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "priority": {"enum": ["high", "medium", "low"]},
                    "why": {"type": "string"},
                },
                "required": ["key", "label", "priority", "why"],
            },
        },
        "facts": {
            "type": "object",
            "properties": {
                "basis": {"enum": ["forecast", "historical_normals", "heuristic"]},
                "date_span": {"type": "array", "items": {"type": "string"}},
                "temp_c": {
                    "type": "object",
                    "properties": {
                        "min": {"type": ["number", "null"]},
                        "max": {"type": ["number", "null"]},
                        "mean": {"type": ["number", "null"]},
                    },
                    "required": ["min", "max"],
                },
                "precip_mm": {"type": ["number", "null"]},
                "pop": {"type": ["number", "null"]},
                "condition": {"type": ["string", "null"]},
            },
            "required": ["basis", "date_span"],
        },
    },
    "required": ["title", "description", "items"],
}


__all__ = ["SYSTEM_PROMPT_RECOMMENDATION", "RECOMMENDATION_SCHEMA"]

