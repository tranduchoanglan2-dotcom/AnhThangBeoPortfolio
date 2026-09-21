#!/usr/bin/env python3
"""
Build the static site into _site/ (GitHub Actions runs this on every push).

Why: Facebook / Zalo / LinkedIn / Google don't wait for JavaScript, so title,
meta description and OG image must be written into the HTML itself. This script
reads the "seo" block of content.json and writes those tags into:

  _site/index.html               home
  _site/about/index.html         /about
  _site/work/<slug>/index.html   each project
  _site/404.html                 fallback for any other URL
  _site/sitemap.xml, robots.txt

Environment (set by the workflow from actions/configure-pages, optional locally):
  SITE_URL   e.g. https://thangnguyen.com   (used if seo.siteUrl is empty)
  BASE_PATH  e.g. "" or "/repo-name"         (canonical / og:url / sitemap; <base> tự nhận lúc chạy)

Run locally:  python scripts/build.py   → then serve the _site folder.
"""
import html, json, os, re, shutil, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
SKIP = {"_site", "scripts", ".github", ".git", ".pages.yml", "README.md", ".gitignore", ".DS_Store"}

def s(v):
    return "" if v is None else str(v).strip()

def slugify(t):
    t = unicodedata.normalize("NFD", s(t).lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("đ", "d")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "project"

def projects(c):
    out, seen = [], []
    raw = [p for p in (c.get("projects") or []) if isinstance(p, dict) and s(p.get("name"))]
    for i, p in enumerate(raw):
        slug = slugify(p.get("slug") or p.get("name"))
        if slug in seen:  # same rule as index.html
            slug += f"-{i + 1}"
        seen.append(slugify(p.get("slug") or p.get("name")))
        out.append({**p, "slug": slug})
    return out

def main():
    c = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
    tpl = (ROOT / "index.html").read_text(encoding="utf-8")
    site, seo = c.get("site") or {}, c.get("seo") or {}

    site_url = (s(seo.get("siteUrl")) or s(os.environ.get("SITE_URL"))).rstrip("/")
    base_path = "/" + s(os.environ.get("BASE_PATH")).strip("/")
    base_path = base_path if base_path == "/" else base_path + "/"
    name = s(site.get("name")) or "Portfolio"
    home_title = s(seo.get("title")) or (f"{name} — {s(site.get('title'))}" if s(site.get("title")) else name)
    desc = s(seo.get("description"))
    og_default = s(seo.get("ogImage"))

    def absu(path):
        if not path or re.match(r"^https?://", path):
            return path
        return (site_url + base_path + path.lstrip("/")) if site_url else ""

    def head(title, description, image, path):
        e = lambda v: html.escape(v, quote=True)
        url = (site_url + base_path + (path.strip("/") + "/" if path else "")) if site_url else ""
        img = absu(image)
        tags = [f"<title>{e(title)}</title>",
                f'<meta name="description" content="{e(description)}">',
                '<meta property="og:type" content="website">',
                f'<meta property="og:site_name" content="{e(name)}">',
                f'<meta property="og:title" content="{e(title)}">',
                f'<meta property="og:description" content="{e(description)}">',
                '<meta name="twitter:card" content="summary_large_image">',
                f'<meta name="twitter:title" content="{e(title)}">',
                f'<meta name="twitter:description" content="{e(description)}">']
        if url:
            tags += [f'<link rel="canonical" href="{e(url)}">', f'<meta property="og:url" content="{e(url)}">']
        if img:
            tags += [f'<meta property="og:image" content="{e(img)}">', f'<meta name="twitter:image" content="{e(img)}">']
        return "<!-- SEO:START (tạo tự động từ content.json) -->\n" + "\n".join(tags) + "\n<!-- SEO:END -->"

    def page(title, description, image, path, noindex=False):
        h = head(title, description, image, path)
        if noindex:
            h = h.replace("<!-- SEO:END -->", '<meta name="robots" content="noindex">\n<!-- SEO:END -->')
        return re.sub(r"<!-- SEO:START.*?<!-- SEO:END -->", lambda m: h, tpl, count=1, flags=re.S)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for item in ROOT.iterdir():
        if item.name in SKIP or item.name == "index.html":
            continue
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, OUT / item.name)

    def write(rel, text):
        f = OUT / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    write("index.html", page(home_title, desc, og_default, ""))
    write("404.html", page(home_title, desc, og_default, "", noindex=True))
    write("about/index.html", page(f"About — {name}", desc, og_default, "about"))
    urls = ["", "about"]
    for p in projects(c):
        write(f"work/{p['slug']}/index.html",
              page(f"{s(p.get('name'))} — {name}", desc, og_default, f"work/{p['slug']}"))
        urls.append(f"work/{p['slug']}")

    if site_url:
        write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              + "".join(f"  <url><loc>{html.escape(site_url + base_path + (u + '/' if u else ''))}</loc></url>\n" for u in urls) + "</urlset>\n")
        write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site_url}{base_path}sitemap.xml\n")
    else:
        write("robots.txt", "User-agent: *\nAllow: /\n")

    print(f"Built {len(urls)} pages → {OUT}  (site_url={site_url or '-'}, base={base_path})")

if __name__ == "__main__":
    sys.exit(main())
