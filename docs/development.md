# Development and package verification

The supported Python range is 3.9 through 3.14. No runtime dependencies are added by the CI tools. Use an isolated environment; do not replace the Python or library bundled inside an installed Ink/Stitch executable.

## Local checks

Create and activate a virtual environment using your preferred shell, then run:

```text
python -m pip install .
python -m unittest discover test -v
python -m unittest discover tests_infrastructure -v
```

The library test run currently has two intentional skips (HUS and a generic G-code case). Skips remain visible in the logs; they are not evidence those behaviors work.

## Verify the actual installable artifacts

From the repository root, in an isolated development environment:

```text
python -m pip install -r requirements-ci.txt
python -m build --outdir dist
python -m twine check --strict dist/pystitch-1.0.1-py3-none-any.whl dist/pystitch-1.0.1.tar.gz
python scripts/verify_distribution.py --wheel dist/pystitch-1.0.1-py3-none-any.whl --sdist dist/pystitch-1.0.1.tar.gz --report dist/verification.json
```

Use the filenames produced by the build if the package version changes. These commands use explicit filenames and work in PowerShell as well as Unix shells. Build requirements may be downloaded from the package index; library tests do not require a network or machine.

The verifier:

1. Checks wheel and source-archive inventories, matching name/version, license and build inputs. All source-package files must occur in both artifacts.
2. Creates two new environments, installs the wheel in one and the source archive in the other. The source installation exercises an isolated PEP 517 build.
3. Copies only the test directory and its README fixture into independent suite directories, clears source-path overrides, disables user-site imports and verifies package/distribution origins inside the relevant environment.
4. Runs the full library suite from each installation and records hashes, installed identities, import origins and test summaries in JSON.

An optional `--work-dir PATH` selects a **new** directory for environments/logs. Existing directories are rejected rather than overwritten. By default a new system temporary directory is created and its path is recorded in the report; it is retained for inspection. Remove that verifier-created directory when its logs are no longer needed. Keep reports and logs for failed checks as well as successful ones.

## Hosted coverage and merge protection

- The unit matrix runs Python 3.9–3.14 across Linux, Windows and macOS (18 jobs). Ubuntu 24.04 is used for 3.9; the remaining Linux jobs follow ubuntu-latest.
- Distribution jobs build, metadata-check and install-test wheel/sdist on Python 3.14 across all three operating systems.
- `CI required` runs even when a dependency fails or is skipped and only succeeds if **both complete job groups** succeeded. Its stable name is the branch-protection requirement after migration.
- Every pull request, every main push and manual dispatch trigger coverage, including metadata-only changes. Feature pushes do not duplicate PR runs.
- First-party action revisions are pinned to verified releases with Node 24 runtimes. When updating them, verify upstream release/runtime support and run the full workflow.
- Runs upload wheel/sdist artifacts, JSON reports and verification logs under an OS-specific artifact name. Review the job summary and download the matching artifacts for reproduction.

When changing the matrix, keep every mandatory job in the aggregate dependencies. Do not make the gate optional, accept skipped groups as success, or remove protection to merge a failing build. During the initial migration, retain the original required checks until the new complete gate has passed.

This verifies software and packaging. Independent reference exports and physical SE700 sew-outs are tracked separately in issue #7.
