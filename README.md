# Thames Water Smart Meter for Home Assistant

<a href="https://www.buymeacoffee.com/silverscream85" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="60" width="217"></a>

Native port of `gavraq/thames-water-service`. The Selenium/Chrome scraper, FastAPI app,
SQLite, scheduler, dashboard and SMTP alerts are replaced by Home Assistant itself.
Login and data come from the [`thameswaterapi`](https://pypi.org/project/thameswaterapi/)
library (direct web API, no browser).

## Versions
Releases are tagged `v0.<yy>.<m>.<revision>`, with the revision counting from 0. For example,
`v0.26.10.0` is the first release of October 2026 and `v0.26.10.1` the second.

### Beta versions
Betas are GitHub pre-releases tagged with a PEP 440 suffix, for example `v0.26.10.1b1`. HACS
hides them by default. To try one: HACS -> **Thames Water Smart Meter** -> three dots ->
**Redownload** -> switch on **Show beta versions** -> pick the beta. Switching it off returns you
to the latest stable release on the next update.

For maintainers: set `version` in `manifest.json` to the same string as the tag (without the
`v`), push the tag, and `.github/workflows/release.yml` publishes the release. It refuses a tag
that does not match the manifest.

## Source repositories
This project builds on these:
* [`gavraq/thames-water-service`](https://github.com/gavraq/thames-water-service) - the original
  Selenium scraper, API, dashboard and alerts that this integration replaces.
* [`jelmer/homeassistant-thameswater`](https://github.com/jelmer/homeassistant-thameswater) - the
  existing Home Assistant integration (Apache-2.0). This one adds the spike sensor, 7-day
  average, month-to-date and cost sensors, and uses a single coordinator. It is based on earlier
  work by AyrtonB.
* [`jelmer/thameswaterapi`](https://github.com/jelmer/thameswaterapi) - the Thames Water API
  client behind the [`thameswaterapi`](https://pypi.org/project/thameswaterapi/) package that
  this integration uses for login and data.
* [`AyrtonB/Thames-Water`](https://github.com/AyrtonB/Thames-Water) - the earlier Thames Water
  API client that the two above build on.
* [`ale770/ha-thames-water`](https://github.com/ale770/ha-thames-water) - another Home Assistant
  integration for Thames Water, still maintained. The minimum hourly usage and last data sensors
  here, and importing the history in a separate window, come from ideas in it. No code was
  copied: that repository has no licence.

## Acknowledgements
* **gavraq** - the original Thames Water monitoring service, whose features this integration
  carries into Home Assistant.
* **Jelmer Vernooij** - the `thameswaterapi` library that does the login and data fetching, and
  the existing integration whose approach to hourly statistics and test setup this follows. The
  test fixtures in `tests/conftest.py` follow the pattern in his repository.
* **Ayrton Bourn** - the first Thames Water API client and Home Assistant work that the library
  and integration above grew from.
* **Ale (ale770)** - the `ha-thames-water` integration, which inspired the minimum hourly usage
  and last data sensors and the approach to importing history.

## Contributors
Thanks to everyone below ([emoji key](https://allcontributors.org/docs/en/emoji-key)). Add
someone by commenting `@all-contributors please add @user for <type>` on an issue or pull
request, once the [all-contributors app](https://github.com/apps/all-contributors) is installed
on this repository.

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Scream85"><img src="https://avatars.githubusercontent.com/u/29313645?v=4?s=100" width="100px;" alt="Scream85"/><br /><sub><b>Scream85</b></sub></a><br /><a href="https://github.com/Scream85/thames-water-hacs/commits?author=Scream85" title="Code">💻</a> <a href="https://github.com/Scream85/thames-water-hacs/commits?author=Scream85" title="Tests">⚠️</a> <a href="https://github.com/Scream85/thames-water-hacs/commits?author=Scream85" title="Documentation">📖</a> <a href="#infra-Scream85" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/gavraq"><img src="https://avatars.githubusercontent.com/u/59359644?v=4?s=100" width="100px;" alt="gavraq"/><br /><sub><b>gavraq</b></sub></a><br /><a href="https://github.com/Scream85/thames-water-hacs/commits?author=gavraq" title="Code">💻</a> <a href="#ideas-gavraq" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jelmer"><img src="https://avatars.githubusercontent.com/u/49032?v=4?s=100" width="100px;" alt="Jelmer Vernooij"/><br /><sub><b>Jelmer Vernooij</b></sub></a><br /><a href="#tool-jelmer" title="Tools">🔧</a> <a href="#ideas-jelmer" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/AyrtonB"><img src="https://avatars.githubusercontent.com/u/29051639?v=4?s=100" width="100px;" alt="Ayrton Bourn"/><br /><sub><b>Ayrton Bourn</b></sub></a><br /><a href="#tool-AyrtonB" title="Tools">🔧</a> <a href="#ideas-AyrtonB" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ale770"><img src="https://avatars.githubusercontent.com/u/4981303?v=4?s=100" width="100px;" alt="Ale"/><br /><sub><b>Ale</b></sub></a><br /><a href="#ideas-ale770" title="Ideas, Planning, & Feedback">🤔</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## Install
### HACS (recommended)
1. HACS -> three dots -> **Custom repositories** -> add
   `https://github.com/Scream85/thames-water-hacs`, category **Integration**.
2. Download **Thames Water Smart Meter**, restart Home Assistant.
3. Settings -> Devices & services -> Add integration -> Thames Water Smart Meter.

### Manual
1. Copy `custom_components/thames_water_meter/` into your HA `config/custom_components/`
   (or add this folder as a HACS custom repository).
2. Restart Home Assistant (requires 2025.8+).
3. Settings -> Devices & services -> Add integration -> **Thames Water Smart Meter**.
4. Enter your Thames Water email and password.

## Running alongside other Thames Water integrations
The domain is `thames_water_meter`, so this can be installed next to
[`jelmer/homeassistant-thameswater`](https://github.com/jelmer/homeassistant-thameswater)
(domain `thames_water`). Entities and statistics are separate, and each integration logs in on
its own.

### Upgrading from 0.1.x (domain `thames_water`)
The domain changed in 0.26.10.0, so Home Assistant sees a different integration:
1. Delete the old **Thames Water Smart Meter** entry, then remove the old
   `config/custom_components/thames_water/` folder.
2. Install this version and add the integration again.
3. Pick the new statistic (`thames_water_meter:<meter>_water_consumption`) in the Energy
   dashboard. The old statistic keeps its history under its old name and can be left in place.

## What you get
| Entity | Notes |
|---|---|
| Latest day usage | litres; attribute `date` |
| 7-day average usage | litres/day |
| Month-to-date usage | litres |
| Meter reading | litres; attribute `statistic_id` |
| Minimum hourly usage | litres in the quietest hour of the latest complete day, with `date` and `hour`. Stays well above zero overnight if there is a leak |
| Last data | diagnostic timestamp of the newest hour Thames Water has reported |
| Usage and meter reading in m³ | the five volume sensors above again in cubic metres (three decimals), for comparing with meters that report m³ |
| Latest day cost / Month-to-date cost | GBP, uses Thames Water's published tariff + daily standing charge |
| Usage spike | problem binary sensor, on when latest day > threshold (Configure -> default 800 L) |

## Reporting a problem
Settings -> Devices & services -> Thames Water Smart Meter -> three dots -> **Download
diagnostics**, and attach the file to the issue. It holds the latest figures, the options, the
published tariff and whether the history import has run. Your email and password are redacted, and
the account number and meter id are masked to their last two characters, so it is safe to share.
Still skim it before posting.

## Energy dashboard (water)
Thames Water data is ~3 days old, so the integration imports **hourly long-term statistics at
their real timestamps** instead of relying on sensor states. In Settings -> Dashboards -> Energy
-> Water consumption -> Add, pick the statistic named
**"Thames Water <meter> consumption"** (not the sensors). Re-imports are idempotent.

## Alerts
Replace the old email alerts with an automation on the `Usage spike` binary sensor turning on,
calling any `notify.*` action.

## Known limits / things to verify
* On first start the integration imports about 90 days of hourly history into the Energy
  dashboard statistic, which is as much as Thames Water serves (checked against a real account
  in October 2026: 90 days worked, 180 and 365 returned nothing). Older history, such as daily
  figures from an old SQLite database, can't be imported as hourly statistics.
* Usage and meter-read values are litres, confirmed against a real account: hourly and daily
  figures agree, and the meter read is taken at the end of each hour. The `Meter reading`
  attribute `read_taken_at` shows which the integration detected.
* First meter on the default contract account is used.
* Not tested against a live HA instance in the build environment: install on a test instance
  first and watch Settings -> System -> Logs for `thames_water_meter`.
