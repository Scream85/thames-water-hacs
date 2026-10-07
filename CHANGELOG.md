# Changelog

Versions follow `v0.<yy>.<m>.<revision>`, with the revision counting from 0. A letter suffix
(`b1`, `rc1`) marks a beta, published as a GitHub pre-release.

## Unreleased

### Added
- A cost statistic, `thames_water_meter:<meter>_water_cost` (GBP, one value per hour), so the
  Energy dashboard can show spend. Home Assistant cannot price an imported consumption itself, so
  choose "Use an entity tracking the total costs" and pick "Thames Water &lt;meter&gt; cost". Each hour
  is the water used at the combined rate plus its share of the standing charge, spread over the
  hours the local day really has, so a day totals exactly the daily charge even when the clocks
  change. The running total continues from the stored one, nothing is costed before the current
  rates took effect, and nothing is imported without a tariff. It matched a real bill to 1p.

### Fixed
- The README said to use the rate sensor as the Energy dashboard price, which Home Assistant
  does not allow for an imported statistic.

## 0.26.10.1b3 - 2026-10-07 (beta)

Offered by HACS only with "Show beta versions" switched on for this repository. The earlier
betas `0.26.10.1b1` and `0.26.10.1b2` were removed, and their changes are listed below.

### Fixed
- The device page still said "by Thames Water" after 0.26.10.1b2, because leaving the
  manufacturer out keeps the value already stored. It is now cleared explicitly, so existing
  devices lose it on the next start.

## 0.26.10.1b2 - 2026-10-07 (beta)

Offered by HACS only with "Show beta versions" switched on for this repository. Restart Home
Assistant fully after updating, so it notices the new `brand/` icon folder.

### Added
- Three tariff rate sensors in GBP per m³, as a bill states them: Clean water rate,
  Wastewater rate and Combined water rate, each with the date the rates took effect. The
  combined rate is the one the cost sensors price a litre with. Checked against a real bill.

### Changed
- The device no longer says it is made by Thames Water. The manufacturer is left empty and the
  model reads "Thames Water smart meter", because the company does not make this integration
  and the account data does not name the meter's maker. Existing devices pick this up on the
  next start.

## 0.26.10.1b1 - 2026-10-07 (beta)

Offered by HACS only with "Show beta versions" switched on for this repository.

### Changed
- Litre sensors show whole litres (`345 L`, not `345.0 L`), as Thames Water reports whole
  litres.
- Hourly history is no longer limited to 7 days. Each refresh fetches the last 30 days, and on
  the first refresh after start-up the older history up to 90 days is imported as well, so a new
  install fills the Energy dashboard with about three months. The older history is requested
  separately because the wider windows ended a day earlier than the 30-day one. If that request
  fails the recent data is still imported and the history is tried again next time.
- The last known tariff is saved and restored after a restart if the tariff page cannot be read
  at start-up, so the cost sensors have a value instead of `unknown`. It is dropped once its
  charging year (1 April to 31 March) has ended, and deleted when the integration is removed.

### Added
- An integration icon in `brand/` (`icon.png` and `icon@2x.png`), the same Thames Water image
  the Home Assistant brands repository holds for the old `thames_water` domain, used for
  identification only. The domain rename to `thames_water_meter` had lost it. Home Assistant
  2026.3 and later show it from the integration folder. A README notice says the project is
  unofficial.
- Download diagnostics for bug reports, with credentials redacted and the account number and
  meter id masked.
- Cubic metre (m³) twins of the five volume sensors (latest day, 7-day average, month-to-date,
  meter reading and minimum hourly usage), with three decimals, for lining Thames Water up with
  meters that report m³. They are extra entities, so both units are always available.
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
