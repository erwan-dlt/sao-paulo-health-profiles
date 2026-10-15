"""Download public inputs without silently changing the frozen reference snapshot."""
import hashlib
import json
import urllib.request
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    records = json.loads((root/'data/sources.json').read_text())
    for r in records:
        path = root/'data/raw'/r['file']
        if not path.exists() or digest(path) != r['sha256']:
            raise ValueError(f"Snapshot missing or changed: {r['file']}. Restore it from the delivered archive.")
    print(f'Verified {len(records)} frozen source files.')


def fetch(root, refresh=False):
    records = json.loads((root/'data/sources.json').read_text())
    target = root/'data/latest' if refresh else root/'data/raw'
    target.mkdir(parents=True, exist_ok=True)
    for r in records:
        path = target/r['file']
        if path.exists() and not refresh:
            if digest(path) != r['sha256']:
                raise ValueError(f"Unexpected hash for {r['file']}")
            print(f"Using frozen snapshot: {r['file']}")
            continue
        request = urllib.request.Request(r['url'], headers={'User-Agent': 'sp-health-research/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
        candidate = path.with_suffix(path.suffix+'.download')
        candidate.write_bytes(data)
        if not refresh and digest(candidate) != r['sha256']:
            candidate.unlink()
            raise ValueError(f"Live source changed: {r['file']}. Use the bundled snapshot; --refresh downloads separately for a new audit.")
        candidate.replace(path)
        print(f"Downloaded: {r['file']}")
    if refresh:
        manifest = [dict(r, sha256=digest(target/r['file'])) for r in records]
        (target/'sources.json').write_text(json.dumps(manifest, indent=2)+'\n')
