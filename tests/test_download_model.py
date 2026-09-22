import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from fcitx5_voice.model_manifest import (
    DownloadFile, ModelManifest, OFFLINE_MODEL, PUNCTUATION_MODEL, STREAMING_MODEL,
)


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

    def archive_manifest(self, root, content):
        archive = root / 'upstream/test/resolve/abc123/bundle.tar.bz2'
        archive.parent.mkdir(parents=True)
        with tarfile.open(archive, 'w:bz2') as bundle:
            info = tarfile.TarInfo('bundle/model.bin')
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))
        return (
            ModelManifest(
                directory='test-model', repository='upstream/test', revision='abc123',
                files=(DownloadFile(
                    'model.bin', hashlib.sha256(content).hexdigest(),
                    source='bundle.tar.bz2',
                    source_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    archive_member='bundle/model.bin',
                ),),
            ),
            (root).as_uri(),
        )

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

    def test_archive_download_verifies_and_publishes_only_selected_member(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'destination'
            manifest, base = self.archive_manifest(root / 'remote', b'quantized model')

            DOWNLOAD_MODEL.download(destination, manifest, base)

            self.assertEqual((destination / 'model.bin').read_bytes(), b'quantized model')
            self.assertEqual(sorted(path.name for path in destination.iterdir()), ['model.bin'])

    def test_default_streaming_selection_includes_punctuation(self):
        args = DOWNLOAD_MODEL.parse_args([])
        self.assertEqual(
            DOWNLOAD_MODEL.selected_manifests(args),
            (STREAMING_MODEL, PUNCTUATION_MODEL),
        )

    def test_offline_and_explicit_download_modes_preserve_expected_scope(self):
        cases = (
            (['--backend', 'offline'], (OFFLINE_MODEL,)),
            (['--no-punctuation'], (STREAMING_MODEL,)),
            (['--punctuation-only'], (PUNCTUATION_MODEL,)),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(
                    DOWNLOAD_MODEL.selected_manifests(DOWNLOAD_MODEL.parse_args(argv)),
                    expected,
                )

    def test_refinement_download_includes_sensevoice_even_without_punctuation(self):
        for argv, expected in [
            (['--with-refinement'], (STREAMING_MODEL, OFFLINE_MODEL, PUNCTUATION_MODEL)),
            (['--with-refinement', '--no-punctuation'], (STREAMING_MODEL, OFFLINE_MODEL)),
        ]:
            with self.subTest(argv=argv):
                self.assertEqual(DOWNLOAD_MODEL.selected_manifests(DOWNLOAD_MODEL.parse_args(argv)), expected)
