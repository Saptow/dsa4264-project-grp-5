---
title: Appendix

---

# Appendix
## Good Schools
We validated the good school rankings from 2018 to 2026, and found that they remained static in terms of their admission rate, particularly for those below 95%.
## DID: Pooled Sample Construction (Good & Normal Schools)
Observations are stacked across focal schools after applying the same pre/post window, distance-band restrictions, and composition filters used in the unpooled analysis.

Control units are untreated observations that remain outside the relevant priority band and are assigned to the nearest treated flat within the same comparison stratum. Let \(j(i)\) denote the nearest treated flat to control observation \(i\). A control observation is retained if:

$$
j(i) = \arg\min_{j \in \mathcal{T}} \|x_i - x_j\|
\quad \text{and} \quad
\|x_i - x_{j(i)}\| \leq \bar r,
$$

where $\mathcal{T}$ is the set of treated observations, $x_i$ denotes location, and $\bar r$ is the distance threshold used to define the local comparison set.

As in the unpooled specification, we exclude observations with overlapping access to multiple schools and hold constant exposure to schools of the opposite type.
## RDD (School by Quadrant)
`52` school-quadrant models were estimable, with `13` significant at the 5% level. Quadrant results show that the same school can have very different estimated discontinuities on different sides of its boundary, and in some cases the sign flips across quadrants.

Table_n keeps schools that are significant either in the overall school model or in at least one quadrant. Empty cells refer to no transaction data at those areas. 

| School | Overall | NE | NW | SE | SW |
|---|---:|---:|---:|---:|---:|
| CHONGFU SCHOOL | 0.0107 |  | -0.0450*** | -0.0136* | 0.0278** |
| FAIRFIELD METHODIST SCHOOL (PRIMARY) | -0.2507* | -0.2581* | insuff. |  |  |
| FRONTIER PRIMARY SCHOOL | -0.0216** | -0.0256* | 0.0016 |  |  |
| HOLY INNOCENTS' PRIMARY SCHOOL | 0.0109 | 0.0090 | 0.0465*** |  | -0.0058 |
| KONG HWA SCHOOL | 0.0361*** | 0.0110 | -0.0053 |  | 0.0296 |
| NORTHLAND PRIMARY SCHOOL | -0.0042 | 0.0273*** | -0.0548*** |  | -0.0234** |
| PEI CHUN PUBLIC SCHOOL | 0.0084 |  | -0.6059 | -0.0531** | 0.0938** |
| PRINCESS ELIZABETH PRIMARY SCHOOL | -0.0133* | insuff. | -0.0118 | 0.0044 | 0.0146 |
| RED SWASTIKA SCHOOL | 0.0210*** |  | -0.0206 | 0.0372*** | 0.0115 |
| RULANG PRIMARY SCHOOL | 0.0061 | 0.0141 | -0.0330* | -0.0212* | insuff. |
| SOUTH VIEW PRIMARY SCHOOL | 0.0094** | insuff. | -0.0152 | 0.0167 | 0.0158*** |
| ST. HILDA'S PRIMARY SCHOOL | 0.0072 | 0.0158 | 0.0028 | 0.0961*** |  |
| ST. JOSEPH'S INSTITUTION JUNIOR | -0.0135 | 0.2168** |  | 2.3173*** |  |

Several schools show direction-specific effects that were obscured in the overall school average. Chongfu, Northland, and Pei Chun are the clearest examples: their estimated coefficients differ materially across quadrants, and in some cases reverse signs.

Some of the most dramatic quadrant coefficients coincide with  poorer balance. For example, St. Joseph's Institution Junior `SE` has a very large coefficient (`tau = 2.3173`) together with `max |SMD| = 1.18` and `max TVD = 0.49`; and Pei Chun `SE` has `tau = -0.0531` but with `max |SMD| = 1.42` and `max TVD = 0.87`. 

## RDD: Normal School Results 
As a benchmark, the same pooled specification was estimated for normal primary-school boundaries, with a more clearly negative pattern. At 100 m bandwidth, the pooled normal-school estimate of price effect is approximately `-3.02%`. At the tighter 25 m bandwidth, the estimate remains negative, `tau = -0.0182`, but is no longer statistically significant (`p = 0.131`)

It is possible that negative pooled estimate for normal schools suffer similarly from summarising heterogeneity across many schools.

## DID 
### Pooled DID (1 to 2 good schools in 1km radius)
We estimated this specification, but do not explore further; only `6` schools remain after imposing minimum pre- and post-treatment counts (10 each) for treated and control groups, and pre-trends fail.
The marginal premium for flats already within 1km of one good school that newly gained another good school following the rule change was also investigated. However, the pooled estimate of -1.5% was statistically insignificant. 

## Unpooled DID (1 to 2 good schools 1km to 2km)

| School | DID Coefficient | p-value (DID) | Parallel Trend | p-value (Parallel Trend) | DID Significant | Treated (Pre) | Treated (Post) | Control (Pre) | Control (Post) |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|
| ST. JOSEPH'S INSTITUTION JUNIOR | 0.024695 | 0.1688233 | Pass | 0.3334344 | No | 19 | 18 | 35 | 22 |

Only 1 school passed pre-trend, no need to explore.

## Pooled DID (0 to 1 normal school in 1km radius)
For fair comparison, the same pooled specification was also estimated for normal primary-school boundaries. The model estimate was -0.0074, p-value=0.035, but pre trends fail. (F-stat: 4.248, p-value: 0.001) 