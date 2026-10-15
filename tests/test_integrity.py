"""Targeted regression checks for data meaning and mathematical invariants."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sp_health.data.prepare import number, unique
from sp_health.analysis.clustering import matched_labels
from sp_health.analysis.comparisons import aggregate, poisson_interval
from sp_health.analysis.geography import weights, fdr, moran

ROOT = Path(__file__).resolve().parents[1]


class IntegrityTests(unittest.TestCase):
    def test_brazilian_numeric_format(self):
        values = number(pd.Series(['120.393', '1,25', '0', None, 'X']))
        self.assertEqual(values.iloc[0], 120393)
        self.assertEqual(values.iloc[1], 1.25)
        self.assertEqual(values.iloc[2], 0)
        self.assertTrue(values.iloc[3:].isna().all())

    def test_duplicate_join_key_rejected(self):
        with self.assertRaises(ValueError):
            unique(pd.DataFrame({'code': ['3500105', '3500105']}), ['code'], 'sample')

    def test_label_permutation_is_not_instability(self):
        mapping = matched_labels(np.array([0,0,1,1,2,2]), np.array([2,2,0,0,1,1]), 3)
        self.assertEqual(mapping, {2:0,0:1,1:2})

    def test_poisson_zero_has_positive_upper_bound(self):
        low, high = poisson_interval(0, 100)
        self.assertEqual(low, 0)
        self.assertAlmostEqual(float(high), 36.8887945, places=5)

    def test_multiple_testing_against_scipy(self):
        p = np.array([.001,.04,.02,.9,.2])
        np.testing.assert_allclose(fdr(p), false_discovery_control(p, method='bh'))
        np.testing.assert_allclose(fdr(p, True), false_discovery_control(p, method='by'))

    def test_complete_graph_moran_identity(self):
        # Every other observation is a neighbor: I = -1/(n-1) for any nonconstant vector.
        adjacency = np.ones((5,5))-np.eye(5)
        w = weights(adjacency)
        np.testing.assert_allclose(np.asarray(w.sum(axis=1)).ravel(), 1)
        self.assertAlmostEqual(moran([1,4,2,9,5], adjacency, permutations=9)[0], -.25)

    def test_real_data_denominators_and_missingness(self):
        d = pd.read_csv(ROOT/'data/processed/municipalities.csv', dtype={'ibge_code':str})
        self.assertEqual(len(d), 645)
        self.assertTrue(d.ibge_code.is_unique)
        self.assertEqual(d.physician_total_jobs.isna().sum(), 10)
        self.assertEqual(d.reported_beds.isna().sum(), 289)
        self.assertEqual(d.basic_health_units.notna().sum(), 645)
        np.testing.assert_allclose(d.infant_mortality_per1000, 1000*d.infant_deaths/d.live_births)
        observed = d.dropna(subset=['physician_total_jobs'])
        np.testing.assert_allclose(observed.physician_total_jobs, observed.physician_sus_jobs+observed.physician_non_sus_jobs)
        result = aggregate(d, 'profile')
        for _, row in result.iterrows():
            part = d[d.profile.eq(row.profile)].dropna(subset=['physician_total_jobs'])
            self.assertAlmostEqual(row.physician_sus_pooled_per1000, 1000*part.physician_sus_jobs.sum()/part.population_2024.sum())


if __name__ == '__main__':
    unittest.main()
