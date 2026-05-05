# skool-lesson-scrape

Download lessons from any Skool community classroom to local Markdown files.

- Works on Mac, Windows, and Linux
- Skips lessons already saved — safe to re-run when new content is added
- Saves one `.md` file per lesson: `Course Name -- Lesson Title.md`
- Respects your membership tier — only downloads content your account can access
- Works great with Obsidian, Notion, or any Markdown-based knowledge system

---

## Requirements

- Python 3.8 or later
- A paid Skool account with access to the community you want to scrape

---

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Configure the script**

Open `scrape.py` and edit the two lines at the top of the CONFIG section:

```python
COMMUNITY  = "navaigate"          # slug from your Skool community URL
OUTPUT_DIR = Path.home() / "skool-lessons"   # where .md files are saved
```

- `COMMUNITY`: find it in your Skool URL — `skool.com/your-community-slug`
- `OUTPUT_DIR`: any folder on your machine; created automatically if it doesn't exist

**Obsidian users** — point `OUTPUT_DIR` at a folder inside your vault:
```python
OUTPUT_DIR = Path.home() / "Documents" / "MyVault" / "Lessons"
```

**Windows users** — use a raw string for backslash paths:
```python
OUTPUT_DIR = Path(r"C:\Users\YourName\Documents\skool-lessons")
```

---

## Usage

**Full scrape** — downloads all lessons you have access to:
```bash
python scrape.py
```

A browser window will open. Log in to Skool normally (email/password or Google). The script takes over automatically once you land on the community.

**Re-run anytime** — already-saved lessons are skipped automatically.

**Debug mode** — inspect page structure without saving anything:
```bash
python scrape.py --discover
```

---

## How it works

Skool embeds course and lesson structure as JSON in the page source (`__NEXT_DATA__`). The script reads that directly to get course and lesson IDs, then navigates to each lesson and extracts the body text from Skool's TipTap editor (`.ProseMirror` selector). No fragile DOM scraping — the JSON structure is stable.

---

## Notes

- Content is gated by your own Skool membership — you can only download lessons your account has access to
- This tool is for personal offline backup, not redistribution of community content
- Re-running after new lessons are posted will only download what's new

---

## Troubleshooting

**"No courses found"** — a diagnostic HTML file is saved to your system temp folder. The page structure may have changed; open an issue with the HTML attached.

**Browser closes immediately** — make sure you completed the Playwright browser install: `playwright install chromium`

**Lessons saving as navigation boilerplate** — run `--discover` and open an issue with the output.

---

Built by [Kisa Fenn](https://github.com/kisasttil-gif) — STTIL Solutions
