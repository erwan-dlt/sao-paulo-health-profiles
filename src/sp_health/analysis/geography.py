"""Read official polygon rings and test spatial association with explicit graphs.

The SHP/DBF reader supports this frozen Polygon shapefile only. It intentionally
fails on other shape types. No geospatial dependency is required.
"""
import json
import struct
import zipfile
from collections import defaultdict
from itertools import combinations
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, diags
from scipy.sparse.csgraph import connected_components
from scipy.spatial.distance import cdist


def read_polygons(path):
    with zipfile.ZipFile(path) as archive:
        db = archive.read('SP_Municipios_2022.dbf')
        shp = archive.read('SP_Municipios_2022.shp')
    count, header, length = struct.unpack_from('<IHH', db, 4)
    fields, offset, pos = {}, 1, 32
    while db[pos] != 13:
        name = db[pos:pos+11].split(b'\0')[0].decode()
        size = db[pos+16]
        fields[name] = (offset, size)
        offset += size
        pos += 32
    offset, size = fields['CD_MUN']
    codes = [db[header+i*length+offset:header+i*length+offset+size].decode().strip() for i in range(count)]
    result, pos, record = {}, 100, 0
    while pos < len(shp):
        _, words = struct.unpack_from('>ii', shp, pos)
        pos += 8
        body = shp[pos:pos+2*words]
        pos += 2*words
        kind = struct.unpack_from('<i', body)[0]
        if kind != 5:
            raise ValueError(f'Expected Polygon SHP, received {kind}')
        parts, points = struct.unpack_from('<ii', body, 36)
        starts = list(struct.unpack_from('<'+'i'*parts, body, 44))+[points]
        xy = np.frombuffer(body, dtype='<f8', count=points*2, offset=44+4*parts).reshape(-1, 2)
        result[codes[record]] = [xy[a:b].copy() for a, b in zip(starts[:-1], starts[1:])]
        record += 1
    if record != 645 or len(result) != 645:
        raise ValueError('Expected 645 unique municipality polygons')
    return result


def graph(polygons, codes):
    vertices = defaultdict(set)
    centers = []
    for i, code in enumerate(codes):
        rings = polygons[code]
        for ring in rings:
            for xy in np.round(ring, 7):
                vertices[tuple(xy)].add(i)
        # Area centroid from oriented rings, including holes. Geographic coordinates
        # are sufficient here for nearby-neighbor sensitivity, not travel distances.
        total, weighted = 0., np.zeros(2)
        for ring in rings:
            a, b = ring[:-1], ring[1:]
            cross = a[:, 0]*b[:, 1]-b[:, 0]*a[:, 1]
            area = cross.sum()/2
            if abs(area) > 1e-15:
                centroid = ((a+b)*cross[:, None]).sum(axis=0)/(6*area)
                total += area
                weighted += area*centroid
        centers.append(weighted/total)
    edges = set()
    for owners in vertices.values():
        edges.update(combinations(sorted(owners), 2))
    n = len(codes)
    adjacency = np.zeros((n, n), dtype=float)
    for a, b in edges:
        adjacency[a, b] = adjacency[b, a] = 1
    # Great-circle ranking through unit-sphere chord distances of polygon centroids.
    lon, lat = np.deg2rad(np.array(centers)).T
    xyz = np.column_stack([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
    distance = cdist(xyz, xyz)
    np.fill_diagonal(distance, np.inf)
    neighbors = np.argsort(distance, axis=1)[:, :6]
    knn = np.zeros_like(adjacency)
    knn[np.arange(n)[:, None], neighbors] = 1
    knn = np.maximum(knn, knn.T)
    return adjacency, knn, centers


def weights(adjacency):
    degree = adjacency.sum(axis=1)
    inverse = np.divide(1., degree, out=np.zeros_like(degree), where=degree>0)
    return diags(inverse) @ csr_matrix(adjacency)


def fdr(p, dependence=False):
    p = np.asarray(p)
    n = len(p)
    order = np.argsort(p)
    factor = np.sum(1/np.arange(1, n+1)) if dependence else 1
    adjusted = p[order]*n/np.arange(1, n+1)*factor
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty(n)
    result[order] = np.minimum(adjusted, 1)
    return result


def moran(values, adjacency, permutations=9999, seed=2026, local=False):
    w = weights(adjacency)
    z = np.asarray(values, dtype=float)
    z = (z-z.mean())/z.std()
    n, s0 = len(z), float(w.sum())
    local_i = z*(w@z)
    observed = n/s0*local_i.sum()/(z@z)
    expected = -1/(n-1)
    rng = np.random.default_rng(seed)
    exceed, local_exceed = 0, np.zeros(n)
    for _ in range(permutations):
        perm = rng.permutation(z)
        perm_local = perm*(w@perm)
        simulated = n/s0*perm_local.sum()/(perm@perm)
        exceed += abs(simulated-expected) >= abs(observed-expected)
        if local:
            local_exceed += np.abs(perm_local-expected) >= np.abs(local_i-expected)
    p = (exceed+1)/(permutations+1)
    return float(observed), float(p), local_i, (local_exceed+1)/(permutations+1), w@z, z


def run(d, root, permutations=9999):
    polygons = read_polygons(root/'data/raw/municipalities.zip')
    if set(polygons) != set(d.index):
        raise ValueError('Boundary/data key mismatch')
    adjacency, knn, centers = graph(polygons, list(d.index))
    out = root/'reports/tables'
    audit = {'queen_rule': 'At least one shared boundary vertex after rounding coordinates to 7 decimal degrees',
             'queen_edges': int(adjacency.sum()/2), 'queen_islands': d.index[adjacency.sum(axis=1)==0].tolist(),
             'queen_components': int(connected_components(csr_matrix(adjacency))[0]),
             'knn_rule': 'Symmetrized 6-nearest polygon centroids; unit-sphere chord distance',
             'permutations': permutations, 'local_null': 'Total randomization of all income values, not conditional LISA permutations'}
    rows = []
    for name, matrix in [('Queen', adjacency), ('Symmetric 6-NN', knn)]:
        for column in ['income_mean', 'adverse_sanitation_pct', 'physician_sus_per1000', 'physician_non_sus_per1000']:
            keep = d[column].notna().to_numpy()
            submatrix = matrix[np.ix_(keep, keep)]
            values = d.loc[keep, column].to_numpy()
            # Explicitly exclude isolated nodes rather than filling their spatial lag.
            active = submatrix.sum(axis=1)>0
            result = moran(values[active], submatrix[np.ix_(active, active)], permutations)
            rows.append({'graph': name, 'variable': column, 'municipalities': int(active.sum()), 'moran_i': result[0], 'permutation_p': result[1]})
    global_table = pd.DataFrame(rows)
    global_table['bh_q'] = fdr(global_table.permutation_p)
    global_table.to_csv(out/'global_moran.csv', index=False)
    # Local income map only: one predeclared family, no search across outcomes.
    active = adjacency.sum(axis=1)>0
    result = moran(d.loc[active, 'income_mean'], adjacency[np.ix_(active, active)], permutations, local=True)
    local = pd.DataFrame(index=d.index[active])
    local['local_i'], local['permutation_p'] = result[2], result[3]
    local['bh_q'], local['by_q'] = fdr(result[3]), fdr(result[3], True)
    local['quadrant'] = np.where(result[5] >= 0, np.where(result[4]>=0, 'High-high', 'High-low'), np.where(result[4]>=0, 'Low-high', 'Low-low'))
    local['map_class'] = np.where(local.by_q<=.05, local.quadrant, 'Not significant (BY)')
    local.to_csv(out/'local_income_moran.csv', index_label='ibge_code')
    audit['local_significant_bh'] = int(local.bh_q.le(.05).sum())
    audit['local_significant_by'] = int(local.by_q.le(.05).sum())
    (out/'spatial_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    d = d.join(local[['local_i', 'by_q', 'map_class']])
    d['map_class'] = d.map_class.fillna('No Queen neighbors')
    return d, polygons
