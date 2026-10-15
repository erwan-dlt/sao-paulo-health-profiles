"""Describe external health indicators, with denominator-aware aggregation."""
import numpy as np
import pandas as pd
from scipy.stats import chi2, rankdata, spearmanr
from sp_health.data.prepare import SOCIAL, RESOURCE


def poisson_interval(deaths, births):
    deaths, births = np.asarray(deaths), np.asarray(births)
    lower = np.where(deaths > 0, chi2.ppf(.025, 2*deaths)/2, 0)
    upper = chi2.ppf(.975, 2*(deaths+1))/2
    return 1000*lower/births, 1000*upper/births


def association(frame, x, y):
    """Partial rank correlation, controlling for population, density and older age."""
    columns = [x, y, 'population_2024', 'density_per_km2', 'age65plus_pct']
    values = frame[columns].to_numpy(float)
    ranks = np.apply_along_axis(rankdata, 0, values)
    controls = np.column_stack([np.ones(len(frame)), ranks[:, 2:]])
    residuals = ranks[:, :2] - controls @ np.linalg.lstsq(controls, ranks[:, :2], rcond=None)[0]
    return float(np.corrcoef(ranks[:, :2].T)[0, 1]), float(np.corrcoef(residuals.T)[0, 1])


def aggregate(d, group):
    rows = []
    for name, part in d.groupby(group, observed=True):
        row = {group: name, 'municipalities': len(part), 'population': part.population_2024.sum()}
        for column in SOCIAL + RESOURCE + ['basic_health_units_per10000']:
            row[f'{column}_median'] = part[column].median()
        for label in ['physician', 'nurse']:
            valid = part.dropna(subset=[f'{label}_total_jobs'])
            row[f'{label}_observed_municipalities'] = len(valid)
            row[f'{label}_population_coverage_pct'] = 100*valid.population_2024.sum()/part.population_2024.sum()
            for kind in ['sus', 'non_sus']:
                # Both numerator and denominator refer only to municipalities with observations.
                row[f'{label}_{kind}_pooled_per1000'] = 1000*valid[f'{label}_{kind}_jobs'].sum()/valid.population_2024.sum()
        row['basic_health_units_pooled_per10000'] = 10000*part.basic_health_units.sum()/part.population_2024.sum()
        row['infant_deaths'], row['live_births'] = part.infant_deaths.sum(), part.live_births.sum()
        row['pooled_infant_mortality_per1000'] = 1000*row['infant_deaths']/row['live_births']
        row['imr_ci_low'], row['imr_ci_high'] = (float(x) for x in poisson_interval(row['infant_deaths'], row['live_births']))
        row['income_mean_population_weighted'] = np.average(part.income_mean, weights=part.population_2024)
        rows.append(row)
    return pd.DataFrame(rows)


def run(d, root, repeats=400):
    out = root/'reports/tables'
    rng = np.random.default_rng(90210)
    rows = []
    outcomes = RESOURCE + ['basic_health_units_per10000', 'infant_mortality_per1000']
    for income in ['income_mean', 'income_median']:
        for outcome in outcomes:
            columns = [income, outcome, 'population_2024', 'density_per_km2', 'age65plus_pct', 'health_region']
            subset = d[columns].dropna()
            raw, partial = association(subset, income, outcome)
            blocks = [part for _, part in subset.groupby('health_region')]
            estimates = []
            for _ in range(repeats):
                boot = pd.concat([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))], ignore_index=True)
                estimates.append(association(boot, income, outcome))
            estimates = np.array(estimates)
            rows.append({'income': income, 'outcome': outcome, 'n': len(subset), 'spearman': raw,
                         'spearman_low': np.quantile(estimates[:, 0], .025), 'spearman_high': np.quantile(estimates[:, 0], .975),
                         'partial_rank': partial, 'partial_low': np.quantile(estimates[:, 1], .025),
                         'partial_high': np.quantile(estimates[:, 1], .975), 'bootstrap_regions': len(blocks)})
    pd.DataFrame(rows).to_csv(out/'associations.csv', index=False)
    d['mean_income_quartile'] = pd.qcut(d.income_mean, 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
    for group, filename in [('profile', 'profiles'), ('health_region', 'health_regions'),
                            ('mean_income_quartile', 'income_quartiles'), ('income_group', 'income_baseline')]:
        aggregate(d, group).to_csv(out/f'{filename}.csv', index=False)
    # In-sample external descriptive comparison, not an estimate of predictive performance.
    explained = []
    for outcome in outcomes:
        part = d.dropna(subset=[outcome])
        y = np.log1p(part[outcome])
        total = ((y-y.mean())**2).sum()
        for group in ['profile', 'income_group']:
            means = y.groupby(part[group]).transform('mean')
            explained.append({'outcome': outcome, 'grouping': group, 'n': len(part),
                              'log1p_variance_explained': float(1-((y-means)**2).sum()/total)})
    pd.DataFrame(explained).to_csv(out/'baseline_comparison.csv', index=False)
    sensitivities = []
    for occupation in ['physician', 'nurse']:
        for sector in ['sus', 'non_sus']:
            for year in ['2023', '2024']:
                rate = f'{occupation}_{sector}_per1000'+('_pop2023' if year=='2023' else '')
                part = d[['income_mean', rate]].dropna()
                sensitivities.append({'occupation': occupation, 'sector': sector, 'population_year': year,
                                      'n': len(part), 'spearman': spearmanr(part.income_mean, part[rate]).statistic})
    pd.DataFrame(sensitivities).to_csv(out/'population_year_sensitivity.csv', index=False)
    mortality = []
    for threshold in [0, 100, 200, 500, 1000]:
        part = d[d.live_births >= threshold]
        mortality.append({'minimum_births': threshold, 'municipalities': len(part),
                          'income_mean_spearman': spearmanr(part.income_mean, part.infant_mortality_per1000).statistic,
                          'pooled_rate': 1000*part.infant_deaths.sum()/part.live_births.sum()})
    pd.DataFrame(mortality).to_csv(out/'mortality_sensitivity.csv', index=False)
    d['imr_ci_low'], d['imr_ci_high'] = poisson_interval(d.infant_deaths, d.live_births)
    return d
