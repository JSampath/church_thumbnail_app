# Livestream Thumbnail Generator

Local web app that generates 1280×720 YouTube livestream thumbnails:
random background, your logo, title/occasion text, editable date & time,
a badge (e.g. an anniversary shield), a LIVE badge, and a Subscribe bar.
It's generic — not tied to any specific channel, organization, or church —
just fill in your own branding and download.

## Quick start (no typing)

* **Windows:** double-click **`Start Thumbnail Generator.bat`**.
* **macOS / Linux:** run `./start.sh`.

The first time, it sets itself up (about a minute, needs internet), then the
app opens in your browser. You need Python 3.10 or newer from
[python.org](https://www.python.org/downloads/) — on Windows tick
*"Add python.exe to PATH"* while installing. Keep the black window open
while you use the app; close it when you're done.

## Setup (by hand)

**macOS / Linux:**

```bash
cd church_thumbnail_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
cd church_thumbnail_app
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script with an execution-policy
error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
first, or skip activation and call `venv\Scripts\python.exe` directly
in the commands below.

## Run

**macOS / Linux:**

```bash
streamlit run app.py
```

**Windows (PowerShell):**

```powershell
python -m streamlit run app.py
```

Using `python -m streamlit` (instead of the bare `streamlit` command)
avoids "not recognized" errors on Windows even if the venv's Scripts
folder isn't on PATH.

This opens the app in your browser (usually `http://localhost:8501`).

## Using it

The preview on the right redraws as you type — there's no Generate button.

1. **Pick a template** at the top (Sunday worship, Anniversary, Christmas,
   Good Friday, Easter, Wedding, Prayer meeting, Youth night). It fills in
   the headline, colours and start time; change anything afterwards.
2. **Text tab** — your organization name, the small line under it, the big
   word and the handwritten line.
3. **Date & time tab** — pick the date and time from a calendar and clock,
   and choose how they're written (*1st November 2026*, *Sunday, 1 November
   2026*, *01-11-2026* …). Switch on *Type the date and time myself* for
   free wording such as "Every Sunday" or a Telugu date.
4. **Badges tab** — the anniversary shield (it can count the years for you
   from the year you started), the LIVE badge and the Subscribe bar, each
   with editable wording. Upload a ready-made badge image to use instead of
   the drawn shield.
5. **Look tab** — colour palettes or your own three colours, a *Darken the
   photo* slider for busy backgrounds, and a font for each kind of text.
   Upload `.ttf`/`.otf` files to add fonts (marked ⭐).
6. **Background tab** — click *Use* under any photo, upload your own (the
   last one you add is used straight away), or press **Shuffle**.
7. Choose **PNG** or **JPEG** and press **Download**. The app warns you if
   the file is over YouTube's 2 MB limit. *How it looks on YouTube* shows
   the thumbnail at phone size, and *Suggested video title* gives a title
   you can copy.

**Sidebar** — upload your logo, set your YouTube handle, and use
**Save settings** to keep everything in a small `.json` file you can
**Load** again next week. **Start over** resets every field.

That's it — there's no sign-in, and nothing leaves your machine.

## Project files

- `Start Thumbnail Generator.bat` / `start.sh` — one-click start (sets up on first run).
- `app.py` — Streamlit UI.
- `.streamlit/config.toml` — the app's colours and fonts.
- `thumbnail_generator.py` — all image-compositing logic (no UI code);
  can also be run directly (`python3 thumbnail_generator.py`) to drop a
  `_preview.png` using the default config, for quick testing.
- `build_backgrounds.py` — one-off script that generated the 8 starter
  gradient/bokeh backgrounds in `backgrounds/`. Re-run any time for more
  variety, or just drop your own `.jpg`/`.png` photos into that folder.
- `build_default_logo.py` — one-off script that generated the generic
  placeholder logo at `assets/logo.png`. Upload your real logo from the
  app's sidebar to replace it — no need to re-run this script unless you
  want to regenerate the placeholder.
- `fonts/` — bundled display/script/body fonts used for all text.

## Multiple users

If you run this app as one shared instance for several people (e.g. host
it on a server and send people the link), each visitor's browser session
gets its own private storage folder. A logo, badge, background photo, or
font that one visitor uploads is only ever used for their own session —
no other visitor will see it. The 8 bundled stock backgrounds, bundled
fonts, and the generic placeholder logo are the only things everyone
shares.

Session uploads live in a temp folder and are cleaned up automatically
after about a day of inactivity (or whenever the machine clears its temp
directory) — there's nothing to manage by hand.

## Notes

- Backgrounds and the logo placeholder are already generated and
  included, so the app works out of the box. Replace them with your own
  real photos/logo whenever you're ready.
- The Subscribe bar text/handle and badge fields are fully editable from
  the sidebar/form — nothing is hardcoded beyond the placeholder defaults
  shown when the app first loads.
- Uploads are saved to a private, per-session temp folder (see "Multiple
  users" above); the bundled stock assets live in `assets/`,
  `backgrounds/`, `fonts/`. Nothing is uploaded anywhere or shared with
  any third party — everything stays on the machine running the app.
