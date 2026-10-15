# Analytical data dictionary

The main file is `data/processed/municipalities.csv`, with one row per municipality. Missing numeric cells are empty CSV fields. Raw source names remain unchanged; all derived names and definitions are English.

| Column or family | Definition | Unit / reference | Source | Role |
|---|---|---|---|---|
| ibge_code | Seven-digit municipality identifier | Identifier | IBGE/Seade | Join key |
| municipality | Official municipality name | Text | Seade codes | Label |
| health_region | Official health region name | Text | Seade codes | Aggregation and block resampling |
| regional_health_department | Regional health department name | Text | Seade codes | Context |
| income_mean | Mean monthly household income per capita | BRL/month, 2022 | SIDRA 10295, variable 13431 | External association; alternative feature |
| income_median | Median monthly household income per capita | BRL/month, 2022 | SIDRA 10295, variable 13534 | Main feature; natural log |
| literacy_pct | Literate share among residents aged 15+ | Percent, 2022 | SIDRA 9543, variable 2513 | Main feature |
| adverse_sanitation_pct | Household share in selected adverse sanitation categories | Percent, 2022 | SIDRA 6805, variable 381 | Main feature |
| sewer_network_pct | Household share connected to general/rainwater network or septic system linked to network | Percent, 2022 | SIDRA 6805, category 46290 | Alternative feature; not treatment quality |
| unconnected_septic_pct | Household share with septic/filter system not connected to network | Percent, 2022 | SIDRA 6805, category 72112 | Definition check |
| population_2023 / population_2024 | Resident population; sum of men and women at total age | Residents | Seade population | Rate denominator |
| age65plus_pct | Residents aged 65+ divided by total population | Percent, 2024 | Seade age-sex population | Adjustment variable |
| density_per_km2 | Resident population density | Residents/km², 2024 | Seade demographic indicators | Adjustment variable |
| physician_*_jobs / nurse_*_jobs | Recorded employment links, by SUS/non-SUS/total | Employment links, undated 2023/2024 snapshot | Seade/CNES | Resource count; missing records preserved |
| physician_*_per1000 / nurse_*_per1000 | Employment links divided by population 2024 × 1,000 | Links per 1,000 residents | Derived | External resource comparison |
| *_per1000_pop2023 | Same employment-link numerator using population 2023 | Links per 1,000 residents | Derived | Reference-year sensitivity |
| reported_beds / reported_beds_per1000 | Reported total hospital beds and rate; 289 absent municipalities remain missing | Beds / beds per 1,000 residents, period 2024 | Seade/CNES | Audit only |
| basic_health_units | Reported total UBS establishments | Facilities, undated 2023/2024 snapshot | Seade/CNES | External resource count |
| basic_health_units_per10000 | UBS total divided by population 2024 × 10,000 | Facilities per 10,000 residents | Derived | External resource comparison |
| infant_deaths / live_births | Resident infant deaths / live births pooled over 2023–2024 | Events | Seade vital statistics | Secondary outcome numerator / denominator |
| infant_mortality_per1000 | Infant deaths / live births × 1,000 | Deaths per 1,000 live births | Derived | Secondary outcome |
| imr_ci_low / imr_ci_high | Exact Poisson count limits divided by births × 1,000 | Rate units, 95% interval | Derived | Conditional count uncertainty |
| profile | Selected K-means label ordered by median income | Integer 1–k | Model | Exploratory label, not a health ranking |
| profile_stability | Matched agreement among fits excluding the municipality | Fraction 0–1 | Resampling | Algorithm sensitivity, not posterior probability |
| excluded_repeats | Number of resamples excluding the municipality | Count | Resampling | Stability denominator |
| distance_to_profile | Euclidean distance to assigned standardized center | Standardized feature-space distance | Model | Representative/atypical case selection |
| income_group | Equal-frequency median-income group, with ties kept together | Integer | Derived | Simple baseline |
| mean_income_quartile | Quartile of municipal mean income, unweighted | Q1–Q4 | Derived | Mortality aggregation |
| pc1 / pc2 | Scores on the first two principal components | Standardized feature space | PCA | Visualization only |
| local_i | Local income Moran product z_i × spatial lag | Dimensionless | Spatial permutation analysis | Targeted local exploratory association |
| by_q | BY-adjusted total-randomization local income p-value | 0–1 | Spatial permutation analysis | Multiple-testing correction |
| map_class | Local quadrant if BY q ≤ 0.05; otherwise nonsignificant or no neighbors | Category | Spatial analysis | Descriptive map label |

## Sanitation numerator

The adverse numerator sums categories 72113 (rudimentary pit/hole), 92858 (ditch), 72114 (river/lake/stream/sea), 72115 (other form), and 92861 (no bathroom or toilet). The denominator is category 46292 (all occupied permanent private households). Category 46290 aggregates 72110 and 72111; the pipeline never sums the aggregate and its children. Category 72112 (unconnected septic/filter system) is outside the adverse numerator.

## Aggregated tables

Profile, income-group, quartile and health-region tables include medians, pooled rates, observed municipal counts and observed-population coverage. A pooled professional rate uses only municipalities with an observed professional total, both in its numerator and denominator. A pooled mortality rate sums all deaths and births in the group. Resource rate medians and pooled rates answer different questions.
