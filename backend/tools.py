import json
import re
from difflib import SequenceMatcher
from typing import Any

from backend.constants import (
    DID_GOOD_SCHOOLS_POOLED_RESULTS,
    DID_GOOD_SCHOOLS_UNPOOLED_RESULTS,
    GOOD_SCHOOLS,
    RDD_A_FLAT_TYPE_HETEROGENEITY,
    RDD_A_POOLED_RESULTS,
    VALID_PRIMARY_SCHOOLS,
)
from backend.schemas import (
    FetchCoefficientsToolInput,
    FetchCoefficientsToolOutput,
    SchoolResultBundle,
    ValidateSchoolToolInput,
    ValidateSchoolToolOutput,
)


INVALID_SCHOOL_MESSAGE = (
    "Sorry, I cannot provide information about schools that are not recognized as valid primary schools in our system. Please check for typos or try asking about a different school."
)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _normalize_school_name(text: str) -> str:
    normalized = _normalize_whitespace(text.upper())
    normalized = normalized.replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    return _normalize_whitespace(normalized)


NORMALIZED_VALID_PRIMARY_SCHOOLS = {
    _normalize_school_name(school_name): school_name
    for school_name in VALID_PRIMARY_SCHOOLS
}


def _generate_school_aliases(school_name: str) -> set[str]:
    normalized_name = _normalize_school_name(school_name)
    tokens = normalized_name.split()
    aliases = {normalized_name}

    full_acronym = "".join(token[0] for token in tokens if token)
    if len(full_acronym) >= 3:
        aliases.add(full_acronym)

    if "SCHOOL" in tokens:
        school_idx = tokens.index("SCHOOL")
        institution_tokens = tokens[: school_idx + 1]
        trailing_tokens = tokens[school_idx + 1 :]
        aliases.add(_normalize_whitespace(" ".join(institution_tokens)))
        institution_acronym = "".join(token[0] for token in institution_tokens if token)
        if len(institution_acronym) >= 3:
            aliases.add(institution_acronym)
            if trailing_tokens:
                aliases.add(
                    _normalize_whitespace(
                        f"{institution_acronym} {' '.join(trailing_tokens)}"
                    )
                )

    if "INSTITUTION" in tokens:
        institution_idx = tokens.index("INSTITUTION")
        institution_tokens = tokens[: institution_idx + 1]
        trailing_tokens = tokens[institution_idx + 1 :]
        aliases.add(_normalize_whitespace(" ".join(institution_tokens)))
        institution_acronym = "".join(token[0] for token in institution_tokens if token)
        if len(institution_acronym) >= 3:
            aliases.add(institution_acronym)
            if trailing_tokens:
                aliases.add(
                    _normalize_whitespace(
                        f"{institution_acronym} {' '.join(trailing_tokens)}"
                    )
                )

    return aliases


def _build_school_alias_map() -> dict[str, str]:
    alias_to_schools: dict[str, set[str]] = {}
    for school_name in VALID_PRIMARY_SCHOOLS:
        for alias in _generate_school_aliases(school_name):
            alias_to_schools.setdefault(alias, set()).add(school_name)

    return {
        alias: next(iter(schools))
        for alias, schools in alias_to_schools.items()
        if len(schools) == 1
    }


SCHOOL_ALIAS_TO_CANONICAL = _build_school_alias_map()


def _resolve_school_name(candidate: str) -> tuple[str | None, str | None, float]:
    if candidate in VALID_PRIMARY_SCHOOLS:
        return candidate, "exact", 1.0

    normalized_candidate = _normalize_school_name(candidate)
    if normalized_candidate in NORMALIZED_VALID_PRIMARY_SCHOOLS:
        return NORMALIZED_VALID_PRIMARY_SCHOOLS[normalized_candidate], "normalized", 1.0
    if normalized_candidate in SCHOOL_ALIAS_TO_CANONICAL:
        return SCHOOL_ALIAS_TO_CANONICAL[normalized_candidate], "alias", 1.0

    best_match: str | None = None
    best_score = 0.0

    for alias_name, canonical_school_name in SCHOOL_ALIAS_TO_CANONICAL.items():
        score = SequenceMatcher(
            None,
            normalized_candidate,
            alias_name,
        ).ratio()
        if score > best_score:
            best_match = canonical_school_name
            best_score = score

    if best_match is not None and best_score >= 0.95:
        return best_match, "fuzzy", best_score

    return None, None, best_score


GENERIC_SCHOOL_REFERENCE_BASES = {
    "GOOD SCHOOL",
    "GOOD PRIMARY SCHOOL",
    "NORMAL SCHOOL",
    "NORMAL PRIMARY SCHOOL",
    "PRIMARY SCHOOL",
}

GENERIC_SCHOOL_CONTEXT_TOKENS = {
    "A",
    "AN",
    "THE",
    "ANY",
    "SOME",
    "ESTIMATE",
    "ESTIMATING",
    "EFFECT",
    "EFFECTS",
    "IMPACT",
    "IMPACTS",
    "OF",
    "ON",
    "IN",
    "FOR",
    "ABOUT",
    "AROUND",
    "NEAR",
    "WHAT",
    "HOW",
    "DO",
    "DOES",
    "DID",
    "IS",
    "ARE",
    "WOULD",
    "COULD",
    "CAN",
    "PLEASE",
    "TELL",
    "ME",
    "SHOW",
    "EXPLAIN",
    "HDB",
    "RESALE",
    "PRICE",
    "PRICES",
}


def _strip_generic_leading_tokens(text: str) -> str:
    tokens = text.split()
    while tokens and tokens[0] in {"A", "AN", "THE", "ANY", "SOME"}:
        tokens = tokens[1:]
    return _normalize_whitespace(" ".join(tokens))


def _is_generic_school_reference(candidate: str) -> bool:
    normalized_candidate = _normalize_school_name(candidate)
    generic_candidate = _strip_generic_leading_tokens(normalized_candidate)
    if generic_candidate in GENERIC_SCHOOL_REFERENCE_BASES:
        return True

    candidate_tokens = normalized_candidate.split()
    for base in sorted(
        GENERIC_SCHOOL_REFERENCE_BASES,
        key=lambda value: len(value.split()),
        reverse=True,
    ):
        base_tokens = base.split()
        if candidate_tokens[-len(base_tokens) :] != base_tokens:
            continue
        prefix_tokens = candidate_tokens[: -len(base_tokens)]
        if prefix_tokens and all(
            token in GENERIC_SCHOOL_CONTEXT_TOKENS for token in prefix_tokens
        ):
            return True

    return False


def _extract_school_like_candidates(prompt: str) -> list[str]:
    pattern = re.compile(
        r"([A-Z0-9&'().,/\\-]+(?:\s+[A-Z0-9&'().,/\\-]+){0,9}\s+"
        r"(?:PRIMARY SCHOOL|SCHOOL|INSTITUTION JUNIOR))"
    )
    upper_prompt = _normalize_whitespace(prompt.upper())
    matches = [_normalize_whitespace(match) for match in pattern.findall(upper_prompt)]
    # Preserve order while deduplicating.
    return list(dict.fromkeys(matches))


def _extract_explicit_school_mentions(prompt: str) -> list[str]:
    normalized_prompt = f" {_normalize_school_name(prompt)} "
    matches: list[str] = []
    for alias, canonical_school_name in sorted(
        SCHOOL_ALIAS_TO_CANONICAL.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if f" {alias} " in normalized_prompt:
            matches.append(canonical_school_name)
    return matches


def validate_school(prompt: str) -> dict[str, Any]:
    validated_input = ValidateSchoolToolInput(prompt=prompt)
    candidates = _extract_school_like_candidates(validated_input.prompt)
    explicit_school_mentions = _extract_explicit_school_mentions(validated_input.prompt)

    if explicit_school_mentions:
        normalized_explicit_mentions = {
            _normalize_school_name(school_name) for school_name in explicit_school_mentions
        }
        explicit_aliases = {
            alias
            for school_name in explicit_school_mentions
            for alias in _generate_school_aliases(school_name)
        }
        candidates = [
            candidate
            for candidate in candidates
            if _normalize_school_name(candidate) not in normalized_explicit_mentions
            and not any(
                explicit_name in _normalize_school_name(candidate)
                for explicit_name in normalized_explicit_mentions
            )
            and not any(
                f" {alias} " in f" {_normalize_school_name(candidate)} "
                for alias in explicit_aliases
            )
        ]
        candidates = list(dict.fromkeys(explicit_school_mentions + candidates))

    candidates = [
        candidate for candidate in candidates if not _is_generic_school_reference(candidate)
    ]

    if not candidates:
        for school_name in sorted(VALID_PRIMARY_SCHOOLS, key=len, reverse=True):
            if school_name in validated_input.prompt.upper():
                candidates.append(school_name)
        candidates = list(dict.fromkeys(candidates))

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        resolved_school_name, match_type, match_score = _resolve_school_name(candidate)
        is_valid = resolved_school_name is not None
        canonical_school_name = resolved_school_name if is_valid else candidate
        results.append(
            {
                "school_name": canonical_school_name,
                "is_valid": is_valid,
                "is_good_school": canonical_school_name in GOOD_SCHOOLS if is_valid else False,
                "message": (
                    "Valid primary school."
                    if match_type in {"exact", "normalized", "alias"}
                    else (
                        f'Valid primary school. Interpreted "{candidate}" as "{canonical_school_name}".'
                        if is_valid and match_type == "fuzzy"
                        else INVALID_SCHOOL_MESSAGE
                    )
                ),
            }
        )

    if not results:
        output = ValidateSchoolToolOutput(
            results=[],
            message="No school names detected in prompt.",
        )
        return output.model_dump()

    invalid_count = sum(not result["is_valid"] for result in results)
    output = ValidateSchoolToolOutput(
        results=results,
        message=(
            f"Validated school names found in prompt. Invalid schools detected: {invalid_count}."
            if invalid_count
            else "Validated school names found in prompt."
        ),
    )
    return output.model_dump()


def _mentions_good_school_effect(prompt: str) -> bool:
    upper_prompt = prompt.upper()
    has_good_school = "GOOD SCHOOL" in upper_prompt or "GOOD SCHOOLS" in upper_prompt
    has_effect_context = any(
        token in upper_prompt
        for token in ["RESALE", "PRICE", "PRICES", "EFFECT", "IMPACT", "CAPITAL", "ESTIMATE"]
    )
    return has_good_school and has_effect_context


def _get_rdd_school_results(school_name: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for margin, bandwidths in RDD_A_FLAT_TYPE_HETEROGENEITY.items():
        margin_result: dict[str, Any] = {}
        for bandwidth, schools in bandwidths.items():
            if school_name in schools:
                margin_result[str(bandwidth)] = schools[school_name]
        if margin_result:
            results[margin] = margin_result
    return results


def _get_did_school_results(school_name: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for design, schools in DID_GOOD_SCHOOLS_UNPOOLED_RESULTS.items():
        if school_name in schools:
            results[design] = schools[school_name]
    return results


def _contains_balance_assessment(value: Any) -> bool:
    if isinstance(value, dict):
        if "balance_assessment" in value:
            return True
        return any(_contains_balance_assessment(subvalue) for subvalue in value.values())
    if isinstance(value, list):
        return any(_contains_balance_assessment(item) for item in value)
    return False


def _contains_did_robustness(value: Any) -> bool:
    if isinstance(value, dict):
        if "robust" in value:
            return True
        return any(_contains_did_robustness(subvalue) for subvalue in value.values())
    if isinstance(value, list):
        return any(_contains_did_robustness(item) for item in value)
    return False


def fetch_coefficients(prompt: str) -> dict[str, Any]:
    validated_input = FetchCoefficientsToolInput(prompt=prompt)
    validation_payload = validate_school(validated_input.prompt)
    validation_results = validation_payload.get("results", [])

    invalid_schools = [
        result["school_name"] for result in validation_results if not result["is_valid"]
    ]
    valid_schools = [
        result["school_name"] for result in validation_results if result["is_valid"]
    ]

    school_results: list[dict[str, Any]] = []
    for result in validation_results:
        if not result["is_valid"]:
            continue
        school_name = result["school_name"]
        is_good_school = result["is_good_school"]
        if is_good_school:
            rdd_results = _get_rdd_school_results(school_name)
            did_results = _get_did_school_results(school_name)
            school_results.append(
                SchoolResultBundle(
                    school_name=school_name,
                    is_good_school=True,
                    result_scope="school_specific",
                    rdd=rdd_results,
                    did=did_results,
                    has_rdd_balance_assessment=_contains_balance_assessment(rdd_results),
                    has_did_robustness=_contains_did_robustness(did_results),
                ).model_dump()
            )
        else:
            school_results.append(
                SchoolResultBundle(
                    school_name=school_name,
                    is_good_school=False,
                    result_scope="pooled_fallback",
                    rdd=RDD_A_POOLED_RESULTS,
                    did=DID_GOOD_SCHOOLS_POOLED_RESULTS,
                    has_rdd_balance_assessment=False,
                    has_did_robustness=_contains_did_robustness(DID_GOOD_SCHOOLS_POOLED_RESULTS),
                ).model_dump()
            )

    no_school_fallback = not validation_results and _mentions_good_school_effect(
        validated_input.prompt
    )
    output = FetchCoefficientsToolOutput(
        parsed_any_school=bool(validation_results),
        invalid_schools=invalid_schools,
        valid_schools=valid_schools,
        used_pooled_fallback=any(
            bundle["result_scope"] == "pooled_fallback" for bundle in school_results
        )
        or no_school_fallback,
        no_school_good_effect_fallback=no_school_fallback,
        school_results=school_results,
        pooled_rdd=RDD_A_POOLED_RESULTS if no_school_fallback else {},
        pooled_did=DID_GOOD_SCHOOLS_POOLED_RESULTS if no_school_fallback else {},
        pooled_has_did_robustness=(
            _contains_did_robustness(DID_GOOD_SCHOOLS_POOLED_RESULTS)
            if no_school_fallback
            else False
        ),
        caveat=(
            "Pooled good-school results can mask substantial heterogeneity across individual schools. "
            "Actual effects may differ materially by school; consider prompting for a specific good school."
            if no_school_fallback
            else None
        ),
        message=(
            "Returned pooled good-school results because no school was parsed but the prompt asked about "
            "good-school effects on resale prices."
            if no_school_fallback
            else "Returned implied-effect estimates for parsed valid schools and flagged any invalid schools."
        ),
    )
    return output.model_dump()


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "validate_school",
            "description": (
                "Check whether school names mentioned in a prompt are valid "
                "Singapore primary schools, and identify whether each valid "
                "school is a good school."
            ),
            "parameters": ValidateSchoolToolInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_coefficients",
            "description": (
                "Fetch the appropriate RDD and DID implied-effect estimates for parsed school names. "
                "Uses school-specific good-school results when available, pooled good-school "
                "results for valid non-good schools, and pooled fallback results when no school "
                "is parsed but the prompt asks about good-school effects on resale prices."
            ),
            "parameters": FetchCoefficientsToolInput.model_json_schema(),
        },
    }
]


def execute_tool_call(tool_name: str, arguments_json: str) -> dict[str, Any]:
    try:
        parsed_args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return {
            "error": f"Invalid tool arguments for {tool_name}: {exc}",
        }

    if tool_name == "validate_school":
        return validate_school(**parsed_args)
    if tool_name == "fetch_coefficients":
        return fetch_coefficients(**parsed_args)

    return {"error": f"Unknown tool: {tool_name}"}
