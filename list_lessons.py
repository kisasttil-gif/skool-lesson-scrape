#!/usr/bin/env python3
"""List all courses and lessons in a Skool community, then inspect a specific lesson."""

import asyncio, argparse, re, json
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://www.skool.com"
DIAG = Path("/tmp/skool_diag")

def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1)) if m else {}

async def run(community, inspect_index):
    classroom = f"{BASE}/{community}/classroom"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=25)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        print("Opening Skool... please log in.")
        await page.goto("https://www.skool.com/login")
        await page.wait_for_url(f"**/{community}*", timeout=300_000)
        print("Logged in.\n")

        await page.goto(classroom)
        await page.wait_for_load_state("load")
        await asyncio.sleep(3)

        nd = next_data(await page.content())
        all_crses = nd.get("props", {}).get("pageProps", {}).get("allCourses", [])
        courses = [c for c in all_crses if c.get("metadata", {}).get("hasAccess", 0)]

        all_lessons = []
        for course in courses:
            meta = course["metadata"]
            course_title = meta["title"]
            course_name = course["name"]
            course_url = f"{classroom}/{course_name}"

            await page.goto(course_url)
            await page.wait_for_load_state("load")
            await asyncio.sleep(2.5)

            cnd = next_data(await page.content())
            children = cnd.get("props", {}).get("pageProps", {}).get("course", {}).get("children", [])

            print(f"\n[Course] {course_title} ({len(children)} lessons)")
            for i, child in enumerate(children):
                lesson = child.get("course", {})
                lesson_title = lesson.get("metadata", {}).get("title") or lesson.get("name") or "Untitled"
                lesson_id = lesson.get("id", "")
                idx = len(all_lessons)
                print(f"  [{idx:3d}] {lesson_title}")
                all_lessons.append((course_title, course_name, lesson_title, lesson_id))

        if inspect_index is not None and inspect_index < len(all_lessons):
            course_title, course_name, lesson_title, lesson_id = all_lessons[inspect_index]
            course_url = f"{classroom}/{course_name}"
            lesson_url = f"{course_url}?md={lesson_id}"
            print(f"\n\n--- Inspecting lesson [{inspect_index}]: {lesson_title} ---")
            await page.goto(lesson_url)
            await page.wait_for_load_state("load")
            await asyncio.sleep(3)

            lhtml = await page.content()
            lnd = next_data(lhtml)
            lpp = lnd.get("props", {}).get("pageProps", {})

            video = lpp.get("video")
            print(f"\nvideo field: {json.dumps(video, indent=2)[:2000] if video else 'null'}")

            # Check for transcript-like DOM elements
            for sel in ["[class*='transcript']", "[class*='Transcript']", "[class*='caption']",
                        "[class*='subtitle']", ".ProseMirror", "article"]:
                el = await page.query_selector(sel)
                if el:
                    inner = await el.inner_html()
                    if len(inner) > 50:
                        print(f"\nFound content at selector '{sel}' ({len(inner)} chars):")
                        print(inner[:500])
                        break

            DIAG.mkdir(parents=True, exist_ok=True)
            (DIAG / f"lesson_{inspect_index}.html").write_text(lhtml)
            await page.screenshot(path=str(DIAG / f"lesson_{inspect_index}.png"), full_page=True)
            print(f"\nSaved to {DIAG}/lesson_{inspect_index}.html")

        await browser.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("community")
    ap.add_argument("--inspect", type=int, default=None, help="Index of lesson to deep-inspect")
    args = ap.parse_args()
    asyncio.run(run(args.community, args.inspect))
