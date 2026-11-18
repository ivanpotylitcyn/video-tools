"""Check installation safety in temporary directories; never touch Resolve settings."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'resolve/fusion/templates'
TOOLS = (
    ('effects/edge-aberration', 'Edge Aberration.setting'),
    ('effects/film-grain-look', 'Film Grain Look.setting'),
    ('generators/type-drift', 'Type Drift.setting'),
)
BASH = shutil.which('bash')


@unittest.skipUnless(BASH and os.name == 'posix', 'Requires a POSIX Bash environment; Windows is not verified')
class TemplateInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='video-tools-install-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def invoke(self, slug, destination, expected=0, extra=()):
        result = subprocess.run(
            [BASH, str(TEMPLATES / slug / 'install'), str(destination), *extra],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_install_and_repeat_with_spaces(self):
        for slug, name in TOOLS:
            with self.subTest(tool=slug):
                destination = self.work / slug / 'folder with spaces'
                self.invoke(slug, destination)
                target = destination / name
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.resolve(), (TEMPLATES / slug / name).resolve())
                before = target.lstat().st_mtime_ns
                self.invoke(slug, destination)
                self.assertEqual(target.lstat().st_mtime_ns, before)

    def test_foreign_file_is_preserved(self):
        for slug, name in TOOLS:
            with self.subTest(tool=slug):
                target = self.work / name
                target.write_bytes(b'foreign template')
                self.invoke(slug, self.work, expected=1)
                self.assertFalse(target.is_symlink())
                self.assertEqual(target.read_bytes(), b'foreign template')

    def test_dangling_link_is_preserved(self):
        for slug, name in TOOLS:
            with self.subTest(tool=slug):
                target = self.work / name
                target.symlink_to('missing template')
                self.invoke(slug, self.work, expected=1)
                self.assertEqual(os.readlink(target), 'missing template')

    def test_existing_link_chain_is_preserved(self):
        for slug, name in TOOLS:
            with self.subTest(tool=slug):
                old_location = self.work / ('legacy-' + name)
                old_location.symlink_to(TEMPLATES / slug / name)
                target = self.work / name
                target.symlink_to(old_location)
                self.invoke(slug, self.work)
                self.assertEqual(os.readlink(target), str(old_location))

    def test_extra_argument_is_rejected_without_writes(self):
        for slug, _ in TOOLS:
            with self.subTest(tool=slug):
                destination = self.work / slug
                self.invoke(slug, destination, expected=2, extra=('unexpected',))
                self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
