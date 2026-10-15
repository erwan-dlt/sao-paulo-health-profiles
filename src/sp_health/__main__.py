"""Command-line interface; the same commands work on Windows and Unix."""
import argparse
import json
from pathlib import Path
import platform
import time
from threadpoolctl import threadpool_limits


def main():
    parser = argparse.ArgumentParser(description='São Paulo socioeconomic profiles and health resources')
    parser.add_argument('command', choices=['fetch', 'verify', 'prepare', 'run'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--refresh', action='store_true', help='Download current sources into data/latest; preserve reference snapshots')
    args = parser.parse_args()
    root = args.root.resolve()
    for folder in ['data/processed', 'reports/tables', 'reports/figures', 'notebooks']:
        (root/folder).mkdir(parents=True, exist_ok=True)
    from sp_health.data.fetch import fetch, verify
    if args.command == 'fetch':
        fetch(root, args.refresh)
        return
    verify(root)
    if args.command == 'verify':
        return
    from sp_health.data.prepare import prepare
    started = time.perf_counter()
    print('Validating and preparing data...', flush=True)
    d = prepare(root)
    if args.command == 'prepare':
        return
    from sp_health.analysis import clustering, comparisons, geography
    from sp_health.reporting.build import build
    with threadpool_limits(limits=1):
        print('Evaluating profiles and refitting stability tests...', flush=True)
        d, model = clustering.run(d, root)
        print('Comparing health resources and mortality...', flush=True)
        d = comparisons.run(d, root)
        print('Testing spatial association...', flush=True)
        d, polygons = geography.run(d, root)
        d.to_csv(root/'data/processed/municipalities.csv')
        print('Building figures, report and notebook...', flush=True)
        build(d, polygons, model, root)
    import numpy, pandas, scipy, sklearn, matplotlib
    environment = {'python': platform.python_version(), 'elapsed_seconds': round(time.perf_counter()-started, 2),
                   'packages': {x.__name__: x.__version__ for x in [numpy, pandas, scipy, sklearn, matplotlib]}}
    (root/'reports/tables/run_environment.json').write_text(json.dumps(environment, indent=2)+'\n')
    print(f"Complete: {root/'reports/report.html'}", flush=True)


if __name__ == '__main__':
    main()
