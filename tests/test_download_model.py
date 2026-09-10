import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from fcitx5_voice.model_manifest import DownloadFile, ModelManifest


SCRIPT = Path(__file__).parents[1] / 'scripts/download-model.py'
SPEC = importlib.util.spec_from_file_location('download_model', SCRIPT)
DOWNLOAD_MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOWNLOAD_MODEL)


class DownloadModelTests(unittest.TestCase):
    def manifest(self, content, checksum=None):
        return ModelManifest(
            directory='test-model', repository='upstream/test', revision='abc123',
            files=(DownloadFile('weights.bin', checksum or hashlib.sha256(content).hexdigest()),))

    def source(self, root, content):
        path = root / 'upstream/test/resolve/abc123/weights.bin'
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        return root.as_uri()

    def test_download_verifies_and_atomically_publishes_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'destination'
            base = self.source(root / 'remote', b'verified weights')

            DOWNLOAD_MODEL.download(destination, self.manifest(b'verified weights'), base)

            self.assertEqual((destination / 'weights.bin').read_bytes(), b'verified weights')
            self.assertEqual(list(destination.glob('*.part')), [])

    def test_checksum_failure_preserves_existing_file_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'destination'
            destination.mkdir()
            target = destination / 'weights.bin'
            target.write_bytes(b'previous')
            base = self.source(root / 'remote', b'corrupt')
            manifest = self.manifest(b'ignored', checksum='0' * 64)

            with self.assertRaisesRegex(ValueError, '校验失败'):
                DOWNLOAD_MODEL.download(destination, manifest, base)

            self.assertEqual(target.read_bytes(), b'previous')
            self.assertEqual(list(destination.glob('*.part')), [])
