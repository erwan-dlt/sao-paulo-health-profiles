"""Build a self-contained report, a readable notebook, and a results-led README."""
import ast
import base64
import html
import json
from pathlib import Path
import pandas as pd
from sp_health.reporting.figures import create


def table(frame, labels=None):
    return frame.rename(columns=labels or {}).to_html(index=False, border=0, float_format=lambda x: f'{x:,.3f}', classes='data-table')


def build_notebook(root, summary):
    cells = []
    namespace = {}
    def markdown(text):
        cells.append({'cell_type': 'markdown', 'metadata': {}, 'source': text.splitlines(True)})
    def code(source):
        parsed = ast.parse(source)
        output = []
        if parsed.body and isinstance(parsed.body[-1], ast.Expr):
            tail = parsed.body.pop()
            exec(compile(parsed, '<notebook>', 'exec'), namespace)
            result = eval(compile(ast.Expression(tail.value), '<notebook>', 'eval'), namespace)
            if result is not None:
                data = {'text/plain': repr(result)}
                if isinstance(result, pd.DataFrame):
                    data['text/html'] = result.to_html()
                output.append({'output_type': 'execute_result', 'execution_count': sum(c['cell_type']=='code' for c in cells)+1,
                               'data': data, 'metadata': {}})
        else:
            exec(compile(parsed, '<notebook>', 'exec'), namespace)
        cells.append({'cell_type':'code','metadata':{},'source':source.splitlines(True),
                      'execution_count':sum(c['cell_type']=='code' for c in cells)+1,'outputs':output})
    markdown('# São Paulo: living conditions and health resources\n\n'+summary+'\n\nThis notebook is the reading companion. Rebuild all results with `python run.py run` from the repository root. Tables below contain actual executed outputs. The analysis is descriptive and ecological.')
    # Use a relative root at execution and in the saved notebook; no workstation paths.
    import os
    old = Path.cwd()
    os.chdir(root)
    try:
        code("from pathlib import Path\nimport pandas as pd\nROOT = Path.cwd() if (Path.cwd() / 'data').exists() else Path.cwd().parent\nd = pd.read_csv(ROOT / 'data/processed/municipalities.csv', dtype={'ibge_code': str})\nd[['municipality', 'income_median', 'literacy_pct', 'adverse_sanitation_pct', 'profile']].head()")
        markdown('## 1. Data and definitions\n645 municipalities; 2022 census social indicators; 2023–2024 vital statistics. Resource snapshots have uncertain 2023/2024 dating. Recorded jobs are employment links, not unique clinicians. Missing records remain missing. Adverse sanitation includes rudimentary pits, ditches, water-body discharge, other forms, and no toilet; unconnected septic systems are excluded.')
        code("pd.read_csv(ROOT / 'reports/tables/profiles.csv')[['profile', 'municipalities', 'income_median_median', 'literacy_pct_median', 'adverse_sanitation_pct_median']]")
        markdown('## 2. Evaluate profiles\nThe same standardized features are used for K-means and Ward. Scaling is refitted in every 80% subsample. Model selection balances separation, minimum size and lower-tail stability; these are exploratory choices, not a preregistered test.')
        code("pd.read_csv(ROOT / 'reports/tables/cluster_validation.csv').round(3)")
        markdown('## 3. Compare external health resources\nThe health indicators were not used to choose profiles. Population, density and older-age share enter the partial rank correlations. Confidence intervals resample entire health regions, assuming regions are sufficiently independent.')
        code("pd.read_csv(ROOT / 'reports/tables/associations.csv').query(\"income == 'income_mean'\").round(3)")
        markdown('## 4. Does clustering add more than income groups?\nThe comparison below is in-sample explained variation of log1p health indicators. It is not a prediction score or an independent validation of the existence of clusters.')
        code("pd.read_csv(ROOT / 'reports/tables/baseline_comparison.csv').round(3)")
        markdown('## 5. Spatial context\nQueen adjacency and a symmetric six-nearest-centroid graph provide sensitivity checks. The local income test uses total randomization and BY correction; it is not a conditional LISA test. A nonsignificant local result must not be presented as a hotspot.')
        code("pd.read_csv(ROOT / 'reports/tables/global_moran.csv').round(4)")
        markdown('## 6. Infant mortality is secondary\nPool deaths and live births, not municipal rates. Poisson intervals describe count uncertainty under a simple model; they do not capture all social, spatial or reporting uncertainty.')
        code("pd.read_csv(ROOT / 'reports/tables/income_quartiles.csv')[['mean_income_quartile', 'infant_deaths', 'live_births', 'pooled_infant_mortality_per1000', 'imr_ci_low', 'imr_ci_high']].round(3)")
        markdown('## 7. Robustness and interpretation\nChanging weights changes the question: equal municipality weights describe territories; population weights emphasize residents of large cities. Profiles are exploratory summaries of gradients. They cannot establish care access, care quality, individual risk or causation.')
        code("pd.read_csv(ROOT / 'reports/tables/cluster_sensitivity.csv').round(3)")
    finally:
        os.chdir(old)
    for path in sorted((root/'reports/figures').glob('*.png')):
        encoded = base64.b64encode(path.read_bytes()).decode()
        cells.append({'cell_type':'markdown','metadata':{},'source':[f'![{path.stem.replace("_", " ")}](attachment:{path.name})'],
                      'attachments':{path.name:{'image/png':encoded}}})
    for i, cell in enumerate(cells):cell['id'] = f'cell-{i:03d}'
    notebook = {'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':5}
    (root/'notebooks/analysis.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+'\n',encoding='utf-8')


def build(d, polygons, model, root):
    root = root.resolve()
    create(d, polygons, model, root)
    tables = root/'reports/tables'
    read = lambda name: pd.read_csv(tables/f'{name}.csv')
    profiles, validation, associations = read('profiles'), read('cluster_validation'), read('associations')
    selected = validation[validation.selected].iloc[0]
    a = associations[associations.income.eq('income_mean')].set_index('outcome')
    quarters = read('income_quartiles')
    spatial = json.loads((tables/'spatial_audit.json').read_text())
    audit = json.loads((tables/'audit.json').read_text())
    baseline = read('baseline_comparison')
    summary = f"The analysis identifies {model['selected_k']} exploratory socioeconomic profiles across 645 municipalities. Non-SUS physician employment links are more strongly associated with income than SUS links. Demographic adjustment weakens these associations, while basic health unit density shows almost no remaining income association."
    def image(name, caption):
        encoded = base64.b64encode((root/'reports/figures'/name).read_bytes()).decode()
        return f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    profile_columns = ['profile','municipalities','income_median_median','literacy_pct_median','adverse_sanitation_pct_median', 'physician_sus_per1000_median','physician_non_sus_per1000_median']
    profile_labels = {'profile':'Profile','municipalities':'Municipalities','income_median_median':'Median income (BRL/month)',
                      'literacy_pct_median':'Literacy (%)','adverse_sanitation_pct_median':'Adverse sanitation (%)',
                      'physician_sus_per1000_median':'SUS jobs / 1,000','physician_non_sus_per1000_median':'Non-SUS jobs / 1,000'}
    sections = []
    def section(title, body):sections.append(f'<section><h2>{title}</h2>{body}</section>')
    section('What the data show',f'''<p>{summary}</p>
    <div class="metrics"><div><strong>645</strong><span>municipalities</span></div><div><strong>{model['selected_k']}</strong><span>exploratory profiles</span></div><div><strong>{selected.silhouette:.2f}</strong><span>silhouette</span></div><div><strong>{selected.refit_ari_median:.2f}</strong><span>median refit ARI</span></div></div>
    <ul><li>Mean income has a Spearman correlation of <b>{a.loc['physician_non_sus_per1000','spearman']:.2f}</b> with non-SUS physician jobs per resident, versus <b>{a.loc['physician_sus_per1000','spearman']:.2f}</b> with SUS jobs.</li>
    <li>After accounting for population, density and the share aged 65+, those correlations become <b>{a.loc['physician_non_sus_per1000','partial_rank']:.2f}</b> and <b>{a.loc['physician_sus_per1000','partial_rank']:.2f}</b>.</li>
    <li>The income association with basic health units per resident changes from <b>{a.loc['basic_health_units_per10000','spearman']:.2f}</b> to <b>{a.loc['basic_health_units_per10000','partial_rank']:.2f}</b> after the same adjustment.</li>
    <li>Pooled infant mortality ranges from <b>{quarters.iloc[0].pooled_infant_mortality_per1000:.2f}</b> in the lowest mean-income quartile to <b>{quarters.iloc[-1].pooled_infant_mortality_per1000:.2f}</b> in the highest, per 1,000 live births. The unweighted municipal income correlation is only <b>{a.loc['infant_mortality_per1000','spearman']:.2f}</b>.</li></ul>
    <p class="callout">These are descriptive municipal associations. Recorded resources do not establish effective access, service capacity or individual health risk.</p>''')
    section('Research question and data', '''<p>Which socioeconomic profiles distinguish São Paulo municipalities, and how do SUS and non-SUS resources vary across them after considering demographic and territorial context?</p>
    <p>SUS is Brazil’s public Unified Health System. “Non-SUS” is the source classification and should not be interpreted as a direct measure of insurance coverage or ownership.</p>
    <table><tr><th>Role</th><th>Indicators</th><th>Reference</th></tr>
    <tr><td>Build profiles</td><td>Median household income per capita; literacy at age 15+; adverse sanitation share</td><td>IBGE census 2022</td></tr>
    <tr><td>Compare resources</td><td>Physician and nurse employment links, SUS/non-SUS; UBS counts</td><td>Seade snapshot; dictionaries say December 2023, catalog labels 2024</td></tr>
    <tr><td>Context</td><td>Population, density, share aged 65+, health region</td><td>Seade, population 2024; 2023 sensitivity</td></tr>
    <tr><td>Secondary outcome</td><td>Infant deaths and live births, pooled</td><td>Seade 2023–2024</td></tr>
    <tr><td>Geography</td><td>Municipality boundaries</td><td>IBGE 2022</td></tr></table>
    <p>All joins use seven-digit IBGE identifiers. Totals, unique keys, positive denominators and percentage ranges are checked. Decimal commas and thousands separators are parsed explicitly. Each source file has a SHA-256 digest.</p>
    <p>Adverse sanitation is the share of occupied permanent private households using rudimentary pits, ditches, rivers/lakes/sea, other forms, or having no toilet. Septic systems unconnected to a network are excluded from this proxy. The grouping is an analytical definition; it does not measure treatment quality or certify individual installations.</p>
    <p>10 municipalities lack a physician record and 2 lack a nurse record. Missingness does not affect socioeconomic clustering. UBS totals are reported for all 645 municipalities. Hospital beds are reported for only 356 municipalities in 2024; missing bed rows remain unknown and beds are excluded from substantive comparisons. Ownership-component blanks in the UBS source are not interpreted as zero; only reported totals are used.</p>'''+image('01_distributions.png','Municipalities receive equal weight in the primary clustering.'))
    section('Profile construction and validation',f'''<p>The pipeline uses log median income, untransformed literacy and adverse sanitation, followed by z-score standardization. Each municipality has equal weight. K-means is fitted in this three-dimensional space; PCA is used for interpretation, with no dimensions discarded before clustering.</p>
    <p>For each k from 2 to 6, the analysis fits K-means with 30 initializations, checks 10 seeds, compares Ward on the same standardized data, and refits scaling and K-means on 80 random subsamples containing 80% of municipalities. ARI compares the resulting assignments across all municipalities and separately among the excluded municipalities.</p>
    <p><b>Selection rule:</b> {html.escape(model['selection_rule'])} This rule is a transparent exploratory trade-off, not a hypothesis test or a universal threshold. Two profiles separate slightly better, while three offer stronger lower-tail stability; four provide additional detail but less consistent stability.</p>
    {table(validation.round(3))}
    <p>The selected model has median refit ARI {selected.refit_ari_median:.3f}, 10th-percentile ARI {selected.refit_ari_p10:.3f}, and Ward agreement {selected.ward_ari:.3f}. The silhouette of {selected.silhouette:.3f} indicates overlap. The first principal component captures {model['pca_variance_ratio'][0]:.1%} of variance, consistent with a substantial continuous socioeconomic gradient.</p>'''+image('02_cluster_validation.png','All candidate models are retained; selected k balances separation and stability.')+image('03_pca_profiles.png','PCA is a visualization of the same three features, not an independent validation.')+table(profiles[profile_columns],profile_labels)+'''<p>Profile 1 combines lower income with much more frequent adverse sanitation. Profile 2 has intermediate income and literacy but substantially less adverse sanitation than Profile 1. Profile 3 combines higher income and literacy with lower adverse sanitation. These contrasts show why an income-only grouping cannot capture every dimension.</p><p>Profile numbers are ordered by median income only. They are not rankings of overall health or municipal performance. The table reports medians of municipal indicators.</p>''')
    section('Health resources outside the clustering',f'''<p>Health resources are external descriptive comparisons, not clustering inputs. Pooled rates sum jobs and population over the same observed municipalities. They answer a different question from the median municipal rate, and neither corrects for patients traveling across borders.</p>'''+image('04_external_resources.png','Recorded jobs are employment links, not distinct people or full-time equivalents.')+image('05_adjusted_associations.png','Intervals use 400 resamples of whole health regions, reranking and refitting each time.')+'''<p>Adjusted values are correlations between rank residuals after linear adjustment for population, density and older-age share. They are not causal effects. Region-block intervals allow dependence inside each region but assume blocks are sufficiently independent; cross-border correlation remains possible. These are pointwise exploratory intervals, without correction across the full family of associations.</p>
    <p>The UBS result is especially useful: differences per resident largely follow demographic context. A count of facilities does not capture their staffing, capacity, utilization or quality.</p>
    <h3>Comparison with a simple income grouping</h3>
    <p>Equal-frequency groups of median income provide a reference, with tied values kept together. The table measures in-sample variation explained in log1p health indicators. It must not be interpreted as prediction on unseen data. Clustering may add descriptive information for some resources, without universally outperforming income groups.</p>'''+table(baseline))
    section('Geography and scale',image('06_municipal_maps.png','IBGE 2022 boundaries; geographic coordinates shown at a local aspect ratio. Missing resource records are gray.')+f'''<p>Queen neighbors share at least one boundary vertex at seven decimal places. The graph has {spatial['queen_edges']} undirected edges and {len(spatial['queen_islands'])} isolated municipality (Ilhabela), excluded from Queen statistics but retained in maps and nearest-neighbor tests. The alternative graph symmetrizes each municipality’s six nearest polygon centroids on a unit sphere.</p>
    <p>Global Moran statistics use 9,999 permutations, two-sided deviations from the permutation-null expectation, and BH adjustment over the eight global comparisons. Local income statistics use total randomization of all incomes, not conditional LISA permutations. The local test family has one municipality-level test per non-isolated municipality. BY correction is shown because it allows arbitrary dependence; BH is retained as a less conservative sensitivity.</p>'''+table(read('global_moran'))+f'''<p>Income, adverse sanitation and non-SUS physician resources exhibit positive spatial association. The SUS physician statistic is much weaker. Local income results include {spatial['local_significant_bh']} municipalities under BH and {spatial['local_significant_by']} under BY at 5%. The main map therefore does not claim confirmed local hotspots. Conservative adjustment and limited permutation resolution reduce power.</p>'''+image('08_spatial_association.png','A map with no BY-significant local results is an analytical finding, not a rendering error.')+'''<p>Health-region tables pool resources and mortality, with explicit population coverage for missing professional records. This reduces fragmentation but does not measure referral flows, travel time or actual access. Conclusions can change with aggregation: an ecological association at one geographic scale need not hold at another.</p>''')
    section('Infant mortality: a secondary analysis',image('07_mortality.png','Intervals are exact Poisson count intervals scaled by live births, conditional on the exposure.')+f'''<p>There are {audit['municipalities_below_100_births']} municipalities with fewer than 100 live births in the pooled period and {audit['municipalities_without_infant_deaths']} with zero recorded infant deaths. Zero events do not demonstrate zero underlying risk. The quartile gradient and the near-zero municipal mean-income correlation coexist because pooling changes weighting and reduces count noise.</p>
    <p>The numerator contains infant deaths in 2023–2024 and the denominator live births in those years, not a longitudinal birth cohort. Poisson intervals ignore overdispersion, spatial dependence and reporting uncertainty. Mortality does not select the profiles and is not used to claim a protective or harmful causal effect of resources.</p>'''+table(read('mortality_sensitivity')))
    section('Sensitivity, representative cases and limitations',image('09_sensitivity.png','Changing the population weights changes the estimand as well as the profiles.')+'''<p>The sensitivity table changes income definition, sanitation definition, transforms, extreme values, capital inclusion and population weights. Every alternative refits its scaler. Leave-one-health-region-out results are also exported. Individual stability aligns labels on the fitting subset with the Hungarian algorithm and counts agreement only when a municipality is excluded. It measures algorithmic sensitivity, not probability of a true group.</p>
    <p>Representative cases are the two municipalities nearest each standardized profile center. Atypical cases are the five farthest from their assigned centers. This rule is explicit and describes feature-space geometry, not service need or policy priority.</p>'''+table(read('case_studies')[['municipality','profile','case_type','profile_stability']])+'''<ul><li>Resource reference dates remain ambiguous. The denominator sensitivity compares 2023 and 2024 population, but cannot prove the underlying resource year.</li><li>Public snapshots can be revised. Frozen hashes support this analysis; fresh downloads require a new audit.</li><li>Municipal averages hide within-municipality inequality and do not establish individual-level relationships.</li><li>The limited feature set and modest sample support interpretable classical methods, not a claim of broad ML engineering or causal discovery.</li><li>High stability does not establish natural clusters; variable and weighting choices materially affect the typology.</li></ul>''')
    sources = json.loads((root/'data/sources.json').read_text())
    source_html = '<ul>'+''.join(f'<li><a href="{html.escape(r["url"])}">{html.escape(r["file"])}</a> — {html.escape(r["origin"])}; snapshot recorded {r["retrieved_on"]}</li>' for r in sources)+'</ul>'
    section('Reproduce and inspect', '''<p>Open this standalone report without a server. The notebook includes actual executed table outputs and embedded figures. The repository contains source snapshots, processed data, model centers, every candidate assignment, validation tables, tests and all nine figures.</p>
    <pre>python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py verify
python run.py run
python -m unittest discover -s tests -v</pre>
    <p><code>python run.py fetch</code> restores missing source files only when live bytes match the frozen hash. <code>python run.py fetch --refresh</code> downloads current sources into a separate folder for review. Existing reference data are preserved. Equivalent Make targets are available, with no Unix-only shell commands.</p>
    <h3>Data sources</h3>'''+source_html+'''<h3>Method references</h3><ul>
    <li><a href="https://scikit-learn.org/stable/modules/clustering.html">scikit-learn: clustering and evaluation</a></li>
    <li><a href="https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html">scikit-learn: PCA</a></li>
    <li><a href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html">SciPy: BH and BY false discovery control</a></li>
    <li><a href="https://pysal.org/esda/generated/esda.Moran.html">PySAL: global Moran statistic</a> (the project implements explicit permutation tests with SciPy sparse matrices)</li>
    <li><a href="https://educa.ibge.gov.br/jovens/conheca-o-brasil/populacao/22064-caracteristicas-dos-domicilios-censo-2022.html">IBGE: sanitation categories, including unconnected septic systems</a></li></ul>''')
    css = '''body{margin:0;background:#f1f4f5;color:#263b48;font:16px/1.65 system-ui,sans-serif}main{max-width:1120px;margin:0 auto;background:white;padding:48px 52px}header{border-bottom:4px solid #276f86;padding-bottom:28px}h1{font-size:40px;line-height:1.15;max-width:850px;color:#193847}h2{font-size:26px;color:#276f86;margin-top:42px}h3{font-size:20px}p{max-width:980px}small,.subtitle{color:#647984}.eyebrow{letter-spacing:.13em;text-transform:uppercase;font-size:13px}.metrics{display:flex;gap:18px;margin:28px 0}.metrics div{background:#edf4f5;padding:20px;flex:1}.metrics strong{display:block;font-size:31px;color:#276f86}.metrics span{font-size:13px}.callout{background:#fff4df;border-left:4px solid #e7a54a;padding:15px 20px}table{border-collapse:collapse;display:block;overflow:auto;max-width:100%;font-size:12px;margin:20px 0}td,th{border-bottom:1px solid #dbe4e7;padding:10px 12px;text-align:left;vertical-align:top}th{background:#edf4f5}figure{margin:30px 0}img{width:100%;height:auto}figcaption{font-size:13px;color:#617683}pre{background:#173747;color:#f4f8fa;padding:24px;overflow:auto}a{color:#226f89}li{margin:8px 0}footer{margin-top:40px;padding-top:24px;border-top:1px solid #cbd8dc;color:#627780;font-size:13px}@media(max-width:750px){main{padding:24px}h1{font-size:30px}.metrics{flex-wrap:wrap}.metrics div{min-width:110px}}@media print{body{background:white}main{padding:0}section{break-inside:auto}figure{break-inside:avoid}h2{break-after:avoid}}'''
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>São Paulo health profiles</title><style>'+css+'</style><main><header><p class="eyebrow">PTC3567 · Data science study · October 2026</p><h1>Living conditions and health resources in São Paulo</h1><p class="subtitle">Socioeconomic profiles, public and non-public resources, and territorial context across 645 municipalities</p></header>'+''.join(sections)+'<footer>Reproducible descriptive analysis. All written project material is in English; official names and original source fields retain their original spelling.</footer></main></html>'
    (root/'reports/report.html').write_text(document,encoding='utf-8')
    build_notebook(root, summary)
    readme = f'''# São Paulo health profiles

**Socioeconomic profiles and inequalities in recorded health resources across 645 municipalities.**

{summary}

## Main results

- Non-SUS physician jobs and mean income: Spearman **{a.loc['physician_non_sus_per1000','spearman']:.2f}**, falling to **{a.loc['physician_non_sus_per1000','partial_rank']:.2f}** after demographic adjustment. SUS: **{a.loc['physician_sus_per1000','spearman']:.2f} → {a.loc['physician_sus_per1000','partial_rank']:.2f}**.
- Basic health units per resident: **{a.loc['basic_health_units_per10000','spearman']:.2f} → {a.loc['basic_health_units_per10000','partial_rank']:.2f}**. Facility density alone does not measure service capacity.
- **{model['selected_k']} exploratory profiles**, silhouette **{selected.silhouette:.2f}**, median full-pipeline refit ARI **{selected.refit_ari_median:.2f}**, Ward agreement **{selected.ward_ari:.2f}**. Profiles overlap and depend on variable and weighting choices.
- Pooled infant mortality: **{quarters.iloc[0].pooled_infant_mortality_per1000:.2f} vs {quarters.iloc[-1].pooled_infant_mortality_per1000:.2f}** deaths per 1,000 live births in lowest/highest mean-income quartiles; the municipal correlation is near zero.
- Spatial patterns in income and non-SUS resources are stronger than in SUS physician jobs. No local income association survives conservative BY correction at 5%.

![Profile validation](reports/figures/02_cluster_validation.png)

## Read the analysis

- [Complete report](reports/report.html): download and open in a browser; all nine figures are embedded.
- [Executed reading notebook](notebooks/analysis.ipynb): tables, explanations and embedded figures.
- [Model selection](reports/tables/cluster_validation.csv), [resource comparisons](reports/tables/profiles.csv), [adjusted associations](reports/tables/associations.csv).
- [Methods and limitations](docs/methodology.md), [data dictionary](docs/data_dictionary.md), [source manifest](data/sources.json).

## Reproduce

Python 3.11 or newer. From the extracted repository folder:

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python run.py verify
python run.py run
python -m unittest discover -s tests -v
```

On macOS/Linux, activate with `source .venv/bin/activate`. Activation can be skipped by calling the virtual environment's Python directly. The analysis needs no internet connection after dependencies are installed: frozen source data are bundled. Tested package versions are pinned in `requirements.txt`; run metadata records actual versions and runtime.

Optional Make targets: `make fetch`, `make run`, `make test`, `make verify`. Make is not required; the Python commands work directly on Windows.

`python run.py fetch` downloads missing sources with frozen-hash verification. `python run.py fetch --refresh` downloads new versions into `data/latest/` for a new audit, preserving this study. A provider revision cannot silently replace reference bytes. All initial CSVs now have official source URLs.

## Methods

1. Validate source keys, units, category totals and denominators; join by seven-digit IBGE code.
2. Build social profiles with log income, literacy and adverse sanitation, standardized with equal municipal weights.
3. Compare K-means/Ward for k=2–6; 80 resamples per k with preprocessing refitted; 10 seeds; leave-one-health-region-out and individual excluded-municipality stability.
4. Compare health indicators against profiles and simple income groups; use partial rank correlations with 400 health-region block resamples.
5. Test global spatial association under two graphs and a targeted local income analysis with multiple-testing correction.
6. Pool infant deaths and births; report count intervals and denominator sensitivity.

PCA visualizes the feature space. Health indicators never define the profiles or select k. The selection heuristic is exploratory, documented and not preregistered. All candidate assignments and a transparent JSON model are included.

## Important interpretation limits

- Professional counts are **employment links**, not unique clinicians or full-time equivalents.
- Resource dictionaries say December 2023 while catalog labels say 2024. The exact year remains uncertain; both population denominators are tested.
- Missing professional/bed records are not zeros. Bed data are retained and audited, but excluded from substantive comparisons.
- UBS counts measure facilities, not capacity. Municipal resources do not measure patient access across borders.
- Social data refer to 2022 and health indicators to around 2023–2024. This is an ecological, descriptive study, not a forecast or causal evaluation.

## Repository structure

| Path | Purpose |
|---|---|
| `src/sp_health/data/` | Acquisition, validation and indicator construction |
| `src/sp_health/analysis/` | Clustering, health comparisons and spatial tests |
| `src/sp_health/reporting/` | Static figures, report and reading notebook |
| `data/raw/` | Unmodified reference snapshots |
| `data/processed/` | Municipality-level analytical dataset |
| `reports/tables/` | Metrics, profiles, uncertainty, audits and model parameters |
| `reports/figures/` | Nine static PNG figures |
| `docs/` | Methods, definitions and provenance |
| `tests/` | Targeted tests of parsing, aggregation, alignment and spatial calculations |

## Data attribution

IBGE/SIDRA (census and boundaries) and Fundação Seade (population, resources, vital statistics and regional codes). See `data/sources.json` and `docs/sources.md` for URLs, snapshot origins and hashes. Original fields and official names remain in Portuguese. Source data retain their providers' terms; no new license is assigned to them.
'''
    (root/'README.md').write_text(readme,encoding='utf-8')
