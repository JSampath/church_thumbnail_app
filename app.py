"""
app_v4.py  (a.k.a. app.py)
------
Streamlit UI for a generic YouTube livestream thumbnail generator -- not
tied to any specific channel, organization, or church. Anyone can fill in
their own branding and generate a thumbnail.

Run with:   streamlit run app.py

All image work lives in thumbnail_generator.py; this file only collects
user input, persists uploaded assets to disk, and renders a live preview
with a download button.

The "Schedule on YouTube" section at the bottom is an OPTIONAL extra: it
creates a real scheduled live broadcast on YOUR OWN YouTube channel via the
official Data API, but only after YOU set up your own Google Cloud OAuth
credentials and sign in with your own Google account (see README.md). It
is used entirely at your own risk and has nothing to do with the basic
thumbnail-generation feature above it.
"""

import datetime as dt
import io
import os
import time

import streamlit as st

import youtube_scheduler as yts
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

YT_CATEGORIES = {
    "People & Blogs": "22",
    "Nonprofits & Activism": "29",
    "Education": "27",
    "Entertainment": "24",
}
YT_TIMEZONES = ["Asia/Kolkata", "UTC", "America/New_York", "America/Los_Angeles", "Europe/London"]

st.set_page_config(page_title="Livestream Thumbnail Generator", page_icon="🎬", layout="wide")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
ANNIVERSARY_BADGE_PATH = os.path.join(ASSETS_DIR, "anniversary_badge.png")

if "last_image" not in st.session_state:
    st.session_state.last_image = None
if "last_bg" not in st.session_state:
    st.session_state.last_bg = None
if "bg_choice_select" not in st.session_state:
    st.session_state.bg_choice_select = "Random"
# Bumping this forces a brand-new (empty) badge file_uploader widget, which is
# the only reliable way to make "Remove badge" stick -- file_uploader otherwise
# keeps returning the same uploaded file on every rerun, even after the file
# on disk has been deleted, and would just re-save it right back.
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

    logo_file = st.file_uploader("Logo (PNG, transparent background ideal)", type=["png", "jpg", "jpeg"])
    if logo_file is not None:
        with open(LOGO_PATH, "wb") as f:
            f.write(logo_file.getbuffer())
        st.success("Logo saved — it will be used from now on.")
    if os.path.isfile(LOGO_PATH):
        st.image(_read_bytes(LOGO_PATH), caption="Current logo", width=90)

    st.divider()
    st.subheader("Backgrounds")
    bg_files = st.file_uploader(
        "Add background photos (you can select several)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    if bg_files:
        last_name = None
        for bf in bg_files:
            dest = os.path.join(BACKGROUNDS_DIR, bf.name)
            with open(dest, "wb") as f:
                f.write(bf.getbuffer())
            last_name = bf.name
        st.success(f"Saved {len(bg_files)} background image(s).")
        # Auto-select the photo just uploaded, same "use it automatically"
        # behavior as the logo and the anniversary badge, instead of silently
        # leaving the dropdown on "Random" and never using the new photo.
        if last_name:
            st.session_state.bg_choice_select = last_name

    available_bgs = list_backgrounds()
    bg_options = ["Random"] + [os.path.basename(p) for p in available_bgs]
    if st.session_state.bg_choice_select not in bg_options:
        st.session_state.bg_choice_select = "Random"

    bg_choice = st.selectbox(
        "Background for next generation",
        options=bg_options,
        key="bg_choice_select",
    )
    if bg_choice != "Random":
        bg_preview_path = os.path.join(BACKGROUNDS_DIR, bg_choice)
        if os.path.isfile(bg_preview_path):
            st.image(_read_bytes(bg_preview_path), caption=f"Background: {bg_choice}", width=140)

    st.divider()
    st.subheader("Fonts")
    font_uploads = st.file_uploader(
        "Add new font files (.ttf / .otf)",
        type=["ttf", "otf"],
        accept_multiple_files=True,
        help="Uploaded fonts are saved into the fonts/ folder and show up as "
             "extra choices in the dropdowns below — for this and future sessions.",
    )
    if font_uploads:
        for ff in font_uploads:
            with open(os.path.join(FONTS_DIR, ff.name), "wb") as f:
                f.write(ff.getbuffer())
        st.success(f"Added {len(font_uploads)} font file(s).")

    available_fonts = list_fonts()
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
        help="Your organization or channel name. Also used to auto-fill the "
             "YouTube title/description below if you use that optional feature.",
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
        "Upload a ready-made badge graphic (optional)",
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
        st.success("Badge image saved — it will be used automatically.")

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
    if bg_choice == "Random":
        background_path = None  # let the generator pick randomly, avoiding repeat of last pick
    else:
        background_path = os.path.join(BACKGROUNDS_DIR, bg_choice)

    anniversary_badge_path = (
        ANNIVERSARY_BADGE_PATH if (show_anniversary and os.path.isfile(ANNIVERSARY_BADGE_PATH)) else None
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
    "automatically from then on. Upload new font files in the sidebar to unlock "
    "extra styles in the font dropdowns."
)

# --------------------------------------------------------------------------
# Schedule on YouTube
# --------------------------------------------------------------------------
st.divider()
st.header("📅 Schedule on YouTube")
st.warning(
    "**Optional, advanced feature — use at your own risk.** This creates a "
    "REAL scheduled broadcast on **your own** YouTube channel via the official "
    "YouTube Data API. It only works after *you* set up your own free Google "
    "Cloud project and OAuth credentials and sign in with your own Google "
    "account (see **Schedule on YouTube setup** in README.md) — nothing here "
    "is tied to, or shared with, anyone else's account. You're responsible "
    "for whatever gets scheduled on your channel. Feel free to skip this "
    "section entirely if you only need the thumbnail above."
)
st.caption(
    "Uses the thumbnail generated above. Two Studio-only settings (the live "
    "chat panel, the Reactions toggle) aren't exposed by Google's API, so "
    "they aren't touched here; YouTube carries over whatever you last set "
    "for those, so check them once in Studio if you ever want to change them."
)

if not yts.is_configured():
    st.info(
        "Not connected yet. Follow the **Schedule on YouTube setup** steps in "
        "README.md (create your own free Google Cloud OAuth credentials, "
        "~5 minutes), then place the downloaded `client_secret.json` next to "
        "`app.py`."
    )
else:
    yt_d1, yt_d2, yt_d3 = st.columns(3)
    with yt_d1:
        yt_date = st.date_input("Live date", value=dt.date.today(), key="yt_date")
    with yt_d2:
        yt_time = st.time_input("Start time", value=dt.time(9, 30), key="yt_time")
    with yt_d3:
        yt_tz = st.selectbox("Timezone", options=YT_TIMEZONES, index=0, key="yt_tz")

    auto_title = yts.default_title(hero_line, script_line, yt_date, title)
    yt_title = st.text_input("YouTube title", value=auto_title, key="yt_title")
    yt_description = st.text_area(
        "Description",
        value=yts.default_description(yt_title, time_text, title),
        height=110,
        key="yt_description",
    )

    yt_c1, yt_c2, yt_c3 = st.columns(3)
    with yt_c1:
        yt_visibility = st.radio("Visibility", ["Public", "Unlisted", "Private"], key="yt_visibility")
    with yt_c2:
        yt_category_label = st.selectbox("Category", options=list(YT_CATEGORIES.keys()), key="yt_category")
    with yt_c3:
        yt_made_for_kids = st.checkbox("Made for kids", value=False, key="yt_made_for_kids")

    yt_playlist = st.text_input(
        "Add to playlist (created automatically if it doesn't exist)",
        value="Live Streams",
        key="yt_playlist",
    )
    st.caption("How you'll go live: streaming software (OBS, etc.) over RTMP — the stream key appears below once scheduled.")

    schedule_clicked = st.button("📡 Schedule Live Stream on YouTube", use_container_width=True)

    if schedule_clicked:
        if st.session_state.last_image is None:
            st.warning(
                "Click **Generate Thumbnail** above first — the scheduled stream "
                "uses that image as its YouTube thumbnail."
            )
        else:
            thumb_path = os.path.join(ASSETS_DIR, "_last_scheduled_thumbnail.png")
            st.session_state.last_image.convert("RGB").save(thumb_path, format="PNG")
            try:
                with st.spinner("Connecting to YouTube (a browser tab may open the first time)..."):
                    creds = yts.get_credentials()
                    youtube = yts.build_youtube_service(creds)
                with st.spinner("Creating your scheduled stream..."):
                    start_utc = yts.local_to_utc(yt_date, yt_time, yt_tz)
                    cfg = yts.ScheduleConfig(
                        title=yt_title,
                        description=yt_description,
                        scheduled_start_utc=start_utc,
                        thumbnail_path=thumb_path,
                        privacy_status=yt_visibility.lower(),
                        made_for_kids=yt_made_for_kids,
                        playlist_name=yt_playlist.strip() or None,
                        category_id=YT_CATEGORIES[yt_category_label],
                    )
                    result = yts.create_scheduled_broadcast(youtube, cfg)
            except yts.NotConfiguredError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Couldn't schedule the stream: {e}")
            else:
                st.success("Scheduled! Check the live chat / Reactions toggles once in Studio if you want to change them.")
                st.markdown(f"**Watch page:** {result.watch_url}")
                st.markdown(f"**Studio (edit / go live):** {result.studio_url}")
                st.markdown(f"**Stream key** (paste into OBS/streaming software): `{result.stream_key}`")
                st.markdown(f"**Server URL:** `{result.ingestion_address}`")
                if result.playlist_name:
                    st.caption(f'Added to playlist "{result.playlist_name}".')
