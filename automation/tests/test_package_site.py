from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_site import DATA_FILES, PUBLIC_FILES, HTML_FILE, package_site


class PackageTests(unittest.TestCase):
    def test_snapshot_paths_change_with_uploads_and_preserve_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output = Path(folder) / 'source', Path(folder) / 'site'
            root.mkdir()
            for name in PUBLIC_FILES:
                (root / name).write_bytes(('original:' + name).encode())
            first = package_site(root, output)
            for name in DATA_FILES:
                self.assertEqual((output / first['files'][name]).read_bytes(), (root / name).read_bytes())
            self.assertEqual((output / 'index.html').read_bytes(), (root / HTML_FILE).read_bytes())
            self.assertEqual(package_site(root, output)['version'], first['version'])
            changed = DATA_FILES[0]
            (root / changed).write_bytes(b'new uploaded data')
            second = package_site(root, output)
            self.assertNotEqual(first['version'], second['version'])
            self.assertNotEqual(first['files'][changed], second['files'][changed])
            self.assertEqual((output / first['files'][changed]).read_bytes(), ('original:' + changed).encode())
            self.assertEqual((output / second['files'][changed]).read_bytes(), b'new uploaded data')
            published = (output / 'data-manifest.json').read_bytes()
            (root / DATA_FILES[-1]).unlink()
            with self.assertRaises(FileNotFoundError):
                package_site(root, output)
            self.assertEqual((output / 'data-manifest.json').read_bytes(), published)
            self.assertEqual(json.loads(published)['version'], second['version'])


if __name__ == '__main__':
    unittest.main()
