from pathlib import Path
import json
import stat
import tempfile
import unittest
import warnings
import zipfile

from nerve_awim.pilot_bundle_v28 import EXTRAS, MANIFEST, build_bundle, read_bundle, unpack_bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'source'
        self.root.mkdir()
        for name in (*EXTRAS, 'src/nerve_awim/__init__.py'):
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n')
        self.archive = Path(self.temp.name)/'bundle.zip'
        self.destination = Path(self.temp.name)/'installed'
        self.build()

    def build(self, path=None):
        return build_bundle(self.root, path or self.archive, revision='a'*40, dirty=False)

    def rewrite(self, transform):
        with zipfile.ZipFile(self.archive) as z:
            members = [(item, z.read(item)) for item in z.infolist()]
        with zipfile.ZipFile(self.archive, 'w') as z:
            for item, data in transform(members):
                z.writestr(item, data)

    def test_roundtrip_and_deterministic_bytes(self):
        second = Path(self.temp.name)/'second.zip'
        self.build(second)
        self.assertEqual(second.read_bytes(), self.archive.read_bytes())
        manifest = unpack_bundle(self.archive, self.destination)
        self.assertEqual(manifest['source_revision'], 'a'*40)
        self.assertFalse(manifest['worktree_dirty'])
        for name in manifest['files']:
            self.assertEqual((self.destination/name).read_bytes(), (self.root/name).read_bytes())

    def test_no_existing_archive_or_directory_overwrite(self):
        original = self.archive.read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(original, self.archive.read_bytes())
        self.destination.mkdir()
        with self.assertRaises(FileExistsError):
            unpack_bundle(self.archive, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_runtime_state_and_identity_files_excluded(self):
        (self.root/'identity.json').write_text('PRIVATE')
        (self.root/'pilot.db').write_text('PRIVATE')
        (self.root/'secret.key').write_text('PRIVATE')
        archive = Path(self.temp.name)/'excluded.zip'
        self.build(archive)
        manifest, payload = read_bundle(archive)
        self.assertFalse(any('PRIVATE' in value.decode() for value in payload.values()))
        self.assertNotIn('identity.json', manifest['files'])

    def test_checksum_failure_before_extraction(self):
        self.rewrite(lambda items: [(i, b'altered' if i.filename == 'README.md' else b) for i,b in items])
        with self.assertRaises(ValueError):
            unpack_bundle(self.archive, self.destination)
        self.assertFalse(self.destination.exists())

    def test_traversal_and_absolute_names_rejected(self):
        for name in ('../escape', '/absolute', 'src/../escape', 'C:/escape', 'src\\escape'):
            archive = Path(self.temp.name)/'unsafe.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(MANIFEST, '{}')
                z.writestr(name, 'bad')
            with self.assertRaises(ValueError):
                unpack_bundle(archive, self.destination)
            self.assertFalse(self.destination.exists())

    def test_duplicate_members_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            self.rewrite(lambda items: items+[items[0]])
        with self.assertRaises(ValueError):
            read_bundle(self.archive)

    def test_archive_symlink_rejected(self):
        def transform(items):
            for item, content in items:
                if item.filename == 'README.md':
                    item.external_attr = (stat.S_IFLNK | 0o777) << 16
                yield item, content
        self.rewrite(transform)
        with self.assertRaises(ValueError):
            read_bundle(self.archive)

    def test_source_symlink_rejected(self):
        source = self.root/'README.md'
        source.unlink()
        source.symlink_to(self.root/'LICENSE')
        with self.assertRaises(ValueError):
            self.build(Path(self.temp.name)/'symlink.zip')

    def test_manifest_extra_or_missing_member_rejected(self):
        self.rewrite(lambda items: [(i,b) for i,b in items if i.filename != 'README.md'])
        with self.assertRaises(ValueError):
            read_bundle(self.archive)

    def test_duplicate_manifest_fields_rejected(self):
        self.rewrite(lambda items: [(i,b'{"format":1,"format":2}' if i.filename == MANIFEST else b) for i,b in items])
        with self.assertRaises(ValueError):
            read_bundle(self.archive)

    def test_dirty_build_is_explicit(self):
        path = Path(self.temp.name)/'dirty.zip'
        manifest = build_bundle(self.root, path, revision='b'*40, dirty=True)
        self.assertTrue(manifest['worktree_dirty'])
        self.assertTrue(read_bundle(path)[0]['worktree_dirty'])
