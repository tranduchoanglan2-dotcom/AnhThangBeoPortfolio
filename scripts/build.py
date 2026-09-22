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
import hashlib, html, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
SKIP = {"_site", "scripts", ".github", ".git", ".pages.yml", "README.md", ".gitignore", ".DS_Store", ".imgcache"}
CACHE = ROOT / ".imgcache"          # ảnh đã resize (GitHub Actions giữ lại giữa các lần deploy)
SIZES = (2880, 1440)                # bản lớn cho desktop, bản nhỏ cho điện thoại
HERO_MAX = 2880

def s(v):
    return "" if v is None else str(v).strip()

def slugify(t):
    t = unicodedata.normalize("NFD", s(t).lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("đ", "d")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "project"

def projects(c):
    out, seen = [], []
    raw = [p for p in (c.get("projects") or []) if isinstance(p, dict) and s(p.get("name")) and p.get("hidden") is not True][:6]  # tối đa 6 dự án, giống index.html  # hidden → không tạo trang, không vào sitemap
    for i, p in enumerate(raw):
        slug = slugify(p.get("slug") or p.get("name"))
        if slug in seen:  # same rule as index.html
            slug += f"-{i + 1}"
        seen.append(slugify(p.get("slug") or p.get("name")))
        out.append({**p, "slug": slug})
    return out

# ---------- Ảnh: tự thu nhỏ ảnh quá lớn (client upload ảnh 4x vẫn ổn) ----------
def _pil():
    try:
        from PIL import Image
    except ImportError:
        for extra in (["--user", "--break-system-packages"], ["--user"], []):   # runner Ubuntu mới chặn pip mặc định
            if subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *extra, "pillow"], check=False).returncode == 0:
                break
        try:
            import site; sys.path.append(site.getusersitepackages())
            from PIL import Image
        except Exception:
            return None
    Image.MAX_IMAGE_PIXELS = None
    return Image

def _resized(Image, src_rel, width):
    """Trả về (đường dẫn web, w, h) của bản rộng tối đa `width` (WebP q82). Dùng cache theo nội dung file."""
    src = ROOT / src_rel
    data = src.read_bytes()
    key = hashlib.sha1(data).hexdigest()[:12]
    CACHE.mkdir(exist_ok=True)
    meta = CACHE / f"{key}-{width}.json"
    if meta.exists():
        m = json.loads(meta.read_text())
    else:
        with Image.open(src) as im:
            im.load()
            W, H = im.size
            if W <= width and src.suffix.lower() == ".webp":
                m = {"file": None, "w": W, "h": H}                  # đủ nhỏ rồi, dùng file gốc
            else:
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
                tw = min(width, W); th = round(H * tw / W)
                k = max(1, W // (tw * 2))
                if k > 1: im = im.reduce(k)                           # thu nhỏ nhanh trước, rồi Lanczos
                im = im.resize((tw, th), Image.LANCZOS)
                out = CACHE / f"{key}-{width}.webp"
                im.save(out, "WEBP", quality=82, method=4)
                m = {"file": out.name, "w": tw, "h": th}
        meta.write_text(json.dumps(m))
    if m["file"] is None:
        return src_rel, m["w"], m["h"]
    dest = OUT / "images" / "_opt" / f"{Path(src_rel).stem}-{m['file']}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(CACHE / m["file"], dest)
    return dest.relative_to(OUT).as_posix(), m["w"], m["h"]

def optimize_images(c):
    Image = _pil()
    if Image is None:
        print("! Không có Pillow — bỏ qua bước tối ưu ảnh"); return c, 0
    n = 0
    for p in c.get("projects") or []:
        if not isinstance(p, dict) or p.get("hidden") is True:
            continue
        h = s(p.get("hero"))
        if h and (ROOT / h).is_file():
            try:
                p["hero"], p["heroW"], p["heroH"] = _resized(Image, h, HERO_MAX); n += 1
            except Exception as e:
                print("! hero", h, e)
        pages = []
        for g in p.get("pages") or []:
            g = s(g) if not isinstance(g, dict) else s(g.get("src"))
            if not g or not (ROOT / g).is_file():
                pages.append(g); continue
            try:
                big, w, hh = _resized(Image, g, SIZES[0])
                small, sw, _ = _resized(Image, g, SIZES[1])
                item = {"src": big, "w": w, "h": hh}
                if sw < w: item["srcset"] = f"{small} {sw}w, {big} {w}w"
                pages.append(item); n += 1
            except Exception as e:
                print("! page", g, e); pages.append(g)
        if "pages" in p: p["pages"] = pages
    return c, n

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

    c_opt, n_img = optimize_images(json.loads(json.dumps(c)))
    (OUT / "content.json").write_text(json.dumps(c_opt, ensure_ascii=False), encoding="utf-8")   # bản content đã trỏ tới ảnh tối ưu
    print(f"Optimized {n_img} project images")

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
