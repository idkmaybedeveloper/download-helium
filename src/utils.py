import re

from workers import fetch

APPCAST_BASE = "https://updates.helium.computer"
LINUX_RELEASE_API = "https://api.github.com/repos/imputnet/helium-linux/releases/latest"
UPSTREAM_TTL_SECONDS = 300
USER_AGENT = "download-helium (+https://github.com/idkmaybedeveloper/download-helium)"


class Platform:
    def __init__(self, name, pretty_name, os_name, arch):
        self.name = name
        self.pretty_name = pretty_name
        self.os_name = os_name
        self.arch = arch
        platforms.append(self)

    def __repr__(self):
        return self.name


platforms = []

MAC_ARM = Platform("mac-arm64", "macOS ARM", "mac", "arm64")
MAC_X64 = Platform("mac-x64", "macOS Intel", "mac", "x86_64")
WIN_ARM64 = Platform("win-arm64", "Windows ARM64", "win", "arm64")
WIN_X64 = Platform("win-x64", "Windows x64", "win", "x86_64")
LINUX_ARM64 = Platform("linux-arm64", "Linux ARM64", "linux", "arm64")
LINUX_X64 = Platform("linux-x64", "Linux x64", "linux", "x86_64")

#NOTE: old download-chromium urls (Win_x64, Mac_Arm, ...) are still bookmarked
#around the web, and helium itself is not consistent either: the mac appcast
#says x86_64 while the windows one says x64. so accept anything reasonable
ALIASES = {
    "mac": MAC_ARM,
    "macos": MAC_ARM,
    "mac_arm": MAC_ARM,
    "mac-arm": MAC_ARM,
    "darwin-arm64": MAC_ARM,
    "mac_x64": MAC_X64,
    "mac-x86_64": MAC_X64,
    "darwin-x64": MAC_X64,
    "win": WIN_X64,
    "win_x64": WIN_X64,
    "windows-x64": WIN_X64,
    "win_arm64": WIN_ARM64,
    "windows-arm64": WIN_ARM64,
    "linux": LINUX_X64,
    "linux_x64": LINUX_X64,
    "linux-x86_64": LINUX_X64,
    "linux_arm64": LINUX_ARM64,
    "linux-aarch64": LINUX_ARM64,
}

LINUX_FORMATS = [("appimage", "AppImage"), ("deb", ".deb"), ("tarball", "tar.xz")]


def get_platform(name):
    wanted = (name or "").lower()
    for platform in platforms:
        if platform.name == wanted:
            return platform
    return ALIASES.get(wanted)


def get_linux_format(name):
    wanted = (name or "").lower()
    if wanted == "deb":
        return "deb"
    if wanted in ("tarball", "tar", "tar.xz"):
        return "tarball"
    return "appimage"


def find_platform(user_agent):
    ua = user_agent or ""

    if re.search("Android", ua, re.I):
        return None
    if re.search("Win", ua, re.I):
        return WIN_ARM64 if re.search("ARM64|aarch64", ua, re.I) else WIN_X64
    if re.search("Mac OS X|Macintosh", ua, re.I):
        #browsers always report int(c)el on apple silicon, and modern ones freeze
        #the os version at 10_15_7 on every mac, so the only thing we can really
        #tell apart is a genuinely old intel mac (<= 10.14) from everything else
        version = re.search(r"Mac OS X (\d+)[._](\d+)", ua)
        major = int(version.group(1)) if version else 0
        minor = int(version.group(2)) if version else 0
        return MAC_X64 if major == 10 and minor < 15 else MAC_ARM
    if re.search("Linux|X11", ua, re.I):
        return LINUX_ARM64 if re.search("aarch64|arm64", ua, re.I) else LINUX_X64
    return None


async def get_last_build(platform, build_format):
    if platform.os_name == "mac":
        return await _get_mac_build(platform)
    if platform.os_name == "win":
        return await _get_windows_build(platform)
    return await _get_linux_build(platform, build_format)


async def _fetch_upstream(url):
    response = await fetch(
        url,
        headers={
            #NOTE: the github api rejects requests without one
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json, application/xml;q=0.9, */*;q=0.8",
        },
        cf={"cacheTtl": UPSTREAM_TTL_SECONDS, "cacheEverything": True},
    )
    if not response.ok:
        raise RuntimeError("upstream %s answered %s" % (url, response.status))
    return response


async def _get_mac_build(platform):
    url = "%s/mac/appcast-%s.xml" % (APPCAST_BASE, platform.arch)
    response = await _fetch_upstream(url)
    item = _first_item(await response.text())
    if not item:
        return None

    enclosure = _first_tag(_without_deltas(item), "enclosure")
    href = _attribute(enclosure, "url") if enclosure else None
    if not href:
        return None

    return {
        "version": _tag_text(item, "sparkle:version") or _tag_text(item, "title") or "unknown",
        #NOTE: mac appcasts use relative urls ("assets/helium_x.y.z_arm64-macos.dmg")
        "url": "%s/mac/%s" % (APPCAST_BASE, href.lstrip("/")) if "://" not in href else href,
        "size": _int_attribute(enclosure, "length"),
        "published_at": _tag_text(item, "pubDate"),
    }


async def _get_windows_build(platform):
    response = await _fetch_upstream("%s/win/appcast.xml" % APPCAST_BASE)
    item = _first_item(await response.text())
    if not item:
        return None

    wanted = "windows-arm64" if platform.arch == "arm64" else "windows-x64"
    enclosure = None
    for tag in _all_tags(item, "enclosure"):
        if _attribute(tag, "sparkle:os") == wanted:
            enclosure = tag
            break

    href = _attribute(enclosure, "url") if enclosure else None
    if not href:
        return None

    return {
        "version": _tag_text(item, "sparkle:version") or _tag_text(item, "title") or "unknown",
        "url": href,
        "size": _int_attribute(enclosure, "length"),
        # NOTE: the windows appcast carries no pubDate, so the appcast mtime is
        # the best release date we can offer
        "published_at": _tag_text(item, "pubDate") or response.headers.get("last-modified"),
    }


async def _get_linux_build(platform, build_format):
    response = await _fetch_upstream(LINUX_RELEASE_API)
    release = await response.json()

    for asset in release.get("assets", []):
        if _matches_linux_asset(asset["name"], platform, build_format):
            return {
                "version": release["tag_name"],
                "url": asset["browser_download_url"],
                "size": asset["size"],
                "published_at": release["published_at"],
            }
    return None


def _matches_linux_asset(name, platform, build_format):
    if build_format == "deb":
        return name.endswith("_%s.deb" % ("arm64" if platform.arch == "arm64" else "amd64"))
    if build_format == "tarball":
        return name.endswith("-%s_linux.tar.xz" % platform.arch)
    return name.endswith("-%s.AppImage" % platform.arch)


#workers python has no lxml and pulling a parser in for two sparkle
#feeds is not worth it
def _first_item(xml):
    match = re.search(r"<item>(.*?)</item>", xml, re.S)
    return match.group(1) if match else None


def _without_deltas(item):
    return re.sub(r"<sparkle:deltas>.*?</sparkle:deltas>", "", item, flags=re.S)


def _tag_text(xml, tag):
    match = re.search(r"<%s[^>]*>(.*?)</%s>" % (re.escape(tag), re.escape(tag)), xml, re.S)
    return _decode_entities(match.group(1).strip()) if match else None


def _all_tags(xml, tag):
    return re.findall(r"<%s\b[^>]*>" % re.escape(tag), xml)


def _first_tag(xml, tag):
    tags = _all_tags(xml, tag)
    return tags[0] if tags else None


def _attribute(tag, name):
    match = re.search(r'\b%s\s*=\s*"([^"]*)"' % re.escape(name), tag or "")
    return _decode_entities(match.group(1)) if match else None


def _int_attribute(tag, name):
    raw = _attribute(tag, name)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _decode_entities(value):
    for entity, char in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&")):
        value = value.replace(entity, char)
    return value