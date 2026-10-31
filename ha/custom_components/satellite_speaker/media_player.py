"""Zephyr, the bullet-radio box's music speaker (the Pi + PC83), as a media player.

satd on the Orange Pi does the work (Spotify, internet radio, Audible); this
entity is its remote, on satd's LAN port with a bearer token. It is what puts
the speaker in front of the Claude satellite: exposed to Assist, "play Bob
Dylan on the radio" becomes HassMediaSearchAndPlay -> search_media ->
play_media, and pause/next/volume are the stock media intents.

Search does not look anything up: it hands back one result carrying the words
and the source they imply, and play_media does the lookup on the Pi. A miss
there is raised as an error, which the agent reads out.

configuration.yaml:

    media_player:
      - platform: satellite_speaker
        host: 192.168.86.62
        token: !secret satellite_speaker_token
"""
from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature as F,
    MediaPlayerState,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TOKEN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_PORT, default=8081): cv.port,
    vol.Optional(CONF_NAME, default="Zephyr"): cv.string,
})

SOURCES = ["Spotify", "Radio", "Audible"]
# The media class the intent asks for -> where satd looks (and, for Spotify, what kind).
CLASS_SOURCE = {
    MediaClass.CHANNEL: ("radio", None),
    MediaClass.PODCAST: ("audible", None),
    MediaClass.ARTIST: ("spotify", "artist"),
    MediaClass.ALBUM: ("spotify", "album"),
    MediaClass.PLAYLIST: ("spotify", "playlist"),
    MediaClass.TRACK: ("spotify", "track"),
}
STATES = {"playing": MediaPlayerState.PLAYING, "paused": MediaPlayerState.PAUSED,
          "idle": MediaPlayerState.IDLE}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([SatelliteSpeaker(hass, config)], True)


class SatelliteSpeaker(MediaPlayerEntity):
    _attr_supported_features = (
        F.PLAY | F.PAUSE | F.STOP | F.NEXT_TRACK | F.PREVIOUS_TRACK | F.VOLUME_SET
        | F.VOLUME_STEP | F.PLAY_MEDIA | F.SEARCH_MEDIA | F.SELECT_SOURCE)
    _attr_source_list = SOURCES
    _attr_volume_step = 0.05

    def __init__(self, hass, config):
        self._base = f"http://{config[CONF_HOST]}:{config[CONF_PORT]}"
        self._auth = {"Authorization": f"Bearer {config[CONF_TOKEN]}"}
        self._session = async_get_clientsession(hass)
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = f"satellite_speaker_{config[CONF_HOST]}"

    async def _call(self, method, path, body=None):
        try:
            async with self._session.request(method, self._base + path, json=body,
                                             headers=self._auth,
                                             timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            raise HomeAssistantError(f"the satellite speaker is unreachable: {e}") from e
        if r.status >= 300:
            raise HomeAssistantError((data or {}).get("error") or f"satellite speaker said {r.status}")
        return data

    async def async_update(self):
        try:
            self._apply(await self._call("GET", "/status"))
            self._attr_available = True
        except HomeAssistantError as e:
            if self._attr_available:
                _LOGGER.warning("%s", e)
            self._attr_available = False

    def _apply(self, st):
        if "state" not in st:
            return
        self._attr_state = STATES.get(st["state"], MediaPlayerState.IDLE)
        src = st.get("source")
        self._attr_source = src.capitalize() if src else None
        self._attr_media_title = st.get("title")
        self._attr_media_artist = st.get("artist")
        self._attr_media_album_name = st.get("album")
        self._attr_media_image_url = st.get("image")
        self._attr_media_image_remotely_accessible = True
        self._attr_media_duration = st.get("duration") or None
        self._attr_media_position = st.get("position")
        self._attr_media_position_updated_at = dt_util.utcnow() if "position" in st else None
        if st.get("volume") is not None:
            self._attr_volume_level = st["volume"] / 100

    async def _cmd(self, cmd):
        self._apply(await self._call("POST", "/cmd", {"cmd": cmd}))
        self.async_write_ha_state()

    async def async_media_play(self):
        await self._cmd("play")

    async def async_media_pause(self):
        await self._cmd("pause")

    async def async_media_stop(self):
        await self._cmd("stop")

    async def async_media_next_track(self):
        await self._cmd("next")

    async def async_media_previous_track(self):
        await self._cmd("previous")

    async def async_set_volume_level(self, volume):
        await self._call("POST", "/volume", {"set": round(volume * 100)})
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_select_source(self, source):
        # The last thing on that source (an empty query resumes it).
        await self.async_play_media(source.lower(), "")

    async def async_play_media(self, media_type, media_id, **kwargs):
        source, _, kind = str(media_type).partition(":")
        if source not in ("spotify", "radio", "audible"):
            source, kind = "", ""            # music / anything else: satd goes by the words
        await self._call("POST", "/play", {"source": source, "query": media_id,
                                           "kind": kind or None})
        await self.async_update()
        self.async_write_ha_state()

    async def async_search_media(self, query: SearchMediaQuery) -> SearchMedia:
        source, kind = "", None
        for cls in query.media_filter_classes or []:
            if cls in CLASS_SOURCE:
                source, kind = CLASS_SOURCE[cls]
                break
        mtype = f"{source}:{kind}" if kind else source or "music"
        return SearchMedia(result=[BrowseMedia(
            media_class=MediaClass.MUSIC, media_content_id=query.search_query,
            media_content_type=mtype, title=query.search_query, can_play=True,
            can_expand=False)])
