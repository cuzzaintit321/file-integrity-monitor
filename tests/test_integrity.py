import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import integrity


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'a.txt').write_text('original')

    def tearDown(self):
        self.tmp.cleanup()

    def test_unchanged_tree(self):
        baseline = integrity.scan(self.source)
        result = integrity.compare(baseline, integrity.scan(self.source))
        self.assertFalse(result['has_changes'])
        self.assertEqual(result['unchanged_count'], 1)

    def test_content_permissions_added_and_missing(self):
        (self.source / 'removed').write_text('old')
        baseline = integrity.scan(self.source)
        (self.source / 'a.txt').write_text('modified')
        (self.source / 'a.txt').chmod(0o700)
        (self.source / 'removed').unlink()
        (self.source / 'new').write_bytes(b'new')
        result = integrity.compare(baseline, integrity.scan(self.source))
        self.assertEqual(result['added'], ['new'])
        self.assertEqual(result['missing'], ['removed'])
        self.assertEqual(result['changed'][0]['reasons'], ['content', 'permissions'])

    def test_symlinks_skipped_and_coverage_marked_incomplete(self):
        (self.source / 'link').symlink_to('/etc/passwd')
        baseline = integrity.scan(self.source)
        self.assertNotIn('link', baseline['files'])
        self.assertEqual(baseline['skipped'], ['link'])
        self.assertTrue(integrity.compare(baseline, baseline)['incomplete'])

    def test_baseline_and_report_outside_source(self):
        with self.assertRaises(ValueError):
            integrity.outside_tree(self.source / 'baseline.json', self.source)

    def test_exclusive_output_keeps_existing_baseline(self):
        path = self.root / 'baseline.json'
        integrity.write_json(path, {'sentinel': True})
        with self.assertRaises(FileExistsError):
            integrity.write_json(path, {})
        self.assertTrue(json.loads(path.read_text())['sentinel'])

    def test_invalid_manifest_rejected(self):
        baseline = integrity.scan(self.source)
        baseline['files']['../outside'] = baseline['files'].pop('a.txt')
        with self.assertRaises(ValueError):
            integrity.validate(baseline)

    def test_cli_detects_drift_and_writes_report(self):
        script = str(Path(integrity.__file__).resolve())
        baseline, report = self.root / 'baseline.json', self.root / 'report.json'
        result = subprocess.run([sys.executable,script,'baseline',str(self.source),str(baseline)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.source / 'a.txt').write_text('changed')
        result = subprocess.run([sys.executable,script,'check',str(self.source),str(baseline),'--report',str(report)], capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(json.loads(report.read_text())['has_changes'])


if __name__ == '__main__':
    unittest.main()
