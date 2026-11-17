"""Verify built packages, then run the library suite from isolated installs.

Development/CI tool only: uses the standard library and does not modify the
calling interpreter. The sdist installation intentionally uses PEP 517 build
isolation and may download declared build requirements.
"""
import argparse
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def _identity(text):
    metadata = Parser().parsestr(text)
    name, version = metadata.get('Name'), metadata.get('Version')
    if name != 'pystitch' or not version:
        raise ValueError('Artifact identity must contain Name: pystitch and a Version')
    return {'name': name, 'version': version}


def _safe_names(names):
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('Unsafe archive member: '+name)


def _inventory(path, names):
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'members': sorted(names)}


def validate_archives(wheel: Path, sdist: Path) -> dict:
    """Check package/build/license inventories and matching distribution IDs."""
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            _safe_names(names)
            if 'pystitch/__init__.py' not in names:
                raise ValueError('wheel is missing the pystitch package')
            metadata = [name for name in names if name.endswith('.dist-info/METADATA')]
            if len(metadata) != 1:
                raise ValueError('wheel must contain exactly one package metadata file')
            prefix = metadata[0].rsplit('/', 1)[0]
            if not any(name in names for name in (prefix+'/LICENSE', prefix+'/licenses/LICENSE')):
                raise ValueError('wheel is missing the license')
            identity = _identity(archive.read(metadata[0]).decode('utf-8'))
            result = dict(identity, wheel=_inventory(wheel, names))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError('Cannot read wheel: '+str(exc)) from exc

    try:
        with tarfile.open(sdist, 'r:gz') as archive:
            names = [member.name for member in archive.getmembers() if member.isfile()]
            _safe_names(names)
            roots = {name.split('/')[0] for name in names}
            if len(roots) != 1:
                raise ValueError('sdist must contain one package root')
            root = roots.pop()
            for required in ('PKG-INFO', 'pyproject.toml', 'README.md', 'LICENSE', 'src/pystitch/__init__.py'):
                if root+'/'+required not in names:
                    raise ValueError('sdist is missing '+required)
            stream = archive.extractfile(root+'/PKG-INFO')
            with stream:
                source_identity = _identity(stream.read().decode('utf-8'))
            if source_identity != identity:
                raise ValueError('Wheel and source distribution identities do not match')
            result['sdist'] = _inventory(sdist, names)
            result['sdist']['root'] = root
    except (OSError, tarfile.TarError) as exc:
        raise ValueError('Cannot read sdist: '+str(exc)) from exc
    return result


def assert_installed_origin(origin: Path, environment: Path) -> None:
    try:
        origin.resolve().relative_to(environment.resolve())
    except ValueError as exc:
        raise ValueError('Package import did not resolve inside its isolated environment: '+str(origin)) from exc


def _run(command, cwd, environment, log):
    with log.open('wb') as output:
        result = subprocess.run(command, cwd=cwd, env=environment,
                                stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        tail = log.read_text(encoding='utf-8', errors='replace')[-3000:]
        raise RuntimeError('Command failed (see '+str(log)+'):\n'+tail)


def verify_install(artifact, kind, root, workspace, expected_version):
    area = workspace/kind
    area.mkdir()
    environment = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'UPDATE'):
        environment.pop(name, None)
    environment['PYTHONNOUSERSITE'] = '1'
    envdir = area/'environment'
    _run([sys.executable, '-I', '-m', 'venv', str(envdir)], area, environment, area/'venv.log')
    python = envdir/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    _run([str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check',
          '--no-cache-dir', '--no-deps', str(artifact)], area, environment, area/'install.log')

    suite = area/'suite'
    suite.mkdir()
    shutil.copytree(root/'test', suite/'test', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(root/'README.md', suite/'README.md')
    code = ("import importlib.metadata as m,json,sys,pystitch; "
            "d=m.distribution('pystitch'); "
            "print(json.dumps({'origin':pystitch.__file__,'distribution_root':str(d.locate_file('')),"
            "'version':d.version,'prefix':sys.prefix}))")
    proof = area/'import.json'
    _run([str(python), '-I', '-c', code], suite, environment, proof)
    imported = json.loads(proof.read_text(encoding='utf-8'))
    assert_installed_origin(Path(imported['origin']), envdir)
    assert_installed_origin(Path(imported['distribution_root']), envdir)
    if imported['version'] != expected_version:
        raise ValueError('Installed version does not match artifact metadata')
    log = area/'tests.log'
    _run([str(python), '-I', '-m', 'unittest', 'discover', '-s', 'test', '-t', '.', '-v'],
         suite, environment, log)
    content = log.read_text(encoding='utf-8', errors='replace')
    count = re.search(r'^Ran (\d+) tests? in ', content, re.MULTILINE)
    if count is None or int(count.group(1)) == 0:
        raise RuntimeError('Installed-artifact test discovery ran no tests')
    summary = [line for line in content.splitlines() if line.startswith(('Ran ', 'OK'))]
    print(kind+': '+'; '.join(summary), flush=True)
    return dict(imported, tests_run=int(count.group(1)), summary=summary, log=str(log))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', required=True, type=Path)
    parser.add_argument('--sdist', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--work-dir', type=Path)
    args = parser.parse_args(argv)
    report = {'schema_version': 1, 'status': 'failed', 'python': sys.version}
    try:
        root = Path(__file__).resolve().parents[1]
        wheel, sdist = args.wheel.resolve(), args.sdist.resolve()
        report.update(validate_archives(wheel, sdist))
        source_files = [str(p.relative_to(root/'src')).replace('\\', '/')
                        for p in (root/'src/pystitch').rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
        for name in source_files:
            if name not in report['wheel']['members']:
                raise ValueError('wheel is missing source package file '+name)
            if report['sdist']['root']+'/src/'+name not in report['sdist']['members']:
                raise ValueError('sdist is missing source package file '+name)
        if args.work_dir is None:
            workspace = Path(tempfile.mkdtemp(prefix='pystitch-distribution-')).resolve()
        else:
            workspace = args.work_dir.resolve()
            workspace.mkdir(parents=True, exist_ok=False)
        report['workspace'] = str(workspace)
        report['installs'] = {}
        for kind, artifact in (('wheel', wheel), ('sdist', sdist)):
            report['installs'][kind] = verify_install(artifact, kind, root, workspace, report['version'])
        report['status'] = 'passed'
    except (ValueError, RuntimeError, OSError) as exc:
        report['error'] = str(exc)
        print(str(exc), file=sys.stderr)
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
