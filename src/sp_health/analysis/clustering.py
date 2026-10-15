"""Evaluate territorial profiles without using health outcomes to define groups."""
import json
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score, davies_bouldin_score
from sklearn.preprocessing import StandardScaler
from sp_health.data.prepare import SOCIAL


def transformed(d, income='income_median', sanitation='adverse_sanitation_pct'):
    return np.column_stack([np.log(d[income]), d.literacy_pct, d[sanitation]])


def fit(values, k, seed=42, weights=None):
    scaler = StandardScaler().fit(values, sample_weight=weights)
    model = KMeans(n_clusters=k, n_init=30, random_state=seed).fit(
        scaler.transform(values), sample_weight=weights)
    return scaler, model


def matched_labels(reference, candidate, k):
    counts = np.zeros((k, k), dtype=int)
    np.add.at(counts, (reference, candidate), 1)
    rows, cols = linear_sum_assignment(-counts)
    return dict(zip(cols, rows))


def run(d, root, repeats=80):
    out = root/'reports/tables'
    rng = np.random.default_rng(2026)
    values = transformed(d)
    metrics, fitted, simulations = [], {}, {}
    n = len(d)
    for k in range(2, 7):
        scaler, model = fit(values, k)
        x = scaler.transform(values)
        records = []
        for repetition in range(repeats):
            train = rng.choice(n, int(.8*n), replace=False)
            test = np.setdiff1d(np.arange(n), train)
            subscaler, submodel = fit(values[train], k, repetition)
            prediction = submodel.predict(subscaler.transform(values))
            # Align on the fitting subset only; individual agreement uses excluded towns.
            mapping = matched_labels(model.labels_[train], prediction[train], k)
            aligned = np.array([mapping[label] for label in prediction])
            records.append((test, aligned[test], adjusted_rand_score(model.labels_, prediction),
                            adjusted_rand_score(model.labels_[test], prediction[test])))
        simulations[k] = records
        ward = AgglomerativeClustering(n_clusters=k, linkage='ward').fit_predict(x)
        metrics.append({'k': k, 'silhouette': silhouette_score(x, model.labels_),
                        'davies_bouldin': davies_bouldin_score(x, model.labels_),
                        'smallest_cluster': int(np.bincount(model.labels_).min()),
                        'refit_ari_median': float(np.median([r[2] for r in records])),
                        'refit_ari_p10': float(np.quantile([r[2] for r in records], .1)),
                        'excluded_ari_median': float(np.median([r[3] for r in records])),
                        'ward_ari': adjusted_rand_score(model.labels_, ward),
                        'ward_silhouette': silhouette_score(x, ward),
                        'seed_ari_min': min(adjusted_rand_score(model.labels_, fit(values, k, s)[1].labels_) for s in range(10))})
        fitted[k] = (scaler, model)
    validation = pd.DataFrame(metrics)
    # Exploratory trade-off: shortlist near-best separation, then prefer robust stability.
    eligible = validation[(validation.smallest_cluster >= 30) & (validation.silhouette >= validation.silhouette.max()-.02)]
    fallback = eligible.empty
    if fallback:
        k = int(validation.loc[validation.silhouette.idxmax(), 'k'])
    else:
        k = int(eligible.sort_values(['refit_ari_p10', 'k'], ascending=[False, True]).iloc[0].k)
    validation['selected'] = validation.k.eq(k)
    validation.to_csv(out/'cluster_validation.csv', index=False)
    pd.DataFrame({f'k_{candidate}': fitted[candidate][1].labels_ for candidate in fitted}, index=d.index).to_csv(out/'candidate_assignments.csv', index_label='ibge_code')
    scaler, model = fitted[k]
    x = scaler.transform(values)
    order = d.assign(label=model.labels_).groupby('label').income_median.median().sort_values().index
    mapping = {int(label): i+1 for i, label in enumerate(order)}
    d['profile'] = [mapping[int(label)] for label in model.labels_]
    agreement = np.zeros(n)
    trials = np.zeros(n)
    for test, labels, _, _ in simulations[k]:
        agreement[test] += labels == model.labels_[test]
        trials[test] += 1
    d['profile_stability'] = np.divide(agreement, trials, out=np.full(n, np.nan), where=trials>0)
    d['excluded_repeats'] = trials.astype(int)
    distances = model.transform(x)
    d['distance_to_profile'] = distances.min(axis=1)
    baseline = pd.qcut(d.income_median, k, labels=False, duplicates='drop').to_numpy()
    d['income_group'] = baseline+1
    # Outcome comparisons never choose k, features or transforms.
    sensitivities = []
    def add(name, v, mask=None, weights=None):
        mask = np.ones(n, dtype=bool) if mask is None else mask
        ss, mm = fit(v[mask], k, weights=weights)
        sensitivities.append({'scenario': name, 'n': int(mask.sum()),
                              'ari': adjusted_rand_score(model.labels_[mask], mm.labels_)})
    add('Mean instead of median income', transformed(d, income='income_mean'))
    add('Network connection instead of adverse sanitation', transformed(d, sanitation='sewer_network_pct'))
    add('Log1p adverse sanitation', np.column_stack([values[:, :2], np.log1p(values[:, 2])]))
    add('No income log transform', np.column_stack([d.income_median, values[:, 1:]]))
    add('Exclude capital', values, d.municipality.ne('São Paulo').to_numpy())
    add('Population weighted fit and scaling', values, weights=d.population_2024.to_numpy())
    clipped = np.clip(values, np.quantile(values, .01, axis=0), np.quantile(values, .99, axis=0))
    add('Winsorize at 1st and 99th percentiles', clipped)
    pd.DataFrame(sensitivities).to_csv(out/'cluster_sensitivity.csv', index=False)
    held_regions = []
    for region in sorted(d.health_region.unique()):
        keep = d.health_region.ne(region).to_numpy()
        ss, mm = fit(values[keep], k)
        prediction = mm.predict(ss.transform(values))
        held_regions.append({'health_region': region, 'excluded_n': int((~keep).sum()),
                             'all_ari': adjusted_rand_score(model.labels_, prediction),
                             'retained_ari': adjusted_rand_score(model.labels_[keep], prediction[keep])})
    pd.DataFrame(held_regions).to_csv(out/'leave_region_out.csv', index=False)
    pca = PCA().fit(x)
    scores = pca.transform(x)
    d['pc1'], d['pc2'] = scores[:, 0], scores[:, 1]
    pd.DataFrame(pca.components_.T, index=SOCIAL,
                 columns=['PC1', 'PC2', 'PC3']).to_csv(out/'pca_components.csv', index_label='feature')
    pd.DataFrame({'component': [1, 2, 3], 'variance_ratio': pca.explained_variance_ratio_}).to_csv(out/'pca_variance.csv', index=False)
    representatives = pd.concat([part.nsmallest(2, 'distance_to_profile').assign(case_type='Nearest profile center')
                                 for _, part in d.groupby('profile')] + [
                                 d.nlargest(5, 'distance_to_profile').assign(case_type='Largest distance to assigned center')])
    representatives[['municipality', 'profile', 'case_type', *SOCIAL, 'distance_to_profile', 'profile_stability']].to_csv(out/'case_studies.csv')
    # Centers and scaler are enough to inspect or assign profiles; no unsafe pickle is required.
    model_card = {'features': SOCIAL, 'transform': ['natural log', 'identity', 'identity'],
                  'scaler_mean': scaler.mean_.tolist(), 'scaler_scale': scaler.scale_.tolist(),
                  'centers': model.cluster_centers_.tolist(), 'label_to_profile': mapping,
                  'selected_k': k, 'selection_fallback': fallback,
                  'selection_rule': 'Among k=2..6 within 0.02 of maximum silhouette and >=30 towns per cluster, maximize the 10th-percentile full-pipeline refit ARI; break ties by smaller k. Exploratory heuristic, not preregistered.',
                  'repeats': repeats, 'seed': 2026,
                  'income_baseline_groups': int(len(np.unique(baseline))),
                  'income_baseline_ari': adjusted_rand_score(model.labels_, baseline),
                  'income_baseline_silhouette': silhouette_score(x, baseline),
                  'pca_variance_ratio': pca.explained_variance_ratio_.tolist()}
    (out/'model.json').write_text(json.dumps(model_card, indent=2)+'\n')
    return d, model_card
