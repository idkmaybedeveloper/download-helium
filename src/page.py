from pathlib import Path
from string import Template

from utils import LINUX_FORMATS, get_repo_url, platforms

TEMPLATES = Path(__file__).parent / "templates"

INDEX = Template((TEMPLATES / "index.html").read_text())
DOWNLOAD = Template((TEMPLATES / "download.html").read_text())
SORRY = (TEMPLATES / "sorry.html").read_text()
SCRIPT = Template((TEMPLATES / "script.html").read_text())


def render_index(platform, build_format, canonical):
    if platform:
        download_path = "/dl/%s?type=%s" % (platform.name, build_format)
        releases_url = "%s/releases" % get_repo_url(platform)
        body = DOWNLOAD.substitute(
            pretty_name=escape(platform.pretty_name),
            download_path=escape(download_path),
            releases_url=escape(releases_url),
        )
        prerender = '<link rel="prerender" href="%s">' % escape(download_path)
        script = SCRIPT.substitute(
            rev_url="/rev/%s?type=%s" % (platform.name, build_format),
            releases_url=releases_url,
        )
    else:
        body, prerender, script = SORRY, "", ""

    rows = []
    if platform and platform.os_name == "linux":
        rows.append(
            _footer_row(
                "Package Types:",
                [
                    ("?platform=%s&type=%s" % (platform.name, name), pretty, name == build_format)
                    for name, pretty in LINUX_FORMATS
                ],
            )
        )
    rows.append(
        _footer_row(
            "Supported Platforms:",
            [
                ("?platform=%s&type=%s" % (p.name, build_format), p.pretty_name, p is platform)
                for p in platforms
            ],
        )
    )

    return INDEX.substitute(
        canonical=escape(canonical),
        prerender=prerender,
        body=body,
        footer="\n          ".join(rows),
        script=script,
    )


def _footer_row(title, links):
    items = "\n            ".join(
        '<a %shref="%s">%s</a>' % ('class="selected" ' if selected else "", escape(href), escape(label))
        for href, label, selected in links
    )
    return "<div>\n            <span>%s</span>\n            %s\n          </div>" % (escape(title), items)


def escape(value):
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
