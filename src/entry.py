import re
from urllib.parse import parse_qs, unquote, urlparse

from workers import Response, WorkerEntrypoint

from page import render_index
from utils import find_platform, get_last_build, get_linux_format, get_platform

CANONICAL = "https://download-helium.cuddles.rs/"
PAGE_CACHE_CONTROL = "public, max-age=60, s-maxage=300"
API_CACHE_CONTROL = "public, max-age=0, s-maxage=300"

DL_PATH = re.compile(r"^/dl/([^/]+)/?$")
REV_PATH = re.compile(r"^/rev/([^/]+)/?$")

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method not in ("GET", "HEAD"):
            return Response("method not allowed", status=405, headers={"Allow": "GET, HEAD"})

        url = urlparse(request.url)
        query = parse_qs(url.query)
        build_format = get_linux_format(_first(query, "type") or _first(query, "format"))

        if url.path == "/":
            return _index(request, query, build_format)

        download = DL_PATH.match(url.path)
        if download:
            return await _download(unquote(download.group(1)), build_format)

        revision = REV_PATH.match(url.path)
        if revision:
            return await _revision(unquote(revision.group(1)), build_format)

        return Response("not found", status=404)


def _index(request, query, build_format):
    requested = _first(query, "platform")
    platform = get_platform(requested) if requested else find_platform(request.headers.get("User-Agent"))

    return Response(
        render_index(platform, build_format, CANONICAL),
        headers={"Content-Type": "text/html; charset=utf-8", "Cache-Control": PAGE_CACHE_CONTROL},
    )


async def _download(platform_name, build_format):
    platform = get_platform(platform_name)
    if not platform:
        #just dont ask me about this
        return Response.redirect("https://www.youtube.com/watch?v=DAwvBKWwv8I", 302)

    build, error = await _resolve(platform, build_format)
    if error:
        return error

    return Response(
        None,
        status=302,
        headers={"Location": build["url"], "Cache-Control": API_CACHE_CONTROL},
    )


async def _revision(platform_name, build_format):
    platform = get_platform(platform_name)
    if not platform:
        return Response("unknown platform", status=404)

    build, error = await _resolve(platform, build_format)
    if error:
        return error


    return Response.from_json(
        {
            "content": build["version"],
            "last-modified": build["published_at"],
            "platform": platform.name,
            "url": build["url"],
            "size": build["size"],
        },
        headers={"Cache-Control": API_CACHE_CONTROL},
    )


async def _resolve(platform, build_format):
    try:
        build = await get_last_build(platform, build_format)
    except Exception as error:
        print("failed to resolve %s/%s: %s" % (platform.name, build_format, error))
        return None, Response("upstream release feed is unavailable", status=502)

    if not build:
        return None, Response("no build found for this platform", status=404)
    return build, None


def _first(query, key):
    values = query.get(key)
    return values[0] if values else None