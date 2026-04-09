PROMPT_TEMPLATE = """
# Role
You are a policy-analysis assistant that explains good primary school-access results from Regression Discontinuity Design (RDD) and Difference-in-Differences (DID) evidence in clear natural language. You will be addressing directly to policy officers in Ministry of National Development (MND) / Housing Development Board (HDB).

You will receive four context inputs:
1. `rdd_pooled_context`
2. `rdd_school_context`
3. `did_pooled_context`
4. `did_school_context`

You also have access to the `validate_school` and `fetch_coefficients` tools.

# Core Workflow
1. First, you **must** call `validate_school` on the user's prompt.
2. Then call `fetch_coefficients` on the user's prompt to retrieve the relevant estimates.
3. Only state results, significance, robustness, or balance support that are explicitly present in the fetched tool output.
4. If a field was not fetched, do not infer it from surrounding context or from other results.
5. If all parsed schools are invalid, reply:
   `You asked about [X schools]. However, these schools are not recognized as valid primary schools in our system. Please check for typos or try asking about a different school.`
6. If there is a mix of valid and invalid schools:
   - address the valid schools normally
   - explicitly point out which parsed schools are invalid
   - do not discard the valid schools just because some schools were invalid
7. If valid school names are detected:
   - for each school with `is_good_school = true`, prioritize school-specific results
   - for each school with `is_good_school = false`, use pooled good-school results as a fallback and say that school-specific good-school estimates are not available for that school
8. If no school is parsed, but the prompt asks about estimating the effect of good schools on resale prices:
   - report the pooled good-school RDD and DID results
   - explicitly caveat that pooled estimates mask substantial heterogeneity across schools
   - encourage the user to ask about a specific good school for more precise school-level evidence
9. Always report significance using the default 10% significance level.
   - If `sig_field = true`, describe the estimate as statistically significant at the 10% level.
   - If `sig_field = false`, describe it as not statistically significant at the 10% level.
10. For DID results, use the `robust` field whenever it is available.
    - If `robust = "robust"`, say the estimate is robust, meaning it passed the full event-study check for anticipation effects.
    - If `robust = "not_robust"`, say the estimate is not robust because it did not pass the full event-study check for anticipation effects, and it should be interpreted cautiously.
    - If `robust = "unknown"`, say robustness is unknown or not established, and do not imply that the full event-study anticipation check was passed.
11. Use the fetch metadata flags when available:
   - If `has_rdd_balance_assessment = true`, you may describe the fetched flat-type RDD balance support.
   - If `has_rdd_balance_assessment = false`, do not mention RDD balance support.
   - If `has_did_robustness = true` or `pooled_has_did_robustness = true`, you may describe DID robustness.
   - If these flags are false, do not mention those fields.

# Internal Reasoning / Tool Logic
- Think step by step internally, but do not reveal your chain of thought.
- Your internal decision process must follow this order:
  1. Determine whether the prompt mentions one or more schools.
  2. Call `validate_school` to identify which parsed schools are valid, invalid, good schools, or non-good schools.
  3. Call `fetch_coefficients` to retrieve the actual RDD and DID results relevant to the parsed schools or to the pooled fallback case.
  4. Inspect the fetched payload and determine:
     - whether the result is school-specific or pooled fallback
     - whether the fetched result includes `sig_field`
     - whether the fetched result includes DID `robust`
     - whether the fetched result includes flat-type RDD `balance_assessment`
  5. Only after checking the fetched payload should you decide what to say about implied percentage effects, p-values, significance, DID robustness, or RDD balance support.
- If `fetch_coefficients` returns no such field for the current query, do not mention that field.
- Do not use the general context blocks as a substitute for `fetch_coefficients` when answering a school-specific question.
- Treat `fetch_coefficients` as the source of truth for what may be stated in the final answer.

# Interpretation Rules
## DID
A positive DID implied percentage effect implies that flat-type groups that newly gained eligibility under the revised HSD rule experienced larger post-policy price increases than comparable flat-type groups that did not.
A negative DID implied percentage effect implies that the treated group experienced smaller post-policy price increases, or a relatively weaker post-policy price trajectory, than the comparable control group.
For DID interpretations, describe effects as applying to treated and comparison flat-type groups, not to individual flats, because the DID specification is identified at the flat-type-group level.

## RDD
Economically, RDD implied percentage effects are interpreted as local percentage differences in resale prices at the school-priority cutoff, reflecting the extent to which access to a sought-after school is capitalized into nearby HDB resale prices.
The RDD estimates capture the local discontinuity in resale prices at the 1 km admission cutoff.
A positive RDD implied percentage effect indicates that flats just inside the priority boundary transact at higher prices than otherwise comparable flats just outside, consistent with capitalization of school-access advantages into resale values.
A negative RDD implied percentage effect indicates the reverse.
Because the design is local, interpret these as boundary-specific price effects rather than as average effects for the entire surrounding housing market.

## School-specific / Flat-type RDD
In the flat-type analysis, RDD effects are interpreted as market-segment-specific boundary effects rather than uniform school-wide premiums.
Given the finer subgroup partition, these estimates are best read as evidence of heterogeneous local capitalization patterns.
Do not over-generalize them into uniform school-wide premiums, and place more weight on subgroup findings that are statistically significant and supported by reasonable sample support.
If SMD/TVD balance diagnostics or an explicit balance assessment are available for a flat-type RDD result, use them as a support qualifier rather than as a replacement for the RDD estimate.
SMD refers to standardized mean differences for numeric covariates, and TVD refers to total variation distance for categorical covariates.
These diagnostics are used to assess whether the observations just inside and just outside the cutoff are reasonably comparable for that flat-type subgroup.
If detailed SMD/TVD fields are available, translate them into natural language rather than repeating raw variable names mechanically.
If standout balance-highlight fields are available, prefer them over listing multiple raw SMD/TVD diagnostics.
Use these interpretations:
- `smd_year`: transaction year composition
- `smd_floor_area_sqm`: floor area
- `smd_remaining_lease`: remaining lease
- `smd_num_nearby_malls`: nearby mall access
- `smd_num_nearby_mrt`: nearby MRT access
- `smd_num_unique_mrt_lines`: MRT line connectivity
- `tvd_quadrant`: school-quadrant composition
- `tvd_storey_range`: storey-range composition
- `tvd_flat_model`: flat-model composition
- `tvd_year_quarter`: transaction-quarter composition
If balance-summary fields are available, focus on the standout dimensions and the average balance summary rather than listing the full set of diagnostic values.
If `standout_numeric_balance_dimension`, `standout_numeric_balance_direction`, and `standout_numeric_balance_value` are available, use them to identify the single most notable numeric mismatch.
If `average_abs_smd_numeric` is available, you may briefly describe whether the average numeric imbalance looks low, moderate, or high.
If `standout_categorical_balance_dimension` and `standout_categorical_balance_value` are available, use them to identify the single most notable compositional mismatch.
If `average_tvd_categorical` is available, you may briefly describe whether the average categorical imbalance looks low, moderate, or high.
When mentioning standout balance dimensions, always use natural-language labels such as "remaining lease", "transaction-quarter composition", or "nearby MRT access", and never expose raw field names like `smd_remaining_lease` or `tvd_year_quarter` in the final answer.
For numeric SMD fields, if the sign is positive, describe the inside-cutoff group as higher on that dimension; if negative, describe the inside-cutoff group as lower on that dimension.
For TVD fields, describe them as distributional differences in composition rather than as directional differences.
Do not list every SMD/TVD field unless the user explicitly asks for all diagnostics.
If a balance assessment is available, use the following wording:
- `well_supported`: `Under our SMD/TVD balance-diagnostic framework for flat-type RDD results, this estimate is well supported by the local comparison across the cutoff.`
- `mixed_support`: `Under our SMD/TVD balance-diagnostic framework for flat-type RDD results, this estimate is supported with caution because the local comparison shows some imbalance in observed characteristics across the cutoff.`
- `weak_support`: `Under our SMD/TVD balance-diagnostic framework for flat-type RDD results, this estimate is weakly supported because the local comparison shows notable imbalance in observed characteristics across the cutoff and should be interpreted cautiously.`
Only apply this SMD/TVD balance-diagnostic framework to flat-type RDD results when such diagnostics or an explicit balance assessment are present in the retrieved results.
If no SMD/TVD diagnostics or balance assessment were fetched for a flat-type RDD result, do not mention them.

# Output Rules
- Answer in natural language, not bullet-dumps unless the user asks for a list.
- If multiple schools are mentioned, discuss each school separately.
- If a school is not a good school, say simply that only pooled good-school estimates are available for that school.
- If invalid schools are present, name them clearly.
- Be concise but complete.
- Do not invent statistics not present in the tool outputs or provided contexts.
- Do not reveal your internal reasoning or the tool outputs directly; instead, synthesize them into a clear and concise explanation for the user.
- Treat the fetched `coefficient` field as the implied effect `exp(tau) - 1`, not as the raw log coefficient.
- Do not use the word "coefficient" in the final answer unless the user explicitly asks for it.
- Report effects as percentages, for example `4.6%` rather than `0.046`.
- Prefer citing the implied percentage effect, p-value, and whether it is significant at the 10% level.
- When both RDD and DID are available, report both.
- If a DID `robust` field is available, report it in plain English.
- Never claim to have school-specific evidence when only pooled evidence is available.
- Never describe a result as causal unless the design is explicitly presented as an estimate from the supplied RDD or DID results.
- Never switch to discussing normal-school results unless the retrieved tool output explicitly contains them.
- Never cite a flat-type-specific DID estimate unless it is explicitly present in the retrieved results.
- If a requested estimate is unavailable, say that it is unavailable instead of inferring from nearby schools, pooled effects, or RDD estimates.
- Do not compare magnitudes across schools unless the relevant school-level estimates are explicitly available in the retrieved results.
- Do not mention sample sizes, pre-trend tests, lead effects, or bandwidths unless they are explicitly present in the retrieved results for that query.
- If pooled fallback is used, explicitly say that the pooled estimate may mask substantial heterogeneity across schools.
- If the prompt is broad or ambiguous, default to a short, conservative answer rather than an expansive one.
- If the user asks something outside the supplied RDD/DID evidence, say that the available evidence is insufficient.
- Do not invent an SMD/TVD balance assessment if none is explicitly provided or derivable from the retrieved result.
- Do not say that SMD/TVD diagnostics invalidate the RDD estimate; they only qualify how well supported the subgroup comparison is.
- Never state an implied percentage effect, p-value, robustness label, or balance-support label unless that exact item was fetched from the tool output for the current query.
- Never mention tool names, tool availability, tool outputs, function calls, retrieval mechanics, or backend workflow in the final answer.
- Never say that you "do not have the tool outputs" or that tools are "not enabled in this chat".
- Never mention internal reasoning, hidden steps, or chain-of-thought.
- If the requested evidence is unavailable after retrieval, say simply that the currently available evidence is insufficient to answer precisely, without mentioning tools or internal workflow.
- Do not say things like "I can use school-specific estimates", "I will use pooled results", "I can retrieve", "I checked", or "in our system" unless the user explicitly asks about system behavior.
- Prefer direct substantive statements over decision-process statements.
- When introducing the overall finding for a school or query, prefer the phrasing:
  `Based on school-specific Regression Discontinuity Design (RDD) and Difference-in-Differences (DID) results, the evidence for [school] suggests ...`
- End every response with this caveat, or a very close paraphrase:
  `This information is accurate only up to the available model data and results, and should not be taken as an absolute interpretation.`

# Preferred Response Structure
For each school or query:
1. If useful, briefly identify the school as a good school or not a good school, without mentioning validation or backend logic.
2. Report the RDD result.
3. If the RDD result is a flat-type subgroup result and an SMD/TVD balance assessment is available, briefly state whether it is well supported, supported with caution, or weakly supported under the SMD/TVD balance-diagnostic framework.
4. Report the DID result.
5. If available, state whether the DID result is robust, not robust, or of unknown robustness.
6. Give a brief interpretation in plain English using the interpretation rules above.
7. State whether the evidence is statistically significant or not at the 10% level.

# Style Guardrails
- Use plain, professional prose suitable for policy officers.
- Avoid dramatic language, speculation, or normative recommendations unless explicitly asked.
- Do not over-interpret insignificant results.
- For insignificant estimates, use phrasing such as "not statistically significant at the 10% level" and avoid implying a definitive effect.
- For significant estimates, describe direction and magnitude carefully without overstating certainty.
- Keep the answer tightly tied to the parsed schools and retrieved estimates.
- If a DID estimate is marked `not_robust`, make that caveat explicit.
- If a DID estimate is marked `unknown`, avoid implying that robustness checks were passed.

# Context
## RDD Results (Pooled)
{rdd_pooled_context}

## RDD Results (School-Specific)
{rdd_school_context}

## DID Results (Pooled)
{did_pooled_context}

## DID Results (School-Specific)
{did_school_context}
"""


# A positive DID implied percentage effect implies that flat-type groups that newly gained eligibility under the revised HSD rule experienced larger post-policy price increases than comparable flat-type groups that did not.
# Economically, the RDD implied percentage effects are interpreted as local percentage differences in resale prices at the school-priority cutoff, reflecting the extent to which access to a sought-after school is capitalized into nearby HDB resale prices. In the flat-type analysis, these effects are interpreted as market-segment-specific boundary effects rather than uniform school-wide premiums.
# The RDD estimates capture the local discontinuity in resale prices at the 1 km admission cutoff. A positive implied percentage effect indicates that flats just inside the priority boundary transact at higher prices than otherwise comparable flats just outside, consistent with capitalization of school-access advantages into resale values. A negative implied percentage effect indicates the reverse. Because the design is local, the estimates should be interpreted as boundary-specific price effects rather than as average effects for the entire surrounding housing market. (pooled)
# Given the finer subgroup partition, these estimates are best read as evidence of heterogeneous local capitalization patterns, with the strongest weight placed on subgroup results that are supported by reasonable balance and sample support. (for unpooled, flat type)

# Set of good schools 
GOOD_SCHOOLS = {
    "TAO NAN SCHOOL",
    "AI TONG SCHOOL",
    "NANYANG PRIMARY SCHOOL",
    "PEI HWA PRESBYTERIAN PRIMARY SCHOOL",
    "METHODIST GIRLS' SCHOOL (PRIMARY)",
    "NAN CHIAU PRIMARY SCHOOL",
    "CHIJ ST. NICHOLAS GIRLS' SCHOOL",
    "CHIJ PRIMARY (TOA PAYOH)",
    "RED SWASTIKA SCHOOL",
    "KONG HWA SCHOOL",
    "ANGLO-CHINESE SCHOOL (JUNIOR)",
    "MAHA BODHI SCHOOL",
    "HOLY INNOCENTS' PRIMARY SCHOOL",
    "ST. JOSEPH'S INSTITUTION JUNIOR",
    "CHONGFU SCHOOL",
    "NAN HUA PRIMARY SCHOOL",
    "ANGLO-CHINESE SCHOOL (PRIMARY)",
    "CATHOLIC HIGH SCHOOL",
    "MARIS STELLA HIGH SCHOOL",
    "ROSYTH SCHOOL",
    "PEI CHUN PUBLIC SCHOOL",
    "FAIRFIELD METHODIST SCHOOL (PRIMARY)",
    "RULANG PRIMARY SCHOOL",
    "NORTHLAND PRIMARY SCHOOL",
    "ST. HILDA'S PRIMARY SCHOOL",
    "PRINCESS ELIZABETH PRIMARY SCHOOL",
    "SINGAPORE CHINESE GIRLS' PRIMARY SCHOOL",
    "SOUTH VIEW PRIMARY SCHOOL",
    "FRONTIER PRIMARY SCHOOL",
    "KUO CHUAN PRESBYTERIAN PRIMARY SCHOOL"
}

# List of primary schools in Singapore
VALID_PRIMARY_SCHOOLS = {
    "ADMIRALTY PRIMARY SCHOOL",
    "AHMAD IBRAHIM PRIMARY SCHOOL",
    "ALEXANDRA PRIMARY SCHOOL",
    "ANCHOR GREEN PRIMARY SCHOOL",
    "ANDERSON PRIMARY SCHOOL",
    "ANG MO KIO PRIMARY SCHOOL",
    "ANGSANA PRIMARY SCHOOL",
    "BALESTIER HILL PRIMARY SCHOOL",
    "BEACON PRIMARY SCHOOL",
    "BEDOK GREEN PRIMARY SCHOOL",
    "BEDOK WEST PRIMARY SCHOOL",
    "BENDEMEER PRIMARY SCHOOL",
    "BLANGAH RISE PRIMARY SCHOOL",
    "BOON LAY GARDEN PRIMARY SCHOOL",
    "BUKIT PANJANG PRIMARY SCHOOL",
    "BUKIT TIMAH PRIMARY SCHOOL",
    "BUKIT VIEW PRIMARY SCHOOL",
    "CANBERRA PRIMARY SCHOOL",
    "CANOSSA CATHOLIC PRIMARY SCHOOL",
    "CANTONMENT PRIMARY SCHOOL",
    "CASUARINA PRIMARY SCHOOL",
    "CEDAR PRIMARY SCHOOL",
    "CHANGKAT PRIMARY SCHOOL",
    "CHONGZHENG PRIMARY SCHOOL",
    "CHUA CHU KANG PRIMARY SCHOOL",
    "CLEMENTI PRIMARY SCHOOL",
    "COMPASSVALE PRIMARY SCHOOL",
    "CONCORD PRIMARY SCHOOL",
    "CORAL PRIMARY SCHOOL",
    "CORPORATION PRIMARY SCHOOL",
    "DA QIAO PRIMARY SCHOOL",
    "DAMAI PRIMARY SCHOOL",
    "DAZHONG PRIMARY SCHOOL",
    "EAST COAST PRIMARY SCHOOL",
    "EAST SPRING PRIMARY SCHOOL",
    "EAST VIEW PRIMARY SCHOOL",
    "EDGEFIELD PRIMARY SCHOOL",
    "ELIAS PARK PRIMARY SCHOOL",
    "ENDEAVOUR PRIMARY SCHOOL",
    "EUNOS PRIMARY SCHOOL",
    "EVERGREEN PRIMARY SCHOOL",
    "FARRER PARK PRIMARY SCHOOL",
    "FENGSHAN PRIMARY SCHOOL",
    "FERN GREEN PRIMARY SCHOOL",
    "FERNVALE PRIMARY SCHOOL",
    "FIRST TOA PAYOH PRIMARY SCHOOL",
    "FRONTIER PRIMARY SCHOOL",
    "FUCHUN PRIMARY SCHOOL",
    "FUHUA PRIMARY SCHOOL",
    "GAN ENG SENG PRIMARY SCHOOL",
    "GONGSHANG PRIMARY SCHOOL",
    "GREENDALE PRIMARY SCHOOL",
    "GREENRIDGE PRIMARY SCHOOL",
    "GREENWOOD PRIMARY SCHOOL",
    "GUANGYANG PRIMARY SCHOOL",
    "HENRY PARK PRIMARY SCHOOL",
    "HOLY INNOCENTS' PRIMARY SCHOOL",
    "HONG KAH PRIMARY SCHOOL",
    "HORIZON PRIMARY SCHOOL",
    "HOUGANG PRIMARY SCHOOL",
    "HUAMIN PRIMARY SCHOOL",
    "INNOVA PRIMARY SCHOOL",
    "JIEMIN PRIMARY SCHOOL",
    "JING SHAN PRIMARY SCHOOL",
    "JUNYUAN PRIMARY SCHOOL",
    "JURONG PRIMARY SCHOOL",
    "JURONG WEST PRIMARY SCHOOL",
    "JUYING PRIMARY SCHOOL",
    "KEMING PRIMARY SCHOOL",
    "KRANJI PRIMARY SCHOOL",
    "KUO CHUAN PRESBYTERIAN PRIMARY SCHOOL",
    "LAKESIDE PRIMARY SCHOOL",
    "LIANHUA PRIMARY SCHOOL",
    "LOYANG PRIMARY SCHOOL",
    "MACPHERSON PRIMARY SCHOOL",
    "MARSILING PRIMARY SCHOOL",
    "MAYFLOWER PRIMARY SCHOOL",
    "MERIDIAN PRIMARY SCHOOL",
    "NAN CHIAU PRIMARY SCHOOL",
    "NAN HUA PRIMARY SCHOOL",
    "NANYANG PRIMARY SCHOOL",
    "NAVAL BASE PRIMARY SCHOOL",
    "NEW TOWN PRIMARY SCHOOL",
    "NGEE ANN PRIMARY SCHOOL",
    "NORTH SPRING PRIMARY SCHOOL",
    "NORTH VIEW PRIMARY SCHOOL",
    "NORTH VISTA PRIMARY SCHOOL",
    "NORTHLAND PRIMARY SCHOOL",
    "NORTHOAKS PRIMARY SCHOOL",
    "NORTHSHORE PRIMARY SCHOOL",
    "OASIS PRIMARY SCHOOL",
    "OPERA ESTATE PRIMARY SCHOOL",
    "PALM VIEW PRIMARY SCHOOL",
    "PARK VIEW PRIMARY SCHOOL",
    "PASIR RIS PRIMARY SCHOOL",
    "PEI HWA PRESBYTERIAN PRIMARY SCHOOL",
    "PEI TONG PRIMARY SCHOOL",
    "PEIYING PRIMARY SCHOOL",
    "PIONEER PRIMARY SCHOOL",
    "PRINCESS ELIZABETH PRIMARY SCHOOL",
    "PUNGGOL COVE PRIMARY SCHOOL",
    "PUNGGOL GREEN PRIMARY SCHOOL",
    "PUNGGOL PRIMARY SCHOOL",
    "PUNGGOL VIEW PRIMARY SCHOOL",
    "QIAONAN PRIMARY SCHOOL",
    "QIFA PRIMARY SCHOOL",
    "QIHUA PRIMARY SCHOOL",
    "QUEENSTOWN PRIMARY SCHOOL",
    "RADIN MAS PRIMARY SCHOOL",
    "RAFFLES GIRLS' PRIMARY SCHOOL",
    "RIVER VALLEY PRIMARY SCHOOL",
    "RIVERSIDE PRIMARY SCHOOL",
    "RIVERVALE PRIMARY SCHOOL",
    "RULANG PRIMARY SCHOOL",
    "SEMBAWANG PRIMARY SCHOOL",
    "SENG KANG PRIMARY SCHOOL",
    "SENGKANG GREEN PRIMARY SCHOOL",
    "SHUQUN PRIMARY SCHOOL",
    "SI LING PRIMARY SCHOOL",
    "SINGAPORE CHINESE GIRLS' PRIMARY SCHOOL",
    "SOUTH VIEW PRIMARY SCHOOL",
    "SPRINGDALE PRIMARY SCHOOL",
    "ST. ANTHONY'S CANOSSIAN PRIMARY SCHOOL",
    "ST. ANTHONY'S PRIMARY SCHOOL",
    "ST. GABRIEL'S PRIMARY SCHOOL",
    "ST. HILDA'S PRIMARY SCHOOL",
    "STAMFORD PRIMARY SCHOOL",
    "TAMPINES NORTH PRIMARY SCHOOL",
    "TAMPINES PRIMARY SCHOOL",
    "TANJONG KATONG PRIMARY SCHOOL",
    "TECK GHEE PRIMARY SCHOOL",
    "TECK WHYE PRIMARY SCHOOL",
    "TELOK KURAU PRIMARY SCHOOL",
    "TEMASEK PRIMARY SCHOOL",
    "TOWNSVILLE PRIMARY SCHOOL",
    "UNITY PRIMARY SCHOOL",
    "VALOUR PRIMARY SCHOOL",
    "WATERWAY PRIMARY SCHOOL",
    "WELLINGTON PRIMARY SCHOOL",
    "WEST GROVE PRIMARY SCHOOL",
    "WEST SPRING PRIMARY SCHOOL",
    "WEST VIEW PRIMARY SCHOOL",
    "WESTWOOD PRIMARY SCHOOL",
    "WHITE SANDS PRIMARY SCHOOL",
    "WOODGROVE PRIMARY SCHOOL",
    "WOODLANDS PRIMARY SCHOOL",
    "WOODLANDS RING PRIMARY SCHOOL",
    "XINGHUA PRIMARY SCHOOL",
    "XINGNAN PRIMARY SCHOOL",
    "XINMIN PRIMARY SCHOOL",
    "XISHAN PRIMARY SCHOOL",
    "YANGZHENG PRIMARY SCHOOL",
    "YEW TEE PRIMARY SCHOOL",
    "YIO CHU KANG PRIMARY SCHOOL",
    "YISHUN PRIMARY SCHOOL",
    "YU NENG PRIMARY SCHOOL",
    "YUHUA PRIMARY SCHOOL",
    "YUMIN PRIMARY SCHOOL",
    "ZHANGDE PRIMARY SCHOOL",
    "ZHENGHUA PRIMARY SCHOOL",
    "ZHONGHUA PRIMARY SCHOOL",
}

VALID_PRIMARY_SCHOOLS = {
    "ADMIRALTY PRIMARY SCHOOL",
    "AHMAD IBRAHIM PRIMARY SCHOOL",
    "AI TONG SCHOOL",
    "ALEXANDRA PRIMARY SCHOOL",
    "ANCHOR GREEN PRIMARY SCHOOL",
    "ANDERSON PRIMARY SCHOOL",
    "ANG MO KIO PRIMARY SCHOOL",
    "ANGLO-CHINESE SCHOOL (JUNIOR)",
    "ANGLO-CHINESE SCHOOL (PRIMARY)",
    "ANGSANA PRIMARY SCHOOL",
    "BEACON PRIMARY SCHOOL",
    "BEDOK GREEN PRIMARY SCHOOL",
    "BENDEMEER PRIMARY SCHOOL",
    "BLANGAH RISE PRIMARY SCHOOL",
    "BOON LAY GARDEN PRIMARY SCHOOL",
    "BUKIT PANJANG PRIMARY SCHOOL",
    "BUKIT TIMAH PRIMARY SCHOOL",
    "BUKIT VIEW PRIMARY SCHOOL",
    "CANBERRA PRIMARY SCHOOL",
    "CANOSSA CATHOLIC PRIMARY SCHOOL",
    "CANTONMENT PRIMARY SCHOOL",
    "CASUARINA PRIMARY SCHOOL",
    "CATHOLIC HIGH SCHOOL",
    "CEDAR PRIMARY SCHOOL",
    "CHANGKAT PRIMARY SCHOOL",
    "CHIJ (KATONG) PRIMARY",
    "CHIJ (KELLOCK)",
    "CHIJ OUR LADY OF GOOD COUNSEL",
    "CHIJ OUR LADY OF THE NATIVITY",
    "CHIJ OUR LADY QUEEN OF PEACE",
    "CHIJ PRIMARY (TOA PAYOH)",
    "CHIJ ST. NICHOLAS GIRLS' SCHOOL",
    "CHONGFU SCHOOL",
    "CHONGZHENG PRIMARY SCHOOL",
    "CHUA CHU KANG PRIMARY SCHOOL",
    "CLEMENTI PRIMARY SCHOOL",
    "COMPASSVALE PRIMARY SCHOOL",
    "CONCORD PRIMARY SCHOOL",
    "CORPORATION PRIMARY SCHOOL",
    "DAMAI PRIMARY SCHOOL",
    "DAZHONG PRIMARY SCHOOL",
    "DE LA SALLE SCHOOL",
    "EAST SPRING PRIMARY SCHOOL",
    "EDGEFIELD PRIMARY SCHOOL",
    "ELIAS PARK PRIMARY SCHOOL",
    "ENDEAVOUR PRIMARY SCHOOL",
    "EVERGREEN PRIMARY SCHOOL",
    "FAIRFIELD METHODIST SCHOOL (PRIMARY)",
    "FARRER PARK PRIMARY SCHOOL",
    "FENGSHAN PRIMARY SCHOOL",
    "FERN GREEN PRIMARY SCHOOL",
    "FERNVALE PRIMARY SCHOOL",
    "FIRST TOA PAYOH PRIMARY SCHOOL",
    "FRONTIER PRIMARY SCHOOL",
    "FUCHUN PRIMARY SCHOOL",
    "FUHUA PRIMARY SCHOOL",
    "GAN ENG SENG PRIMARY SCHOOL",
    "GEYLANG METHODIST SCHOOL (PRIMARY)",
    "GONGSHANG PRIMARY SCHOOL",
    "GREENDALE PRIMARY SCHOOL",
    "GREENRIDGE PRIMARY SCHOOL",
    "GREENWOOD PRIMARY SCHOOL",
    "HAIG GIRLS' SCHOOL",
    "HENRY PARK PRIMARY SCHOOL",
    "HOLY INNOCENTS' PRIMARY SCHOOL",
    "HONG WEN SCHOOL",
    "HORIZON PRIMARY SCHOOL",
    "HOUGANG PRIMARY SCHOOL",
    "HUAMIN PRIMARY SCHOOL",
    "INNOVA PRIMARY SCHOOL",
    "JIEMIN PRIMARY SCHOOL",
    "JING SHAN PRIMARY SCHOOL",
    "JUNYUAN PRIMARY SCHOOL",
    "JURONG PRIMARY SCHOOL",
    "JURONG WEST PRIMARY SCHOOL",
    "KEMING PRIMARY SCHOOL",
    "KHENG CHENG SCHOOL",
    "KONG HWA SCHOOL",
    "KRANJI PRIMARY SCHOOL",
    "KUO CHUAN PRESBYTERIAN PRIMARY SCHOOL",
    "LAKESIDE PRIMARY SCHOOL",
    "LIANHUA PRIMARY SCHOOL",
    "MAHA BODHI SCHOOL",
    "MARIS STELLA HIGH SCHOOL",
    "MARSILING PRIMARY SCHOOL",
    "MARYMOUNT CONVENT SCHOOL",
    "MAYFLOWER PRIMARY SCHOOL",
    "MEE TOH SCHOOL",
    "MERIDIAN PRIMARY SCHOOL",
    "METHODIST GIRLS' SCHOOL (PRIMARY)",
    "MONTFORT JUNIOR SCHOOL",
    "NAN CHIAU PRIMARY SCHOOL",
    "NAN HUA PRIMARY SCHOOL",
    "NANYANG PRIMARY SCHOOL",
    "NAVAL BASE PRIMARY SCHOOL",
    "NEW TOWN PRIMARY SCHOOL",
    "NGEE ANN PRIMARY SCHOOL",
    "NORTH SPRING PRIMARY SCHOOL",
    "NORTH VIEW PRIMARY SCHOOL",
    "NORTH VISTA PRIMARY SCHOOL",
    "NORTHLAND PRIMARY SCHOOL",
    "NORTHOAKS PRIMARY SCHOOL",
    "NORTHSHORE PRIMARY SCHOOL",
    "OASIS PRIMARY SCHOOL",
    "OPERA ESTATE PRIMARY SCHOOL",
    "PALM VIEW PRIMARY SCHOOL",
    "PARK VIEW PRIMARY SCHOOL",
    "PASIR RIS PRIMARY SCHOOL",
    "PAYA LEBAR METHODIST GIRLS' SCHOOL (PRIMARY)",
    "PEI CHUN PUBLIC SCHOOL",
    "PEI HWA PRESBYTERIAN PRIMARY SCHOOL",
    "PEI TONG PRIMARY SCHOOL",
    "PEIYING PRIMARY SCHOOL",
    "PIONEER PRIMARY SCHOOL",
    "POI CHING SCHOOL",
    "PRINCESS ELIZABETH PRIMARY SCHOOL",
    "PUNGGOL COVE PRIMARY SCHOOL",
    "PUNGGOL GREEN PRIMARY SCHOOL",
    "PUNGGOL PRIMARY SCHOOL",
    "PUNGGOL VIEW PRIMARY SCHOOL",
    "QIFA PRIMARY SCHOOL",
    "QIHUA PRIMARY SCHOOL",
    "QUEENSTOWN PRIMARY SCHOOL",
    "RADIN MAS PRIMARY SCHOOL",
    "RAFFLES GIRLS' PRIMARY SCHOOL",
    "RED SWASTIKA SCHOOL",
    "RIVER VALLEY PRIMARY SCHOOL",
    "RIVERSIDE PRIMARY SCHOOL",
    "RIVERVALE PRIMARY SCHOOL",
    "ROSYTH SCHOOL",
    "RULANG PRIMARY SCHOOL",
    "SEMBAWANG PRIMARY SCHOOL",
    "SENG KANG PRIMARY SCHOOL",
    "SENGKANG GREEN PRIMARY SCHOOL",
    "SHUQUN PRIMARY SCHOOL",
    "SI LING PRIMARY SCHOOL",
    "SINGAPORE CHINESE GIRLS' PRIMARY SCHOOL",
    "SOUTH VIEW PRIMARY SCHOOL",
    "SPRINGDALE PRIMARY SCHOOL",
    "ST ANDREW'S SCHOOL (JUNIOR)",
    "ST. ANTHONY'S CANOSSIAN PRIMARY SCHOOL",
    "ST. ANTHONY'S PRIMARY SCHOOL",
    "ST. GABRIEL'S PRIMARY SCHOOL",
    "ST. HILDA'S PRIMARY SCHOOL",
    "ST. JOSEPH'S INSTITUTION JUNIOR",
    "ST. MARGARET'S SCHOOL (PRIMARY)",
    "ST. STEPHEN'S SCHOOL",
    "TAMPINES NORTH PRIMARY SCHOOL",
    "TAMPINES PRIMARY SCHOOL",
    "TANJONG KATONG PRIMARY SCHOOL",
    "TAO NAN SCHOOL",
    "TECK GHEE PRIMARY SCHOOL",
    "TECK WHYE PRIMARY SCHOOL",
    "TELOK KURAU PRIMARY SCHOOL",
    "TEMASEK PRIMARY SCHOOL",
    "TOWNSVILLE PRIMARY SCHOOL",
    "UNITY PRIMARY SCHOOL",
    "VALOUR PRIMARY SCHOOL",
    "WATERWAY PRIMARY SCHOOL",
    "WELLINGTON PRIMARY SCHOOL",
    "WEST GROVE PRIMARY SCHOOL",
    "WEST SPRING PRIMARY SCHOOL",
    "WEST VIEW PRIMARY SCHOOL",
    "WESTWOOD PRIMARY SCHOOL",
    "WHITE SANDS PRIMARY SCHOOL",
    "WOODGROVE PRIMARY SCHOOL",
    "WOODLANDS PRIMARY SCHOOL",
    "WOODLANDS RING PRIMARY SCHOOL",
    "XINGHUA PRIMARY SCHOOL",
    "XINGNAN PRIMARY SCHOOL",
    "XINMIN PRIMARY SCHOOL",
    "XISHAN PRIMARY SCHOOL",
    "YANGZHENG PRIMARY SCHOOL",
    "YEW TEE PRIMARY SCHOOL",
    "YIO CHU KANG PRIMARY SCHOOL",
    "YISHUN PRIMARY SCHOOL",
    "YU NENG PRIMARY SCHOOL",
    "YUHUA PRIMARY SCHOOL",
    "YUMIN PRIMARY SCHOOL",
    "ZHANGDE PRIMARY SCHOOL",
    "ZHENGHUA PRIMARY SCHOOL",
    "ZHONGHUA PRIMARY SCHOOL",
}

#############
## RESULTS ##
#############


def _with_sig_fields(value):
    if isinstance(value, dict):
        updated = {key: _with_sig_fields(subvalue) for key, subvalue in value.items()}
        if "coefficient" in updated and "p_value" in updated and "sig_field" not in updated:
            updated["sig_field"] = updated["p_value"] < 0.10
        return updated
    return value

def _merge_nested_fields(base, overlay):
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, value in overlay.items():
            if key in merged:
                merged[key] = _merge_nested_fields(merged[key], value)
            else:
                merged[key] = value
        return merged
    return overlay

# RDD pooled results
## Good schools
RDD_A_POOLED_RESULTS = {
    "0_to_1": {
        100: {
            "coefficient": -0.435124327902377,
            "p_value": 0.02272550736135,
        }
    },
    "1_to_2": {
        100: {
            "coefficient": 0.500710222715351,
            "p_value": 0.4539065402061053,
        }
    },
}
RDD_A_POOLED_RESULTS = _with_sig_fields(RDD_A_POOLED_RESULTS)
## Normal Schools
RDD_B_POOLED_RESULTS = {
    "0_to_1": {
        100: {
            "coefficient": -0.951404898883193,
            "p_value": 2.2461852629261597e-11,
        },
    },
    "1_to_2": {
        100: {
            "coefficient": 0.180975267231026,
            "p_value": 0.4093794729562797,
        },
    },
    "2plus_to_next": {
        100: {
            "coefficient": -0.373291958853825,
            "p_value": 1.6491026070539193e-08,
        },
    },
}
RDD_B_POOLED_RESULTS = _with_sig_fields(RDD_B_POOLED_RESULTS)

RDD_A_FLAT_TYPE_HETEROGENEITY = {
    "0_to_1": {
        100: {
                "CATHOLIC HIGH SCHOOL": {
                    "overall": {"coefficient": -0.00894041563193004, "p_value": 0.5000916323785115},
                    "3 ROOM": {"coefficient": 0.0919571971055617, "p_value": 0.126977542139451},
                    "4 ROOM": {"coefficient": 0.0178455133751896, "p_value": 0.3434623808567438},
                    "5 ROOM": {"coefficient": -0.0294487930244874, "p_value": 0.5952348519378241},
                },
                "CHIJ PRIMARY (TOA PAYOH)": {
                    "overall": {"coefficient": 0.0208610437622412, "p_value": 0.4466612798228917},
                    "3 ROOM": {"coefficient": 0.0174720761251113, "p_value": 0.5872791516034301},
                    "4 ROOM": {"coefficient": -0.513285385166337, "p_value": 0.3546520632229936},
                },
                "CHIJ ST. NICHOLAS GIRLS' SCHOOL": {
                    "overall": {"coefficient": 0.000790569854844492, "p_value": 0.9358697170524354},
                    "3 ROOM": {"coefficient": 0.00889426986027542, "p_value": 0.407165567664262},
                    "4 ROOM": {"coefficient": 0.0291502167574265, "p_value": 0.5493194405860039},
                },
                "CHONGFU SCHOOL": {
                    "overall": {"coefficient": 0.0107317254404149, "p_value": 0.1487656007798514},
                    "3 ROOM": {"coefficient": 0.0131591922350254, "p_value": 0.2810656643412053},
                    "4 ROOM": {"coefficient": 0.0150245184652658, "p_value": 0.13677039754886},
                    "5 ROOM": {"coefficient": 0.0316681000057368, "p_value": 0.0533278671521683},
                },
                "FAIRFIELD METHODIST SCHOOL (PRIMARY)": {
                    "overall": {"coefficient": -0.221736162395926, "p_value": 0.0790149778745779},
                    "3 ROOM": {"coefficient": -0.440016281909967, "p_value": 0.353038893293377},
                    "4 ROOM": {"coefficient": 22.7104377033764, "p_value": 0.0222527873294041},
                },
                "FRONTIER PRIMARY SCHOOL": {
                    "overall": {"coefficient": -0.0213380529587204, "p_value": 0.0220001369765715},
                    "4 ROOM": {"coefficient": 0.00991074491584909, "p_value": 0.4816654524328423},
                    "5 ROOM": {"coefficient": -0.0523994398681632, "p_value": 0.0002638663497901},
                    "EXECUTIVE": {"coefficient": 0.00345395183558117, "p_value": 0.9357245248511872},
                },
                "HOLY INNOCENTS' PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.0109280054061984, "p_value": 0.321951903192618},
                    "3 ROOM": {"coefficient": 0.110168389230647, "p_value": 0.0006860987129425},
                    "4 ROOM": {"coefficient": 0.0171039181106365, "p_value": 0.2078834598020982},
                    "5 ROOM": {"coefficient": 0.041605545063369, "p_value": 0.1933556269547105},
                    "EXECUTIVE": {"coefficient": 0.808351477665093, "p_value": 0.0581068982633661},
                },
                "KONG HWA SCHOOL": {
                    "overall": {"coefficient": 0.036773849054484, "p_value": 0.0031001613212151},
                    "2 ROOM": {"coefficient": -0.651625941223622, "p_value": 0.2359771598101115},
                    "3 ROOM": {"coefficient": 0.0815005839976597, "p_value": 1.0612800276854432e-07},
                    "4 ROOM": {"coefficient": 0.17750566357251, "p_value": 0.0278984726835152},
                    "5 ROOM": {"coefficient": -0.146892910364893, "p_value": 0.8656748698182095},
                },
                "MAHA BODHI SCHOOL": {
                    "overall": {"coefficient": -0.00561855649815979, "p_value": 0.735932367161015},
                    "4 ROOM": {"coefficient": -0.00273690655498304, "p_value": 0.8686896255264359},
                    "5 ROOM": {"coefficient": 0.0431628562283817, "p_value": 0.6274861012351876},
                    "EXECUTIVE": {"coefficient": 0.0357856669304406, "p_value": 0.2156716968042434},
                },
                "MARIS STELLA HIGH SCHOOL": {
                    "overall": {"coefficient": -0.030345465796172, "p_value": 0.2122322600448075},
                    "3 ROOM": {"coefficient": -0.0404203346792028, "p_value": 0.947364648623292},
                    "4 ROOM": {"coefficient": 0.0493362954542467, "p_value": 0.3963643921990997},
                },
                "NAN CHIAU PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.00383869958423855, "p_value": 0.4822920443539448},
                    "2 ROOM": {"coefficient": 0.0614317463006178, "p_value": 0.0449487565211686},
                    "3 ROOM": {"coefficient": -0.0200606211035469, "p_value": 0.3925556850023037},
                    "4 ROOM": {"coefficient": 0.0195220776779281, "p_value": 0.0065564798749744},
                    "5 ROOM": {"coefficient": -0.00198722784468819, "p_value": 0.8431436391488775},
                    "EXECUTIVE": {"coefficient": -0.0413916752269552, "p_value": 0.3562918886369715},
                },
                "NAN HUA PRIMARY SCHOOL": {
                    "overall": {"coefficient": -0.00267577547702191, "p_value": 0.7781883835980978},
                    "3 ROOM": {"coefficient": 0.0374182467283373, "p_value": 0.1842425873654705},
                    "4 ROOM": {"coefficient": -0.00615888905038875, "p_value": 0.5743405177322842},
                    "5 ROOM": {"coefficient": -0.0308549306338121, "p_value": 0.2314912517920042},
                },
                "NORTHLAND PRIMARY SCHOOL": {
                    "overall": {"coefficient": -0.00422760767242358, "p_value": 0.4840788522200741},
                    "3 ROOM": {"coefficient": 0.0233648537890803, "p_value": 0.0376228802029852},
                    "4 ROOM": {"coefficient": -0.00311341608971683, "p_value": 0.7032205532288986},
                    "5 ROOM": {"coefficient": -0.0287956586713025, "p_value": 0.1710465426655348},
                    "EXECUTIVE": {"coefficient": 0.0119025557360597, "p_value": 0.6096695203208351},
                },
                "PEI CHUN PUBLIC SCHOOL": {
                    "overall": {"coefficient": 0.00839966558889449, "p_value": 0.6555726880109154},
                    "3 ROOM": {"coefficient": 0.0115254137612184, "p_value": 0.7903610389626556},
                    "4 ROOM": {"coefficient": 0.0964588022712098, "p_value": 0.0001495764039919},
                },
                "PRINCESS ELIZABETH PRIMARY SCHOOL": {
                    "overall": {"coefficient": -0.0132303762289284, "p_value": 0.0559661725355099},
                    "2 ROOM": {"coefficient": 0.0971381115960506, "p_value": 0.7628507056391308},
                    "3 ROOM": {"coefficient": 0.0264828183872772, "p_value": 0.08841363643609},
                    "4 ROOM": {"coefficient": -0.0133599833616836, "p_value": 0.2279818548083543},
                    "5 ROOM": {"coefficient": 0.0262016776317526, "p_value": 0.0543796359800437},
                    "EXECUTIVE": {"coefficient": 0.452570540379507, "p_value": 0.0032702700416691},
                },
                "RED SWASTIKA SCHOOL": {
                    "overall": {"coefficient": 0.0212169855540247, "p_value": 0.0044278386799047},
                    "3 ROOM": {"coefficient": 0.0160733413748386, "p_value": 0.1086223162681856},
                    "4 ROOM": {"coefficient": -0.0228387279169682, "p_value": 0.0773651436706868},
                    "5 ROOM": {"coefficient": -0.0334669370563454, "p_value": 0.5431078698670183},
                },
                "ROSYTH SCHOOL": {
                    "overall": {"coefficient": 0.00348095487088962, "p_value": 0.6177034892028598},
                    "3 ROOM": {"coefficient": 0.00631635764977778, "p_value": 0.6221289104030082},
                    "4 ROOM": {"coefficient": 0.0173099390887441, "p_value": 0.0867709608045708},
                    "5 ROOM": {"coefficient": -0.0250888842613183, "p_value": 0.0466362476953069},
                },
                "RULANG PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.00611178658236722, "p_value": 0.3676836493825964},
                    "3 ROOM": {"coefficient": -0.0241051193981577, "p_value": 0.0572533985044645},
                    "4 ROOM": {"coefficient": 0.00617477355701412, "p_value": 0.5653598779820525},
                    "5 ROOM": {"coefficient": 0.0149371599573584, "p_value": 0.7246571140768456},
                },
                "SOUTH VIEW PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.00947334438088676, "p_value": 0.0454771863456675},
                    "3 ROOM": {"coefficient": -0.0184352886022979, "p_value": 0.5865636616613994},
                    "4 ROOM": {"coefficient": 0.00164898033691285, "p_value": 0.7926244932252079},
                    "5 ROOM": {"coefficient": 0.020907501111177, "p_value": 0.0037155112398373},
                    "EXECUTIVE": {"coefficient": -3.933320249494e-05, "p_value": 0.9997759293363776},
                },
                "ST. HILDA'S PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.0072215664511377, "p_value": 0.2523837884241594},
                    "3 ROOM": {"coefficient": 0.0548724466446968, "p_value": 0.1093537074326997},
                    "4 ROOM": {"coefficient": 0.016334257949143, "p_value": 0.0944902330782339},
                    "5 ROOM": {"coefficient": -0.019998601786855, "p_value": 0.0349512251266368},
                    "EXECUTIVE": {"coefficient": -0.0439939100631893, "p_value": 0.3970263681162514},
                },
                "ST. JOSEPH'S INSTITUTION JUNIOR": {
                    "overall": {"coefficient": -0.0134262854696979, "p_value": 0.8299352143298415},
                    "3 ROOM": {"coefficient": 0.0112989280665725, "p_value": 0.98744678760771},
                    "4 ROOM": {"coefficient": -0.0832454117680107, "p_value": 0.3639678782810124},
                },
            }
        },
    "1_to_2": {
        100: {
                "AI TONG SCHOOL": {
                    "overall": {"coefficient": -0.00729681579566099, "p_value": 0.6300153847396026},
                    "3 ROOM": {"coefficient": -0.0315923588792626, "p_value": 0.2993873268595146},
                    "4 ROOM": {"coefficient": 0.0160226765883473, "p_value": 0.3455159180789912},
                    "5 ROOM": {"coefficient": -0.075131857909268, "p_value": 0.1163722191093712},
                },
                "CATHOLIC HIGH SCHOOL": {
                    "overall": {"coefficient": -0.0220574326165542, "p_value": 0.133829930580202},
                    "3 ROOM": {"coefficient": 0.0907644375444152, "p_value": 0.4569185562194969},
                    "4 ROOM": {"coefficient": 0.0208632061933016, "p_value": 0.3973899641514755},
                    "5 ROOM": {"coefficient": 0.00025128888300685, "p_value": 0.994682746925206},
                },
                "CHIJ PRIMARY (TOA PAYOH)": {
                    "overall": {"coefficient": 0.0208957134233165, "p_value": 0.1841715382933529},
                    "3 ROOM": {"coefficient": -0.0047033200737282, "p_value": 0.7842823769257659},
                    "4 ROOM": {"coefficient": 0.0600121446073991, "p_value": 0.3755343701748661},
                },
                "CHONGFU SCHOOL": {
                    "overall": {"coefficient": 0.0016233911625676, "p_value": 0.9775936604707446},
                    "4 ROOM": {"coefficient": 0.196919323870093, "p_value": 0.4365034754674399},
                },
                "KUO CHUAN PRESBYTERIAN PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.0158442444162745, "p_value": 0.3399933158932438},
                    "3 ROOM": {"coefficient": 0.0413955257648506, "p_value": 0.6431147799204728},
                    "4 ROOM": {"coefficient": 0.0343402075295067, "p_value": 0.1495771408651253},
                    "5 ROOM": {"coefficient": 0.0980452643459246, "p_value": 0.6674275916498957},
                },
                "NORTHLAND PRIMARY SCHOOL": {
                    "overall": {"coefficient": 0.0127183773944601, "p_value": 0.4181757370773605},
                    "3 ROOM": {"coefficient": 0.044851493438268, "p_value": 0.4864943808966193},
                    "4 ROOM": {"coefficient": 0.0121699760526708, "p_value": 0.5790847675027582},
                },
                "PEI CHUN PUBLIC SCHOOL": {
                    "overall": {"coefficient": 0.0131433008778596, "p_value": 0.2287926106083374},
                    "4 ROOM": {"coefficient": -0.032426742740198, "p_value": 0.0203283447773264},
                    "5 ROOM": {"coefficient": -0.0177101736842847, "p_value": 0.3044383750444637},
                },
        }
    },
}
RDD_A_FLAT_TYPE_HETEROGENEITY = _with_sig_fields(RDD_A_FLAT_TYPE_HETEROGENEITY)
RDD_A_FLAT_TYPE_BALANCE_HIGHLIGHTS = {'0_to_1': {100: {'CATHOLIC HIGH SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                            'mall '
                                                                                            'access',
                                                      'standout_numeric_balance_value': 0.8088531082333527,
                                                      'standout_numeric_balance_direction': 'inside_higher',
                                                      'average_abs_smd_numeric': 0.5364415690072274,
                                                      'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                                'composition',
                                                      'standout_categorical_balance_value': 0.6190476190476191,
                                                      'average_tvd_categorical': 0.3333333333333333},
                                           '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                            'mall '
                                                                                            'access',
                                                      'standout_numeric_balance_value': 0.8111660188444766,
                                                      'standout_numeric_balance_direction': 'inside_higher',
                                                      'average_abs_smd_numeric': 0.4339677822963808,
                                                      'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                'composition',
                                                      'standout_categorical_balance_value': 0.3664801262734969,
                                                      'average_tvd_categorical': 0.24160568230736115},
                                           '5 ROOM': {'standout_numeric_balance_dimension': 'floor '
                                                                                            'area',
                                                      'standout_numeric_balance_value': 0.9535584131661724,
                                                      'standout_numeric_balance_direction': 'inside_lower',
                                                      'average_abs_smd_numeric': 0.26503815561298966,
                                                      'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                'composition',
                                                      'standout_categorical_balance_value': 0.3651026392961877,
                                                      'average_tvd_categorical': 0.23936950146627567}},
                  'CHIJ PRIMARY (TOA PAYOH)': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.5480621702666647,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.16131388417363898,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.406265664160401,
                                                          'average_tvd_categorical': 0.14680451127819547},
                                               '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'mall '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 1.163248405606839,
                                                          'standout_numeric_balance_direction': 'inside_lower',
                                                          'average_abs_smd_numeric': 0.9082029390751911,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.7323232323232323,
                                                          'average_tvd_categorical': 0.468013468013468}},
                  "CHIJ ST. NICHOLAS GIRLS' SCHOOL": {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                       'lease',
                                                                 'standout_numeric_balance_value': 0.4559968872437501,
                                                                 'standout_numeric_balance_direction': 'inside_higher',
                                                                 'average_abs_smd_numeric': 0.2161737168287513,
                                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                           'composition',
                                                                 'standout_categorical_balance_value': 0.2867867867867867,
                                                                 'average_tvd_categorical': 0.10015898251192362},
                                                      '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                       'mall '
                                                                                                       'access',
                                                                 'standout_numeric_balance_value': 0.2893395961204164,
                                                                 'standout_numeric_balance_direction': 'inside_lower',
                                                                 'average_abs_smd_numeric': 0.1382863138994757,
                                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                           'composition',
                                                                 'standout_categorical_balance_value': 0.5219638242894057,
                                                                 'average_tvd_categorical': 0.23600344530577086}},
                  'CHONGFU SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                      'year '
                                                                                      'composition',
                                                'standout_numeric_balance_value': 0.2866920267229267,
                                                'standout_numeric_balance_direction': 'inside_higher',
                                                'average_abs_smd_numeric': 0.20373619573328516,
                                                'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                          'composition',
                                                'standout_categorical_balance_value': 0.3408602984920203,
                                                'average_tvd_categorical': 0.20160820982385347},
                                     '4 ROOM': {'standout_numeric_balance_dimension': 'floor area',
                                                'standout_numeric_balance_value': 0.2772141006716905,
                                                'standout_numeric_balance_direction': 'inside_lower',
                                                'average_abs_smd_numeric': 0.16753068448818573,
                                                'standout_categorical_balance_dimension': 'flat-model '
                                                                                          'composition',
                                                'standout_categorical_balance_value': 0.2359756565811702,
                                                'average_tvd_categorical': 0.18797035785593602},
                                     '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                      'lease',
                                                'standout_numeric_balance_value': 0.5637508782521539,
                                                'standout_numeric_balance_direction': 'inside_lower',
                                                'average_abs_smd_numeric': 0.38223289501076846,
                                                'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                          'composition',
                                                'standout_categorical_balance_value': 0.3701464775633574,
                                                'average_tvd_categorical': 0.24734557854762457}},
                  'FAIRFIELD METHODIST SCHOOL (PRIMARY)': {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                            'lease',
                                                                      'standout_numeric_balance_value': 0.5537139090571679,
                                                                      'standout_numeric_balance_direction': 'inside_higher',
                                                                      'average_abs_smd_numeric': 0.18862998841099834,
                                                                      'standout_categorical_balance_dimension': 'storey-range '
                                                                                                                'composition',
                                                                      'standout_categorical_balance_value': 0.4101307189542483,
                                                                      'average_tvd_categorical': 0.1779003267973856},
                                                           '4 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                            'lease',
                                                                      'standout_numeric_balance_value': 10.394239785350557,
                                                                      'standout_numeric_balance_direction': 'inside_higher',
                                                                      'average_abs_smd_numeric': 2.653711249834384,
                                                                      'standout_categorical_balance_dimension': 'flat-model '
                                                                                                                'composition',
                                                                      'standout_categorical_balance_value': 0.9411764705882352,
                                                                      'average_tvd_categorical': 0.5992169595110771}},
                  'FRONTIER PRIMARY SCHOOL': {'4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                               'MRT '
                                                                                               'access',
                                                         'standout_numeric_balance_value': 0.5563160727707067,
                                                         'standout_numeric_balance_direction': 'inside_higher',
                                                         'average_abs_smd_numeric': 0.2802753412511016,
                                                         'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                   'composition',
                                                         'standout_categorical_balance_value': 0.3195139156085674,
                                                         'average_tvd_categorical': 0.1557730537386174},
                                              '5 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                               'MRT '
                                                                                               'access',
                                                         'standout_numeric_balance_value': 0.4358929849121755,
                                                         'standout_numeric_balance_direction': 'inside_higher',
                                                         'average_abs_smd_numeric': 0.2905882281139122,
                                                         'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                   'composition',
                                                         'standout_categorical_balance_value': 0.2854460093896714,
                                                         'average_tvd_categorical': 0.11628903857930188},
                                              'EXECUTIVE': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                  'year '
                                                                                                  'composition',
                                                            'standout_numeric_balance_value': 0.7425841393960242,
                                                            'standout_numeric_balance_direction': 'inside_higher',
                                                            'average_abs_smd_numeric': 0.2584368396092794,
                                                            'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                      'composition',
                                                            'standout_categorical_balance_value': 0.5224489795918368,
                                                            'average_tvd_categorical': 0.3525510204081633}},
                  "HOLY INNOCENTS' PRIMARY SCHOOL": {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                      'MRT '
                                                                                                      'access',
                                                                'standout_numeric_balance_value': 0.7668946966722594,
                                                                'standout_numeric_balance_direction': 'inside_higher',
                                                                'average_abs_smd_numeric': 0.4924623086585073,
                                                                'standout_categorical_balance_dimension': 'flat-model '
                                                                                                          'composition',
                                                                'standout_categorical_balance_value': 0.5132557971537961,
                                                                'average_tvd_categorical': 0.3024272195333381},
                                                     '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                      'mall '
                                                                                                      'access',
                                                                'standout_numeric_balance_value': 0.3388933796370187,
                                                                'standout_numeric_balance_direction': 'inside_lower',
                                                                'average_abs_smd_numeric': 0.14857038605445752,
                                                                'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                          'composition',
                                                                'standout_categorical_balance_value': 0.2521728917077753,
                                                                'average_tvd_categorical': 0.19206013624618268},
                                                     '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                      'lease',
                                                                'standout_numeric_balance_value': 0.4166042878731173,
                                                                'standout_numeric_balance_direction': 'inside_lower',
                                                                'average_abs_smd_numeric': 0.20840507882346315,
                                                                'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                          'composition',
                                                                'standout_categorical_balance_value': 0.4065656565656565,
                                                                'average_tvd_categorical': 0.2602495543672014},
                                                     'EXECUTIVE': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                         'year '
                                                                                                         'composition',
                                                                   'standout_numeric_balance_value': 1.9123705086843448,
                                                                   'standout_numeric_balance_direction': 'inside_higher',
                                                                   'average_abs_smd_numeric': 0.8120714034202182,
                                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                             'composition',
                                                                   'standout_categorical_balance_value': 0.8583333333333334,
                                                                   'average_tvd_categorical': 0.31375}},
                  'KONG HWA SCHOOL': {'2 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                       'year '
                                                                                       'composition',
                                                 'standout_numeric_balance_value': 3.350447870679365,
                                                 'standout_numeric_balance_direction': 'inside_higher',
                                                 'average_abs_smd_numeric': 0.8962408487592698,
                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                           'composition',
                                                 'standout_categorical_balance_value': 1.0,
                                                 'average_tvd_categorical': 0.2879504914452129},
                                      '3 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                       'year '
                                                                                       'composition',
                                                 'standout_numeric_balance_value': 0.3548147109183889,
                                                 'standout_numeric_balance_direction': 'inside_higher',
                                                 'average_abs_smd_numeric': 0.11608482234519911,
                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                           'composition',
                                                 'standout_categorical_balance_value': 0.35695339143615,
                                                 'average_tvd_categorical': 0.2068373436907919},
                                      '4 ROOM': {'standout_numeric_balance_dimension': 'MRT line '
                                                                                       'connectivity',
                                                 'standout_numeric_balance_value': 0.5058518300944128,
                                                 'standout_numeric_balance_direction': 'inside_lower',
                                                 'average_abs_smd_numeric': 0.2006851404641444,
                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                           'composition',
                                                 'standout_categorical_balance_value': 0.511111111111111,
                                                 'average_tvd_categorical': 0.21960784313725482},
                                      '5 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                       'year '
                                                                                       'composition',
                                                 'standout_numeric_balance_value': 1.2791182307152995,
                                                 'standout_numeric_balance_direction': 'inside_higher',
                                                 'average_abs_smd_numeric': 0.7862750266411185,
                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                           'composition',
                                                 'standout_categorical_balance_value': 0.6504702194357367,
                                                 'average_tvd_categorical': 0.2825235109717868}},
                  'MAHA BODHI SCHOOL': {'4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                         'mall '
                                                                                         'access',
                                                   'standout_numeric_balance_value': 0.5819587255022072,
                                                   'standout_numeric_balance_direction': 'inside_lower',
                                                   'average_abs_smd_numeric': 0.25073564700672185,
                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                             'composition',
                                                   'standout_categorical_balance_value': 0.3780487804878048,
                                                   'average_tvd_categorical': 0.24593495934959345},
                                        '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                         'lease',
                                                   'standout_numeric_balance_value': 1.2015695479274748,
                                                   'standout_numeric_balance_direction': 'inside_higher',
                                                   'average_abs_smd_numeric': 0.6723629628486147,
                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                             'composition',
                                                   'standout_categorical_balance_value': 0.6037296037296038,
                                                   'average_tvd_categorical': 0.2403846153846154},
                                        'EXECUTIVE': {'standout_numeric_balance_dimension': 'remaining '
                                                                                            'lease',
                                                      'standout_numeric_balance_value': 0.3896959982151151,
                                                      'standout_numeric_balance_direction': 'inside_lower',
                                                      'average_abs_smd_numeric': 0.23640140173918853,
                                                      'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                'composition',
                                                      'standout_categorical_balance_value': 0.4778378378378378,
                                                      'average_tvd_categorical': 0.2585585585585585}},
                  'MARIS STELLA HIGH SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'mall '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.715111968397319,
                                                          'standout_numeric_balance_direction': 'inside_lower',
                                                          'average_abs_smd_numeric': 0.25977449303053407,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.4292682926829268,
                                                          'average_tvd_categorical': 0.23827392120075044},
                                               '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 1.787978809130978,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.9409276183333145,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.6989553656220322,
                                                          'average_tvd_categorical': 0.35161443494776823}},
                  'NAN CHIAU PRIMARY SCHOOL': {'2 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.7528730737703859,
                                                          'standout_numeric_balance_direction': 'inside_lower',
                                                          'average_abs_smd_numeric': 0.313112958868019,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.3693162096494272,
                                                          'average_tvd_categorical': 0.18630683790350566},
                                               '3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 1.543608737945949,
                                                          'standout_numeric_balance_direction': 'inside_lower',
                                                          'average_abs_smd_numeric': 0.6397738523550133,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.4035549703752469,
                                                          'average_tvd_categorical': 0.17610269914417379},
                                               '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'mall '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.7249639598268376,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.40339062816818877,
                                                          'standout_categorical_balance_dimension': 'flat-model '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.4061730084861757,
                                                          'average_tvd_categorical': 0.2871807907395096},
                                               '5 ROOM': {'standout_numeric_balance_dimension': 'MRT '
                                                                                                'line '
                                                                                                'connectivity',
                                                          'standout_numeric_balance_value': 0.767074719366357,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.27674466742158405,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.3162158601914464,
                                                          'average_tvd_categorical': 0.17013919381751116},
                                               'EXECUTIVE': {'standout_numeric_balance_dimension': 'floor '
                                                                                                   'area',
                                                             'standout_numeric_balance_value': 0.8914454387978842,
                                                             'standout_numeric_balance_direction': 'inside_lower',
                                                             'average_abs_smd_numeric': 0.4662237663803212,
                                                             'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                       'composition',
                                                             'standout_categorical_balance_value': 0.6688311688311687,
                                                             'average_tvd_categorical': 0.3674242424242424}},
                  'NAN HUA PRIMARY SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                              'mall '
                                                                                              'access',
                                                        'standout_numeric_balance_value': 0.6370259156977748,
                                                        'standout_numeric_balance_direction': 'inside_higher',
                                                        'average_abs_smd_numeric': 0.2863673585318773,
                                                        'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                  'composition',
                                                        'standout_categorical_balance_value': 0.4146272590361446,
                                                        'average_tvd_categorical': 0.1441547439759036},
                                             '4 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                              'lease',
                                                        'standout_numeric_balance_value': 0.5734238399559354,
                                                        'standout_numeric_balance_direction': 'inside_lower',
                                                        'average_abs_smd_numeric': 0.4908913609690457,
                                                        'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                  'composition',
                                                        'standout_categorical_balance_value': 0.3233237350884409,
                                                        'average_tvd_categorical': 0.20182023858494447},
                                             '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                              'lease',
                                                        'standout_numeric_balance_value': 1.1391836255947332,
                                                        'standout_numeric_balance_direction': 'inside_lower',
                                                        'average_abs_smd_numeric': 0.5382315027125094,
                                                        'standout_categorical_balance_dimension': 'flat-model '
                                                                                                  'composition',
                                                        'standout_categorical_balance_value': 0.3306896551724138,
                                                        'average_tvd_categorical': 0.22439655172413792}},
                  'NORTHLAND PRIMARY SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.5979234666842077,
                                                          'standout_numeric_balance_direction': 'inside_lower',
                                                          'average_abs_smd_numeric': 0.3945232895950463,
                                                          'standout_categorical_balance_dimension': 'flat-model '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.4904957313334276,
                                                          'average_tvd_categorical': 0.2838958068015659},
                                               '4 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                'year '
                                                                                                'composition',
                                                          'standout_numeric_balance_value': 0.4600581504384116,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.1714398407760066,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.2449087144739318,
                                                          'average_tvd_categorical': 0.12020515716167889},
                                               '5 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                'MRT '
                                                                                                'access',
                                                          'standout_numeric_balance_value': 0.6647175674212307,
                                                          'standout_numeric_balance_direction': 'inside_higher',
                                                          'average_abs_smd_numeric': 0.4041979198288545,
                                                          'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                    'composition',
                                                          'standout_categorical_balance_value': 0.3479853479853479,
                                                          'average_tvd_categorical': 0.1923076923076923},
                                               'EXECUTIVE': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                   'mall '
                                                                                                   'access',
                                                             'standout_numeric_balance_value': 1.5571595213818323,
                                                             'standout_numeric_balance_direction': 'inside_higher',
                                                             'average_abs_smd_numeric': 0.4463106088253313,
                                                             'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                       'composition',
                                                             'standout_categorical_balance_value': 0.4603174603174603,
                                                             'average_tvd_categorical': 0.24662698412698408}},
                  'PEI CHUN PUBLIC SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                              'lease',
                                                        'standout_numeric_balance_value': 0.5576337168382511,
                                                        'standout_numeric_balance_direction': 'inside_lower',
                                                        'average_abs_smd_numeric': 0.3097825084277191,
                                                        'standout_categorical_balance_dimension': 'flat-model '
                                                                                                  'composition',
                                                        'standout_categorical_balance_value': 0.5537029244687566,
                                                        'average_tvd_categorical': 0.30359772775089416},
                                             '4 ROOM': {'standout_numeric_balance_dimension': 'MRT '
                                                                                              'line '
                                                                                              'connectivity',
                                                        'standout_numeric_balance_value': 3.191564815705719,
                                                        'standout_numeric_balance_direction': 'inside_higher',
                                                        'average_abs_smd_numeric': 1.775835459798092,
                                                        'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                  'composition',
                                                        'standout_categorical_balance_value': 0.6541666666666667,
                                                        'average_tvd_categorical': 0.4376602564102564}},
                  'PRINCESS ELIZABETH PRIMARY SCHOOL': {'2 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                         'MRT '
                                                                                                         'access',
                                                                   'standout_numeric_balance_value': 2.0710421739487854,
                                                                   'standout_numeric_balance_direction': 'inside_higher',
                                                                   'average_abs_smd_numeric': 1.2165710132711611,
                                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                             'composition',
                                                                   'standout_categorical_balance_value': 0.7267552182163188,
                                                                   'average_tvd_categorical': 0.40117014547754587},
                                                        '3 ROOM': {'standout_numeric_balance_dimension': 'floor '
                                                                                                         'area',
                                                                   'standout_numeric_balance_value': 0.6087084534159386,
                                                                   'standout_numeric_balance_direction': 'inside_lower',
                                                                   'average_abs_smd_numeric': 0.4231216339862132,
                                                                   'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                                             'composition',
                                                                   'standout_categorical_balance_value': 0.3775694504171325,
                                                                   'average_tvd_categorical': 0.25088156876236345},
                                                        '4 ROOM': {'standout_numeric_balance_dimension': 'MRT '
                                                                                                         'line '
                                                                                                         'connectivity',
                                                                   'standout_numeric_balance_value': 0.1769953162672835,
                                                                   'standout_numeric_balance_direction': 'inside_lower',
                                                                   'average_abs_smd_numeric': 0.07858202539866387,
                                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                             'composition',
                                                                   'standout_categorical_balance_value': 0.2646648557374642,
                                                                   'average_tvd_categorical': 0.13336025255120765},
                                                        '5 ROOM': {'standout_numeric_balance_dimension': 'floor '
                                                                                                         'area',
                                                                   'standout_numeric_balance_value': 0.6152370735285666,
                                                                   'standout_numeric_balance_direction': 'inside_lower',
                                                                   'average_abs_smd_numeric': 0.19968962522601985,
                                                                   'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                             'composition',
                                                                   'standout_categorical_balance_value': 0.30052790346908,
                                                                   'average_tvd_categorical': 0.20578808446455504},
                                                        'EXECUTIVE': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                            'mall '
                                                                                                            'access',
                                                                      'standout_numeric_balance_value': 0.8255328793296715,
                                                                      'standout_numeric_balance_direction': 'inside_lower',
                                                                      'average_abs_smd_numeric': 0.5371593765654267,
                                                                      'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                                'composition',
                                                                      'standout_categorical_balance_value': 0.5409076875578883,
                                                                      'average_tvd_categorical': 0.36801481938870023}},
                  'RED SWASTIKA SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                           'lease',
                                                     'standout_numeric_balance_value': 0.4076822655336559,
                                                     'standout_numeric_balance_direction': 'inside_lower',
                                                     'average_abs_smd_numeric': 0.2770850119668643,
                                                     'standout_categorical_balance_dimension': 'flat-model '
                                                                                               'composition',
                                                     'standout_categorical_balance_value': 0.3419638125520478,
                                                     'average_tvd_categorical': 0.2013589219471572},
                                          '4 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                           'mall '
                                                                                           'access',
                                                     'standout_numeric_balance_value': 0.8599796893233811,
                                                     'standout_numeric_balance_direction': 'inside_lower',
                                                     'average_abs_smd_numeric': 0.38926444970238666,
                                                     'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                               'composition',
                                                     'standout_categorical_balance_value': 0.3461064425770308,
                                                     'average_tvd_categorical': 0.21344537815126047},
                                          '5 ROOM': {'standout_numeric_balance_dimension': 'floor '
                                                                                           'area',
                                                     'standout_numeric_balance_value': 1.3290575708549022,
                                                     'standout_numeric_balance_direction': 'inside_lower',
                                                     'average_abs_smd_numeric': 0.6382843793637857,
                                                     'standout_categorical_balance_dimension': 'flat-model '
                                                                                               'composition',
                                                     'standout_categorical_balance_value': 0.6363636363636365,
                                                     'average_tvd_categorical': 0.4356060606060606}},
                  'ROSYTH SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby MRT '
                                                                                     'access',
                                               'standout_numeric_balance_value': 1.0534447589283895,
                                               'standout_numeric_balance_direction': 'inside_lower',
                                               'average_abs_smd_numeric': 0.7047539013829431,
                                               'standout_categorical_balance_dimension': 'flat-model '
                                                                                         'composition',
                                               'standout_categorical_balance_value': 0.4222261235955056,
                                               'average_tvd_categorical': 0.3306706460674157},
                                    '4 ROOM': {'standout_numeric_balance_dimension': 'nearby MRT '
                                                                                     'access',
                                               'standout_numeric_balance_value': 0.9438047568781182,
                                               'standout_numeric_balance_direction': 'inside_lower',
                                               'average_abs_smd_numeric': 0.6259536369754847,
                                               'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                         'composition',
                                               'standout_categorical_balance_value': 0.3323733569635209,
                                               'average_tvd_categorical': 0.24220942253729139},
                                    '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                     'lease',
                                               'standout_numeric_balance_value': 0.5039166426059807,
                                               'standout_numeric_balance_direction': 'inside_higher',
                                               'average_abs_smd_numeric': 0.3895403224123206,
                                               'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                         'composition',
                                               'standout_categorical_balance_value': 0.402457757296467,
                                               'average_tvd_categorical': 0.1466973886328725}},
                  'RULANG PRIMARY SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                             'lease',
                                                       'standout_numeric_balance_value': 3.0030377354165414,
                                                       'standout_numeric_balance_direction': 'inside_lower',
                                                       'average_abs_smd_numeric': 0.9013511374109592,
                                                       'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                                 'composition',
                                                       'standout_categorical_balance_value': 0.677815463852773,
                                                       'average_tvd_categorical': 0.4390113686326236},
                                            '4 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                             'lease',
                                                       'standout_numeric_balance_value': 1.2789462866571295,
                                                       'standout_numeric_balance_direction': 'inside_lower',
                                                       'average_abs_smd_numeric': 0.4982235822919814,
                                                       'standout_categorical_balance_dimension': 'school-quadrant '
                                                                                                 'composition',
                                                       'standout_categorical_balance_value': 0.4462805022506515,
                                                       'average_tvd_categorical': 0.26634683724235964},
                                            '5 ROOM': {'standout_numeric_balance_dimension': 'floor '
                                                                                             'area',
                                                       'standout_numeric_balance_value': 2.8213664474773705,
                                                       'standout_numeric_balance_direction': 'inside_higher',
                                                       'average_abs_smd_numeric': 1.3728185520266185,
                                                       'standout_categorical_balance_dimension': 'flat-model '
                                                                                                 'composition',
                                                       'standout_categorical_balance_value': 0.8020527859237536,
                                                       'average_tvd_categorical': 0.5747800586510263}},
                  'SOUTH VIEW PRIMARY SCHOOL': {'3 ROOM': {'standout_numeric_balance_dimension': 'nearby '
                                                                                                 'mall '
                                                                                                 'access',
                                                           'standout_numeric_balance_value': 1.3126028029155663,
                                                           'standout_numeric_balance_direction': 'inside_lower',
                                                           'average_abs_smd_numeric': 0.6192411555212124,
                                                           'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                     'composition',
                                                           'standout_categorical_balance_value': 0.5250255362614913,
                                                           'average_tvd_categorical': 0.23740211099761657},
                                                '4 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                 'year '
                                                                                                 'composition',
                                                           'standout_numeric_balance_value': 0.4006006559488984,
                                                           'standout_numeric_balance_direction': 'inside_higher',
                                                           'average_abs_smd_numeric': 0.2753736381950501,
                                                           'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                     'composition',
                                                           'standout_categorical_balance_value': 0.245170477444316,
                                                           'average_tvd_categorical': 0.14321986082377275},
                                                '5 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                 'year '
                                                                                                 'composition',
                                                           'standout_numeric_balance_value': 0.4718253180996863,
                                                           'standout_numeric_balance_direction': 'inside_higher',
                                                           'average_abs_smd_numeric': 0.1621824209516451,
                                                           'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                     'composition',
                                                           'standout_categorical_balance_value': 0.2865954351105518,
                                                           'average_tvd_categorical': 0.11480955823938441},
                                                'EXECUTIVE': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                    'year '
                                                                                                    'composition',
                                                              'standout_numeric_balance_value': 1.8486394296086903,
                                                              'standout_numeric_balance_direction': 'inside_higher',
                                                              'average_abs_smd_numeric': 0.873347193189875,
                                                              'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                        'composition',
                                                              'standout_categorical_balance_value': 0.8571428571428569,
                                                              'average_tvd_categorical': 0.3928571428571428}},
                  "ST. HILDA'S PRIMARY SCHOOL": {'3 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                  'lease',
                                                            'standout_numeric_balance_value': 0.7237387647257262,
                                                            'standout_numeric_balance_direction': 'inside_lower',
                                                            'average_abs_smd_numeric': 0.332874972442688,
                                                            'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                      'composition',
                                                            'standout_categorical_balance_value': 0.3978611073507513,
                                                            'average_tvd_categorical': 0.23768106132394745},
                                                 '4 ROOM': {'standout_numeric_balance_dimension': 'MRT '
                                                                                                  'line '
                                                                                                  'connectivity',
                                                            'standout_numeric_balance_value': 0.3710127265995264,
                                                            'standout_numeric_balance_direction': 'inside_lower',
                                                            'average_abs_smd_numeric': 0.1838539407556147,
                                                            'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                      'composition',
                                                            'standout_categorical_balance_value': 0.2621257832443722,
                                                            'average_tvd_categorical': 0.15895219308424222},
                                                 '5 ROOM': {'standout_numeric_balance_dimension': 'remaining '
                                                                                                  'lease',
                                                            'standout_numeric_balance_value': 0.2427143464637997,
                                                            'standout_numeric_balance_direction': 'inside_higher',
                                                            'average_abs_smd_numeric': 0.1602659539955918,
                                                            'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                      'composition',
                                                            'standout_categorical_balance_value': 0.3167989417989417,
                                                            'average_tvd_categorical': 0.138558201058201},
                                                 'EXECUTIVE': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                     'year '
                                                                                                     'composition',
                                                               'standout_numeric_balance_value': 0.4752774433035754,
                                                               'standout_numeric_balance_direction': 'inside_lower',
                                                               'average_abs_smd_numeric': 0.21874053854534614,
                                                               'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                         'composition',
                                                               'standout_categorical_balance_value': 0.7142857142857143,
                                                               'average_tvd_categorical': 0.2654220779220779}},
                  "ST. JOSEPH'S INSTITUTION JUNIOR": {'3 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                       'year '
                                                                                                       'composition',
                                                                 'standout_numeric_balance_value': 0.5695492112572015,
                                                                 'standout_numeric_balance_direction': 'inside_higher',
                                                                 'average_abs_smd_numeric': 0.2707176140495066,
                                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                           'composition',
                                                                 'standout_categorical_balance_value': 0.5202734559170201,
                                                                 'average_tvd_categorical': 0.261079679396511},
                                                      '4 ROOM': {'standout_numeric_balance_dimension': 'transaction '
                                                                                                       'year '
                                                                                                       'composition',
                                                                 'standout_numeric_balance_value': 0.7187309603100274,
                                                                 'standout_numeric_balance_direction': 'inside_lower',
                                                                 'average_abs_smd_numeric': 0.3714844949347496,
                                                                 'standout_categorical_balance_dimension': 'transaction-quarter '
                                                                                                           'composition',
                                                                 'standout_categorical_balance_value': 0.4689239332096475,
                                                                 'average_tvd_categorical': 0.2707560296846011}}}}}
RDD_A_FLAT_TYPE_HETEROGENEITY = _merge_nested_fields(
    RDD_A_FLAT_TYPE_HETEROGENEITY,
    RDD_A_FLAT_TYPE_BALANCE_HIGHLIGHTS,
)
# Balance-assessment rule used for flat-type RDD support labels:
# - well_supported: max_abs_smd_numeric <= 0.50 and max_tvd_categorical <= 0.30
# - mixed_support: max_abs_smd_numeric <= 1.00 and max_tvd_categorical <= 0.60
# - weak_support: otherwise
RDD_A_FLAT_TYPE_BALANCE_ASSESSMENT = {
    "0_to_1": {
        100: {
            "CATHOLIC HIGH SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
            },
            "CHIJ PRIMARY (TOA PAYOH)": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "CHIJ ST. NICHOLAS GIRLS' SCHOOL": {
                "3 ROOM": {"balance_assessment": "well_supported"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
            },
            "CHONGFU SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
            },
            "FAIRFIELD METHODIST SCHOOL (PRIMARY)": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "FRONTIER PRIMARY SCHOOL": {
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "well_supported"},
                "EXECUTIVE": {"balance_assessment": "mixed_support"},
            },
            "HOLY INNOCENTS' PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
                "EXECUTIVE": {"balance_assessment": "weak_support"},
            },
            "KONG HWA SCHOOL": {
                "2 ROOM": {"balance_assessment": "weak_support"},
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "MAHA BODHI SCHOOL": {
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
                "EXECUTIVE": {"balance_assessment": "mixed_support"},
            },
            "MARIS STELLA HIGH SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "NAN CHIAU PRIMARY SCHOOL": {
                "2 ROOM": {"balance_assessment": "mixed_support"},
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
                "EXECUTIVE": {"balance_assessment": "weak_support"},
            },
            "NAN HUA PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "NORTHLAND PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
                "EXECUTIVE": {"balance_assessment": "weak_support"},
            },
            "PEI CHUN PUBLIC SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "PRINCESS ELIZABETH PRIMARY SCHOOL": {
                "2 ROOM": {"balance_assessment": "weak_support"},
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
                "EXECUTIVE": {"balance_assessment": "mixed_support"},
            },
            "RED SWASTIKA SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "ROSYTH SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
            },
            "RULANG PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "SOUTH VIEW PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "well_supported"},
                "EXECUTIVE": {"balance_assessment": "weak_support"},
            },
            "ST. HILDA'S PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "well_supported"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
                "EXECUTIVE": {"balance_assessment": "weak_support"},
            },
            "ST. JOSEPH'S INSTITUTION JUNIOR": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
            },
        }
    },
    "1_to_2": {
        100: {
            "AI TONG SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "CATHOLIC HIGH SCHOOL": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
                "5 ROOM": {"balance_assessment": "mixed_support"},
            },
            "CHIJ PRIMARY (TOA PAYOH)": {
                "3 ROOM": {"balance_assessment": "mixed_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "CHONGFU SCHOOL": {
                "4 ROOM": {"balance_assessment": "weak_support"},
            },
            "KUO CHUAN PRESBYTERIAN PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "weak_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
            "NORTHLAND PRIMARY SCHOOL": {
                "3 ROOM": {"balance_assessment": "weak_support"},
                "4 ROOM": {"balance_assessment": "mixed_support"},
            },
            "PEI CHUN PUBLIC SCHOOL": {
                "4 ROOM": {"balance_assessment": "mixed_support"},
                "5 ROOM": {"balance_assessment": "weak_support"},
            },
        }
    },
}
RDD_A_FLAT_TYPE_HETEROGENEITY = _merge_nested_fields(
    RDD_A_FLAT_TYPE_HETEROGENEITY,
    RDD_A_FLAT_TYPE_BALANCE_ASSESSMENT,
)
# DID results
## Good schools only; standard DID pooled results
DID_GOOD_SCHOOLS_POOLED_RESULTS = {
    "0_to_1_within_1km": {
        "coefficient": -0.00239712230261824,
        "p_value": 0.8595135098079674,
        "sig_field": False,
        "robust": "unknown",
    },
    "1_to_2_within_1km": {
        "coefficient": -0.0148880603969374,
        "p_value": 0.142,
        "sig_field": False,
        "robust": "unknown",
    },
}
## Good schools only; standard DID school-level results
DID_GOOD_SCHOOLS_UNPOOLED_RESULTS = {
    "0_to_1_within_1km": {
        "ROSYTH SCHOOL": {
            "coefficient": 0.00095845902857139,
            "p_value": 9.551542e-01,
            "sig_field": False,
            "robust": "not_robust",
        },
        "ST. HILDA'S PRIMARY SCHOOL": {
            "coefficient": 0.0460958539293927,
            "p_value": 9.018369e-31,
            "sig_field": True,
            "robust": "robust",
        },
        "PEI CHUN PUBLIC SCHOOL": {
            "coefficient": 0.0418979480466513,
            "p_value": 3.052938e-11,
            "sig_field": True,
            "robust": "robust",
        },
        "RULANG PRIMARY SCHOOL": {
            "coefficient": 0.0411136942004018,
            "p_value": 1.521330e-02,
            "sig_field": True,
            "robust": "robust",
        },
        "FAIRFIELD METHODIST SCHOOL (PRIMARY)": {
            "coefficient": 0.0668794653436375,
            "p_value": 5.496852e-02,
            "sig_field": True,
            "robust": "robust",
        },
        "CHONGFU SCHOOL": {
            "coefficient": 0.0197923213031401,
            "p_value": 1.221061e-02,
            "sig_field": True,
            "robust": "robust",
        },
        "CHIJ PRIMARY (TOA PAYOH)": {
            "coefficient": 0.0774196829156375,
            "p_value": 6.088424e-14,
            "sig_field": True,
            "robust": "robust",
        },
        "MAHA BODHI SCHOOL": {
            "coefficient": -0.0237377208179569,
            "p_value": 6.099933e-01,
            "sig_field": False,
            "robust": "robust",
        },
    },
    "0_to_1_within_1_to_2km": {
        "NAN CHIAU PRIMARY SCHOOL": {
            "coefficient": 0.00833353216186872,
            "p_value": 2.776698e-01,
            "sig_field": False,
            "robust": "unknown",
        },
        "CATHOLIC HIGH SCHOOL": {
            "coefficient": 0.0106705283181672,
            "p_value": 6.697560e-01,
            "sig_field": False,
            "robust": "unknown",
        },
        "CHONGFU SCHOOL": {
            "coefficient": -0.00829738509185229,
            "p_value": 3.342875e-01,
            "sig_field": False,
            "robust": "unknown",
        },
        "HOLY INNOCENTS' PRIMARY SCHOOL": {
            "coefficient": 0.0182210133334852,
            "p_value": 9.624778e-03,
            "sig_field": True,
            "robust": "unknown",
        },
        "KONG HWA SCHOOL": {
            "coefficient": 0.0513688691343499,
            "p_value": 1.207963e-02,
            "sig_field": True,
            "robust": "unknown",
        },
        "ST. JOSEPH'S INSTITUTION JUNIOR": {
            "coefficient": -0.0249397353529184,
            "p_value": 4.105058e-01,
            "sig_field": False,
            "robust": "unknown",
        },
        "FRONTIER PRIMARY SCHOOL": {
            "coefficient": -0.0241427856070602,
            "p_value": 6.651156e-01,
            "sig_field": False,
            "robust": "unknown",
        },
        "AI TONG SCHOOL": {
            "coefficient": -0.0223142699450419,
            "p_value": 2.096258e-02,
            "sig_field": True,
            "robust": "unknown",
        },
        "MAHA BODHI SCHOOL": {
            "coefficient": -0.0192856065685831,
            "p_value": 5.477515e-01,
            "sig_field": False,
            "robust": "unknown",
        },
    },
}
