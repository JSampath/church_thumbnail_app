"""
app.py
------
Streamlit UI for a generic livestream thumbnail generator -- not tied to
any specific channel, organization, or church. Anyone can fill in their
own branding and get a 1280x720 thumbnail in seconds.

Run with:   python -m streamlit run app.py

What's new in this version
  * Live preview: the thumbnail redraws as you type -- no Generate button.
  * Templates (Sunday worship, anniversary, Christmas, ...) fill everything
    in with one click.
  * Real date and time pickers, with a choice of date styles; the
    anniversary number can count itself from the start year.
  * Theme colour pickers and ready-made colour palettes.
  * Background gallery with one-click selection and a Shuffle button.
  * Save your settings to a small file and load them again next week.
  * "How it looks on YouTube" small-size check and a suggested video title.

All image work lives in thumbnail_generator.py; this file only collects
user input, keeps uploaded assets on disk, and shows the preview.

Multi-user note: everything a visitor uploads (logo, badge, background
photos, fonts) is saved under a folder unique to THEIR browser session,
never into the shared assets/backgrounds/fonts folders bundled with the
app (see "Multiple users" in README.md).
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import random
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict

import streamlit as st

from thumbnail_generator import (
    ASSETS_DIR,
    BACKGROUNDS_DIR,
    FONT_BODY,
    FONT_HERO,
    FONT_SCRIPT,
    FONT_TITLE,
    FONTS_DIR,
    ThumbnailConfig,
    generate_thumbnail,
    list_backgrounds,
    list_fonts,
)

st.set_page_config(
    page_title="Livestream Thumbnail Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

for _d in (ASSETS_DIR, BACKGROUNDS_DIR, FONTS_DIR):
    os.makedirs(_d, exist_ok=True)

# --------------------------------------------------------------------------
# Per-session, private storage
# --------------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:16]

SESSION_ROOT = os.path.join(tempfile.gettempdir(), "thumbnail_app_sessions")
SESSION_DIR = os.path.join(SESSION_ROOT, st.session_state.session_id)
SESSION_BG_DIR = os.path.join(SESSION_DIR, "backgrounds")
SESSION_FONTS_DIR = os.path.join(SESSION_DIR, "fonts")
os.makedirs(SESSION_BG_DIR, exist_ok=True)
os.makedirs(SESSION_FONTS_DIR, exist_ok=True)
os.utime(SESSION_DIR, None)  # mark this session folder as recently active

DEFAULT_LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")  # shared placeholder
LOGO_PATH = os.path.join(SESSION_DIR, "logo.png")  # this visitor's own upload
BADGE_PATH = os.path.join(SESSION_DIR, "anniversary_badge.png")


def _cleanup_old_sessions(max_age_hours: float = 24) -> None:
    """Best-effort removal of session folders from visitors who left a while
    ago, so disk use stays bounded on a shared deployment. Never raises."""
    try:
        cutoff = time.time() - max_age_hours * 3600
        for name in os.listdir(SESSION_ROOT):
            path = os.path.join(SESSION_ROOT, name)
            if name != st.session_state.session_id and os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


if "_did_cleanup" not in st.session_state:
    _cleanup_old_sessions()
    st.session_state._did_cleanup = True


# --------------------------------------------------------------------------
# Defaults, templates and colour palettes
# --------------------------------------------------------------------------
def _next_sunday(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return today + dt.timedelta(days=(6 - today.weekday()) % 7 or 7)


DEFAULTS: dict = {
    # text
    "title": "YOUR ORGANIZATION NAME",
    "presented_by": "Presents",
    "hero_line": "LIVE",
    "script_line": "Stream",
    # date & time
    "event_date": _next_sunday(),
    "event_time": dt.time(9, 30),
    "date_style": "ordinal",
    "time_style": "12h",
    "time_suffix": "onwards",
    "custom_datetime": False,
    "date_text_custom": "28th June 2026",
    "time_text_custom": "09:30 AM onwards",
    # badge
    "show_anniversary": False,
    "ann_start_year": 1974,
    "ann_auto": True,
    "ann_number_custom": "52",
    "ann_caption": "Years",
    "ribbon_text": "ANNIVERSARY",
    # branding / youtube
    "show_logo": True,
    "show_live_badge": True,
    "live_label": "LIVE",
    "show_subscribe_bar": True,
    "youtube_handle": "@yourchannel",
    "subscribe_label": "SUBSCRIBE",
    # look
    "primary_color": "#101e4a",
    "accent_color": "#f4c442",
    "highlight_color": "#d12127",
    "background_dim": 0,
    "font_title": FONT_TITLE,
    "font_hero": FONT_HERO,
    "font_script": FONT_SCRIPT,
    "font_body": FONT_BODY,
    # output
    "file_format": "PNG",
    "jpeg_quality": 92,
}

PALETTES: dict[str, tuple[str, str, str]] = {
    "Royal gold": ("#101e4a", "#f4c442", "#d12127"),
    "Christmas": ("#0f3d2e", "#f4c442", "#c8102e"),
    "Lent purple": ("#2b1a3d", "#d9c3ff", "#8e2b3b"),
    "Easter dawn": ("#1b4d3e", "#ffd166", "#e76f51"),
    "Ocean": ("#0b2545", "#7ee0e6", "#ef476f"),
    "Rose": ("#3b2a4a", "#f5d7a1", "#c0587e"),
    "Classic white": ("#111111", "#ffffff", "#e10600"),
}

# Each template only sets the fields it cares about.
TEMPLATES: dict[str, dict] = {
    "⛪ Sunday worship": dict(
        hero_line="SUNDAY", script_line="Worship Service", presented_by="Presents",
        show_anniversary=False, palette="Royal gold", event_time=dt.time(9, 30),
    ),
    "🎉 Anniversary": dict(
        hero_line="ANNIVERSARY", script_line="Thanksgiving Service", presented_by="Celebrates",
        show_anniversary=True, ribbon_text="ANNIVERSARY", ann_caption="Years", palette="Royal gold",
    ),
    "🎄 Christmas": dict(
        hero_line="CHRISTMAS", script_line="Carol Service", presented_by="Presents",
        show_anniversary=False, palette="Christmas", event_time=dt.time(18, 30),
    ),
    "✝️ Good Friday": dict(
        hero_line="GOOD FRIDAY", script_line="Meditation Service", presented_by="Presents",
        show_anniversary=False, palette="Lent purple", background_dim=25, event_time=dt.time(12, 0),
    ),
    "🌅 Easter": dict(
        hero_line="EASTER", script_line="Sunrise Service", presented_by="Presents",
        show_anniversary=False, palette="Easter dawn", event_time=dt.time(5, 30),
    ),
    "💍 Wedding": dict(
        hero_line="WEDDING", script_line="Holy Matrimony", presented_by="Invites you to the",
        show_anniversary=False, palette="Rose", event_time=dt.time(11, 0),
    ),
    "🙏 Prayer meeting": dict(
        hero_line="PRAYER", script_line="Meeting", presented_by="Presents",
        show_anniversary=False, palette="Ocean", event_time=dt.time(19, 0),
    ),
    "🔥 Youth night": dict(
        hero_line="YOUTH", script_line="Fellowship Night", presented_by="Presents",
        show_anniversary=False, palette="Ocean", event_time=dt.time(18, 0),
    ),
}

# Keys written to / read from a saved settings file.
SETTINGS_KEYS = [k for k in DEFAULTS if k not in ("file_format", "jpeg_quality")]

# Re-assigning every value on each run keeps it even while its widget is
# hidden (e.g. the badge fields when the badge is switched off) -- Streamlit
# otherwise forgets the value of any widget that isn't drawn.
for _k, _v in DEFAULTS.items():
    st.session_state[_k] = st.session_state.get(_k, _v)
st.session_state.setdefault("bg_path", None)
st.session_state.setdefault("uploader_v", {"logo": 0, "badge": 0, "bg": 0, "font": 0, "settings": 0})


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _font_label(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    label = name.replace("-", " ").replace("_", " ")
    return f"⭐ {label}" if os.path.dirname(path) == SESSION_FONTS_DIR else label


def _list_images(directory: str) -> list[str]:
    exts = (".jpg", ".jpeg", ".png", ".webp")
    if not os.path.isdir(directory):
        return []
    return sorted(os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(exts))


def _all_backgrounds() -> list[str]:
    return _list_images(SESSION_BG_DIR) + list_backgrounds()


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


DATE_STYLES = {
    "ordinal": lambda d: f"{_ordinal(d.day)} {d:%B %Y}",
    "weekday": lambda d: f"{d:%A}, {d.day} {d:%B %Y}",
    "short": lambda d: f"{d:%a} {d.day} {d:%b %Y}",
    "numeric": lambda d: f"{d:%d-%m-%Y}",
}
TIME_STYLES = {
    "12h": lambda t: t.strftime("%I:%M %p"),
    "12h-short": lambda t: f"{t.hour % 12 or 12}:{t:%M} {'am' if t.hour < 12 else 'pm'}",
    "24h": lambda t: t.strftime("%H:%M"),
}


def _date_text() -> str:
    if st.session_state.custom_datetime:
        return st.session_state.date_text_custom
    d = st.session_state.event_date or dt.date.today()
    return DATE_STYLES[st.session_state.date_style or "ordinal"](d)


def _time_text() -> str:
    if st.session_state.custom_datetime:
        return st.session_state.time_text_custom
    t = st.session_state.event_time
    if t is None:
        return ""
    text = TIME_STYLES[st.session_state.time_style or "12h"](t)
    suffix = (st.session_state.time_suffix or "").strip()
    return f"{text} {suffix}".strip()


def _event_year() -> int:
    d = st.session_state.event_date
    return d.year if isinstance(d, dt.date) else dt.date.today().year


def _ensure_background() -> None:
    """Keep the preview stable: always remember one concrete background."""
    bgs = _all_backgrounds()
    if st.session_state.bg_path not in bgs:
        st.session_state.bg_path = random.choice(bgs) if bgs else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "thumbnail"


# --------------------------------------------------------------------------
# Callbacks (they run before the page redraws, so they can safely change
# widget values)
# --------------------------------------------------------------------------
def _bump(name: str) -> None:
    st.session_state.uploader_v[name] += 1


def cb_apply_template() -> None:
    choice = st.session_state.get("template_pick")
    if not choice:
        return
    tpl = dict(TEMPLATES[choice])
    palette = tpl.pop("palette", None)
    if palette:
        cb_apply_palette(palette)
    for k, v in tpl.items():
        st.session_state[k] = v
    st.toast(f"Template applied: {choice}", icon=":material/auto_awesome:")


def cb_apply_palette(name: str | None = None) -> None:
    name = name or st.session_state.get("palette_pick")
    if not name:
        return
    p, a, h = PALETTES[name]
    st.session_state.primary_color, st.session_state.accent_color, st.session_state.highlight_color = p, a, h


def cb_save_upload(kind: str, key: str) -> None:
    up = st.session_state.get(key)
    if not up:
        return
    files = up if isinstance(up, list) else [up]
    if kind == "logo":
        with open(LOGO_PATH, "wb") as f:
            f.write(files[0].getbuffer())
        st.session_state.show_logo = True
        st.toast("Logo saved — it's on the thumbnail now.", icon=":material/check_circle:")
    elif kind == "badge":
        with open(BADGE_PATH, "wb") as f:
            f.write(files[0].getbuffer())
        st.session_state.show_anniversary = True
        st.toast("Badge image saved — it replaces the drawn shield.", icon=":material/check_circle:")
    elif kind == "bg":
        last = None
        for uf in files:
            last = os.path.join(SESSION_BG_DIR, os.path.basename(uf.name))
            with open(last, "wb") as f:
                f.write(uf.getbuffer())
        st.session_state.bg_path = last
        st.toast(f"Added {len(files)} photo(s) — the last one is now the background.", icon=":material/image:")
    elif kind == "font":
        for uf in files:
            with open(os.path.join(SESSION_FONTS_DIR, os.path.basename(uf.name)), "wb") as f:
                f.write(uf.getbuffer())
        st.toast(f"Added {len(files)} font(s) — pick them in the font lists (marked ⭐).", icon=":material/font_download:")
    _bump(kind)  # fresh, empty uploader so removing later really sticks


def cb_remove(path: str, kind: str) -> None:
    try:
        os.remove(path)
    except OSError as e:
        st.toast(f"Couldn't remove the file: {e}", icon=":material/error:")
        return
    _bump(kind)


def cb_clear_my_backgrounds() -> None:
    for p in _list_images(SESSION_BG_DIR):
        try:
            os.remove(p)
        except OSError:
            pass
    st.session_state.bg_path = None


def cb_pick_background(path: str) -> None:
    st.session_state.bg_path = path


def cb_shuffle() -> None:
    bgs = _all_backgrounds()
    others = [p for p in bgs if p != st.session_state.bg_path] or bgs
    st.session_state.bg_path = random.choice(others) if others else None


def cb_reset_all() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.template_pick = None
    st.session_state.palette_pick = None
    st.toast("Everything is back to the starting values.", icon=":material/restart_alt:")


def cb_load_settings(key: str) -> None:
    up = st.session_state.get(key)
    if not up:
        return
    try:
        data = json.loads(up.getvalue().decode("utf-8"))
        for k in SETTINGS_KEYS:
            if k not in data:
                continue
            v = data[k]
            if k == "event_date" and v:
                v = dt.date.fromisoformat(v)
            elif k == "event_time" and v:
                v = dt.time.fromisoformat(v)
            elif k.startswith("font_") and not (isinstance(v, str) and os.path.isfile(v)):
                v = DEFAULTS[k]  # font from another computer -> use the default
            st.session_state[k] = v
        st.toast("Settings loaded.", icon=":material/upload_file:")
    except Exception as e:  # noqa: BLE001 - show any problem to the user
        st.toast(f"That file couldn't be read as saved settings ({e}).", icon=":material/error:")
    _bump("settings")


def _settings_json() -> bytes:
    out = {}
    for k in SETTINGS_KEYS:
        v = st.session_state.get(k)
        if isinstance(v, (dt.date, dt.time)):
            v = v.isoformat()
        out[k] = v
    out["_app"] = "Livestream Thumbnail Generator"
    return json.dumps(out, indent=2).encode("utf-8")


# --------------------------------------------------------------------------
# Rendering (cached, so unchanged settings don't redraw the image)
# --------------------------------------------------------------------------
def _mtime(path: str | None) -> float:
    try:
        return os.path.getmtime(path) if path else 0.0
    except OSError:
        return 0.0


@st.cache_data(max_entries=24, show_spinner=False)
def _render(cfg_dict: dict, _stamp: tuple) -> bytes:
    img = generate_thumbnail(ThumbnailConfig(**cfg_dict))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_config() -> ThumbnailConfig:
    s = st.session_state
    logo_path = LOGO_PATH if os.path.isfile(LOGO_PATH) else (
        DEFAULT_LOGO_PATH if os.path.isfile(DEFAULT_LOGO_PATH) else None
    )
    year = _event_year()
    start = int(s.ann_start_year or year)
    number = str(max(0, year - start)) if s.ann_auto else s.ann_number_custom
    return ThumbnailConfig(
        title=s.title or "YOUR ORGANIZATION NAME",
        presented_by=s.presented_by,
        hero_line=s.hero_line,
        script_line=s.script_line,
        date_text=_date_text(),
        time_text=_time_text(),
        show_anniversary=s.show_anniversary,
        anniversary_start_year=str(start),
        anniversary_end_year=str(year),
        anniversary_number=number,
        anniversary_caption=s.ann_caption,
        anniversary_badge_path=BADGE_PATH if os.path.isfile(BADGE_PATH) else None,
        show_live_badge=s.show_live_badge,
        show_subscribe_bar=s.show_subscribe_bar,
        youtube_handle=s.youtube_handle,
        logo_path=logo_path,
        background_path=s.bg_path,
        font_title=s.font_title,
        font_hero=s.font_hero,
        font_script=s.font_script,
        font_body=s.font_body,
        primary_color=s.primary_color,
        accent_color=s.accent_color,
        highlight_color=s.highlight_color,
        background_dim=int(s.background_dim),
        show_logo=s.show_logo,
        live_label=s.live_label,
        subscribe_label=s.subscribe_label,
        ribbon_text=s.ribbon_text,
    )


# --------------------------------------------------------------------------
# A little styling: sticky preview, softer cards
# --------------------------------------------------------------------------
st.html(
    """
<style>
  .block-container { padding-top: 2.2rem; }
  /* keep the preview in view while scrolling the long settings column */
  @media (min-width: 900px) {
    .stColumn:has(.st-key-preview_panel) { position: sticky; top: 3.75rem; align-self: flex-start; }
  }
  .st-key-preview_panel img { border-radius: 12px; box-shadow: 0 18px 38px -22px rgba(16,30,74,.55); }
  .st-key-bg_gallery img { border-radius: 8px; }
  .st-key-steps p { margin: 0; }
</style>
"""
)

# --------------------------------------------------------------------------
# Sidebar: branding, fonts, saved settings
# --------------------------------------------------------------------------
_ensure_background()
v = st.session_state.uploader_v

with st.sidebar:
    st.subheader(":material/verified: Your branding")
    st.caption("Uploads stay private to your browser session.")

    has_logo = os.path.isfile(LOGO_PATH)
    with st.container(border=True):
        logo_show_path = LOGO_PATH if has_logo else (DEFAULT_LOGO_PATH if os.path.isfile(DEFAULT_LOGO_PATH) else None)
        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        with c1:
            if logo_show_path:
                st.image(_read_bytes(logo_show_path), width=64)
        with c2:
            st.markdown("**Your logo**" if has_logo else "**Placeholder logo**")
            if has_logo:
                st.button("Remove", icon=":material/delete:", type="tertiary",
                          on_click=cb_remove, args=(LOGO_PATH, "logo"), key="rm_logo")
        st.file_uploader(
            "Upload logo", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed",
            key=f"up_logo_{v['logo']}", on_change=cb_save_upload, args=("logo", f"up_logo_{v['logo']}"),
            help="A PNG with a transparent background looks best.",
        )
        st.toggle("Show logo on the thumbnail", key="show_logo")

    st.text_input("YouTube handle", key="youtube_handle", icon=":material/alternate_email:",
                  placeholder="@yourchannel")

    st.divider()
    st.subheader(":material/save: Save for next time")
    st.caption("Keep your text, colours and fonts in a small file, and load it again next week.")
    st.download_button(
        "Save settings", data=_settings_json(), file_name="thumbnail-settings.json",
        mime="application/json", icon=":material/download:", on_click="ignore", width="stretch",
    )
    with st.popover("Load settings", icon=":material/upload_file:", width="stretch"):
        st.file_uploader(
            "Settings file (.json)", type=["json"], key=f"up_settings_{v['settings']}",
            on_change=cb_load_settings, args=(f"up_settings_{v['settings']}",),
        )
    st.button("Start over", icon=":material/restart_alt:", on_click=cb_reset_all, width="stretch",
              help="Put every field back to its starting value (your uploads are kept).")

    st.divider()
    with st.expander("How to use", icon=":material/help:"):
        st.markdown(
            "1. **Pick a template** at the top, or start from scratch.\n"
            "2. **Change the words** in the *Text* tab and set the **date & time**.\n"
            "3. Try **🎲 Shuffle** or choose a photo in the *Background* tab.\n"
            "4. Press **Download**. Upload it in YouTube Studio → your live stream → *Thumbnail*.\n\n"
            "What you upload is kept only for your own session and is deleted after about a day."
        )
    with st.expander("Terms of use", icon=":material/gavel:"):
        st.markdown(
            "- This app is **free and provided as is**, without any warranty.\n"
            "- **You are responsible** for the logos, photos, names and words you use, and for how you "
            "use the thumbnails. Only use material you own or have permission to use, and don't use the "
            "app to imitate another person, church or organization.\n"
            "- Thumbnails must follow **YouTube's Community Guidelines** and the law where you live.\n"
            "- SJ Tech Solutions is **not responsible** for content made with this app or for any loss "
            "arising from its use.\n\n"
            "[Full terms](https://github.com/JSampath/church_thumbnail_app/blob/main/TERMS.md) · "
            "[MIT License](https://github.com/JSampath/church_thumbnail_app/blob/main/LICENSE) · "
            "[Font licenses](https://github.com/JSampath/church_thumbnail_app/blob/main/fonts/LICENSES.txt)"
        )
    st.caption("By using this app you agree to the terms of use. © 2026 SJ Tech Solutions")

# --------------------------------------------------------------------------
# Header + templates
# --------------------------------------------------------------------------
st.title("🎬 Livestream Thumbnail Generator")
st.caption("Make a 1280 × 720 YouTube thumbnail for your next service or event — it updates as you type.")

st.pills(
    "Start from a template",
    options=list(TEMPLATES),
    key="template_pick",
    on_change=cb_apply_template,
    help="Fills in the headline, colours and time for you. You can change anything afterwards.",
)

col_form, col_preview = st.columns([1, 1.25], gap="large", vertical_alignment="top")

# --------------------------------------------------------------------------
# Settings column
# --------------------------------------------------------------------------
with col_form:
    t_text, t_date, t_badges, t_look, t_bg = st.tabs(
        [":material/title: Text", ":material/event: Date & time", ":material/workspace_premium: Badges",
         ":material/palette: Look", ":material/image: Background"]
    )

    # ---- Text -------------------------------------------------------------
    with t_text:
        st.text_input("Main title", key="title", help="Your church, organization or channel name.",
                      placeholder="YOUR ORGANIZATION NAME")
        st.text_input("Small line under the title", key="presented_by", placeholder="Presents")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Big word", key="hero_line", help="Shown very large at the bottom left.",
                          placeholder="SUNDAY")
        with c2:
            st.text_input("Handwritten line", key="script_line", help="The cursive line under the big word.",
                          placeholder="Worship Service")

    # ---- Date & time ------------------------------------------------------
    with t_date:
        custom = st.toggle("Type the date and time myself", key="custom_datetime",
                           help="Use this for wording like 'Every Sunday' or a Telugu date.")
        if custom:
            st.text_input("Date line", key="date_text_custom")
            st.text_input("Time line", key="time_text_custom")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.date_input("Date", key="event_date", format="DD/MM/YYYY")
            with c2:
                st.time_input("Start time", key="event_time", step=dt.timedelta(minutes=15))
            sample_d = st.session_state.event_date or dt.date.today()
            st.segmented_control(
                "Date style", options=list(DATE_STYLES), key="date_style", required=True,
                format_func=lambda k: DATE_STYLES[k](sample_d),
            )
            sample_t = st.session_state.event_time or dt.time(9, 30)
            c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
            with c1:
                st.segmented_control(
                    "Time style", options=list(TIME_STYLES), key="time_style", required=True,
                    format_func=lambda k: TIME_STYLES[k](sample_t),
                )
            with c2:
                st.text_input("Word after the time", key="time_suffix", placeholder="onwards")
        st.caption(f"Will show: **{_date_text() or '—'}** · **{_time_text() or '—'}**")

    # ---- Badges -----------------------------------------------------------
    with t_badges:
        with st.container(border=True):
            st.toggle("Anniversary badge", key="show_anniversary", help="The shield at the top right.")
            if st.session_state.show_anniversary:
                has_badge = os.path.isfile(BADGE_PATH)
                if has_badge:
                    c1, c2 = st.columns([1, 3], vertical_alignment="center")
                    with c1:
                        st.image(_read_bytes(BADGE_PATH), width=70)
                    with c2:
                        st.markdown("Using **your badge image**.")
                        st.button("Remove and draw the shield again", icon=":material/delete:", type="tertiary",
                                  on_click=cb_remove, args=(BADGE_PATH, "badge"), key="rm_badge")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.number_input("Started in (year)", min_value=1800, max_value=2100, step=1,
                                        key="ann_start_year")
                    with c2:
                        st.text_input("Word under the number", key="ann_caption")
                    st.toggle(f"Count the years for me (up to {_event_year()})", key="ann_auto")
                    if st.session_state.ann_auto:
                        n = max(0, _event_year() - int(st.session_state.ann_start_year or _event_year()))
                        st.badge(f"{n} {st.session_state.ann_caption or 'years'}", icon=":material/cake:",
                                 color="orange")
                    else:
                        st.text_input("Number on the badge", key="ann_number_custom")
                    st.text_input("Ribbon text", key="ribbon_text", placeholder="ANNIVERSARY",
                                  help="E.g. JUBILEE, GOLDEN JUBILEE, DEDICATION")
                with st.expander("Use my own badge image instead", icon=":material/upload:"):
                    st.file_uploader(
                        "Badge image", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed",
                        key=f"up_badge_{v['badge']}", on_change=cb_save_upload,
                        args=("badge", f"up_badge_{v['badge']}"),
                        help="A transparent PNG looks best. It's scaled to fit the same spot.",
                    )

        with st.container(border=True):
            c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
            with c1:
                st.toggle("LIVE badge", key="show_live_badge")
            with c2:
                st.text_input("Label", key="live_label", disabled=not st.session_state.show_live_badge,
                              label_visibility="collapsed", placeholder="LIVE")
        with st.container(border=True):
            c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
            with c1:
                st.toggle("Subscribe bar", key="show_subscribe_bar")
            with c2:
                st.text_input("Button text", key="subscribe_label",
                              disabled=not st.session_state.show_subscribe_bar,
                              label_visibility="collapsed", placeholder="SUBSCRIBE")
            st.caption("The handle shown in the bar is set in the sidebar.")

    # ---- Look -------------------------------------------------------------
    with t_look:
        st.pills("Colour palettes", options=list(PALETTES), key="palette_pick",
                 on_change=cb_apply_palette)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.color_picker("Outline & badge", key="primary_color")
        with c2:
            st.color_picker("Highlight text", key="accent_color")
        with c3:
            st.color_picker("LIVE & Subscribe", key="highlight_color")

        st.slider("Darken the photo", 0, 70, key="background_dim", format="%d%%",
                  help="Helps the words stand out on bright or busy photos.")

        st.markdown("**Fonts**")
        builtin_fonts = list_fonts()
        session_fonts = sorted(
            os.path.join(SESSION_FONTS_DIR, f) for f in os.listdir(SESSION_FONTS_DIR)
            if f.lower().endswith((".ttf", ".otf"))
        )
        fonts = builtin_fonts + session_fonts
        for k in ("font_title", "font_hero", "font_script", "font_body"):
            if st.session_state[k] not in fonts:
                st.session_state[k] = DEFAULTS[k] if DEFAULTS[k] in fonts else (fonts[0] if fonts else DEFAULTS[k])
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Title", fonts, key="font_title", format_func=_font_label)
            st.selectbox("Handwritten lines", fonts, key="font_script", format_func=_font_label)
        with c2:
            st.selectbox("Big word & badge number", fonts, key="font_hero", format_func=_font_label)
            st.selectbox("Date, time & labels", fonts, key="font_body", format_func=_font_label)
        with st.expander("Add your own fonts (.ttf / .otf)", icon=":material/font_download:"):
            st.file_uploader(
                "Font files", type=["ttf", "otf"], accept_multiple_files=True, label_visibility="collapsed",
                key=f"up_font_{v['font']}", on_change=cb_save_upload, args=("font", f"up_font_{v['font']}"),
                help="For example a Telugu font such as Ramabhadra or Mandali.",
            )

    # ---- Background -------------------------------------------------------
    with t_bg:
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        with c1:
            st.file_uploader(
                "Add your own photos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
                key=f"up_bg_{v['bg']}", on_change=cb_save_upload, args=("bg", f"up_bg_{v['bg']}"),
                help="The last photo you add becomes the background straight away.",
            )
        with c2:
            st.button("Shuffle", icon=":material/shuffle:", on_click=cb_shuffle, width="stretch",
                      key="shuffle_tab")

        mine = _list_images(SESSION_BG_DIR)
        all_bgs = mine + list_backgrounds()
        with st.container(key="bg_gallery"):
            cols = st.columns(4)
            for i, path in enumerate(all_bgs):
                with cols[i % 4]:
                    st.image(_read_bytes(path), width="stretch")
                    selected = path == st.session_state.bg_path
                    label = "Using" if selected else ("Mine" if path in mine else "Use")
                    st.button(
                        label, key=f"bg_{i}_{os.path.basename(path)}", width="stretch",
                        type="primary" if selected else "secondary",
                        icon=":material/check:" if selected else (":material/star:" if path in mine else None),
                        on_click=cb_pick_background, args=(path,),
                    )
        if mine:
            st.button(f"Remove my {len(mine)} photo(s)", icon=":material/delete:", type="tertiary",
                      on_click=cb_clear_my_backgrounds)

# --------------------------------------------------------------------------
# Preview column
# --------------------------------------------------------------------------
cfg = _build_config()
stamp = tuple(_mtime(p) for p in (cfg.logo_path, cfg.anniversary_badge_path, cfg.background_path))
png_bytes = _render(asdict(cfg), stamp)

with col_preview:
    with st.container(key="preview_panel"):
        head_l, head_r = st.columns([2, 1], vertical_alignment="center")
        with head_l:
            st.subheader("Preview")
        with head_r:
            st.button("Shuffle photo", icon=":material/shuffle:", on_click=cb_shuffle,
                      width="stretch", key="shuffle_top", help="Try a different background photo")

        st.image(png_bytes, width="stretch")

        with st.container(horizontal=True, vertical_alignment="bottom", gap="small"):
            fmt = st.segmented_control("Format", ["PNG", "JPEG"], key="file_format", required=True,
                                       label_visibility="collapsed")
            if fmt == "JPEG":
                with st.popover("Quality", icon=":material/tune:"):
                    st.slider("JPEG quality", 60, 100, key="jpeg_quality",
                              help="Higher = sharper but a bigger file. YouTube allows up to 2 MB.")

            if fmt == "JPEG":
                from PIL import Image  # local import keeps start-up light

                out = io.BytesIO()
                Image.open(io.BytesIO(png_bytes)).convert("RGB").save(
                    out, format="JPEG", quality=int(st.session_state.jpeg_quality), optimize=True
                )
                data, mime, ext = out.getvalue(), "image/jpeg", "jpg"
            else:
                data, mime, ext = png_bytes, "image/png", "png"

            size_mb = len(data) / 1_048_576
            name = f"{_slug(cfg.hero_line + ' ' + cfg.script_line)}-{_slug(cfg.date_text)}.{ext}"
            st.download_button(
                f"Download {fmt}", data=data, file_name=name, mime=mime, type="primary",
                icon=":material/download:", on_click="ignore", width="stretch",
            )

        if size_mb > 2:
            st.warning(
                f"This file is {size_mb:.1f} MB. YouTube thumbnails must be under 2 MB — choose JPEG.",
                icon=":material/warning:",
            )
        else:
            st.caption(f"1280 × 720 · {size_mb * 1024:.0f} KB · ready for YouTube")

        with st.expander("How it looks on YouTube", icon=":material/smartphone:"):
            from PIL import Image

            big = Image.open(io.BytesIO(png_bytes))
            c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
            with c1:
                st.image(big.resize((360, 202), Image.LANCZOS), caption="Home page / TV")
            with c2:
                st.image(big.resize((168, 94), Image.LANCZOS), caption="Search on a phone")
            st.caption("If the words are hard to read at the small size, shorten them or darken the photo.")

        with st.expander("Suggested video title", icon=":material/subtitles:"):
            parts = [f"{cfg.hero_line.title()} {cfg.script_line}".strip(), cfg.date_text, cfg.title.title()]
            yt_title = " | ".join(p for p in parts if p)
            st.code(yt_title, language=None, wrap_lines=True)
            st.caption(f"{len(yt_title)} / 100 characters — use the copy button at the top right.")
