#!/usr/bin/env python3
"""We killed Confluence with 12 KB.

Converts a Confluence XML site export into clean Markdown.

Usage: python3 confluence-to-md.py <export-dir> <output-dir>

The export dir must contain entities.xml (standard Confluence XML export).
Output is organized by Space > Page hierarchy with attachments alongside.
Only current-version pages are emitted; old revisions are discarded.
"""

import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from lxml import etree
from markdownify import markdownify


# ── Helpers ──────────────────────────────────────────────────────────────────


def sanitize(name: str) -> str:
    """Page title -> filesystem-safe name."""
    s = re.sub(r'[<>:"/\\|?*\s]+', "-", name or "").strip("-. ")
    return (s[:100].rstrip("-") if len(s) > 100 else s) or "untitled"


def dedup(path: Path) -> Path:
    """Return *path* unchanged, or append -2, -3, ... until unique."""
    if not path.exists():
        return path
    stem, sfx = path.stem, path.suffix
    return next(
        c for n in range(2, 10_000)
        if not (c := path.parent / f"{stem}-{n}{sfx}").exists()
    )


# ── Confluence HTML -> Markdown ──────────────────────────────────────────────

EMOJI = {
    "smile": ":)", "sad": ":(", "wink": ";)", "thumbs-up": "\U0001f44d",
    "thumbs-down": "\U0001f44e", "warning": "\u26a0\ufe0f", "tick": "\u2705",
    "cross": "\u274c", "information": "\u2139\ufe0f", "question": "\u2753",
    "light-on": "\U0001f4a1", "yellow-star": "\u2b50",
}
ADMONITIONS = frozenset(("info", "note", "tip", "warning"))


def _clean(html: str) -> str:
    """Strip Confluence-proprietary XML into standard HTML."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # ac:adf-extension -> prefer fallback, then content
    for adf in soup.find_all("ac:adf-extension"):
        if r := (adf.find("ac:adf-fallback") or adf.find("ac:adf-content")):
            adf.replace_with(r)

    # ac:structured-macro -> blockquote / code / placeholder
    for m in soup.find_all("ac:structured-macro"):
        name = m.get("ac:name", "")
        if body := m.find("ac:rich-text-body"):
            pfx = f"**{name.upper()}:** " if name in ADMONITIONS else ""
            bq = soup.new_tag("blockquote")
            bq.append(BeautifulSoup(pfx + body.decode_contents(), "html.parser"))
            m.replace_with(bq)
        elif name == "jira":
            k = m.find("ac:parameter", attrs={"ac:name": "key"})
            m.replace_with(f"[{k.string}]" if k else "")
        elif name in ("toc", "children"):
            m.replace_with({"toc": "[TOC]", "children": "[Child Pages]"}[name])
        elif name in ("code", "noformat") and (ptb := m.find("ac:plain-text-body")):
            pre = soup.new_tag("pre")
            c = soup.new_tag("code")
            c.string = ptb.string or ""
            pre.append(c)
            m.replace_with(pre)
        else:
            text = m.get_text()
            m.replace_with(text) if text.strip() else m.decompose()

    # ac:link -> markdown-style link
    for link in soup.find_all("ac:link"):
        if link.find("ri:user"):
            link.replace_with("@user")
        elif pg := link.find("ri:page"):
            title = pg.get("ri:content-title", "link")
            lb = link.find("ac:link-body") or link.find("ac:plain-text-link-body")
            link.replace_with(f"[{lb.get_text() if lb else title}]({title})")
        elif att := link.find("ri:attachment"):
            fn = att.get("ri:filename", "attachment")
            link.replace_with(f"[{fn}](attachments/{fn})")
        else:
            text = link.get_text()
            link.replace_with(text) if text.strip() else link.decompose()

    # ac:image -> <img>
    for img in soup.find_all("ac:image"):
        if att := img.find("ri:attachment"):
            fn = att.get("ri:filename", "image")
            img.replace_with(soup.new_tag("img", src=f"attachments/{fn}", alt=fn))
        elif url := img.find("ri:url"):
            img.replace_with(soup.new_tag("img", src=url.get("ri:value", ""), alt="image"))
        else:
            img.decompose()

    # ac:emoticon -> emoji text
    for em in soup.find_all("ac:emoticon"):
        n = em.get("ac:name", "")
        em.replace_with(EMOJI.get(n, f":{n}:"))

    # Sweep remaining proprietary tags
    for tag in soup.find_all(re.compile(r"^ac:")):
        text = tag.get_text()
        tag.replace_with(text) if text.strip() else tag.decompose()
    for tag in soup.find_all(re.compile(r"^ri:")):
        tag.decompose()

    return str(soup)


def to_md(html: str) -> str:
    """Confluence HTML -> Markdown, end to end."""
    if not html:
        return ""
    try:
        out = markdownify(_clean(html), heading_style="ATX", bullets="-", strip=["script", "style"])
    except Exception:
        out = BeautifulSoup(_clean(html), "html.parser").get_text()
    return re.sub(r"\n{4,}", "\n\n\n", out).strip()


# ── XML Parsing (memory-efficient iterparse) ────────────────────────────────


def _find_id(elem):
    e = elem.find("id[@name='id']")
    return e.text if e is not None else None


def _prop(elem, name):
    return next((p for p in elem.findall("property") if p.get("name") == name), None)


def _text(elem, name):
    p = _prop(elem, name)
    return (p.text or "").strip() if p is not None else ""


def _ref(elem, name):
    p = _prop(elem, name)
    return _find_id(p) if p is not None else None


def _body_ids(elem):
    return [
        bid.text
        for coll in elem.findall("collection") if coll.get("name") == "bodyContents"
        for el in coll.findall("element") if (bid := el.find("id[@name='id']")) is not None
    ]


def parse_xml(xml_path: Path):
    """Parse entities.xml -> (spaces, pages, blogs, bodies, attachments)."""
    print("Phase 1: Parsing XML...")
    spaces, pages, blogs, bodies, atts = {}, {}, {}, {}, {}

    for n, (_, elem) in enumerate(
        etree.iterparse(str(xml_path), events=("end",), tag="object"), 1
    ):
        cls = elem.get("class", "")
        if n % 10_000 == 0:
            print(f"  {n:,} objects...", end="\r")

        if cls == "Space":
            if (sid := _find_id(elem)) and (key := _text(elem, "key")):
                spaces[sid] = {"key": key, "name": _text(elem, "name") or key}

        elif cls == "Page" and _text(elem, "contentStatus") == "current":
            if pid := _find_id(elem):
                try:
                    ver = int(_text(elem, "version") or "0")
                except ValueError:
                    ver = 0
                pages[pid] = dict(
                    title=_text(elem, "title") or "Untitled",
                    space=_ref(elem, "space"), parent=_ref(elem, "parent"),
                    bodies=_body_ids(elem), ver=ver,
                    orig=_text(elem, "originalVersionId") or None,
                )

        elif cls == "BlogPost" and _text(elem, "contentStatus") == "current":
            if pid := _find_id(elem):
                blogs[pid] = dict(
                    title=_text(elem, "title") or "Untitled",
                    space=_ref(elem, "space"), bodies=_body_ids(elem),
                    created=_text(elem, "creationDate"),
                )

        elif cls == "BodyContent" and _text(elem, "bodyType") == "2":
            if bid := _find_id(elem):
                p = _prop(elem, "body")
                raw = (p.text or "") if p is not None else ""  # no strip — preserve body whitespace
                if raw:
                    bodies[bid] = {"html": raw, "page": _ref(elem, "content")}

        elif cls == "Attachment" and _text(elem, "contentStatus") == "current":
            if (aid := _find_id(elem)) and (title := _text(elem, "title")):
                atts[aid] = {"title": title, "page": _ref(elem, "containerContent")}

        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    print(f"\n  {len(spaces)} spaces | {len(pages)} pages | {len(blogs)} blogs | "
          f"{len(bodies)} bodies | {len(atts)} attachments")
    return spaces, pages, blogs, bodies, atts


# ── Transform & Write ────────────────────────────────────────────────────────


def dedup_pages(pages: dict) -> dict:
    """Keep only the highest-version page per original."""
    print("Phase 2: Deduplicating...")
    groups = defaultdict(list)
    for pid, p in pages.items():
        groups[p.get("orig") or pid].append((p["ver"], pid))
    keep = {max(vs)[1] for vs in groups.values()}
    out = {pid: p for pid, p in pages.items() if pid in keep}
    print(f"  {len(out)} kept, {len(pages) - len(out)} old versions removed")
    return out


def body_of(page: dict, bodies: dict) -> str:
    return next((bodies[bid]["html"] for bid in page.get("bodies", []) if bid in bodies), "")


def copy_attachments(page_id: str, src_root: Path, dest_root: Path, atts: dict):
    """Copy attachment files for a page. Logs failures instead of swallowing them."""
    page_dir = src_root / "attachments" / str(page_id)
    if not page_dir.is_dir():
        return
    out = dest_root / "attachments"
    for ver_dir in page_dir.iterdir():
        if not ver_dir.is_dir():
            continue
        for src in ver_dir.iterdir():
            if not src.is_file():
                continue
            out.mkdir(exist_ok=True)
            dest_name = atts[ver_dir.name]["title"] if ver_dir.name in atts else src.name
            try:
                shutil.copy2(src, out / dest_name)
            except Exception as e:
                print(f"  \u26a0 {src.name}: {e}", file=sys.stderr)


def write_tree(spaces, pages, bodies, atts, export_dir: Path, output_dir: Path):
    """Build hierarchy and write every page iteratively (no recursion limit)."""
    print("Phase 3: Writing Markdown...")

    # Parent -> children + space -> roots
    children, roots = defaultdict(list), defaultdict(list)
    ids = set(pages)
    for pid, p in pages.items():
        parent = p["parent"]
        if parent and parent in ids:
            children[parent].append(pid)
        else:
            roots[p["space"]].append(pid)

    # Iterative DFS: (page_id, target_dir)
    stack = []
    for sid in sorted(roots, key=lambda s: spaces.get(s, {}).get("name", "")):
        sp = spaces.get(sid, {"key": f"unknown-{sid}", "name": f"Unknown-{sid}"})
        sdir = output_dir / sanitize(f"{sp['key']}-{sp['name']}")
        sdir.mkdir(parents=True, exist_ok=True)
        pids = roots[sid]
        print(f"  {sp['name']} ({sp['key']}): {len(pids)} root pages")
        for pid in sorted(pids, key=lambda p: pages[p]["title"], reverse=True):
            stack.append((pid, sdir))

    seen, total = set(), 0
    while stack:
        pid, out = stack.pop()
        if pid in seen:
            continue  # guard against circular parent refs
        seen.add(pid)

        page = pages[pid]
        name = sanitize(page["title"])
        kids = children.get(pid, [])

        if kids:
            pdir = dedup(out / name)
            pdir.mkdir(exist_ok=True)
            fpath = pdir / "index.md"
            copy_attachments(pid, export_dir, pdir, atts)
            for cid in sorted(kids, key=lambda c: pages[c]["title"], reverse=True):
                stack.append((cid, pdir))
        else:
            fpath = dedup(out / f"{name}.md")
            copy_attachments(pid, export_dir, out, atts)

        fpath.write_text(f"# {page['title']}\n\n{to_md(body_of(page, bodies))}\n", encoding="utf-8")
        total += 1

    return total


def write_blogs(blogs, bodies, spaces, output_dir: Path) -> int:
    if not blogs:
        return 0
    print(f"  {len(blogs)} blog posts...")
    for post in blogs.values():
        sp = spaces.get(post["space"], {"key": "unknown", "name": "Unknown"})
        bdir = output_dir / sanitize(f"{sp['key']}-{sp['name']}") / "blog"
        bdir.mkdir(parents=True, exist_ok=True)
        date = (post.get("created") or "")[:10]
        fpath = dedup(bdir / f"{date}-{sanitize(post['title'])}.md")
        fpath.write_text(f"# {post['title']}\n\n{to_md(body_of(post, bodies))}\n", encoding="utf-8")
    return len(blogs)


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <confluence-export-dir> <output-dir>")
        sys.exit(1)

    export_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    xml = export_dir / "entities.xml"

    if not xml.is_file():
        sys.exit(f"Error: {xml} not found — is this a Confluence XML export?")

    print(f"Confluence \u2192 Markdown\n  In:  {export_dir}\n  Out: {output_dir}\n")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    spaces, pages, blogs, bodies, atts = parse_xml(xml)
    pages = dedup_pages(pages)
    np = write_tree(spaces, pages, bodies, atts, export_dir, output_dir)
    nb = write_blogs(blogs, bodies, spaces, output_dir)
    print(f"\nDone: {np} pages + {nb} blogs \u2192 {output_dir}")


if __name__ == "__main__":
    main()
