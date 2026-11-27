"""CI integration: uploaded months and revisions must refresh sharing images.

All synthetic data stays in TemporaryDirectory, outside the published site.
No BEA/Haver requests, calculations, source data, or live dashboards are changed.
"""
from pathlib import Path
from datetime import date
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile

AUTOMATION = Path(__file__).resolve().parents[1]
ROOT = AUTOMATION.parent
sys.path.insert(0, str(AUTOMATION))
from package_site import PUBLIC_FILES, DATA_FILES, package_site


def month(value):
    match = re.match(r'^(\d{4})(?:-|m)(\d{1,2})', value)
    if match:
        return int(match[1]), int(match[2])
    number = int(value)
    return 1960 + number // 12, number % 12 + 1


def following(value):
    year, number = month(value)
    year, number = (year + 1, 1) if number == 12 else (year, number + 1)
    if re.match(r'^\d{4}m', value):
        return f'{year}m{number}'
    if re.fullmatch(r'-?\d+', value):
        return str((year - 1960) * 12 + number - 1)
    return f'{year}-{number:02d}' + value[7:]


def change_csv(path, append):
    rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8'))))
    while rows and not rows[-1]:
        rows.pop()
    index = rows[0].index('date')
    row = rows[-1].copy()
    if append:
        row[index] = following(row[index])
    for column, value in enumerate(row):
        if column != index and value.strip():
            row[column] = str(float(value) + 0.05)
    if append:
        rows.append(row)
    else:
        rows[-1] = row
    output = io.StringIO(newline='')
    csv.writer(output, lineterminator='\n').writerows(rows)
    path.write_text(output.getvalue(), encoding='utf-8')


def main():
    site = Path(sys.argv[1]).resolve()
    baseline = json.loads((site / 'preview-release.json').read_text())
    public_hash = hashlib.sha256((site / 'preview.png').read_bytes()).hexdigest()
    original_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in PUBLIC_FILES}
    reports = {}
    with tempfile.TemporaryDirectory(prefix='preview-upload-tests-') as directory:
        for kind in ('new-month', 'same-month-revision'):
            source, output = Path(directory) / kind / 'source', Path(directory) / kind / 'site'
            source.mkdir(parents=True)
            for name in PUBLIC_FILES:
                shutil.copyfile(ROOT / name, source / name)
            for name in DATA_FILES:
                if name.endswith('.csv'):
                    # A new month inside the current quarter does not append a
                    # fictitious quarterly observation.
                    if kind == 'new-month' and 'quarterly' in name:
                        continue
                    change_csv(source / name, append=kind == 'new-month')
            # Deliberately retain old metadata to exercise manual uploads that
            # update CSVs without also changing data-update.json.
            package_site(source, output)
            subprocess.run(['node', str(AUTOMATION / 'preview/render.mjs'), '--site', str(output)], check=True)
            report = json.loads((output / 'preview-release.json').read_text())
            if kind == 'new-month':
                expected = following(baseline['data_through'])
                assert report['data_through'] == expected, report
            else:
                assert report['data_through'] == baseline['data_through'], report
            assert report['image'] != baseline['image'], report
            assert report['data_version'] != baseline['data_version'], report
            for html in ('index.html', json.loads((AUTOMATION / 'preview/config.json').read_text())['html']):
                assert report['image_url'] in (output / html).read_text(encoding='utf-8')
            reports[kind] = {'data_through': report['data_through'], 'image': report['image'], 'passed': True}
    assert hashlib.sha256((site / 'preview.png').read_bytes()).hexdigest() == public_hash
    assert {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in PUBLIC_FILES} == original_hashes
    (site.parent / 'preview-upload-test-results.json').write_text(json.dumps(reports, indent=2) + '\n')
    print('New-month and same-month revision previews passed; synthetic data was not published.')


if __name__ == '__main__':
    main()
