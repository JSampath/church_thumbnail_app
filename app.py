"""
app.py
------
Streamlit UI for a generic livestream thumbnail generator -- not tied to
any specific channel, organization, or church. Anyone can fill in their
own branding and generate a 1280x720 thumbnail in seconds.

Run with:   streamlit run app.py

All image work lives in thumbnail_generator.py; this file only collects
user input, persists uploaded assets to disk, and renders a live preview
with a download button.

Multi-user note: everything a visitor uploads (logo, anniversary badge,
their own background photos, their own fonts) is saved under a folder
unique to THEIR browser session, never into the shared assets/backgrounds/
fonts/ folders bundled with the app. That keeps one visitor's uploads from
ever appearing for someone else if this app is deployed as a single
shared instance for multiple people to use (see "Multiple users" in
README.md).
"""

import io
import os
import shutil
import tempfile
import time
import uuid

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

st.set_page_config(page_title="Livestream Thumbnail Generator", page_icon="🎬", layout="wide")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# Per-session, private storage -- see the multi-user note in the module
# docstring above. Each browser session gets its own folder under the
# system temp dir; nothing uploaded there is ever shown to a different
# session.
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

DEFAULT_LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")  # shared, read-only placeholder
LOGO_PATH = os.path.join(SESSION_DIR, "logo.png")  # this visitor's own upload, if any
ANNIVERSARY_BADGE_PATH = os.path.join(SESSION_DIR, "anniversary_badge.png")


def _cleanup_old_sessions(max_age_hours: float = 24) -> None:
    """Best-effort removal of session folders left behind by visitors who
    closed their tab a while ago, so disk usage stays bounded on a
    long-running shared deployment. Never raises -- a failed cleanup just
    leaves the old folder for next time."""
    try:
        cutoff = time.time() - max_age_hours * 3600
        for name in os.listdir(SESSION_ROOT):
            path = os.path.join(SESSION_ROOT, name)
            if (
                name != st.session_state.session_id
                and os.path.isdir(path)
                and os.path.getmtime(path) < cutoff
            ):
                shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


if "_did_cleanup" not in st.session_state:
    _cleanup_old_sessions()
    st.session_state._did_cleanup = True

if "last_image" not in st.session_state:
    st.session_state.last_image = None
if "last_bg" not in st.session_state:
    st.session_state.last_bg = None
if "bg_choice_select" not in st.session_state:
    st.session_state.bg_choice_select = "Random"
# Bumping these forces a brand-new (empty) file_uploader widget, which is
# the only reliable way to make "Remove logo" / "Remove badge" stick --
# file_uploader otherwise keeps returning the same uploaded file on every
# rerun, even after the file on disk has been deleted, and would just
# re-save it right back.
if "logo_uploader_version" not in st.session_state:
    st.session_state.logo_uploader_version = 0
if "badge_uploader_version" not in st.session_state:
    st.session_state.badge_uploader_version = 0


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _font_label(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace("-", " ").replace("_", " ")


def _font_index(paths, target):
    try:
        return paths.index(target)
    except ValueError:
        return 0


def _list_images(directory: str):
    exts = (".jpg", ".jpeg", ".png", ".webp")
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(exts)
    )


st.title("🎬 Livestream Thumbnail Generator")
st.caption(
    "Works for any channel, organization, or event — fill in your own branding "
    "below, then click Generate. Every click can pull a fresh background."
)

# --------------------------------------------------------------------------
# Sidebar: branding assets
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Branding assets")
    st.caption("Anything you upload here is private to your browser session — other visitors never see it.")

    logo_file = st.file_uploader(
        "Logo (PNG, transparent background ideal)",
        type=["png", "jpg", "jpeg"],
        key=f"logo_upload_{st.session_state.logo_uploader_version}",
    )
    if logo_file is not None:
        with open(LOGO_PATH, "wb") as f:
            f.write(logo_file.getbuffer())
        st.success("Logo saved for this session — it will be used from now on.")

    has_uploaded_logo = os.path.isfile(LOGO_PATH)
    if has_uploaded_logo:
        logo_col1, logo_col2 = st.columns([3, 1])
        with logo_col1:
            st.image(_read_bytes(LOGO_PATH), caption="Your logo", width=90)
        with logo_col2:
            st.write("")
            st.write("")
            if st.button("Remove logo"):
                try:
                    os.remove(LOGO_PATH)
                except OSError as e:
                    st.warning(f"Couldn't remove the logo file (it may be open elsewhere): {e}")
                else:
                    # Force a fresh, empty uploader widget so it doesn't just
                    # re-save the same file back on the next rerun.
                    st.session_state.logo_uploader_version += 1
                    st.rerun()
    elif os.path.isfile(DEFAULT_LOGO_PATH):
        st.image(_read_bytes(DEFAULT_LOGO_PATH), caption="Placeholder logo (upload your own above)", width=90)

    st.divider()
    st.subheader("Backgrounds")
    st.caption("Stock backgrounds below are shared by everyone. Anything you upload here is private to you.")
    bg_files = st.file_uploader(
        "Add your own background photos (you can select several)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    if bg_files:
        last_name = None
        for bf in bg_files:
            dest = os.path.join(SESSION_BG_DIR, bf.name)
            with open(dest, "wb") as f:
                f.write(bf.getbuffer())
            last_name = bf.name
        st.success(f"Saved {len(bg_files)} background image(s) for this session.")
        # Auto-select the photo just uploaded, same "use it automatically"
        # behavior as the logo and the anniversary badge, instead of silently
        # leaving the dropdown on "Random" and never using the new photo.
        if last_name:
            st.session_state.bg_choice_select = f"⭐ {last_name}"

    stock_bgs = list_backgrounds()  # shared stock images bundled with the app
    session_bgs = _list_images(SESSION_BG_DIR)  # this visitor's own uploads only

    bg_lookup = {"Random": None}
    bg_lookup.update({f"⭐ {os.path.basename(p)}": p for p in session_bgs})
    bg_lookup.update({os.path.basename(p): p for p in stock_bgs})
    bg_options = list(bg_lookup.keys())
    if st.session_state.bg_choice_select not in bg_options:
        st.session_state.bg_choice_select = "Random"

    bg_choice = st.selectbox(
        "Background for next generation",
        options=bg_options,
        key="bg_choice_select",
        help="⭐ marks your own uploaded photos (only visible to you).",
    )
    bg_preview_path = bg_lookup[bg_choice]
    if bg_preview_path:
        st.image(_read_bytes(bg_preview_path), caption=f"Background: {bg_choice}", width=140)

    st.divider()
    st.subheader("Fonts")
    st.caption("Built-in fonts are shared. Fonts you upload here are private to you.")
    font_uploads = st.file_uploader(
        "Add new font files (.ttf / .otf)",
        type=["ttf", "otf"],
        accept_multiple_files=True,
        help="Uploaded fonts are private to this session and show up as extra "
             "choices in the dropdowns below for the rest of this session.",
    )
    if font_uploads:
        for ff in font_uploads:
            with open(os.path.join(SESSION_FONTS_DIR, ff.name), "wb") as f:
                f.write(ff.getbuffer())
        st.success(f"Added {len(font_uploads)} font file(s) for this session.")

    builtin_fonts = list_fonts()  # shared, bundled fonts only
    session_fonts = sorted(
        os.path.join(SESSION_FONTS_DIR, f)
        for f in os.listdir(SESSION_FONTS_DIR)
        if f.lower().endswith((".ttf", ".otf"))
    )
    available_fonts = builtin_fonts + session_fonts
    with st.expander("Choose fonts for each text role", expanded=False):
        font_title = st.selectbox(
            "Title font (organization name)",
            options=available_fonts,
            index=_font_index(available_fonts, FONT_TITLE),
            format_func=_font_label,
        )
        font_hero = st.selectbox(
            "Hero word font (big bold word + badge number)",
            options=available_fonts,
            index=_font_index(available_fonts, FONT_HERO),
            format_func=_font_label,
        )
        font_script = st.selectbox(
            "Script font (cursive lines)",
            options=available_fonts,
            index=_font_index(available_fonts, FONT_SCRIPT),
            format_func=_font_label,
        )
        font_body = st.selectbox(
            "Body font (date/time, LIVE badge, subscribe bar)",
            options=available_fonts,
            index=_font_index(available_fonts, FONT_BODY),
            format_func=_font_label,
        )

# --------------------------------------------------------------------------
# Main column: text content
# --------------------------------------------------------------------------
col_form, col_preview = st.columns([1, 1.3], gap="large")

with col_form:
    st.subheader("Title & heading")
    title = st.text_input(
        "Main title",
        value="YOUR ORGANIZATION NAME",
        help="Your organization or channel name.",
    )
    presented_by = st.text_input("Small line under title", value="Presents")

    st.subheader("Occasion")
    hero_line = st.text_input("Hero word (large, bold)", value="LIVE")
    script_line = st.text_input("Script line under hero word", value="Stream")

    st.subheader("Date & time")
    date_text = st.text_input("Date text", value="28th June 2026")
    time_text = st.text_input("Time text", value="09:30 AM onwards")

    st.subheader("Anniversary badge")
    show_anniversary = st.checkbox("Show anniversary badge", value=True)

    badge_file = st.file_uploader(
        "Upload a ready-made badge graphic (optional, private to you)",
        type=["png", "jpg", "jpeg"],
        disabled=not show_anniversary,
        key=f"badge_upload_{st.session_state.badge_uploader_version}",
        help="Works just like the logo: if you upload an image here, it's "
             "used automatically instead of the auto-generated shield — no extra "
             "toggle needed. A transparent PNG looks best.",
    )
    if badge_file is not None:
        with open(ANNIVERSARY_BADGE_PATH, "wb") as f:
            f.write(badge_file.getbuffer())
        st.success("Badge image saved for this session — it will be used automatically.")

    has_uploaded_badge = os.path.isfile(ANNIVERSARY_BADGE_PATH)
    if show_anniversary and has_uploaded_badge:
        badge_col1, badge_col2 = st.columns([3, 1])
        with badge_col1:
            st.image(_read_bytes(ANNIVERSARY_BADGE_PATH), caption="Uploaded badge (in use)", width=80)
        with badge_col2:
            st.write("")
            st.write("")
            if st.button("Remove badge"):
                try:
                    os.remove(ANNIVERSARY_BADGE_PATH)
                except OSError as e:
                    st.warning(f"Couldn't remove the badge file (it may be open elsewhere): {e}")
                else:
                    # Force a fresh, empty uploader widget so it doesn't just
                    # re-save the same file back on the next rerun.
                    st.session_state.badge_uploader_version += 1
                    st.rerun()

    fields_disabled = (not show_anniversary) or has_uploaded_badge
    ann_c1, ann_c2 = st.columns(2)
    with ann_c1:
        anniversary_start_year = st.text_input("Start year", value="1974", disabled=fields_disabled)
        anniversary_number = st.text_input("Big number", value="52", disabled=fields_disabled)
    with ann_c2:
        anniversary_end_year = st.text_input("End year", value="2026", disabled=fields_disabled)
        anniversary_caption = st.text_input("Caption", value="Years", disabled=fields_disabled)

    st.subheader("YouTube branding")
    show_live_badge = st.checkbox("Show LIVE badge", value=True)
    show_subscribe_bar = st.checkbox("Show Subscribe bar", value=True)
    youtube_handle = st.text_input(
        "Channel handle", value="@yourchannel", disabled=not show_subscribe_bar
    )

    st.subheader("Output")
    file_format = st.radio("File format", ["PNG", "JPEG"], horizontal=True)
    jpeg_quality = 92
    if file_format == "JPEG":
        jpeg_quality = st.slider("JPEG quality", 60, 100, 92)

    generate_clicked = st.button("🎨 Generate Thumbnail", type="primary", use_container_width=True)

# --------------------------------------------------------------------------
# Build config + generate
# --------------------------------------------------------------------------
if generate_clicked:
    background_path = bg_lookup.get(bg_choice)  # None => pick randomly from the stock library

    anniversary_badge_path = (
        ANNIVERSARY_BADGE_PATH if (show_anniversary and os.path.isfile(ANNIVERSARY_BADGE_PATH)) else None
    )
    logo_path = LOGO_PATH if os.path.isfile(LOGO_PATH) else (
        DEFAULT_LOGO_PATH if os.path.isfile(DEFAULT_LOGO_PATH) else None
    )

    cfg = ThumbnailConfig(
        title=title or "YOUR ORGANIZATION NAME",
        presented_by=presented_by,
        hero_line=hero_line,
        script_line=script_line,
        date_text=date_text,
        time_text=time_text,
        show_anniversary=show_anniversary,
        anniversary_start_year=anniversary_start_year,
        anniversary_end_year=anniversary_end_year,
        anniversary_number=anniversary_number,
        anniversary_caption=anniversary_caption,
        anniversary_badge_path=anniversary_badge_path,
        show_live_badge=show_live_badge,
        show_subscribe_bar=show_subscribe_bar,
        youtube_handle=youtube_handle,
        logo_path=logo_path,
        background_path=background_path,
        font_title=font_title,
        font_hero=font_hero,
        font_script=font_script,
        font_body=font_body,
    )

    with st.spinner("Compositing thumbnail..."):
        image = generate_thumbnail(cfg)
        st.session_state.last_image = image
        st.session_state.last_bg = cfg.background_path

with col_preview:
    st.subheader("Live preview (1280 × 720)")
    if st.session_state.last_image is not None:
        st.image(st.session_state.last_image, use_container_width=True)

        buf = io.BytesIO()
        if file_format == "PNG":
            st.session_state.last_image.save(buf, format="PNG")
            mime, ext = "image/png", "png"
        else:
            st.session_state.last_image.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality)
            mime, ext = "image/jpeg", "jpg"
        buf.seek(0)

        st.download_button(
            label=f"⬇️ Download {file_format}",
            data=buf,
            file_name=f"thumbnail_{int(time.time())}.{ext}",
            mime=mime,
            use_container_width=True,
        )
    else:
        st.info("Fill in the details and click **Generate Thumbnail** to see a preview here.")

st.divider()
st.caption(
    "Tip: drop your own photos into the sidebar uploader for variety — the one "
    "you just uploaded is auto-selected as the background. Upload your real "
    "logo or a ready-made anniversary badge once and each is reused "
    "automatically for the rest of your session — none of it is visible to "
    "other visitors. Upload new font files in the sidebar to unlock extra "
    "styles in the font dropdowns, also private to you."
)
