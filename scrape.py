#!/usr/bin/env python3
"""
skool-lesson-scrape
Downloads lessons from a Skool community classroom to a local folder as Markdown files.
Skips lessons already saved — safe to re-run when new content is added.

Usage:
    python scrape.py               # full scrape
    python scrape.py --discover    # inspect page structure without saving (debug)

Setup: see README.md
"""

import asyncio
import argparse
import re
import json
import tempfile
import html2text
from pathlib import Path
from playwright.async_api import async_playwright

# ── CONFIG — edit these two lines ────────────────────────────────────────────
#
# COMMUNITY: the slug from your Skool community URL
#   e.g. https://www.skool.com/navaigate  →  "navaigate"
COMMUNITY = "navaigate"
#
# OUTPUT_DIR: folder where .md files are saved (created if it doesn't exist)
#   Mac/Linux: Path.home() / "skool-lessons"
#   Windows:   Path(r"C:\Users\YourName\Documents\skool-lessons")
#   Obsidian:  Path.home() / "Documents" / "ObsidianVault" / "Lessons"
OUTPUT_DIR = Path.home() / "skool-lessons"
#
# ─────────────────────────────────────────────────────────────────────────────

BASE      = "https://www.skool.com"
CLASSROOM = f"{BASE}/{COMMUNITY}/classroom"
DIAG_DIR  = Path(tempfile.gettempdir()) / "skool_scrape_diag"

CONTENT_SELECTORS = [
    ".ProseMirror",           # Skool's TipTap editor — primary target
    "[class*='lesson-content']",
    "[class*='lessonContent']",
    "[class*='module-content']",
    "[class*='content-body']",
    "article",
    "main",
]


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '', str(name)).strip().strip(".")
    return name[:120]


def existing_stems() -> set:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return {f.stem for f in OUTPUT_DIR.glob("*.md")}


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1)) if m else {}


def html_to_md(raw: str) -> str:
    h = html2text.HTML2Text()
    h.body_width    = 0
    h.ignore_links  = False
    h.ignore_images = True
    return h.handle(raw)


def write_lesson(course_title: str, lesson_title: str, body: str) -> str:
    stem = f"{sanitize(course_title)} -- {sanitize(lesson_title)}"
    out  = OUTPUT_DIR / f"{stem}.md"
    out.write_text(f"# {lesson_title}\n\n{body}", encoding="utf-8")
    return stem


async def lesson_body(page) -> str:
    """Content is rendered client-side into .ProseMirror (Skool's TipTap editor)."""
    for sel in CONTENT_SELECTORS:
        el = await page.query_selector(sel)
        if el:
            inner = await el.inner_html()
            if len(inner) > 200:
                return html_to_md(inner)
    return html_to_md(await page.evaluate("() => document.body.innerHTML"))


async def run(discover: bool = False):
    existing = existing_stems()
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Lessons already saved: {len(existing)}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=25)
        ctx     = await browser.new_context(viewport={"width": 1440, "height": 900})
        page    = await ctx.new_page()

        print("Opening Skool — please log in when the browser window appears.")
        print("The script will continue automatically once you land on the community.\n")
        await page.goto("https://www.skool.com/login")
        await page.wait_for_url(f"**/{COMMUNITY}/**", timeout=300_000)
        print("Logged in.\n")

        await page.goto(CLASSROOM)
        await page.wait_for_load_state("load")
        await asyncio.sleep(3)

        nd        = next_data(await page.content())
        all_crses = nd.get("props", {}).get("pageProps", {}).get("allCourses", [])
        courses   = [c for c in all_crses if c.get("metadata", {}).get("hasAccess", 0)]
        print(f"Accessible courses: {len(courses)} of {len(all_crses)} total\n")

        if not courses:
            DIAG_DIR.mkdir(parents=True, exist_ok=True)
            (DIAG_DIR / "classroom.html").write_text(await page.content())
            print(f"No courses found. Diagnostic HTML saved to {DIAG_DIR}")
            await browser.close()
            return

        if discover:
            course_url = f"{CLASSROOM}/{courses[0]['name']}"
            await page.goto(course_url)
            await page.wait_for_load_state("load")
            await asyncio.sleep(3)
            cnd      = next_data(await page.content())
            children = cnd.get("props", {}).get("pageProps", {}).get("course", {}).get("children", [])
            first    = children[0]["course"] if children else None
            if first:
                await page.goto(f"{course_url}?md={first['id']}")
                await page.wait_for_load_state("load")
                await asyncio.sleep(3)
                lpp = next_data(await page.content()).get("props", {}).get("pageProps", {})
                print("Lesson pageProps keys:", list(lpp.keys()))
                DIAG_DIR.mkdir(parents=True, exist_ok=True)
                (DIAG_DIR / "lesson.html").write_text(await page.content())
                await page.screenshot(path=str(DIAG_DIR / "lesson.png"), full_page=True)
                print(f"Diagnostic files saved to {DIAG_DIR}")
            await browser.close()
            return

        saved = skipped = errors = 0

        for course in courses:
            course_title = course["metadata"]["title"]
            course_url   = f"{CLASSROOM}/{course['name']}"
            print(f"Course: {course_title}")

            await page.goto(course_url)
            await page.wait_for_load_state("load")
            await asyncio.sleep(2.5)

            children = (
                next_data(await page.content())
                .get("props", {})
                .get("pageProps", {})
                .get("course", {})
                .get("children", [])
            )

            if not children:
                print("  No lessons found — skipping\n")
                continue

            print(f"  {len(children)} lessons")

            for child in children:
                lesson       = child.get("course", {})
                lesson_title = lesson.get("metadata", {}).get("title") or lesson.get("name") or "Untitled"
                lesson_id    = lesson.get("id", "")
                stem         = f"{sanitize(course_title)} -- {sanitize(lesson_title)}"

                if stem in existing:
                    skipped += 1
                    continue

                try:
                    await page.goto(f"{course_url}?md={lesson_id}")
                    await page.wait_for_load_state("load")
                    await asyncio.sleep(2)
                    stem = write_lesson(course_title, lesson_title, await lesson_body(page))
                    existing.add(stem)
                    saved += 1
                    print(f"  [saved]  {lesson_title[:65]}")
                except Exception as e:
                    errors += 1
                    print(f"  [error]  {lesson_title[:65]} — {e}")

            print()

        print("─" * 52)
        print(f"Done.   Saved: {saved}   Skipped: {skipped}   Errors: {errors}")
        print(f"Output: {OUTPUT_DIR}")
        await browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Download Skool community lessons to Markdown")
    ap.add_argument("--discover", action="store_true", help="Debug page structure without saving")
    asyncio.run(run(discover=ap.parse_args().discover))
