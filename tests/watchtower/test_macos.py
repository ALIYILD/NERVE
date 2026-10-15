import json
from pathlib import Path
import plistlib
import tempfile
import unittest

from nerve_guardian.macos import inspect_local


class MacOSPreflightTests(unittest.TestCase):
    def setUp(self):
        self.home = Path('/test-user')
        self.learning = self.home / 'Library/LaunchAgents/com.aliyildirim.nerve.learning.plist'
        self.telemetry = self.home / '.local/share/nerve-watchtower/state/telemetry.json'
        self.files = {self.learning: plistlib.dumps({'Label': 'com.aliyildirim.nerve.learning',
            'ProgramArguments': ['/Library/Frameworks/Python.framework/Versions/3.10/bin/python3',
                                 '/test-user/nerve-review/scripts/agentos_bridge.py', 'cycle'],
            'StartInterval': 900, 'RunAtLoad': True})}
        self.report()

    def report(self, stamp=100, source_stamp=100):
        self.files[self.telemetry] = json.dumps({'timestamp': stamp, 'health': {'status': 'OK', 'dropped': 0},
            'observations': [{'status': 'OK', 'observed_at': source_stamp, 'private': 'DO-NOT-EXPORT'}]}).encode()

    def metadata(self, path):
        return {'exists': path in self.files, 'uid': 501, 'mode': 0o600, 'regular': True, 'symlink': False}

    def inspect(self, **kwargs):
        return inspect_local(home=self.home, platform_name='Darwin', uid=501, now=100,
                             read_bytes=self.files.__getitem__, metadata=kwargs.pop('metadata', self.metadata), **kwargs)

    def test_observed_schedule_and_metadata_never_claim_ready(self):
        result = self.inspect()
        self.assertFalse(result['ready'])
        self.assertEqual('NOT_READY', result['status'])
        self.assertTrue(result['facts']['learning_launch_agent']['expected_command'])
        self.assertFalse(result['facts']['learning_launch_agent']['root_owned'])
        self.assertEqual('OBSERVED_METADATA_ONLY', result['facts']['passive_telemetry']['status'])
        self.assertNotIn('DO-NOT-EXPORT', json.dumps(result))
        self.assertNotIn('/test-user', json.dumps(result))

    def test_stale_or_falsely_fresh_telemetry_unknown(self):
        for stamp, source in ((1, 1), (100, 1), (101, 100), (float('nan'), 100)):
            self.report(stamp, source)
            self.assertEqual('UNKNOWN', self.inspect()['facts']['passive_telemetry']['status'])

    def test_malformed_plist_unexpected_arguments_and_missing_files(self):
        self.files[self.learning] = b'private-malformed'
        self.assertEqual('UNKNOWN', self.inspect()['facts']['learning_launch_agent']['status'])
        self.files[self.learning] = b'<?xml version="1.0"?><plist><dict>'
        self.assertEqual('UNKNOWN', self.inspect()['facts']['learning_launch_agent']['status'])
        self.files[self.learning] = plistlib.dumps({'ProgramArguments': ['secret-token', 'arbitrary.py']})
        result = self.inspect()
        self.assertFalse(result['facts']['learning_launch_agent']['expected_command'])
        self.assertNotIn('secret-token', json.dumps(result))
        self.files.clear()
        self.assertEqual('UNKNOWN', self.inspect()['facts']['passive_telemetry']['status'])

    def test_root_metadata_still_does_not_verify_independent_identity(self):
        def root_metadata(path):
            regular = path.suffix in ('.json', '.plist')
            return {'exists': True, 'uid': 0, 'mode': 0o600, 'regular': regular, 'directory': not regular, 'symlink': False}
        result = self.inspect(metadata=root_metadata)
        self.assertTrue(result['facts']['independent_installation']['protected_metadata'])
        self.assertFalse(result['ready'])
        self.assertTrue(all(gate['status'] == 'BLOCKED' for gate in result['blocking_gates']))

    def test_unreadable_metadata_is_unknown_and_wrong_install_types_rejected(self):
        from unittest.mock import patch
        from nerve_guardian.macos import _metadata
        with patch.object(Path, 'lstat', side_effect=PermissionError('private')):
            result = inspect_local(home=self.home, platform_name='Darwin', metadata=_metadata)
        self.assertIsNone(result['facts']['learning_launch_agent']['exists'])
        self.assertTrue(result['facts']['learning_launch_agent']['metadata_unavailable'])
        def wrong_type(path):
            return {'exists': True, 'uid': 0, 'mode': 0o600, 'regular': True, 'directory': False}
        self.assertFalse(self.inspect(metadata=wrong_type)['facts']['independent_installation']['protected_metadata'])

    def test_symlink_and_unprotected_installation(self):
        def unsafe(path):
            return {'exists': True, 'uid': 501, 'mode': 0o777, 'regular': True, 'symlink': True}
        result = self.inspect(metadata=unsafe)
        self.assertFalse(result['facts']['independent_installation']['protected_metadata'])
        self.assertEqual('UNKNOWN', result['facts']['learning_launch_agent']['status'])

    def test_real_files_unchanged_and_no_missing_file_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            plist = home / 'Library/LaunchAgents/com.aliyildirim.nerve.learning.plist'
            plist.parent.mkdir(parents=True)
            plist.write_bytes(self.files[self.learning])
            before = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            result = inspect_local(home=home, root=home / 'absent-root', platform_name='Darwin', uid=501, now=100)
            after = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse((home / 'absent-root').exists())
            self.assertFalse(result['mutations_performed'])


if __name__ == '__main__':
    unittest.main()
