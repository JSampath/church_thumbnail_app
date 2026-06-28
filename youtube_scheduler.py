"""
youtube_scheduler.py
------
Schedules a real YouTube Live broadcast directly from this app, using the
official YouTube Data API v3 (no browser automation, no clicking through
Studio by hand).

This is an OPTIONAL, advanced feature layered on top of the (fully generic,
not tied to any organization) thumbnail generator. It only does anything
once YOU connect YOUR OWN YouTube channel via your own Google Cloud OAuth
credentials -- nothing here is shared with, or runs through, anyone else's
account or project. You are responsible for whatever this creates on your
channel; use it at your own risk.

What this sets automatically: title, description, scheduled start time,
visibility, "made for kids", the broadcast thumbnail (the one this app
just generated), stream-software (RTMP) ingestion, and adding the
broadcast to a playlist (created automatically if it doesn't exist yet).

What this can NOT set: the live-chat panel settings and the "Reactions"
toggle. Google's public API has no fields for either -- they only exist
in YouTube Studio's web UI. In practice YouTube carries over whatever you
last set for these on your channel, so they usually only need a one-time
check in Studio, not a per-stream one. See README.md.

One-time setup required before any of this works -- see README.md:
  1. Create a Google Cloud project and enable "YouTube Data API v3".
  2. Configure an OAuth consent screen (Testing is fine for personal use)
     and add your own Google account as a test user.
  3. Create an OAuth Client ID of type "Desktop app" and download it as
     client_secret.json into this same folder.

The first time you connect, a browser tab opens to Google's real
sign-in/consent page. After that, credentials are cached in token.json
and refreshed silently. Keep both files private -- each grants access to
your YouTube channel.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube"]

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_PATH = os.path.join(HERE, "client_secret.json")
TOKEN_PATH = os.path.join(HERE, "token.json")


class NotConfiguredError(RuntimeError):
    """Raised when client_secret.json hasn't been set up yet."""


@dataclass
class ScheduleConfig:
    title: str
    description: str
    scheduled_start_utc: dt.datetime  # must be tz-aware, UTC
    thumbnail_path: str
    privacy_status: str = "public"  # "public" | "unlisted" | "private"
    made_for_kids: bool = False
    playlist_name: Optional[str] = "Live Streams"
    category_id: str = "22"  # People & Blogs


@dataclass
class ScheduleResult:
    broadcast_id: str
    watch_url: str
    studio_url: str
    stream_key: str
    ingestion_address: str
    playlist_name: Optional[str]


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def is_configured() -> bool:
    """True once client_secret.json has been dropped into this folder."""
    return os.path.isfile(CLIENT_SECRET_PATH)


def is_connected() -> bool:
    """True if we already have a (possibly refreshable) cached token, i.e.
    scheduling won't need to pop open a fresh sign-in tab."""
    if not os.path.isfile(TOKEN_PATH):
        return False
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except Exception:
        return False
    return bool(creds and (creds.valid or creds.refresh_token))


def get_credentials() -> Credentials:
    """Return cached, refreshed credentials, or run the interactive Google
    sign-in flow (opens a real browser tab) if there's no usable token yet."""
    if not is_configured():
        raise NotConfiguredError(
            "client_secret.json not found next to app.py. Follow the "
            "'Schedule on YouTube' setup steps in README.md first."
        )

    creds: Optional[Credentials] = None
    if os.path.isfile(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            creds = None  # fall through to a fresh interactive sign-in

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def build_youtube_service(creds: Credentials):
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_channel_title(youtube) -> str:
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    return items[0]["snippet"]["title"] if items else "Unknown channel"


# --------------------------------------------------------------------------
# Small pure helpers (easy to unit-test without any real API access)
# --------------------------------------------------------------------------
def local_to_utc(local_date: dt.date, local_time: dt.time, tz_name: str) -> dt.datetime:
    """Combine a date + time picked in the given timezone into a tz-aware
    UTC datetime, ready for the API's RFC3339 scheduledStartTime."""
    local_dt = dt.datetime.combine(local_date, local_time, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(dt.timezone.utc)


def to_rfc3339(utc_dt: dt.datetime) -> str:
    utc_dt = utc_dt.astimezone(dt.timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def default_title(
    hero_line: str, script_line: str = "", event_date: dt.date = None, org_name: str = ""
) -> str:
    """Auto-suggested YouTube title -- always editable before scheduling.
    Pattern: "{hero word} {script line} || {DD-MM-YYYY} || {your org/channel
    name}", e.g. "LIVE Stream || 29-06-2026 || Your Organization Name". The
    org-name segment is dropped entirely if left blank."""
    headline = " ".join(p.strip() for p in (hero_line, script_line) if p and p.strip())
    headline = headline or "Live Stream"
    base = f"{headline} || {event_date:%d-%m-%Y}" if event_date else headline
    org_name = (org_name or "").strip()
    return f"{base} || {org_name}" if org_name else base


def default_description(title: str, time_text: str = "", org_name: str = "") -> str:
    org_name = (org_name or "").strip()
    intro = f"Join us live — presented by {org_name}." if org_name else "Join us live."
    lines = [intro, "", f"Stream: {title}"]
    if time_text:
        lines.append(f"Time: {time_text}")
    lines += ["", "Subscribe and turn on notifications so you never miss a live stream."]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Playlist
# --------------------------------------------------------------------------
def get_or_create_playlist(youtube, title: str) -> str:
    """Return the playlist ID for `title` on the signed-in channel,
    creating it (as a public playlist) if it doesn't already exist."""
    page_token = None
    while True:
        resp = (
            youtube.playlists()
            .list(part="snippet", mine=True, maxResults=50, pageToken=page_token)
            .execute()
        )
        for item in resp.get("items", []):
            if item["snippet"]["title"].strip().lower() == title.strip().lower():
                return item["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    created = (
        youtube.playlists()
        .insert(
            part="snippet,status",
            body={"snippet": {"title": title}, "status": {"privacyStatus": "public"}},
        )
        .execute()
    )
    return created["id"]


# --------------------------------------------------------------------------
# The actual scheduling flow
# --------------------------------------------------------------------------
def create_scheduled_broadcast(youtube, cfg: ScheduleConfig) -> ScheduleResult:
    broadcast = (
        youtube.liveBroadcasts()
        .insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {
                    "title": cfg.title,
                    "description": cfg.description,
                    "scheduledStartTime": to_rfc3339(cfg.scheduled_start_utc),
                },
                "status": {
                    "privacyStatus": cfg.privacy_status,
                    "selfDeclaredMadeForKids": cfg.made_for_kids,
                },
                "contentDetails": {
                    # Skip the "testing" stage and the monitor stream so that
                    # starting/stopping your streaming software (OBS, etc.)
                    # takes the broadcast live/offline with no extra clicks
                    # in Studio -- the natural fit for "Stream software".
                    "monitorStream": {"enableMonitorStream": False},
                    "enableAutoStart": True,
                    "enableAutoStop": True,
                    "enableDvr": True,
                    "recordFromStart": True,
                    "enableEmbed": True,
                    "latencyPreference": "normal",
                },
            },
        )
        .execute()
    )
    broadcast_id = broadcast["id"]

    stream = (
        youtube.liveStreams()
        .insert(
            part="snippet,cdn,contentDetails,status",
            body={
                "snippet": {"title": cfg.title},
                "cdn": {
                    "frameRate": "variable",
                    "ingestionType": "rtmp",
                    "resolution": "variable",
                },
            },
        )
        .execute()
    )
    stream_id = stream["id"]

    youtube.liveBroadcasts().bind(
        id=broadcast_id, part="id,contentDetails", streamId=stream_id
    ).execute()

    # Category lives on the underlying *video* resource, not liveBroadcasts.
    video = youtube.videos().list(part="snippet", id=broadcast_id).execute()
    if video.get("items"):
        snippet = video["items"][0]["snippet"]
        snippet["categoryId"] = cfg.category_id
        youtube.videos().update(
            part="snippet", body={"id": broadcast_id, "snippet": snippet}
        ).execute()

    if cfg.thumbnail_path and os.path.isfile(cfg.thumbnail_path):
        youtube.thumbnails().set(
            videoId=broadcast_id,
            media_body=MediaFileUpload(cfg.thumbnail_path, mimetype="image/png"),
        ).execute()

    playlist_name = cfg.playlist_name.strip() if cfg.playlist_name else None
    if playlist_name:
        playlist_id = get_or_create_playlist(youtube, playlist_name)
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": broadcast_id},
                }
            },
        ).execute()

    ingestion = stream.get("cdn", {}).get("ingestionInfo", {})

    return ScheduleResult(
        broadcast_id=broadcast_id,
        watch_url=f"https://youtu.be/{broadcast_id}",
        studio_url=f"https://studio.youtube.com/video/{broadcast_id}/livestreaming",
        stream_key=ingestion.get("streamName", ""),
        ingestion_address=ingestion.get("ingestionAddress", ""),
        playlist_name=playlist_name,
    )


if __name__ == "__main__":
    # Quick manual smoke test of the pure helpers (no network/API calls).
    d = dt.date(2026, 6, 21)
    t = dt.time(9, 30)
    title = default_title("LIVE", "Stream", d, "Your Organization")
    print(title)
    utc = local_to_utc(d, t, "Asia/Kolkata")
    print("UTC:", to_rfc3339(utc))
    print(default_description(title, "09:30 AM onwards", "Your Organization"))
