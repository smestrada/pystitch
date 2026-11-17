# Distribution CI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The user authorized continuous goal execution; routine choices are recorded in `docs/goal-progress.md`.

**Goal:** Complete issue #5 with Python 3.14 coverage and independently installed wheel/sdist checks, while preserving effective merge protection.

**Architecture:** Keep the 3-OS interpreter matrix for Python 3.9–3.14. Add distribution jobs on Python 3.14 for all three OSes. A standard-library helper validates archives, installs each artifact into a fresh environment, proves import origin outside the checkout and runs copied library tests. A stable required gate depends on every test/distribution job.

**Tech Stack:** Python unittest/venv/zipfile/tarfile, PEP 517 build, twine check, GitHub Actions. Build tools are development-only dependencies.

**Spec:** https://github.com/smestrada/pystitch/issues/5 and `docs/goal-progress.md`.

## Global Constraints

- Keep Python >=3.9; preserve the Ubuntu 24.04/Python 3.9 exception.
- No runtime dependency additions or global installs.
- Existing required checks stay enforced until the replacement is proven.
- Use isolated package installs; tests must not accidentally import `src`.
- Build metadata changes and all PRs trigger relevant checks.

## Review Focus

- Checkout imports masquerading as installed artifacts: prove origin and distribution metadata from a child interpreter in an independent directory.
- Source distribution missing build inputs: install the actual sdist in a distinct environment.
- Missing package/license contents: fail archive validation before install.
- Failed, cancelled or skipped matrix jobs: aggregate gate must fail.
- Test helpers that rely on repo files: copy tests and README explicitly, never the source package or an editable installation.

### Task 1: Artifact verification helper

**Files:** create `scripts/verify_distribution.py`, `tests_infrastructure/test_distribution_verifier.py`.

**Interfaces:** `validate_archives(wheel: Path, sdist: Path) -> dict`; `assert_installed_origin(origin: Path, environment: Path) -> None`; CLI accepts `--wheel`, `--sdist`, `--report` and optional `--work-dir`. Tests/callers do not depend on private workflow names.

- [x] Write tests for valid/missing package and license inventories, incorrect metadata, and rejection of source-tree import origins.
- [x] Run `python -m unittest discover tests_infrastructure -v`; expect failure because verification is absent.
- [x] Implement archive checks and an isolated wheel/sdist install-and-test harness. Preserve useful failure logs and serialize artifact hashes, identities and test results.
- [x] Run helper tests; expect all pass.
- [x] Build real artifacts using an isolated development environment and run the helper; expect both installed suites pass outside source.
- [x] Commit helper/tests with recorded red/green evidence.

### Task 2: Hosted matrix, artifacts and aggregate gate

**Files:** modify `.github/workflows/unittests.yml`, `pyproject.toml`; add `docs/development.md`.

**Interfaces:** jobs `unittests`, `distributions`, `ci-required`; required status context `CI required`. Distribution jobs call Task 1's CLI; the aggregate requires both job-group results to equal `success`.

- [x] Verify Python manifest availability and action runtimes/tags from official repositories.
- [x] Extend interpreter matrix to 3.14; retain 3.9 exception. Build/check wheel+sdist and run isolated artifact checks on each OS. Upload artifacts, reports and logs.
- [x] Run infrastructure and existing library tests locally; parse workflow structure and review failure paths.
- [x] Push focused branch and open PR with issue acceptance/validation details. Expect all 18 unit jobs, 3 distribution jobs, aggregate and CodeQL to pass.
- [x] Preserve required old contexts while adding the proven aggregate; remove old names only once equivalent complete enforcement is verified.
- [x] Commit workflow, metadata and usage documentation.

### Task 3: Review and integrate

**Files:** update `docs/goal-progress.md` and plan checkboxes with evidence.

- [x] Obtain one fresh branch review using the execution skill's review instructions; resolve important findings with focused regression tests.
- [x] Verify package artifacts and hosted results for the exact PR revision.
- [x] Merge through normal protection, sync local main and verify main's checks.
- [x] Close #5/update roadmap only after the acceptance criteria are demonstrated. Record versions, commands, links and any outstanding limitations.

## Authoritative completion evidence

Fresh local suite and installed artifact logs, archive inventories and import origins, hosted 18+3 jobs and aggregate, CodeQL, protection read-back, merged PR and clean synced main. Do not substitute a YAML parser for an executed hosted workflow.
