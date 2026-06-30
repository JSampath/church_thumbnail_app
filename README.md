# Livestream Thumbnail Generator

Local web app that generates 1280×720 YouTube livestream thumbnails:
random background, your logo, title/occasion text, editable date & time,
a badge (e.g. an anniversary shield), a LIVE badge, and a Subscribe bar.
It's generic — not tied to any specific channel, organization, or church —
just fill in your own branding and download.

## Setup

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

1. **Sidebar** — upload your own logo (PNG with transparent background
   works best) and any photos you want in the background rotation. Both
   stay private to your browser session for as long as it's open (see
   "Multiple users" below). Click "Remove logo" to go back to the
   placeholder.
2. **Form** — edit the title (your organization or channel name),
   occasion text, date/time, badge fields, and YouTube handle. Toggle
   the badge, LIVE badge, and Subscribe bar on/off as needed.
   - For the badge, you can either let the app generate one from the
     year/number/caption fields, or upload your own ready-made badge
     graphic (e.g. a designed "52 Years" shield) in the form. Just like
     the logo, an uploaded badge is used automatically — no extra toggle
     needed — and is scaled to fit the same spot. Click "Remove badge"
     to go back to the auto-generated version.
   - Pick a font for the title, hero word, script lines, and body text
     from the sidebar's "Fonts" section, or upload your own `.ttf`/
     `.otf` files to add new choices.
3. Click **Generate Thumbnail**. A photo you just uploaded is
   auto-selected in the background dropdown (with a small preview) so
   it's clear it'll actually be used — switch back to "Random" for a
   different photo each time, or pin any other one.
4. Pick PNG or JPEG (with a quality slider) and click **Download**.

That's it — there's no sign-in, no setup beyond the steps above, and
nothing leaves your machine. The app only generates and downloads images.

## Project files

- `app.py` — Streamlit UI.
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
