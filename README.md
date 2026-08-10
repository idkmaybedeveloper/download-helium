# [`download-helium`](https://github.com/idkmaybedeveloper/download-helium)

reborn of [download-chromium](https://github.com/beaufortfrancois/download-chromium) but
for [helium](https://github.com/imputnet/helium)!

same idea as the original: one page, one big button, always the latest build for
whatever you are browsing from. it runs on cloudflare workers (python) instead of
google app engine because gae really deprecated

### routes

| route | what it does |
| --- | --- |
| `/` | the page, platform guessed from the user agent, `?platform=` and `?type=` override it |
| `/dl/<platform>` | 302 to the latest build (unknown platform gets the original easter egg) |
| `/rev/<platform>` | json `{content, last-modified, platform, url, size}`, same keys the old frontend used |

platform names are `mac-arm64`, `mac-x64`, `win-arm64`, `win-x64`, `linux-arm64`,
`linux-x64`, plus the old download-chromium spellings (`Win_x64`, `Mac_Arm`, ...).
`?type=` picks the linux package: `appimage` (default), `deb` or `tarball`

### where the builds come from

- mac: `https://updates.helium.computer/mac/appcast-{arm64,x86_64}.xml` (sparkle feed)
- windows: `https://updates.helium.computer/win/appcast.xml` (sparkle feed)
- linux: github releases of [`imputnet/helium-linux`](https://github.com/imputnet/helium-linux)
upstream responses are cached at the edge for 5 minutes

### development

```bash
uv sync
uv run pywrangler dev
uv run pywrangler deploy
```