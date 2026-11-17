import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

try:
    from scripts import verify_distribution as verifier
except ImportError:
    verifier = None


class TestVerifierAvailability(unittest.TestCase):
    def test_distribution_verifier_is_available(self):
        self.assertIsNotNone(verifier, 'The distribution verification helper is not implemented')


@unittest.skipIf(verifier is None, 'Verifier not implemented yet')
class TestDistributionVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wheel = self.root / 'pystitch-1.0.1-py3-none-any.whl'
        self.sdist = self.root / 'pystitch-1.0.1.tar.gz'

    def archives(self, omit_wheel=(), omit_sdist=(), source_version='1.0.1'):
        metadata = 'Metadata-Version: 2.4\nName: pystitch\nVersion: 1.0.1\nLicense-Expression: MIT\n'
        files = {
            'pystitch/__init__.py': '',
            'pystitch-1.0.1.dist-info/METADATA': metadata,
            'pystitch-1.0.1.dist-info/WHEEL': 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
            'pystitch-1.0.1.dist-info/licenses/LICENSE': 'MIT test license',
        }
        with zipfile.ZipFile(self.wheel, 'w') as archive:
            for name, content in files.items():
                if name not in omit_wheel:
                    archive.writestr(name, content)
        files = {
            'pystitch-1.0.1/PKG-INFO': metadata.replace('Version: 1.0.1\n', 'Version: '+source_version+'\n'),
            'pystitch-1.0.1/pyproject.toml': '[build-system]\nrequires = ["setuptools"]\n',
            'pystitch-1.0.1/src/pystitch/__init__.py': '',
            'pystitch-1.0.1/LICENSE': 'MIT test license',
            'pystitch-1.0.1/README.md': '# Test package',
        }
        with tarfile.open(self.sdist, 'w:gz') as archive:
            for name, content in files.items():
                if name not in omit_sdist:
                    data = content.encode()
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

    def test_valid_artifacts_report_identity_and_hashes(self):
        self.archives()
        result = verifier.validate_archives(self.wheel, self.sdist)
        self.assertEqual(result['name'], 'pystitch')
        self.assertEqual(result['version'], '1.0.1')
        self.assertEqual(len(result['wheel']['sha256']), 64)
        self.assertEqual(len(result['sdist']['sha256']), 64)

    def test_wheel_must_include_package(self):
        self.archives(omit_wheel=('pystitch/__init__.py',))
        with self.assertRaisesRegex(ValueError, 'package'):
            verifier.validate_archives(self.wheel, self.sdist)

    def test_wheel_must_include_license(self):
        self.archives(omit_wheel=('pystitch-1.0.1.dist-info/licenses/LICENSE',))
        with self.assertRaisesRegex(ValueError, 'license'):
            verifier.validate_archives(self.wheel, self.sdist)

    def test_sdist_must_include_build_inputs(self):
        self.archives(omit_sdist=('pystitch-1.0.1/pyproject.toml',))
        with self.assertRaisesRegex(ValueError, 'pyproject'):
            verifier.validate_archives(self.wheel, self.sdist)

    def test_artifact_versions_must_agree(self):
        self.archives(source_version='9.9.9')
        with self.assertRaisesRegex(ValueError, 'identit'):
            verifier.validate_archives(self.wheel, self.sdist)

    def test_corrupt_archive_is_rejected(self):
        self.archives()
        self.wheel.write_bytes(b'not a wheel')
        with self.assertRaisesRegex(ValueError, 'wheel'):
            verifier.validate_archives(self.wheel, self.sdist)

    def test_installed_origin_rejects_checkout_or_sibling(self):
        env = self.root / 'environment'
        for origin in (self.root/'src/pystitch/__init__.py', self.root/'environment-other/pystitch/__init__.py'):
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, 'environment'):
                verifier.assert_installed_origin(origin, env)

    def test_installed_origin_accepts_environment_package(self):
        env = self.root / 'environment'
        verifier.assert_installed_origin(env/'lib/site-packages/pystitch/__init__.py', env)


if __name__ == '__main__':
    unittest.main()
