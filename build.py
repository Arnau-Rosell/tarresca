"""Build the static Tárrega y Escaned website.

Reads one Markdown file per work from ``content/obra`` and writes plain HTML into
``docs/``, which GitHub Pages can publish as-is. Uses the standard library only.

Usage:
    python3 build.py
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content" / "obra"
SITE_DIR = ROOT / "docs"
IMG_DIR = SITE_DIR / "img"

SITE_NAME = "Tárrega y Escaned"
ARTISTS = "Javier Tárrega e Inés Escaned"
SITE_DESCRIPTION = (
    "Obra de Tárrega y Escaned: intervenciones en el espacio público, escultura "
    "y arcilla salvaje."
)
CONTACT_EMAIL: str | None = None
CONTACT_INSTAGRAM: str | None = None

IMAGE_SIZES = (900, 1800)
META_LABELS = (
    ("dimensions", "Dimensiones"),
    ("materials", "Materiales"),
    ("thanks", "Agradecimientos"),
    ("photos", "Fotos"),
)
SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD}

FrontMatter = dict[str, str | list[str]]


@dataclass(frozen=True)
class Image:
    """A photograph available in every size listed in ``IMAGE_SIZES``."""

    slug: str
    name: str
    widths: tuple[int, ...]
    width: int
    height: int

    @property
    def is_portrait(self) -> bool:
        """Whether the image is noticeably taller than it is wide."""
        return self.height > self.width * 1.05


@dataclass(frozen=True)
class Video:
    """An embedded video hosted elsewhere (Vimeo or YouTube)."""

    url: str


@dataclass(frozen=True)
class Work:
    """A single work, as described by its content file."""

    number: int
    slug: str
    title: str
    year: str
    date: str
    cover: Image
    media: tuple[Image | Video, ...]
    meta: FrontMatter
    body: str


def jpeg_size(path: Path) -> tuple[int, int]:
    """Read the pixel size of a JPEG from its frame header.

    Args:
        path: The JPEG file to inspect.

    Returns:
        The width and height in pixels.

    Raises:
        ValueError: If the file has no readable frame header.
    """
    data = path.read_bytes()
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in SOF_MARKERS:
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    raise ValueError(f"No JPEG frame header found in {path}")


def load_image(slug: str, name: str) -> Image:
    """Describe an image from the files produced for it in ``docs/img``.

    Args:
        slug: The work the image belongs to.
        name: The image's base name, such as ``01`` or ``cover``.

    Returns:
        The image with its available widths and its largest size.
    """
    sizes = [jpeg_size(IMG_DIR / slug / f"{name}-{s}.jpg") for s in IMAGE_SIZES]
    width, height = sizes[-1]
    return Image(slug, name, tuple(w for w, _ in sizes), width, height)


def parse_front_matter(text: str) -> tuple[FrontMatter, str]:
    """Split a content file into its front matter and its body.

    Supports ``key: value`` lines and ``key:`` followed by ``  - item`` lines.

    Args:
        text: The full content file.

    Returns:
        The front matter fields and the Markdown body.
    """
    _, head, body = text.split("---\n", 2)
    fields: FrontMatter = {}
    current: list[str] | None = None
    for line in head.splitlines():
        if line.startswith("  - ") and current is not None:
            current.append(line[4:].strip())
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value:
            fields[key.strip()] = value
            current = None
        else:
            current = []
            fields[key.strip()] = current
    return fields, body.strip()


def load_work(path: Path) -> Work:
    """Load a work from its content file.

    Args:
        path: A file in ``content/obra`` named ``NN-slug.md``.

    Returns:
        The parsed work.
    """
    number_text, _, slug = path.stem.partition("-")
    fields, body = parse_front_matter(path.read_text(encoding="utf-8"))
    video_url = str(fields.get("video_url") or "")
    media: list[Image | Video] = []
    for item in fields.get("media", []):
        if item == "video":
            if video_url:
                media.append(Video(video_url))
        else:
            media.append(load_image(slug, Path(item).stem))
    year = str(fields["year"])
    return Work(
        number=int(number_text),
        slug=slug,
        title=str(fields["title"]),
        year=year,
        date=str(fields.get("date") or year),
        cover=load_image(slug, Path(str(fields["cover"])).stem),
        media=tuple(media),
        meta={key: fields[key] for key, _ in META_LABELS if key in fields},
        body=body,
    )


def esc(text: str) -> str:
    """Escape text for safe use in HTML content and attributes."""
    return html.escape(text, quote=True)


def inline(text: str) -> str:
    """Render the inline Markdown subset: ``**bold**`` and ``*italic*``."""
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)


def paragraphs(body: str) -> str:
    """Render a Markdown body as paragraphs, keeping single line breaks.

    Short multi-line paragraphs are set as verse, and all-caps ones as signage.

    Args:
        body: Paragraphs separated by blank lines.

    Returns:
        The HTML for the paragraphs.
    """
    blocks = []
    for block in re.split(r"\n\s*\n", body.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        plain = [line.replace("*", "") for line in lines]
        css_class = ""
        if len(lines) >= 3 and all(p.upper() == p for p in plain):
            css_class = ' class="sign"'
        elif len(lines) >= 3 and all(len(p) <= 45 for p in plain):
            css_class = ' class="verse"'
        content = "<br>\n".join(inline(line) for line in lines)
        blocks.append(f"<p{css_class}>{content}</p>")
    return "\n".join(blocks)


def picture(
    image: Image,
    root: str,
    alt: str,
    sizes: str,
    *,
    eager: bool = False,
) -> str:
    """Render a responsive ``<img>`` element for an image.

    Args:
        image: The image to show.
        root: Relative path from the page to the site root.
        alt: Alternative text.
        sizes: The ``sizes`` attribute describing the rendered width.
        eager: Load immediately instead of lazily, for images above the fold.

    Returns:
        The HTML for the image.
    """
    base = f"{root}img/{image.slug}/{image.name}"
    srcset = ", ".join(
        f"{base}-{size}.jpg {width}w"
        for size, width in zip(IMAGE_SIZES, image.widths, strict=True)
    )
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (
        f'<img src="{base}-{IMAGE_SIZES[-1]}.jpg" srcset="{srcset}" '
        f'sizes="{sizes}" width="{image.width}" height="{image.height}" '
        f'alt="{esc(alt)}" {loading} decoding="async">'
    )


def page(
    *,
    root: str,
    title: str,
    description: str,
    main: str,
    current: str,
    og_image: str | None = None,
    wordmark_tag: str = "p",
    scripts: tuple[str, ...] = (),
) -> str:
    """Wrap page content in the shared document shell.

    Args:
        root: Relative path from the page to the site root.
        title: The page title, without the site name.
        description: The meta description.
        main: The HTML inside ``<main>``.
        current: Which navigation item is current: ``obra`` or ``contacto``.
        og_image: Relative URL of the image used when the page is shared.
        wordmark_tag: The element used for the site name in the header.
        scripts: Script paths, relative to the site root, loaded with ``defer``.

    Returns:
        The complete HTML document.
    """
    script_tags = "".join(
        f'\n  <script src="{root}{src}" defer></script>' for src in scripts
    )
    full_title = f"{title} — {SITE_NAME}" if title != SITE_NAME else SITE_NAME

    def nav_link(key: str, href: str, label: str) -> str:
        marker = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{marker}>{label}</a>'

    og = f'\n  <meta property="og:image" content="{og_image}">' if og_image else ""
    year = date.today().year
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="author" content="{esc(ARTISTS)}">
  <meta property="og:title" content="{esc(full_title)}">
  <meta property="og:description" content="{esc(description)}">{og}
  <meta name="theme-color" content="#f3ede4">
  <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
  <link rel="preload" href="{root}fonts/schibsted-grotesk-normal-latin.woff2"
        as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{root}fonts/newsreader-normal-latin.woff2"
        as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{root}css/style.css">{script_tags}
</head>
<body>
  <a class="skip" href="#contenido">Saltar al contenido</a>
  <header class="site-header">
    <{wordmark_tag} class="wordmark"><a href="{root}">{SITE_NAME}</a></{wordmark_tag}>
    <div class="site-actions">
      <nav class="site-nav" aria-label="Principal">
        {nav_link("obra", root, "Obra")}
        {nav_link("contacto", f"{root}contacto/", "Contacto")}
      </nav>
      <form class="search" role="search" action="{root or "./"}" method="get">
        <label class="visually-hidden" for="buscar">Buscar obras</label>
        <input class="search-input" id="buscar" name="q" type="search"
               placeholder="Buscar" autocomplete="off" spellcheck="false">
      </form>
    </div>
  </header>
  <main id="contenido">
{main}
  </main>
  <footer class="site-footer">
    <p>© {year} {esc(ARTISTS)}</p>
    <p><a href="{root}contacto/">Contacto</a></p>
  </footer>
</body>
</html>
"""


def render_index(works: list[Work]) -> str:
    """Render the catalogue of works, grouped by year, newest first."""
    years: dict[str, list[Work]] = {}
    for work in works:
        years.setdefault(work.year, []).append(work)
    sections = []
    for year in sorted(years, reverse=True):
        items = []
        for work in years[year]:
            when = (
                f'\n          <span class="work-date">{esc(work.date)}</span>'
                if work.date != work.year
                else ""
            )
            thumb = picture(
                work.cover,
                "",
                "",
                "(min-width: 64rem) 22vw, (min-width: 40rem) 30vw, 46vw",
                eager=work is works[0],
            )
            keywords = esc(search_text(work))
            items.append(f"""        <li class="work" data-search="{keywords}">
          <a href="obra/{work.slug}/">
          <span class="work-thumb">{thumb}</span>
          <span class="work-title">{esc(work.title)}</span>{when}
          </a>
        </li>""")
        sections.append(f"""    <section class="year" aria-labelledby="y{year}">
      <h2 class="year-title" id="y{year}">{year}</h2>
      <ol class="works">
{chr(10).join(items)}
      </ol>
    </section>""")
    return page(
        root="",
        title=SITE_NAME,
        description=SITE_DESCRIPTION,
        main='    <p class="search-status" role="status"></p>\n' + "\n".join(sections),
        current="obra",
        og_image=f"img/{works[0].cover.slug}/{works[0].cover.name}-900.jpg",
        wordmark_tag="h1",
        scripts=("js/search.js",),
    )


def normalise(text: str) -> str:
    """Lower-case text and strip accents, so searches ignore both.

    Must match ``normalise`` in ``docs/js/search.js``.

    Args:
        text: Any text.

    Returns:
        The text without diacritics, in lower case, with single spaces.
    """
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def search_text(work: Work) -> str:
    """Collect everything a visitor might search a work by.

    Args:
        work: The work to index.

    Returns:
        The normalised title, dates, facts and text of the work.
    """
    facts = [
        v
        for value in work.meta.values()
        for v in (value if isinstance(value, list) else [value])
    ]
    parts = [work.title, work.year, work.date, *facts, work.body.replace("*", "")]
    return normalise(" ".join(parts))


def render_facts(work: Work) -> str:
    """Render the dimensions, materials and credits of a work."""
    rows = []
    for key, label in META_LABELS:
        value = work.meta.get(key)
        if not value:
            continue
        values = value if isinstance(value, list) else [value]
        items = "".join(f"<dd>{inline(v)}</dd>" for v in values)
        rows.append(f"<div><dt>{label}</dt>{items}</div>")
    return f'<dl class="facts">{"".join(rows)}</dl>' if rows else ""


def render_plates(work: Work, media: list[Image | Video], total: int) -> str:
    """Render the image sequence that follows the text.

    Landscape images span the full measure; portraits sit in pairs, and a
    portrait without a partner is centred on its own.

    Args:
        work: The work the media belongs to.
        media: The media items to lay out, in order.
        total: The total number of images, used in the alt text.

    Returns:
        The HTML for the image sequence.
    """
    plates = []
    i = 0
    while i < len(media):
        item = media[i]
        if isinstance(item, Video):
            plates.append(render_video(item, work))
            i += 1
            continue
        alt = f"{work.title}, imagen {image_number(work, item)} de {total}"
        if not item.is_portrait:
            sizes = "(min-width: 82rem) 76rem, 92vw"
            plates.append(
                f'<figure class="plate plate--wide">'
                f"{picture(item, '../../', alt, sizes)}</figure>"
            )
            i += 1
            continue
        partner = media[i + 1] if i + 1 < len(media) else None
        if isinstance(partner, Image) and partner.is_portrait:
            sizes = "(min-width: 82rem) 38rem, (min-width: 40rem) 46vw, 92vw"
            for image in (item, partner):
                alt = f"{work.title}, imagen {image_number(work, image)} de {total}"
                plates.append(
                    f'<figure class="plate plate--tall">'
                    f"{picture(image, '../../', alt, sizes)}</figure>"
                )
            i += 2
        else:
            sizes = "(min-width: 40rem) 36rem, 92vw"
            plates.append(
                f'<figure class="plate plate--solo">'
                f"{picture(item, '../../', alt, sizes)}</figure>"
            )
            i += 1
    if not plates:
        return ""
    return '    <div class="plates">\n      ' + "\n      ".join(plates) + "\n    </div>"


def image_number(work: Work, image: Image) -> int:
    """Return the 1-based position of an image among a work's images."""
    images = [m for m in work.media if isinstance(m, Image)] or [work.cover]
    return images.index(image) + 1


def render_video(video: Video, work: Work) -> str:
    """Render an embedded video in a fixed 16:9 frame."""
    return (
        '<figure class="plate plate--wide plate--video">'
        f'<iframe src="{esc(video.url)}" title="{esc(work.title)} (vídeo)" '
        'loading="lazy" allow="fullscreen; picture-in-picture" allowfullscreen>'
        "</iframe></figure>"
    )


def render_work(work: Work, previous: Work, following: Work) -> str:
    """Render the page of a single work.

    Args:
        work: The work to render.
        previous: The work linked as "Anterior".
        following: The work linked as "Siguiente".

    Returns:
        The complete HTML document.
    """
    media = list(work.media) or [work.cover]
    images = [m for m in media if isinstance(m, Image)]
    lead_index = next(i for i, m in enumerate(media) if isinstance(m, Image))
    lead = media[lead_index]
    assert isinstance(lead, Image)
    rest = media[:lead_index] + media[lead_index + 1 :]
    lead_class = "plate--lead-tall" if lead.is_portrait else "plate--lead"
    lead_html = picture(
        lead,
        "../../",
        f"{work.title}, imagen 1 de {len(images)}",
        "(min-width: 40rem) 40rem, 92vw"
        if lead.is_portrait
        else "(min-width: 82rem) 76rem, 92vw",
        eager=True,
    )
    when = (
        f'\n      <p class="work-when">{esc(work.date)}</p>'
        if work.date != work.year
        else ""
    )
    prose = paragraphs(work.body)
    text_class = "work-text" if prose else "work-text work-text--facts-only"
    prose_html = f'\n      <div class="prose">\n{prose}\n      </div>' if prose else ""
    main = f"""    <article class="work-page">
    <header class="work-head">
      <p class="work-kicker">
        <a href="../../">Obra</a><span aria-hidden="true">/</span>{work.year}
      </p>
      <h1 class="work-name">{esc(work.title)}</h1>{when}
    </header>
    <figure class="plate {lead_class}">{lead_html}</figure>
    <section class="{text_class}" aria-label="Sobre la obra">{prose_html}
      {render_facts(work)}
    </section>
{render_plates(work, rest, len(images))}
    </article>
    <nav class="work-nav" aria-label="Más obras">
      <a class="work-nav-prev" href="../{previous.slug}/" rel="prev">
        <span class="work-nav-label">Anterior</span>
        <span class="work-nav-title">{esc(previous.title)}</span>
      </a>
      <a class="work-nav-next" href="../{following.slug}/" rel="next">
        <span class="work-nav-label">Siguiente</span>
        <span class="work-nav-title">{esc(following.title)}</span>
      </a>
    </nav>"""
    return page(
        root="../../",
        title=work.title,
        description=work_description(work),
        main=main,
        current="obra",
        og_image=f"../../img/{work.cover.slug}/{work.cover.name}-900.jpg",
    )


def work_description(work: Work, limit: int = 155) -> str:
    """Summarise a work for its meta description.

    Args:
        work: The work to describe.
        limit: The maximum length before the text is cut at a word boundary.

    Returns:
        The opening of the work's text, or a short fallback when it has none.
    """
    if not work.body:
        return f"{work.title} ({work.date}), obra de {SITE_NAME}."
    first = re.sub(r"\*+", "", work.body.split("\n\n")[0]).replace("\n", " ")
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0] + "…"


def render_contact() -> str:
    """Render the contact page."""
    links = []
    if CONTACT_EMAIL:
        links.append(
            f'<li><a href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a></li>'
        )
    if CONTACT_INSTAGRAM:
        handle = CONTACT_INSTAGRAM.lstrip("@")
        links.append(
            f'<li><a href="https://www.instagram.com/{esc(handle)}/">'
            f"Instagram @{esc(handle)}</a></li>"
        )
    body = (
        f'<ul class="contact-links">{"".join(links)}</ul>'
        if links
        else '<p class="contact-pending">Datos de contacto en preparación.</p>'
    )
    main = f"""    <section class="contact">
      <h1 class="page-title">Contacto</h1>
      <p class="contact-names">{esc(ARTISTS)}</p>
      {body}
    </section>"""
    return page(
        root="../",
        title="Contacto",
        description=f"Contacto de {ARTISTS}.",
        main=main,
        current="contacto",
    )


def render_not_found() -> str:
    """Render the page GitHub Pages shows for unknown URLs."""
    main = """    <section class="contact">
      <h1 class="page-title">Esta página no existe</h1>
      <p class="contact-pending"><a href="/">Volver a la obra</a></p>
    </section>"""
    return page(
        root="/",
        title="Página no encontrada",
        description=SITE_DESCRIPTION,
        main=main,
        current="",
    )


def write(path: Path, content: str) -> None:
    """Write a generated file, creating its folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Build every page of the site into ``docs/``."""
    works = [load_work(p) for p in sorted(CONTENT_DIR.glob("*.md"))]
    write(SITE_DIR / "index.html", render_index(works))
    for i, work in enumerate(works):
        previous = works[i - 1]
        following = works[(i + 1) % len(works)]
        write(
            SITE_DIR / "obra" / work.slug / "index.html",
            render_work(work, previous, following),
        )
    write(SITE_DIR / "contacto" / "index.html", render_contact())
    write(SITE_DIR / "404.html", render_not_found())
    write(SITE_DIR / ".nojekyll", "")
    print(f"Built {len(works)} works into {SITE_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
