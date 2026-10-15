"""Static, English-language figures generated directly from the analysis tables."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Patch
from matplotlib.collections import PatchCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
from sp_health.data.prepare import SOCIAL

COLORS = ['#276F86', '#E7A54A', '#728A46', '#9C638C', '#BA594E', '#5A74A5']
LABELS = {'income_median': 'Median income (BRL/month)', 'literacy_pct': 'Literacy, age 15+ (%)',
          'adverse_sanitation_pct': 'Adverse sanitation (%)', 'physician_sus_per1000': 'SUS physician jobs',
          'physician_non_sus_per1000': 'Non-SUS physician jobs', 'nurse_sus_per1000': 'SUS nurse jobs',
          'nurse_non_sus_per1000': 'Non-SUS nurse jobs', 'basic_health_units_per10000': 'Basic health units',
          'infant_mortality_per1000': 'Infant mortality'}


def map_panel(ax, polygons, d, column, title, categorical=False, limits=None, colors=None):
    patches = []
    for code in d.index:
        vertices, commands = [], []
        for ring in polygons[code]:
            vertices.extend(ring)
            commands.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(ring)-2)+[MplPath.CLOSEPOLY])
        patches.append(PathPatch(MplPath(np.array(vertices), commands)))
    values = d[column].to_numpy(float)
    if categorical:
        k = int(np.nanmax(values))
        cmap = ListedColormap((colors or COLORS)[:k])
        norm = BoundaryNorm(np.arange(.5, k+1.5), k)
    else:
        cmap = plt.get_cmap('viridis').copy()
        low, high = limits or tuple(d[column].quantile([.02, .98]))
        norm = plt.Normalize(low, high)
    cmap.set_bad('#D3D7DB')
    collection = PatchCollection(patches, array=np.ma.masked_invalid(values), cmap=cmap, norm=norm,
                                 edgecolor='white', linewidth=.12)
    ax.add_collection(collection)
    ax.autoscale_view()
    ax.set_aspect(1/np.cos(np.deg2rad(23)))
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, pad=10)
    bar = ax.figure.colorbar(collection, ax=ax, orientation='horizontal', shrink=.75, pad=.02)
    if categorical:
        bar.set_ticks(range(1, k+1))
    return bar


def create(d, polygons, model, root):
    out, tables = root/'reports/figures', root/'reports/tables'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.titleweight': 'bold', 'figure.dpi': 140,
                         'axes.labelcolor': '#253A47', 'text.color': '#253A47'})
    def save(name):
        plt.savefig(out/name, bbox_inches='tight', facecolor='white')
        plt.close()
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), layout='constrained')
    for ax, col in zip(axes, SOCIAL):
        ax.hist(d[col], bins=28, color=COLORS[0], edgecolor='white')
        ax.set(xlabel=LABELS[col], ylabel='Municipalities')
    fig.suptitle('Three dimensions of living conditions | 2022', fontsize=17)
    save('01_distributions.png')
    v = pd.read_csv(tables/'cluster_validation.csv')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
    axes[0].plot(v.k, v.silhouette, 'o-', color=COLORS[0], label='K-means')
    axes[0].plot(v.k, v.ward_silhouette, 's--', color=COLORS[1], label='Ward')
    axes[0].set(ylabel='Silhouette', title='Separation');axes[0].legend()
    axes[1].plot(v.k, v.refit_ari_median, 'o-', color=COLORS[0], label='Median')
    axes[1].plot(v.k, v.refit_ari_p10, 'o--', color=COLORS[1], label='10th percentile')
    axes[1].set(ylabel='Adjusted Rand index', title='Stability: refit the full pipeline', ylim=(0, 1.03));axes[1].legend()
    axes[2].plot(v.k, v.ward_ari, 'o-', color=COLORS[2])
    axes[2].set(ylabel='Adjusted Rand index', title='Agreement with Ward', ylim=(-.05, 1.03))
    for ax in axes:
        ax.set_xticks(v.k);ax.set_xlabel('Number of profiles');ax.axvline(model['selected_k'], color='#7A8791', ls=':', label='Selected k')
    fig.suptitle('Profile selection | dashed vertical line marks the selected solution', fontsize=15)
    save('02_cluster_validation.png')
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for profile, part in d.groupby('profile'):
        axes[0].scatter(part.pc1, part.pc2, s=19, alpha=.65, color=COLORS[int(profile)-1], label=f'Profile {profile} (n={len(part)})')
    variance = model['pca_variance_ratio']
    axes[0].set(xlabel=f'PC1 ({variance[0]:.1%} of variance)', ylabel=f'PC2 ({variance[1]:.1%} of variance)', title='PCA projection');axes[0].legend(fontsize=9)
    x = np.column_stack([np.log(d.income_median), d.literacy_pct, d.adverse_sanitation_pct])
    x = (x-np.array(model['scaler_mean']))/np.array(model['scaler_scale'])
    means = pd.DataFrame(x, columns=SOCIAL).assign(profile=d.profile.to_numpy()).groupby('profile').mean()
    im = axes[1].imshow(means, cmap='RdBu_r', vmin=-2, vmax=2, aspect='auto')
    axes[1].set_xticks(range(3), ['Log income', 'Literacy', 'Adverse sanitation'], rotation=25, ha='right')
    axes[1].set_yticks(range(len(means)), [f'Profile {p}' for p in means.index])
    for i in range(len(means)):
        for j in range(3):axes[1].text(j, i, f'{means.iloc[i,j]:.2f}', ha='center', va='center', color='white' if abs(means.iloc[i,j])>1.3 else '#152E3C')
    axes[1].set_title('Standardized feature means');fig.colorbar(im, ax=axes[1], label='Standard deviations')
    save('03_pca_profiles.png')
    p = pd.read_csv(tables/'profiles.csv')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
    for sector, color in [('sus', COLORS[0]), ('non_sus', COLORS[1])]:
        axes[0].plot(p.profile, p[f'physician_{sector}_per1000_median'], 'o-', color=color, label=sector.replace('_', '-').upper())
        axes[1].plot(p.profile, p[f'physician_{sector}_pooled_per1000'], 'o-', color=color)
    axes[0].set(title='Typical municipality', ylabel='Median physician jobs / 1,000 residents');axes[0].legend()
    axes[1].set(title='Pooled resource rate', ylabel='Recorded jobs / observed population × 1,000')
    axes[2].plot(p.profile, p.basic_health_units_per10000_median, 'o-', color=COLORS[2], label='Median municipal rate')
    axes[2].plot(p.profile, p.basic_health_units_pooled_per10000, 's--', color=COLORS[3], label='Pooled rate')
    axes[2].set(title='Basic health units', ylabel='Units / 10,000 residents');axes[2].legend(fontsize=8)
    for ax in axes:ax.set_xticks(p.profile);ax.set_xlabel('Socioeconomic profile')
    fig.suptitle('Health resources were not used to define the profiles', fontsize=16)
    save('04_external_resources.png')
    a = pd.read_csv(tables/'associations.csv');a = a[a.income.eq('income_mean')].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 5.3), layout='constrained')
    for column, lo, hi, offset, label, color in [('spearman', 'spearman_low', 'spearman_high', -.12, 'Unadjusted', COLORS[0]),
                                               ('partial_rank', 'partial_low', 'partial_high', .12, 'Adjusted for demographic context', COLORS[1])]:
        ax.errorbar(a[column], np.arange(len(a))+offset, xerr=np.maximum(0,np.vstack([a[column]-a[lo],a[hi]-a[column]])), fmt='o', capsize=3, color=color, label=label)
    ax.set_yticks(range(len(a)), [LABELS[c] for c in a.outcome]);ax.invert_yaxis()
    ax.axvline(0, color='#9AA5AB', lw=1);ax.set(xlabel='Rank correlation with mean income; 95% region-block bootstrap intervals', title='Urban and demographic context changes the association')
    ax.legend(loc='lower right', fontsize=9);save('05_adjusted_associations.png')
    fig, axes = plt.subplots(2, 2, figsize=(13, 11), layout='constrained')
    map_panel(axes[0,0], polygons, d, 'profile', 'Socioeconomic profiles', True).set_label('Profile, ordered by median income')
    map_panel(axes[0,1], polygons, d, 'profile_stability', 'Agreement when a municipality is excluded', limits=(0,1)).set_label('Matched-label agreement (not a probability)')
    map_panel(axes[1,0], polygons, d, 'adverse_sanitation_pct', 'Adverse sanitation | 2022').set_label('% of occupied permanent private households')
    map_panel(axes[1,1], polygons, d, 'physician_non_sus_per1000', 'Non-SUS physician employment links').set_label('Jobs / 1,000 residents; gray = missing')
    fig.suptitle('São Paulo state | continuous colors clipped at 2nd–98th percentiles, except stability', fontsize=14)
    save('06_municipal_maps.png')
    q = pd.read_csv(tables/'income_quartiles.csv')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), layout='constrained')
    axes[0].errorbar(np.arange(4), q.pooled_infant_mortality_per1000, yerr=np.vstack([q.pooled_infant_mortality_per1000-q.imr_ci_low,q.imr_ci_high-q.pooled_infant_mortality_per1000]),fmt='o-',capsize=5,color=COLORS[0])
    axes[0].set_xticks(range(4),q.mean_income_quartile);axes[0].set(xlabel='Mean-income quartile (lowest → highest)',ylabel='Deaths / 1,000 live births',title='Pooled infant mortality, 2023–2024')
    axes[1].scatter(d.live_births,d.infant_mortality_per1000,s=17,alpha=.45,color=COLORS[0])
    axes[1].axhline(1000*d.infant_deaths.sum()/d.live_births.sum(),color=COLORS[1],ls='--',label='State pooled rate')
    axes[1].set(xscale='log',xlabel='Live births, 2023–2024 (log scale)',ylabel='Deaths / 1,000 live births',title='Small counts make local rates noisy');axes[1].legend()
    save('07_mortality.png')
    fig, axes = plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
    classes = ['High-high','Low-low','High-low','Low-high','Not significant (BY)','No Queen neighbors']
    codes = d.assign(local_class_number=d.map_class.map({c:i+1 for i,c in enumerate(classes)}))
    bar = map_panel(axes[0],polygons,codes,'local_class_number','Local income association | BY q ≤ 0.05',True,colors=['#B44848','#276F86','#D9A847','#8A719B','#D3D7DB','#777777'])
    bar.remove()
    present = sorted(codes.local_class_number.unique())
    local_colors = ['#B44848','#276F86','#D9A847','#8A719B','#D3D7DB','#777777']
    axes[0].legend(handles=[Patch(facecolor=local_colors[int(c)-1], label=classes[int(c)-1]) for c in present], loc='lower left', frameon=False, fontsize=9)
    g = pd.read_csv(tables/'global_moran.csv')
    for name, marker, color in [('Queen','o',COLORS[0]),('Symmetric 6-NN','s',COLORS[1])]:
        t=g[g.graph.eq(name)];axes[1].plot(t.moran_i,range(len(t)),marker=marker,ls='',color=color,label=name)
    axes[1].set_yticks(range(4),['Mean income','Adverse sanitation','SUS physician jobs','Non-SUS physician jobs']);axes[1].invert_yaxis();axes[1].set(xlabel="Global Moran's I",title='Sensitivity to the neighborhood graph');axes[1].legend()
    save('08_spatial_association.png')
    s = pd.read_csv(tables/'cluster_sensitivity.csv')
    fig, ax = plt.subplots(figsize=(10,4.5),layout='constrained')
    ax.barh(s.scenario,s.ari,color=COLORS[0]);ax.invert_yaxis();ax.set(xlim=(-.05,1),xlabel='Adjusted Rand index against the main profiles',title='How much do modeling choices change the profiles?')
    save('09_sensitivity.png')
