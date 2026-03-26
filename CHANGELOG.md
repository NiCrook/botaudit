# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Batch URL scanning: audit multiple URLs in one invocation via positional args or `--file`/`-f` flag
- URL file format with comments (`#`), blank line handling, and UTF-8 BOM support
- Deduplication of URLs across all input sources
- Per-URL error isolation: failed URLs don't abort the batch
- Batch output for all formats: text (with summary table), JSON (with batch wrapper), CSV
- Progress reporting to stderr in batch mode (`[N/T] Auditing URL...`)
- `-q`/`--quiet` flag to suppress progress messages
- Batch-aware exit codes: `--fail-under` evaluates all successful URLs
- Spec document: `docs/SPEC-batch.md`

## [1.2.0] - 2026-03-21

### Added
- `--fail-under` flag for CI grade enforcement (exit code 1 if grade is below threshold)
- GitHub Actions workflow to run tests on Python 3.11, 3.12, 3.13

## [1.1.0] - 2026-03-20

### Added
- JSON output format (`--format json`)
- CSV output format (`--format csv`)

## [1.0.0] - 2026-03-20

### Added
- Initial release of botaudit CLI tool
- Six analysis categories: Content Availability, Semantic HTML, Link Discoverability, Structured Data, Metadata & Discoverability, LLM Discoverability
- Weighted scoring with A–F letter grades
- Recommendation engine with HIGH/MEDIUM/LOW severity
- LLM Discoverability: robots.txt, llms.txt, llms-full.txt analysis
- `--skip-llm-discovery` flag to skip supplementary fetches
- `--no-recommendations` flag to suppress recommendations
- `--timeout` flag for HTTP request timeout
- PyPI packaging with `botaudit` entry point

[Unreleased]: https://github.com/NiCrook/botaudit/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/NiCrook/botaudit/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/NiCrook/botaudit/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/NiCrook/botaudit/releases/tag/v1.0.0
