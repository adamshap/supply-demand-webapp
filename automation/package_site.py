"""Stage public Pages files and publish an immutable, versioned data snapshot."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = ['supply_demand_baseline.csv', 'supply_demand_ambiguous.csv', 'supply_demand_quarterly.csv', 'supply_demand_goods_services.csv', 'supply_demand_goods_services_ambiguous.csv', 'supply_demand_precision.csv', 'supply_demand_public.xlsx', 'data-update.json']
PUBLIC_FILES = ['supply_demand_webapp.html', 'supply_demand_baseline.csv', 'supply_demand_ambiguous.csv', 'supply_demand_quarterly.csv', 'supply_demand_goods_services.csv', 'supply_demand_goods_services_ambiguous.csv', 'supply_demand_precision.csv', 'supply_demand_public.xlsx', 'data-update.json', 'preview.png']
HTML_FILE = 'supply_demand_webapp.html'

def package_site(root: Path, output: Path):
    # Read once: the manifest and hashed URLs describe exactly the staged bytes.
    payloads = {name: (root / name).read_bytes() for name in DATA_FILES}
    digest = hashlib.sha256()
    for name, raw in sorted(payloads.items()):
        digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(raw).digest())
    version = digest.hexdigest()
    target = output / 'data' / version
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, raw in payloads.items():
        (target / name).write_bytes(raw)
        files[name] = f'data/{version}/{name}'
    manifest = {'version': version, 'published_at': datetime.now(timezone.utc).isoformat(), 'files': files}
    (output / 'data-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    for name in PUBLIC_FILES:
        shutil.copyfile(root / name, output / name)
    shutil.copyfile(root / HTML_FILE, output / 'index.html')
    (output / '.nojekyll').touch()
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    args = parser.parse_args()
    manifest = package_site(ROOT, args.output)
    print(f"Packaged data snapshot {manifest['version']} ({len(manifest['files'])} files)")
