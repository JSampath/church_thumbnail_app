# Livestream Thumbnail Generator

Local web app that generates 1280×720 YouTube livestream thumbnails:
random background, your logo, title/occasion text, editable date & time,
a badge (e.g. an anniversary shield), a LIVE badge, and a Subscribe bar.
It's generic — not tied to any specific channel, organization, or church —
just fill in your own branding.

The core feature is the thumbnail generator above; everything in
**📅 Schedule on YouTube** is an entirely optional, separate add-on (see
below) that you only need if you also want this app to create the actual
scheduled live broadcast for you.

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
   are saved into `assets/` and `backgrounds/` so they persist across
   sessions.
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
5. If you want it, scroll down to **📅 Schedule on YouTube** — see the
   disclaimer and setup steps below before using it.

## Schedule on YouTube — optional, use at your own risk

This section is **not required** to generate or download thumbnails —
skip it entirely if that's all you need. If you *do* want it, it can
create a real scheduled YouTube Live broadcast (title, description,
schedule time, visibility, "made for kids", category, thumbnail, and
playlist) directly from the app, via the official YouTube Data API v3.

Important things to understand before turning it on:

- It only ever acts on **your own** YouTube channel, using **your own**
  Google Cloud project and OAuth credentials that *you* set up below.
  This app does not ship with, store, or have access to anyone's
  credentials — there is nothing "shared" or central about it.
- You are solely responsible for what gets created on your channel.
  Review the auto-filled title/description before clicking **Schedule
  Live Stream on YouTube**, the same way you'd review anything before
  publishing it yourself. Use this feature at your own risk.
- It requires a one-time setup per Google account, about 5 minutes, all
  inside Google's own console — no payment, no special access:

1. Go to [console.cloud.google.com](https://console.cloud.google.com/),
   create a project (any name), then **APIs & Services → Library** and
   enable **YouTube Data API v3**.
2. **APIs & Services → OAuth consent screen**: choose **External**, fill
   in just the required fields, and leave the publishing status as
   **Testing**. Under "Test users," add your own Google account's email —
   this avoids Google's app-review process, which isn't needed for
   personal use.
3. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID**, application type **Desktop app**. Download the resulting JSON
   and save it as `client_secret.json` directly inside this
   `church_thumbnail_app/` folder (same folder as `app.py`).
4. Run the app and open **📅 Schedule on YouTube** — it now shows the
   scheduling form. The first time you click **Schedule Live Stream on
   YouTube**, a browser tab opens to Google's real sign-in/consent page
   (since the app is in Testing mode, Google will show an "unverified
   app" warning — click **Continue** as the account you added as a test
   user). After signing in once, your session is cached in `token.json`
   and refreshed automatically; you won't be prompted again.

**What it sets automatically:** title (auto-filled from your hero word,
script line, the date you pick, and your organization/channel name —
editable before scheduling), description, scheduled date/time,
visibility, category (People & Blogs by default), "made for kids" = No,
the broadcast thumbnail (the image you just generated), stream-software
(RTMP) ingestion so starting/stopping OBS takes the stream live/offline
automatically, and adding the broadcast to a playlist (default "Live
Streams," created automatically if it doesn't exist yet).

**What it can't set:** the live-chat panel settings and the "Reactions"
toggle. Google's public API doesn't expose either one — they only exist
in YouTube Studio's web UI. In practice YouTube carries over whatever you
last set for these on your channel, so they typically only need a
one-time check in Studio rather than a per-stream one.

**Keep `client_secret.json` and `token.json` private** — don't share or
commit either file; both grant access to your YouTube channel.

## Project files

- `app.py` — Streamlit UI.
- `thumbnail_generator.py` — all image-compositing logic (no UI code);
  can also be run directly (`python3 thumbnail_generator.py`) to drop a
  `_preview.png` using the default config, for quick testing.
- `youtube_scheduler.py` — OAuth sign-in and YouTube Data API v3 calls
  behind the optional "Schedule on YouTube" section (no UI code).
- `build_backgrounds.py` — one-off script that generated the 8 starter
  gradient/bokeh backgrounds in `backgrounds/`. Re-run any time for more
  variety, or just drop your own `.jpg`/`.png` photos into that folder.
- `build_default_logo.py` — one-off script that generated the generic
  placeholder logo at `assets/logo.png`. Upload your real logo from the
  app's sidebar to replace it — no need to re-run this script unless you
  want to regenerate the placeholder.
- `fonts/` — bundled display/script/body fonts used for all text.

## Notes

- Backgrounds and the logo placeholder are already generated and
  included, so the app works out of the box. Replace them with your own
  real photos/logo whenever you're ready.
- The Subscribe bar text/handle and badge fields are fully editable from
  the sidebar/form — nothing is hardcoded beyond the placeholder defaults
  shown when the app first loads.
- Uploads and generated files are saved locally to disk (`assets/`,
  `backgrounds/`, `fonts/`, plus `client_secret.json`/`token.json` if you
  use the YouTube feature). If you ever deploy this somewhere other than
  your own machine, remember that storage and the Google sign-in popup
  both currently assume a single local user — see the comments at the
  top of `app.py` and `youtube_scheduler.py` before adapting it for a
  shared, multi-user deployment.
