from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ...,
        description="Role of the message in the chat history.",
    )
    content: Any = Field(..., description="Message content.")
    name: Optional[str] = Field(default=None, description="Optional participant name.")


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(default="openai-proxy")
    messages: List[ChatMessage] = Field(
        ...,
        description="OpenAI-style chat messages from Open WebUI.",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream tokens back using server-sent events.",
    )
    temperature: Optional[float] = Field(default=None)
    top_p: Optional[float] = Field(default=None)
    max_tokens: Optional[int] = Field(default=None)
    stop: Optional[str | List[str]] = Field(default=None)
    user: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata used by the backend when fetching extra context.",
    )


class RDDResult(BaseModel):
    coefficient: float = Field(
        ...,
        description="Implied treatment effect on the exp(beta) - 1 scale.",
    )
    p_value: float = Field(..., description="P-value for the underlying estimate.")
    sig_field: bool = Field(
        ...,
        description="Whether the implied effect is significant at the 10% level.",
    )
    smd_year: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for transaction year.",
    )
    smd_floor_area_sqm: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for floor area in square meters.",
    )
    smd_remaining_lease: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for remaining lease.",
    )
    smd_num_nearby_malls: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for number of nearby malls.",
    )
    smd_num_nearby_mrt: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for number of nearby MRT stations.",
    )
    smd_num_unique_mrt_lines: Optional[float] = Field(
        default=None,
        description="Standardized mean difference for number of unique MRT lines.",
    )
    tvd_quadrant: Optional[float] = Field(
        default=None,
        description="Total variation distance for school quadrant balance.",
    )
    tvd_storey_range: Optional[float] = Field(
        default=None,
        description="Total variation distance for storey-range balance.",
    )
    tvd_flat_model: Optional[float] = Field(
        default=None,
        description="Total variation distance for flat-model balance.",
    )
    tvd_year_quarter: Optional[float] = Field(
        default=None,
        description="Total variation distance for transaction quarter balance.",
    )
    max_abs_smd_numeric: Optional[float] = Field(
        default=None,
        description="Maximum absolute standardized mean difference across numeric covariates.",
    )
    max_tvd_categorical: Optional[float] = Field(
        default=None,
        description="Maximum total variation distance across categorical covariates.",
    )
    balance_assessment: Optional[
        Literal["well_supported", "mixed_support", "weak_support"]
    ] = Field(
        default=None,
        description=(
            "Support label under the SMD/TVD balance-diagnostic framework for "
            "flat-type RDD results."
        ),
    )
    standout_numeric_balance_dimension: Optional[str] = Field(
        default=None,
        description="Natural-language label for the numeric balance dimension with the largest absolute SMD.",
    )
    standout_numeric_balance_direction: Optional[
        Literal["inside_higher", "inside_lower", "inside_equal"]
    ] = Field(
        default=None,
        description="Whether the inside-cutoff group is higher, lower, or equal on the standout numeric balance dimension.",
    )
    standout_numeric_balance_value: Optional[float] = Field(
        default=None,
        description="Absolute SMD value for the standout numeric balance dimension.",
    )
    average_abs_smd_numeric: Optional[float] = Field(
        default=None,
        description="Average absolute SMD across available numeric balance dimensions.",
    )
    standout_categorical_balance_dimension: Optional[str] = Field(
        default=None,
        description="Natural-language label for the categorical balance dimension with the largest TVD.",
    )
    standout_categorical_balance_value: Optional[float] = Field(
        default=None,
        description="TVD value for the standout categorical balance dimension.",
    )
    average_tvd_categorical: Optional[float] = Field(
        default=None,
        description="Average TVD across available categorical balance dimensions.",
    )

    @model_validator(mode="after")
    def validate_sig_field(self) -> "RDDResult":
        expected_sig_field = self.p_value < 0.10
        if self.sig_field != expected_sig_field:
            raise ValueError(
                f"sig_field must equal (p_value < 0.10). "
                f"Got sig_field={self.sig_field} for p_value={self.p_value}."
            )
        return self


class DIDResult(BaseModel):
    coefficient: float = Field(
        ...,
        description="Implied treatment effect on the exp(beta) - 1 scale.",
    )
    p_value: float = Field(..., description="P-value for the underlying estimate.")
    sig_field: bool = Field(
        ...,
        description="Whether the implied effect is significant at the 10% level.",
    )
    robust: Literal["robust", "not_robust", "unknown"] = Field(
        ...,
        description=(
            "Robustness label for the DID estimate. "
            "'robust' means the estimate passed the relevant robustness checks, "
            "'not_robust' means it did not, and 'unknown' means robustness is not established."
        ),
    )

    @model_validator(mode="after")
    def validate_sig_field(self) -> "DIDResult":
        expected_sig_field = self.p_value < 0.10
        if self.sig_field != expected_sig_field:
            raise ValueError(
                f"sig_field must equal (p_value < 0.10). "
                f"Got sig_field={self.sig_field} for p_value={self.p_value}."
            )
        return self


class RDDPooledResults(RootModel[Dict[str, Dict[int, RDDResult]]]):
    pass


class RDDSchoolFlatTypeResults(
    RootModel[Dict[str, Dict[int, Dict[str, Dict[str, RDDResult]]]]]
):
    pass


class DIDPooledResults(RootModel[Dict[str, DIDResult]]):
    pass


class DIDUnpooledResults(RootModel[Dict[str, Dict[str, DIDResult]]]):
    pass


class ValidateSchoolToolInput(BaseModel):
    prompt: str = Field(
        ...,
        description="The user's prompt text to inspect for school names.",
    )


class ValidateSchoolResult(BaseModel):
    school_name: str = Field(..., description="The detected school name.")
    is_valid: bool = Field(
        ...,
        description="Whether the detected school is a valid Singapore primary school.",
    )
    is_good_school: bool = Field(
        ...,
        description="Whether the school is in the configured good-school set.",
    )
    message: str = Field(
        ...,
        description="Validation message for the detected school.",
    )


class ValidateSchoolToolOutput(BaseModel):
    results: List[ValidateSchoolResult] = Field(
        default_factory=list,
        description="Validation results for all detected school names.",
    )
    message: str = Field(
        ...,
        description="Overall validation summary.",
    )


class FetchCoefficientsToolInput(BaseModel):
    prompt: str = Field(
        ...,
        description="The user's prompt text used to determine which results to fetch.",
    )


class ResultPayload(BaseModel):
    coefficient: float = Field(
        ...,
        description="Implied effect estimate on the exp(beta) - 1 scale.",
    )
    p_value: float = Field(..., description="P-value for the underlying estimate.")
    sig_field: bool = Field(
        ...,
        description="Whether the estimate is significant at the 10% level.",
    )
    balance_assessment: Optional[
        Literal["well_supported", "mixed_support", "weak_support"]
    ] = Field(
        default=None,
        description="Optional balance-support label for flat-type RDD results.",
    )
    robust: Optional[Literal["robust", "not_robust", "unknown"]] = Field(
        default=None,
        description="Optional robustness label for DID results.",
    )


class SchoolResultBundle(BaseModel):
    school_name: str = Field(..., description="School name.")
    is_good_school: bool = Field(
        ...,
        description="Whether the school is part of the configured good-school set.",
    )
    result_scope: Literal["school_specific", "pooled_fallback"] = Field(
        ...,
        description="Whether school-specific or pooled fallback results were used.",
    )
    rdd: Dict[str, Any] = Field(
        default_factory=dict,
        description="RDD results keyed by design or subgroup.",
    )
    did: Dict[str, Any] = Field(
        default_factory=dict,
        description="DID results keyed by design.",
    )
    has_rdd_balance_assessment: bool = Field(
        default=False,
        description="Whether any fetched RDD result for this school includes a balance assessment.",
    )
    has_did_robustness: bool = Field(
        default=False,
        description="Whether any fetched DID result for this school includes a robustness label.",
    )


class FetchCoefficientsToolOutput(BaseModel):
    parsed_any_school: bool = Field(
        ...,
        description="Whether any school-like names were parsed from the prompt.",
    )
    invalid_schools: List[str] = Field(
        default_factory=list,
        description="Parsed school names that are not valid Singapore primary schools.",
    )
    valid_schools: List[str] = Field(
        default_factory=list,
        description="Parsed school names that are valid Singapore primary schools.",
    )
    used_pooled_fallback: bool = Field(
        ...,
        description="Whether pooled fallback estimates were used.",
    )
    no_school_good_effect_fallback: bool = Field(
        ...,
        description=(
            "Whether pooled estimates were returned because no school was parsed "
            "but the prompt asked about good-school effects on resale prices."
        ),
    )
    school_results: List[SchoolResultBundle] = Field(
        default_factory=list,
        description="Per-school result bundles for valid schools.",
    )
    pooled_rdd: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pooled RDD results when fallback is used.",
    )
    pooled_did: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pooled DID results when fallback is used.",
    )
    pooled_has_did_robustness: bool = Field(
        default=False,
        description="Whether fetched pooled DID results include robustness labels.",
    )
    caveat: Optional[str] = Field(
        default=None,
        description="Optional interpretation caveat for pooled fallback responses.",
    )
    message: str = Field(
        ...,
        description="Overall retrieval summary.",
    )
