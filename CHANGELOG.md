# Changelog

Versions follow `v0.<yy>.<m>.<revision>`, with the revision counting from 0. A letter suffix
(`b1`, `rc1`) marks a beta, published as a GitHub pre-release.

## Unreleased

### Added
- Minimum hourly usage sensor (the quietest hour of the latest complete day, a leak indicator)
  and a Last data diagnostic timestamp sensor. Idea from `ale770/ha-thames-water`.
- `scripts/live_check.py`, a read-only check of the real Thames Water API for maintainers.
- Buy Me a Coffee: the official button in the README and the GitHub Sponsor button
  (`.github/FUNDING.yml`).
- Acknowledgements and an all-contributors table in the README, crediting gavraq, Jelmer
  Vernooij and Ayrton Bourn, links to their repositories (including `thameswaterapi`), and a
  credit comment for the test fixtures.

## 0.26.10.0 - 2026-10-07

### Changed
- **Breaking:** the domain is now `thames_water_meter` (was `thames_water`), so the integration
  can run beside `jelmer/homeassistant-thameswater`. Delete the old entry, remove
  `custom_components/thames_water/`, install this version and add the integration again. The
  Energy dashboard statistic is now `thames_water_meter:<meter>_water_consumption`; the old one
  keeps its history under its old name.

### Fixed
- Month-to-date usage and cost read 0 for the first days of each month, because the data lags
  about three days. They now follow the month of the latest data point, and expose it in the
  `month` and `days` attributes.
- Re-authenticating accepted credentials for any Thames Water account. It now aborts with
  `wrong_account` unless they belong to the configured one.

- The imported statistic now sets `mean_type`, which newer Home Assistant versions require and
  would otherwise warn about, then reject.

### Added
- Pre-commit hooks (ruff lint and format, codespell, actionlint, gitleaks and the standard file
  checks) and a mypy job, both run in CI.
- Home Assistant tests for the config, reauth and options flows, entity values, statistics
  import and setup failures, run in CI.
- Tag-driven release workflow. Beta tags (for example `v0.26.10.1b1`) become pre-releases that
  HACS offers behind "Show beta versions".
- Dependabot for workflow actions and test dependencies.

## 0.1.1

First native Home Assistant version, replacing the Selenium scraper, API and dashboard of
`gavraq/thames-water-service`.
