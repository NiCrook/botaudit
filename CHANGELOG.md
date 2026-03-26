# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-03-25

### Fixed
- HTTPS connections failing on systems where certifi's CA bundle is incomplete (e.g., Python 3.14 on Windows); `truststore` now provides OS-native certificate verification with automatic fallback to certifi

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
- Sitemap crawl mode: `--crawl <URL>` auto-discovers and audits pages from XML sitemaps
- Sitemap discovery via `robots.txt` `Sitemap:` directives with `/sitemap.xml` fallback
- Support for XML sitemaps (`<urlset>`), sitemap indexes (`<sitemapindex>`), and plain-text sitemaps
- Recursive sitemap index parsing (depth-limited to 2, max 50 child sitemaps)
- Origin-based scope filtering (default) with `--crawl-allow-external` override
- `--crawl-limit`/`-l` flag to cap the number of crawl-discovered URLs
- Crawl metadata in JSON output (`crawl` object with discovery stats)
- Spec document: `docs/SPEC-crawl.md`
- HTML report output: `--format html` generates a self-contained, shareable HTML document
- Grade color coding (A green, B blue, C yellow, D orange, F red) in HTML reports
- Light and dark mode support via `prefers-color-scheme` media query
- Responsive layout (375px–1920px) with system font stack
- Batch HTML reports with sortable summary table and collapsible per-URL detail sections
- Expand All / Collapse All controls in batch HTML reports
- Crawl metadata display in batch HTML reports when `--crawl` is used
- XSS prevention via HTML escaping of all user-supplied content
- Spec document: `docs/SPEC-html-report.md`
- Custom weight profiles: `--weight-profile` flag with built-in presets (`ecommerce`, `docs`, `ai-ready`)
- Per-category weight overrides: `--weight`/`-w` flag with decimal or percentage syntax
- `--list-profiles` flag to display available weight profiles
- Case-insensitive category aliases for `--weight` (e.g., `structured`, `llm`, `meta`)
- Spec document: `docs/SPEC-custom-weights.md`
- AI metadata detection in LLM Discoverability: `ai.txt`, `/.well-known/ai-plugin.json`, `/.well-known/agent.json`
- Structural validation of `ai-plugin.json` (required fields) and `agent.json` (non-empty object)
- Revised LLM Discoverability scoring to accommodate new AI metadata signals (100-point budget preserved)
- Spec document: `docs/SPEC-ai-metadata.md`
- Deeper Structured Data validation: JSON-LD parsing, `@context`/`@type` verification, schema.org property completeness
- Open Graph required (4) and recommended (2) property validation
- Meta description length classification (too short < 50, optimal 50–160, too long > 160)
- Twitter Card meta tag detection
- HTML Microdata (`itemscope`) detection
- Multi-format bonus scoring (15 pts for 2+ structured data formats)
- Revised Structured Data scoring from binary presence to granular quality signals
- Spec document: `docs/SPEC-structured-data-validation.md`
- Per-page type heuristics: auto-detect page type (article, product, documentation, listing, homepage) from JSON-LD, og:type, URL patterns, and HTML structure signals
- Vote-based classification with confidence levels (high, medium, low)
- Type-aware recommendations: targeted advice based on detected page type (e.g., "add Article schema" for blog posts, "add Product schema" for product pages)
- `--page-type` flag to force a specific page type, bypassing heuristic detection
- `--no-page-type` flag to disable page-type detection entirely
- Page type displayed in all output formats: text header, JSON `page_type` object with signals, CSV column, HTML badge
- Spec document: `docs/SPEC-page-type-heuristics.md`
- API / Library mode: public Python API via `from botaudit import audit`
- `audit()` function for single-URL programmatic auditing (returns `Report`, raises `FetchError`)
- `audit_batch()` function for multi-URL programmatic auditing (returns `BatchResult`)
- `Report.to_dict()` and `BatchResult.to_dict()` for JSON-serializable output
- Public `__init__.py` exports with `__all__`: data classes, enums, exceptions, constants
- `__version__` attribute (`"0.1.0"`) accessible via `from botaudit import __version__`
- Spec document: `docs/SPEC-library-mode.md`
- Configuration file support: `.botaudit.yaml` or `[tool.botaudit]` in `pyproject.toml` for persistent project-level settings
- `--config PATH` flag to load an explicit config file, `--config none` to disable config discovery
- Config file supports all existing CLI options: `format`, `timeout`, `fail_under`, `quiet`, `no_recommendations`, `skip_llm_discovery`, `weight_profile`, `weights`, `page_type`, `no_page_type`
- CLI flags always take precedence over config file values; weight overrides are additive
- `load_config()` function in public API for programmatic config file loading
- Strict validation with descriptive errors for unknown keys, invalid values, and mutual exclusions (exit code 2)
- `pyyaml` added as a dependency for YAML config support
- Spec document: `docs/SPEC-config.md`

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

[Unreleased]: https://github.com/NiCrook/botaudit/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/NiCrook/botaudit/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/NiCrook/botaudit/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/NiCrook/botaudit/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/NiCrook/botaudit/releases/tag/v1.0.0
