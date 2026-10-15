"""Validate source tables and build one row per municipality; preserve missingness."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

SOCIAL = ['income_median', 'literacy_pct', 'adverse_sanitation_pct']
RESOURCE = [f'{o}_{s}_per1000' for o in ['physician', 'nurse'] for s in ['sus', 'non_sus']]


def number(series):
    """Parse Brazilian decimal notation, preserving missing or suppressed cells."""
    return pd.to_numeric(series.str.strip().str.replace('.', '', regex=False)
                         .str.replace(',', '.', regex=False), errors='coerce')


def read_csv(raw, name):
    for encoding in ['utf-8-sig', 'cp1252']:
        try:
            return pd.read_csv(raw / name, sep=';', encoding=encoding, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError(f'Cannot decode {name}')


def unique(frame, columns, label):
    if frame.duplicated(columns).any():
        raise ValueError(f'Duplicate keys in {label}: {columns}')


def sidra(raw, name, variable, category=None):
    table = pd.DataFrame(json.loads((raw / name).read_text(encoding='utf-8'))[1:])
    table = table[table.D2C.eq(variable)]
    if category is not None:
        table = table[table.D4C.eq(category)]
    unique(table, ['D1C'], name)
    return pd.Series(pd.to_numeric(table.V, errors='coerce').to_numpy(), index=table.D1C)


def prepare(root: Path):
    raw = root / 'data/raw'
    base = read_csv(raw, 'codigos_municipios_regioes.csv')
    base = base[base.cod_ibge.str.match(r'^35\d{5}$') & base.cod_ibge.ne('3500000')]
    unique(base, ['cod_ibge'], 'municipalities')
    d = base.set_index('cod_ibge')[['municipio', 'drs', 'r_saude']].rename(columns={
        'municipio': 'municipality', 'drs': 'regional_health_department', 'r_saude': 'health_region'})
    d.index.name = 'ibge_code'
    if len(d) != 645:
        raise ValueError(f'Expected 645 municipalities, received {len(d)}')
    d['income_mean'] = sidra(raw, 'income.json', '13431')
    d['income_median'] = sidra(raw, 'income.json', '13534')
    d['literacy_pct'] = sidra(raw, 'literacy.json', '2513')
    denominator = sidra(raw, 'sanitation.json', '381', '46292')
    # Use mutually exclusive categories; 46290 is already an aggregate of 72110/72111.
    categories = ['72110', '72111', '72112', '72113', '92858', '72114', '72115', '92861']
    sanitation = pd.concat({c: sidra(raw, 'sanitation.json', '381', c) for c in categories}, axis=1)
    # SIDRA '-' denotes numeric zero in this count table. 'X' remains suppressed/missing.
    raw_sanitation = pd.DataFrame(json.loads((raw / 'sanitation.json').read_text(encoding='utf-8'))[1:])
    for c in categories:
        zero = raw_sanitation[raw_sanitation.D4C.eq(c) & raw_sanitation.V.eq('-')].D1C
        sanitation.loc[zero, c] = 0
    if sanitation.isna().any().any():
        raise ValueError('Suppressed or missing sanitation counts require review')
    if not np.allclose(sanitation.sum(axis=1).reindex(denominator.index), denominator):
        raise ValueError('Sanitation categories do not reconcile with total')
    adverse = sanitation[['72113', '92858', '72114', '72115', '92861']].sum(axis=1)
    d['adverse_sanitation_pct'] = 100 * adverse / denominator
    d['sewer_network_pct'] = 100 * sidra(raw, 'sanitation.json', '381', '46290') / denominator
    d['unconnected_septic_pct'] = 100 * sanitation['72112'] / denominator
    population = read_csv(raw, 'population.csv')
    population['value'] = number(population.populacao)
    for year in ['2023', '2024']:
        pop = population[population.ano.eq(year) & population.sexo.isin(['Homens', 'Mulheres'])]
        unique(pop, ['cod_ibge', 'sexo', 'idade'], 'population')
        totals = pop[pop.idade.eq('Total')].groupby('cod_ibge').value.sum(min_count=2)
        d[f'population_{year}'] = totals
        if year == '2024':
            older = pop[pd.to_numeric(pop.idade.str[:2], errors='coerce').ge(65)]
            d['age65plus_pct'] = 100 * older.groupby('cod_ibge').value.sum() / totals
    demography = read_csv(raw, 'estimativa_pop_indicadores_esp.csv')
    demography = demography[demography.ano.eq('2024')]
    unique(demography, ['cod_ibge'], 'demography')
    d['density_per_km2'] = number(demography.set_index('cod_ibge').dens_demog)
    professionals = read_csv(raw, 'saude_med_enf_mun_ano.csv')
    unique(professionals, ['cod_ibge', 'medenf'], 'professionals')
    for occupation, label in [('Médico', 'physician'), ('Enfermeiro', 'nurse')]:
        subset = professionals[professionals.medenf.eq(occupation)].set_index('cod_ibge')
        for source, suffix in [('prof_sus', 'sus'), ('prof_nsus', 'non_sus'), ('prof_tot', 'total')]:
            d[f'{label}_{suffix}_jobs'] = number(subset[source])
            d[f'{label}_{suffix}_per1000'] = 1000 * d[f'{label}_{suffix}_jobs'] / d.population_2024
            d[f'{label}_{suffix}_per1000_pop2023'] = 1000 * d[f'{label}_{suffix}_jobs'] / d.population_2023
        valid = d[[f'{label}_{s}_jobs' for s in ['sus', 'non_sus', 'total']]].dropna()
        if not np.allclose(valid.iloc[:, 0] + valid.iloc[:, 1], valid.iloc[:, 2]):
            raise ValueError(f'{label} totals do not reconcile')
    beds = read_csv(raw, 'saude_leitos_mun_ano.csv')
    beds = beds[beds.periodos.eq('2024')]
    unique(beds, ['cod_ibge'], 'beds')
    d['reported_beds'] = number(beds.set_index('cod_ibge').leitos_total)
    d['reported_beds_per1000'] = 1000 * d.reported_beds / d.population_2024
    facilities = read_csv(raw, 'estabelecimentos_saude.csv')
    facilities.tiposeade = facilities.tiposeade.str.strip()
    unique(facilities, ['co_mun', 'tiposeade'], 'establishments')
    ubs = facilities[facilities.tiposeade.eq('Unidade Básica de Saúde')].set_index('co_mun')
    d['basic_health_units'] = number(ubs.total_geral)
    d['basic_health_units_per10000'] = 10000 * d.basic_health_units / d.population_2024
    vital = read_csv(raw, 'obitosinfantis_periodo.csv')
    vital = vital[vital.ano.isin(['2023', '2024']) & vital.cod_ibge.isin(d.index)].copy()
    unique(vital, ['cod_ibge', 'ano'], 'vital statistics')
    vital['infant_deaths'] = number(vital['obitos menores de 1 Ano'])
    vital['live_births'] = number(vital['nascidos vivos (por local de residência)'])
    if len(vital) != 1290 or vital[['infant_deaths', 'live_births']].isna().any().any():
        raise ValueError('Incomplete 2023–2024 vital statistics')
    d = d.join(vital.groupby('cod_ibge')[['infant_deaths', 'live_births']].sum())
    d['infant_mortality_per1000'] = 1000 * d.infant_deaths / d.live_births
    required = SOCIAL + ['population_2023', 'population_2024', 'density_per_km2', 'age65plus_pct', 'basic_health_units']
    if d[required].isna().any().any():
        raise ValueError('Missing values in required indicators')
    if (d[['population_2023', 'population_2024', 'live_births', 'income_median']] <= 0).any().any():
        raise ValueError('Nonpositive denominator or income')
    for c in ['literacy_pct', 'adverse_sanitation_pct', 'sewer_network_pct', 'age65plus_pct']:
        if not d[c].between(0, 100).all():
            raise ValueError(f'Invalid percentage: {c}')
    audit = {'municipalities': len(d), 'health_regions': int(d.health_region.nunique()),
             'missing_by_column': d.isna().sum().to_dict(),
             'municipalities_below_100_births': int(d.live_births.lt(100).sum()),
             'municipalities_without_infant_deaths': int(d.infant_deaths.eq(0).sum()),
             'sanitation_categories_reconcile': True,
             'snapshot_date_status': 'December 2023 in dictionaries; 2024 catalog labels; exact reference remains uncertain',
             'missing_policy': 'Missing resource rows remain missing; never inferred as zero.'}
    (root/'reports/tables/audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    d.to_csv(root/'data/processed/municipalities.csv')
    return d
