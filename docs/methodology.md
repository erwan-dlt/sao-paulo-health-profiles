# Methodology and interpretation

## Study design

The unit of analysis is a municipality in the state of São Paulo. The reference dataset contains all 645 municipalities. Social census variables refer to 2022, population context to 2024, vital events to 2023–2024, and resource snapshots to an uncertain 2023/2024 reference. This is a cross-sectional ecological description, not individual-level inference, causal identification or prediction.

The primary question is how social profiles and demographic context relate to the distribution of recorded SUS/non-SUS resources. Mortality is a secondary outcome. Beds are retained for auditing, but missing records prevent an unconditional territorial comparison.

## Feature design

The clustering uses three variables: natural log of median household income per capita, literacy among residents aged 15+, and the percentage of occupied permanent private households with adverse sanitation categories. The latter aggregates rudimentary pits, ditches, discharge into water bodies, other forms, and absence of a toilet. Network-connected systems and unconnected septic/filter systems are excluded from this proxy. It is not an assessment of treatment compliance.

Percentages remain on their original scale before z-score standardization; one standard deviation in each feature has equal distance weight. Features may be correlated, so equality of variable weights does not imply equality of independent substantive dimensions. Sensitivity analyses change the income definition, sanitation definition, transformations and weights.

## Clustering and PCA

K-means minimizes squared Euclidean within-cluster distance after standardization. Ward uses the same transformed and standardized observations. Both prefer compact groups and can impose partitions on gradients. PCA is fitted on all three standardized features and used only for visualization; clustering uses all three dimensions. PCA components are eigenvector coefficients, not variable/component correlations.

For each k=2–6, evaluate silhouette, Davies–Bouldin, smallest cluster, 10 seed runs, Ward agreement, and 80 independent 80% subsamples. Each subsample refits both StandardScaler and K-means. Refit models assign all observations to their learned centers. Full-sample ARI is a perturbation diagnostic; excluded-subset ARI reports the analogous calculation on municipalities absent from fitting. Neither is supervised accuracy.

The exploratory selection rule shortlists k within 0.02 of the maximum silhouette with at least 30 municipalities per cluster, then maximizes the 10th percentile of refit ARI, breaking ties by smaller k. The tolerance and size requirement are heuristics chosen during development, not preregistered or universal criteria. Every candidate metric and assignment is retained so a reader can assess alternatives. No health outcome is used for selection.

Individual stability uses Hungarian label matching on the sampled municipalities, then measures agreement only on excluded municipalities. The number of exclusions is exported. This is sensitivity to sampling, not posterior probability or evidence of a true category. Leave-one-health-region-out refits the full pipeline and reports full/retained ARI; spatial exclusion is a perturbation check, not an assessment of transportability to a new state.

A simple equal-frequency grouping of median income provides a baseline, keeping ties together. Baseline and profile comparisons of log1p resource variation are in-sample descriptive summaries. Clustering is not guaranteed to improve every outcome, and no external outcome score is optimized.

## Health comparisons

Rates divide reported employment links by population, not by workers' hours or clinical capacity. A worker may hold multiple links. SUS/non-SUS classification is preserved and is not equated with ownership or insurance membership. Main rates use population 2024; 2023 rates test the ambiguous resource reference period. This sensitivity cannot identify the actual reference year.

Report both the median municipal rate and the pooled sum-of-jobs / sum-of-population rate. For incomplete professional records, numerator and denominator use the same observed municipalities; export counts and population coverage. Never average local rates and label the result a pooled rate.

Rank associations adjust for the ranks of population, density and older-age share by residualizing both variables with an intercept and linear least squares. This is partial rank correlation, not nonlinear adjustment or causal estimation. Four hundred whole-health-region bootstrap resamples rerank and refit the calculations. This preserves within-region dependence but assumes sufficiently independent regions. The reported intervals are pointwise exploratory intervals; no claim of familywise confirmation is made.

## Spatial statistics

The project reads the frozen IBGE Polygon SHP/DBF directly, rejecting other geometry formats. Boundary rings and holes are retained for rendering. Queen adjacency means at least one shared vertex after rounding longitude/latitude to seven decimal places. This implements the shared-vertex graph on this mesh, not a general geometry-intersection engine. The graph audit reports edges, components and islands.

The sensitivity graph symmetrizes six nearest polygon centroids, ranked by unit-sphere chord distance. Geographic-coordinate polygon centroids are an approximation suitable for a neighboring-graph sensitivity; they are not travel times or exact geodesic area centroids.

Graphs have no self-links and are row-standardized. Missing-variable municipalities are removed before weights are recalculated; isolated municipalities are excluded from the relevant test. For centered standardized values z and W, global Moran I = (n / sum(W)) × (z'Wz / z'z). Its randomization expectation is -1/(n-1). Two-sided permutation p-values compare absolute deviations from this expectation, including the observed configuration through the +1 correction. Global tests use 9,999 random permutations and BH correction over eight tests.

Local income statistics are I_i = z_i × (Wz)_i. The project uses **total randomization**, permuting all incomes, including each focal value. These are not the conditional randomization tests commonly used in LISA implementations. Local p-values compare deviations from -1/(n-1). BY adjustment is used for the main map because it accommodates arbitrary dependence; BH is a sensitivity. The family contains the 644 non-isolated municipalities. At 9,999 permutations, the minimum possible p-value is 0.0001; conservative multiple-testing correction can limit detection. Nonsignificance is not proof of spatial independence. Raw p-values and both corrections are provided.

## Infant mortality

Sum deaths under one year and resident live births across 2023–2024. The ratio is a period measure, not a linked birth-cohort risk. Municipal rates are unstable at small denominators. Report pooled rates by profile, mean-income quartile and health region, together with numerator, denominator and exact Poisson intervals. Repeat municipal correlations after excluding municipalities below prespecified birth-count thresholds.

Poisson intervals assume independent Poisson counts conditional on exposure. They do not account for overdispersion, spatial dependence or data-quality errors. No mortality model is used to choose clusters, and a zero count is not interpreted as zero underlying risk.

## Scope decisions

Included: validated UBS totals, classical non-supervised modeling, full-pipeline robustness, simple baseline, context adjustment, region aggregation, targeted spatial analysis and secondary mortality uncertainty.

Not included: deep learning, arbitrary predictive targets, travel-time accessibility, APS coverage, insurance coverage, GMM, or clinical need estimates. These would add dependencies or unresolved data definitions without being required by the research question. No claim is made that this study diagnoses underprovision.
