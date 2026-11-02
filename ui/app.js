// Satellite face: a ring of apps around a centre stage.
// The centre shows time / date / weather until an app is picked; the picked
// app then owns the centre. Tapping the lit app again goes back home.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const C = 400;                    // face centre
const ICON_R = 346;               // radius of the icon ring
const IDLE_HOME_MS = 2 * 60e3;    // back to the home view after this
const IDLE_SAVER_MS = 10 * 60e3;  // clock screensaver after this

// Uncaught errors go to satd's journal: nobody can open devtools on the wall.
function report(msg) { fetch("/api/log", { method: "POST", body: String(msg).slice(0, 2000) }).catch(() => {}); }
window.addEventListener("error", e => report(`error: ${e.message} @ ${e.filename}:${e.lineno}`));
window.addEventListener("unhandledrejection", e => report(`rejection: ${e.reason && (e.reason.stack || e.reason.message) || e.reason}`));

// ------------------------------------------------------------------ icons
const I = {
  spotify: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9.5"/><path d="M7 9.2c3.6-1.1 7.4-.8 10.4.9M7.6 12.4c3-.8 6-.5 8.4.8M8.3 15.4c2.3-.6 4.6-.4 6.4.6"/></svg>',
  radio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="12" rx="3"/><circle cx="8.5" cy="14" r="3"/><path d="M14 12h4M14 15h4M7 8l9-4.5"/></svg>',
  weather: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3.5v1.5M3.5 9H5M5.1 5.1l1.1 1.1M12.9 5.1l-1.1 1.1"/><path d="M6.3 11.2A3.5 3.5 0 1 1 12.4 7.6"/><path d="M8 19.5h9a3.5 3.5 0 0 0 .4-7 5 5 0 0 0-9.6 1.2A3 3 0 0 0 8 19.5z"/></svg>',
  timers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5V9.5M10 2.5h4M18.5 6.5l1.3-1.3"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 6.5V12l3.5 2.2"/></svg>',
  ha: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6.5" y="5" width="4" height="14" rx="1"/><rect x="13.5" y="5" width="4" height="14" rx="1"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 6v12l9-6zM15.5 6h2.5v12h-2.5z"/></svg>',
  prev: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6v12l-9-6zM6 6h2.5v12H6z"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h3.5c4 0 5 10 9 10H20M4 17h3.5c1.6 0 2.7-1.6 3.6-3.5M16.5 7H20M17.5 4.5 20 7l-2.5 2.5M17.5 14.5 20 17l-2.5 2.5"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
};

I.phone = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7.5l10 9-5 4.5v-18l5 4.5-10 9"/></svg>';
I.audible = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.5v-2a8 8 0 0 1 16 0v2"/><rect x="3" y="14" width="4.5" height="6.5" rx="1.6"/><rect x="16.5" y="14" width="4.5" height="6.5" rx="1.6"/><path d="M10 9.5l4 1.5-4 1.5z" fill="currentColor"/></svg>';
I.calendar = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h3"/></svg>';

const APPS = [
  { id: "spotify", name: "Spotify", icon: I.spotify },
  { id: "radio", name: "Radio", icon: I.radio },
  { id: "phone", name: "Phone audio", icon: I.phone },
  { id: "audible", name: "Books", icon: I.audible },
  { id: "weather", name: "Weather", icon: I.weather },
  { id: "calendar", name: "Calendar", icon: I.calendar },
  { id: "clock", name: "Clock", icon: I.clock },
  { id: "timers", name: "Timers", icon: I.timers },
  { id: "ha", name: "Home", icon: I.ha },
];

// ------------------------------------------------------------------ util
async function api(path, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), opts.timeout || 8000);
  try {
    const r = await fetch(path, {
      method: opts.method || (opts.body ? "POST" : "GET"),
      headers: opts.body ? { "Content-Type": "application/json" } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctl.signal,
    });
    if (r.status === 204) return null;
    const j = await r.json().catch(() => null);
    if (!r.ok) {
      // satd says {error: "text"}; Spotify's Web API says {error: {status, message}}.
      const err = j && j.error;
      const msg = (err && typeof err === "object" ? err.message : err) || r.statusText || `HTTP ${r.status}`;
      throw Object.assign(new Error(msg), { status: r.status });
    }
    return j;
  } finally { clearTimeout(t); }
}
const post = (path, body = {}) => api(path, { body });

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function mmss(sec) { sec = Math.max(0, Math.round(sec)); const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = sec % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0"); }

let toastTimer;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("shown"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("shown"), 2600); }

// Sub-screen header: the title is the back button ("‹ LIVING ROOM"). It sits
// above any list, so nothing can cover it, and it's where a thumb looks.
function backHead(id, title, top) {
  return `<button class="back-head" id="${id}" style="margin-top:${top}px">${I.back}<span>${esc(title)}</span></button>`;
}

function polar(r, deg) { const a = (deg - 90) * Math.PI / 180; return [C + r * Math.cos(a), C + r * Math.sin(a)]; }

// ------------------------------------------------------------------ weather codes
function wmo(code, day = 1) {
  const n = !day;
  if (code === 0) return [n ? "🌙" : "☀️", "Clear"];
  if (code === 1) return [n ? "🌙" : "🌤️", "Mostly clear"];
  if (code === 2) return [n ? "☁️" : "⛅", "Partly cloudy"];
  if (code === 3) return ["☁️", "Overcast"];
  if (code === 45 || code === 48) return ["🌫️", "Fog"];
  if (code >= 51 && code <= 57) return ["🌦️", "Drizzle"];
  if (code >= 61 && code <= 67) return ["🌧️", "Rain"];
  if (code >= 71 && code <= 77) return ["🌨️", "Snow"];
  if (code >= 80 && code <= 82) return ["🌦️", "Showers"];
  if (code === 85 || code === 86) return ["🌨️", "Snow showers"];
  if (code >= 95) return ["⛈️", "Thunderstorm"];
  return ["🌡️", "—"];
}

// ------------------------------------------------------------------ state
const S = {
  view: "home",
  lastTouch: Date.now(),
  saver: false,
  weather: null,
  radio: { playing: false },
  timers: [],
  radioBrowse: null,                   // null -> now-playing screen, else genre key
  bt: null,                            // /api/bt/status
  cal: null,                           // /api/calendar
  spotifyBrowse: false,
};

// ------------------------------------------------------------------ ring
function buildRing() {
  const ring = $("#ring");
  const step = 360 / APPS.length;
  let ticks = "";
  for (let d = 0; d < 360; d += 4) {
    const nearIcon = APPS.some((_, i) => { const diff = Math.abs(((d - i * step) % 360 + 540) % 360 - 180); return diff < 15; });
    if (nearIcon) continue;
    const major = d % 20 === 0;
    const [x1, y1] = polar(major ? 318 : 324, d), [x2, y2] = polar(major ? 374 : 368, d);
    ticks += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${major ? "#f1e7cf55" : "#f1e7cf22"}" stroke-width="${major ? 2 : 1.5}" stroke-linecap="round"/>`;
  }
  ring.innerHTML = `<svg class="dial" viewBox="0 0 800 800">
      <defs><radialGradient id="bandg" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#28484a"/><stop offset="1" stop-color="#15292a"/></radialGradient></defs>
      <circle cx="400" cy="400" r="${(296 + 400) / 2}" fill="none" stroke="url(#bandg)" stroke-width="${400 - 296}"/>
      <circle cx="400" cy="400" r="297" fill="none" stroke="#f1e7cf30" stroke-width="1.5"/>
      ${ticks}
      <path id="sel-arc" fill="none" stroke="var(--turq)" stroke-width="5" stroke-linecap="round" opacity="0"/>
      <g id="vol-ring"><circle cx="400" cy="400" r="392" fill="none" stroke="#f1e7cf26" stroke-width="7"/>
        <path id="vol-arc" fill="none" stroke="var(--ivory)" stroke-width="7" stroke-linecap="round"/></g>
    </svg>`;
  APPS.forEach((app, i) => {
    const [x, y] = polar(ICON_R, i * step);
    const b = document.createElement("button");
    b.className = "app-btn"; b.dataset.app = app.id; b.title = app.name;
    b.style.left = x + "px"; b.style.top = y + "px";
    b.innerHTML = app.icon + '<i class="badge"></i>';
    b.addEventListener("click", () => openApp(S.view === app.id ? "home" : app.id));
    ring.appendChild(b);
  });
}

function arcPath(r, a0, a1) {
  const [x0, y0] = polar(r, a0), [x1, y1] = polar(r, a1);
  return `M${x0} ${y0} A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}

function markActive() {
  document.querySelectorAll(".app-btn").forEach(b => b.classList.toggle("active", b.dataset.app === S.view));
  const i = APPS.findIndex(a => a.id === S.view);
  const arc = $("#sel-arc");
  if (i < 0) { arc.setAttribute("opacity", 0); return; }
  const mid = i * 360 / APPS.length;
  arc.setAttribute("d", arcPath(388, mid - 22, mid + 22));
  arc.setAttribute("opacity", 1);
}

function markLive() {
  const live = {
    spotify: spotifyIsPlaying(),
    radio: !!S.radio.playing,
    phone: btIsPlaying(),
    audible: typeof audIsPlaying === "function" && audIsPlaying(),
    timers: S.timers.length > 0,
  };
  document.querySelectorAll(".app-btn").forEach(b => b.classList.toggle("live", !!live[b.dataset.app]));
}

// ------------------------------------------------------------------ navigation
const RENDER = {};
function openApp(id) {
  S.view = id;
  if (id === "radio") S.radioBrowse = S.radio.playing ? null : (S.radioBrowse || "favorites");
  if (id === "spotify") S.spotifyBrowse = false;
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("shown", v.id === "v-" + id));
  markActive();
  (RENDER[id] || (() => {}))(true);
}

// ------------------------------------------------------------------ home
function renderHomeClock() {
  const d = new Date();
  let h = d.getHours(); const ampm = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
  $("#h-time").innerHTML = `${h}:${String(d.getMinutes()).padStart(2, "0")}<small>${ampm}</small>`;
  $("#h-date").textContent = d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

RENDER.home = () => {
  renderHomeClock();
  const w = S.weather;
  if (w && w.current) {
    const [ico, desc] = wmo(w.current.weather_code, w.current.is_day);
    const today = w.daily;
    $("#h-wx").innerHTML = `<span class="ico">${ico}</span><span class="temp">${Math.round(w.current.temperature_2m)}°</span>
      <span class="desc">${esc(desc)}<br><span class="muted">H ${Math.round(today.temperature_2m_max[0])}° · L ${Math.round(today.temperature_2m_min[0])}°</span></span>`;
  } else if (w && w.error) {
    $("#h-wx").innerHTML = `<span class="muted">Weather unavailable</span>`;
  }
  const chips = [];
  const ringing = S.timers.filter(t => t.done);
  S.timers.filter(t => !t.done).slice(0, 2).forEach(t => chips.push(`<button class="chip" data-go="timers">⏱ ${mmss(t.remaining)}${t.label ? " · " + esc(t.label) : ""}</button>`));
  ringing.forEach(() => chips.push(`<button class="chip ring" data-go="timers">⏰ Timer done</button>`));
  const spt = spTrack();
  if (spotifyIsPlaying()) chips.push(`<button class="chip" data-go="spotify">♪ ${esc(spt.name)} — ${esc((spt.artists || []).map(a => a.name).join(", "))}</button>`);
  else if (S.radio.playing) chips.push(`<button class="chip" data-go="radio">📻 ${esc(S.radio.station.name)}${S.radio.now ? " · " + esc(S.radio.now) : ""}</button>`);
  else if (typeof audIsPlaying === "function" && audIsPlaying()) {
    const a = AUD.st;
    chips.push(`<button class="chip" data-go="audible">📖 ${esc(a.title || "Books")}${a.chapter ? " · " + esc(a.chapter.title) : ""}</button>`);
  }
  else if (btIsPlaying()) { const p = S.bt.player; chips.push(`<button class="chip" data-go="phone">🎧 ${esc(p.title || p.device || "Phone audio")}${p.artist ? " · " + esc(p.artist) : ""}</button>`); }
  const ev = nextEvent();
  if (ev && calStart(ev).getTime() - Date.now() < 12 * 3600e3)
    chips.push(`<button class="chip" data-go="calendar">📅 ${calTime(calStart(ev))} ${esc(ev.summary)}</button>`);
  const strip = $("#h-strip");
  const html = chips.join("");
  if (strip.dataset.html !== html) { strip.innerHTML = html; strip.dataset.html = html; }
};
$("#h-strip").addEventListener("click", e => { const b = e.target.closest("[data-go]"); if (b) openApp(b.dataset.go); });

// ------------------------------------------------------------------ spotify
// The page itself is the Spotify Connect device ("Satellite"), via Spotify's
// official Web Playback SDK (needs Widevine). satd holds the login and hands
// out access tokens; browsing and "play on this device" use the Web API proxy.
const SP = { cfg: null, status: null, player: null, deviceId: null, state: null, stateAt: 0, error: null, loading: false };
const spWeb = (path, opts) => api("/api/spotify/web/" + path, opts);

async function initSpotify() {
  if (SP.player || SP.loading) return;
  try { SP.status = await api("/api/spotify/token", { timeout: 6000 }); } catch (e) { SP.status = { error: e.message }; }
  if (!SP.status || !SP.status.logged_in) { setTimeout(initSpotify, 30e3); return; }   // pick up a login without a reload
  SP.loading = true;
  try { SP.cfg = await api("/api/spotify/config"); } catch { SP.cfg = { device_name: "Zephyr", volume: 0.6 }; }
  window.onSpotifyWebPlaybackSDKReady = () => {
    const p = new Spotify.Player({
      name: SP.cfg.device_name,
      volume: 1,                       // the master (knob) is the one volume
      getOAuthToken: cb => api("/api/spotify/token").then(t => cb(t.access_token)).catch(e => report("sp token: " + e.message)),
    });
    p.addListener("ready", ({ device_id }) => {
      SP.deviceId = device_id; SP.error = null; report("spotify ready " + device_id);
      post("/api/spotify/device", { id: device_id }).catch(() => {});   // satd plays to it for HA
      spRefresh();
    });
    p.addListener("not_ready", () => { SP.deviceId = null; post("/api/spotify/device", { id: null }).catch(() => {}); spRefresh(); });
    p.addListener("player_state_changed", st => {
      SP.state = st; SP.stateAt = Date.now();
      if (st && !st.paused && S.radio.playing) post("/api/radio/stop").catch(() => {});
      if (st && !st.paused && typeof audIsPlaying === "function" && audIsPlaying())
        post("/api/audible/cmd", { action: "pause" }).catch(() => {});
      spRefresh();
    });
    for (const ev of ["initialization_error", "authentication_error", "account_error", "playback_error"])
      p.addListener(ev, ({ message }) => { SP.error = `${ev.replace("_", " ")}: ${message}`; report("spotify " + SP.error); spRefresh(); });
    p.connect();
    SP.player = p;
  };
  const s = document.createElement("script");
  s.src = "https://sdk.scdn.co/spotify-player.js";
  s.onerror = () => { SP.loading = false; SP.error = "couldn't load Spotify's player (offline?)"; spRefresh(); setTimeout(initSpotify, 60e3); };
  document.head.appendChild(s);
}

// Something started from HA / Claude: bring its app up so the screen (and the
// knob's play/pause) shows what is playing. Spotify's state arrives over the
// SDK a moment after satd's play call; without it the app would open on the
// library, so give it a few seconds.
async function remoteOpen(id) {
  wake();
  if (id === "radio") await pollRadio().catch(() => {});
  if (id === "spotify") for (let i = 0; i < 20 && !spotifyIsPlaying(); i++) await new Promise(r => setTimeout(r, 250));
  openApp(id);
}

// Spotify drops a web player that idles for hours without telling it; satd
// notices when it goes to play there and asks for a fresh registration.
async function spReconnect() {
  if (!SP.player) { initSpotify(); return; }
  try { SP.player.disconnect(); } catch {}
  await new Promise(r => setTimeout(r, 300));
  SP.player.connect();
}

function spRefresh() { markLive(); if (S.view === "spotify" && !S.spotifyBrowse) RENDER.spotify(); else if (S.view === "home") RENDER.home(); }

function spotifyIsPlaying() { return !!(SP.state && !SP.state.paused && SP.state.track_window && SP.state.track_window.current_track); }
function spTrack() { return SP.state && SP.state.track_window && SP.state.track_window.current_track; }
function spotifyPosition() {
  const st = SP.state; if (!st) return 0;
  return Math.min(st.position + (st.paused ? 0 : Date.now() - SP.stateAt), st.duration || st.position);
}

const PROG_R = 282, PROG_LEN = 2 * Math.PI * PROG_R;
function progressSvg(id) {
  return `<svg class="progress" viewBox="0 0 580 580"><circle class="track-bg" cx="290" cy="290" r="${PROG_R}"/>
    <circle class="fill" id="${id}" cx="290" cy="290" r="${PROG_R}" stroke-dasharray="${PROG_LEN}" stroke-dashoffset="${PROG_LEN}"/></svg>`;
}

function spMessage(title, body, button) {
  const v = $("#v-spotify");
  const key = title + body;
  if (v.dataset.mode === "msg:" + key) return;
  v.dataset.mode = "msg:" + key;
  v.innerHTML = `<div class="label">Spotify</div>
    <p style="font-size:22px;margin:16px 0 4px">${title}</p>
    <p class="muted" style="font-size:16px;max-width:340px;margin:0 0 22px">${body}</p>${button || ""}`;
  if ($("#sp-lib")) $("#sp-lib").onclick = () => { S.spotifyBrowse = true; spotifyLibrary(true); };
}

RENDER.spotify = (fresh) => {
  if (S.spotifyBrowse) return spotifyLibrary(fresh);
  const st = SP.status;
  if (!st) return spMessage("Connecting…", "");
  if (st.configured === false) return spMessage("Not set up yet", "Add <b>spotify_client_id</b> to /etc/satd.json.");
  if (st.error && !st.logged_in) return spMessage("Spotify problem", esc(st.error));
  if (!st.logged_in) return spMessage("Waiting for sign-in", "Spotify login hasn't been completed for this speaker yet.");
  if (SP.error && !SP.deviceId) return spMessage("Spotify problem", esc(SP.error));
  if (!SP.deviceId) return spMessage("Starting the player…", "");
  const t = spTrack();
  if (!t) { S.spotifyBrowse = true; return spotifyLibrary(fresh); }   // nothing loaded: browsing is the only thing to do

  const v = $("#v-spotify");
  if (v.dataset.mode !== "playing" || v.dataset.uri !== t.uri) {
    v.dataset.mode = "playing"; v.dataset.uri = t.uri;
    v.innerHTML = `${progressSvg("sp-prog")}
      <button class="corner-btn" id="sp-lib" style="left:120px;top:96px">${I.list}</button>
      <button class="corner-btn" id="sp-shuf" style="right:120px;top:96px">${I.shuffle}</button>
      <img class="art" id="sp-art" alt="">
      <div class="track" id="sp-track"></div><div class="artist" id="sp-artist"></div>
      <div class="controls">
        <button class="round" id="sp-prev">${I.prev}</button>
        <button class="round primary" id="sp-pp"></button>
        <button class="round" id="sp-next">${I.next}</button>
      </div>
      <div class="vol"><button id="sp-vdn">−</button><span id="sp-vol"></span><button id="sp-vup">+</button></div>`;
    const imgs = (t.album && t.album.images) || [];
    $("#sp-art").src = (imgs.find(i => i.width >= 300) || imgs[0] || {}).url || "";
    $("#sp-track").textContent = t.name;
    $("#sp-artist").textContent = (t.artists || []).map(a => a.name).join(", ");
    $("#sp-prev").onclick = () => SP.player.previousTrack();
    $("#sp-next").onclick = () => SP.player.nextTrack();
    $("#sp-pp").onclick = () => SP.player.togglePlay();
    $("#sp-vdn").onclick = () => masterStep(-5);
    $("#sp-vup").onclick = () => masterStep(5);
    $("#sp-shuf").onclick = () => spWeb(`me/player/shuffle?state=${!SP.state.shuffle}&device_id=${SP.deviceId}`, { method: "PUT" }).catch(e => toast("Spotify: " + e.message));
    $("#sp-lib").onclick = () => { S.spotifyBrowse = true; spotifyLibrary(true); };
    volLabels();
  }
  const playing = !SP.state.paused;
  $("#sp-pp").innerHTML = playing ? I.pause : I.play;
  $("#sp-art").classList.toggle("spin", playing);
  $("#sp-shuf").style.color = SP.state.shuffle ? "var(--turq)" : "";
  const d = SP.state.duration;
  $("#sp-prog").style.strokeDashoffset = PROG_LEN * (1 - (d ? spotifyPosition() / d : 0));
};


// Browse: his library, plus genre playlists from search.
const SP_TABS = [
  { id: "recent", name: "Recent" }, { id: "playlists", name: "Playlists" }, { id: "liked", name: "Liked" },
  { id: "albums", name: "Albums" }, { id: "top", name: "Top" }, { id: "discover", name: "Discover" },
];
const SP_GENRES = ["jazz", "chill", "classic rock", "soul", "focus", "indie", "hip hop", "country", "classical", "50s"];
let spTab = "recent", spGenre = "jazz";

async function spLoadTab() {
  const art = (imgs) => ((imgs || []).slice(-1)[0] || {}).url || "";   // smallest image
  const trackRows = (tracks) => {
    const uris = tracks.map(t => t.uri);
    return tracks.map((t, i) => ({ name: t.name, sub: (t.artists || []).map(a => a.name).join(", "), img: art(t.album && t.album.images),
      play: { uris, offset: { position: i } } }));
  };
  if (spTab === "recent") {
    const j = await spWeb("me/player/recently-played?limit=50");
    const seen = new Set(), rows = [];
    for (const it of (j && j.items) || []) {
      const t = it.track, ctx = it.context && it.context.uri;
      const key = ctx || t.uri; if (seen.has(key)) continue; seen.add(key);
      // Spotify only takes "start at this track" (offset) for albums and playlists;
      // for an artist context it rejects the call, so play the song itself.
      const ctxOk = ctx && /^spotify:(album|playlist):/.test(ctx);
      rows.push({ name: t.name, sub: (t.artists || []).map(a => a.name).join(", "), img: art(t.album && t.album.images),
        play: ctxOk ? { context_uri: ctx, offset: { uri: t.uri } } : { uris: [t.uri] } });
    }
    return rows;
  }
  if (spTab === "top") return trackRows(((await spWeb("me/top/tracks?limit=50&time_range=medium_term")) || {}).items || []);
  if (spTab === "liked") return trackRows((((await spWeb("me/tracks?limit=50")) || {}).items || []).map(i => i.track));
  if (spTab === "playlists") return ((((await spWeb("me/playlists?limit=50")) || {}).items) || []).filter(Boolean).map(p =>
    ({ name: p.name, sub: (p.owner && p.owner.display_name) || "", img: art(p.images), play: { context_uri: p.uri } }));
  if (spTab === "albums") return ((((await spWeb("me/albums?limit=50")) || {}).items) || []).map(({ album: a }) =>
    ({ name: a.name, sub: (a.artists || []).map(x => x.name).join(", "), img: art(a.images), play: { context_uri: a.uri } }));
  const j = await spWeb(`search?type=playlist&limit=30&q=${encodeURIComponent(spGenre)}`);
  return (((j && j.playlists && j.playlists.items) || []).filter(Boolean)).map(p =>
    ({ name: p.name, sub: (p.owner && p.owner.display_name) || "", img: art(p.images), play: { context_uri: p.uri } }));
}

async function spotifyLibrary(fresh) {
  const v = $("#v-spotify");
  if (!fresh && v.dataset.mode === "library") return;
  v.dataset.mode = "library";
  const tabs = SP_TABS.map(t => `<button data-tab="${t.id}" class="${t.id === spTab ? "on" : ""}">${t.name}</button>`).join("");
  const genres = spTab === "discover" ? `<div class="chips" id="sp-genres" style="margin-top:6px;width:400px">${SP_GENRES.map(g =>
    `<button data-g="${esc(g)}" class="${g === spGenre ? "on" : ""}">${esc(g)}</button>`).join("")}</div>` : "";
  v.innerHTML = `${backHead("sp-back", "Spotify", spTab === "discover" ? 30 : 60)}
    <div class="chips" id="sp-tabs" style="margin-top:6px">${tabs}</div>${genres}
    <div class="list" id="sp-list" style="max-height:${spTab === "discover" ? 200 : 290}px"><p class="muted">Loading…</p></div>`;
  $("#sp-back").onclick = () => {
    if (!spTrack()) return openApp("home");
    S.spotifyBrowse = false; v.dataset.mode = ""; RENDER.spotify();
  };
  $("#sp-tabs").onclick = e => { const b = e.target.closest("[data-tab]"); if (b) { spTab = b.dataset.tab; spotifyLibrary(true); } };
  if ($("#sp-genres")) $("#sp-genres").onclick = e => { const b = e.target.closest("[data-g]"); if (b) { spGenre = b.dataset.g; spotifyLibrary(true); } };
  const tab = spTab;
  let rows;
  try { rows = await spLoadTab(); } catch (e) { $("#sp-list").innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  if (tab !== spTab || v.dataset.mode !== "library") return;
  const empty = { recent: "Nothing played yet.", top: "No top tracks yet — Spotify builds these over time.", liked: "No liked songs yet.", playlists: "No saved playlists.", albums: "No saved albums.", discover: "No playlists found." };
  $("#sp-list").innerHTML = rows.map((r, i) => `<button class="row" data-i="${i}">
      ${r.img ? `<img src="${esc(r.img)}" alt="">` : `<span class="thumb"></span>`}
      <span class="t"><b>${esc(r.name)}</b><span>${esc(r.sub)}</span></span></button>`).join("")
    || `<p class="muted">${empty[tab]}</p>`;
  $("#sp-list").onclick = async e => {
    const b = e.target.closest("[data-i]"); if (!b) return;
    if (!SP.deviceId) { toast("Spotify player isn't ready"); return; }
    const r = rows[+b.dataset.i];
    toast("Playing " + r.name);
    try { await spWeb(`me/player/play?device_id=${SP.deviceId}`, { method: "PUT", body: r.play }); }
    catch (err) { toast("Spotify: " + err.message); return; }
    S.spotifyBrowse = false; v.dataset.mode = "";
  };
}

// ------------------------------------------------------------------ radio
// A station just picked stays on the now-playing screen while satd pauses the other
// players and mpv tunes in -- a slow or empty status in that window must not bounce
// the screen back to the station list.
let radioStarting = null;               // { station, at }
async function pollRadio() {
  let r;
  try { r = await api("/api/radio/status", { timeout: 3000 }) || { playing: false }; } catch { r = { playing: false }; }
  const st = radioStarting;
  if (st && Date.now() - st.at < 10000 && !(r.station && r.station.url === st.station.url && r.playing))
    r = { ...r, playing: true, buffering: true, station: st.station };
  else if (st && (r.playing || Date.now() - st.at >= 10000)) radioStarting = null;
  S.radio = r;
}

function needleFor(name) { let h = 0; for (const c of name || "") h = (h * 31 + c.charCodeAt(0)) >>> 0; return 8 + (h % 84); }

RENDER.radio = async (fresh) => {
  const v = $("#v-radio");
  if (fresh) await pollRadio();
  const r = S.radio;
  if (S.radioBrowse) return radioBrowse(fresh);
  if (!r.playing && !r.station) { S.radioBrowse = "favorites"; return radioBrowse(true); }
  if (v.dataset.mode !== "playing" || v.dataset.url !== r.station.url) {
    v.dataset.mode = "playing"; v.dataset.url = r.station.url;
    v.innerHTML = `<div class="label">Radio</div>
      <div class="dialwin"><div class="ticks"></div><div class="needle" id="rd-needle" style="left:50%"></div></div>
      <div class="station" id="rd-station"></div><div class="now" id="rd-now"></div>
      <div class="eq" id="rd-eq"><i></i><i></i><i></i><i></i><i></i></div>
      <div class="controls" style="display:flex;gap:20px;margin-top:18px;align-items:center">
        <button class="round" id="rd-browse">${I.list}</button>
        <button class="round primary" id="rd-stop">${I.stop}</button>
        <span style="width:72px"></span>
      </div>
      <div class="vol"><button id="rd-vdn">−</button><span id="rd-vol"></span><button id="rd-vup">+</button></div>`;
    $("#rd-station").textContent = r.station.name;
    requestAnimationFrame(() => { $("#rd-needle").style.left = needleFor(r.station.name) + "%"; });
    $("#rd-stop").onclick = async () => { await post("/api/radio/stop"); await pollRadio(); S.radioBrowse = "favorites"; RENDER.radio(true); };
    $("#rd-browse").onclick = () => { S.radioBrowse = "favorites"; radioBrowse(true); };
    $("#rd-vdn").onclick = () => masterStep(-5);
    $("#rd-vup").onclick = () => masterStep(5);
  }
  $("#rd-now").textContent = r.buffering ? "Tuning…" : (r.now || "");
  $("#rd-eq").style.visibility = r.playing && !r.buffering ? "visible" : "hidden";
  volLabels();
};

let radioPresets = null;
async function radioBrowse(fresh) {
  const v = $("#v-radio");
  if (!radioPresets) { try { radioPresets = await api("/api/radio/presets"); } catch { radioPresets = { presets: [], genres: [] }; } }
  const key = S.radioBrowse || "favorites";
  if (!fresh && v.dataset.mode === "browse:" + key) return;
  v.dataset.mode = "browse:" + key;
  const chips = ["favorites", ...radioPresets.genres].map(g =>
    `<button data-g="${esc(g)}" class="${g === key ? "on" : ""}">${g === "favorites" ? "★ Favorites" : esc(g[0].toUpperCase() + g.slice(1))}</button>`).join("");
  v.innerHTML = `${S.radio.playing ? backHead("rd-back", "Radio", 46) : `<div class="label" style="margin-top:56px">Radio</div>`}
    <div class="chips" id="rd-chips" style="margin:12px 0 6px">${chips}</div>
    <div class="list" id="rd-list" style="max-height:250px"><p class="muted">Loading…</p></div>`;
  $("#rd-chips").onclick = e => { const b = e.target.closest("[data-g]"); if (!b) return; S.radioBrowse = b.dataset.g; radioBrowse(true); };
  if ($("#rd-back")) $("#rd-back").onclick = () => { S.radioBrowse = null; v.dataset.mode = ""; RENDER.radio(true); };
  let stations;
  if (key === "favorites") stations = radioPresets.presets;
  else {
    try { stations = (await api("/api/radio/genre/" + encodeURIComponent(key), { timeout: 10000 })).stations; }
    catch (e) { $("#rd-list").innerHTML = `<p class="muted">Station directory unreachable.</p>`; return; }
  }
  if (S.radioBrowse !== key) return;
  $("#rd-list").innerHTML = stations.map((s, i) => `<button class="row${S.radio.station && S.radio.station.url === s.url ? " on" : ""}" data-i="${i}">
      ${s.favicon ? `<img src="${esc(s.favicon)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'thumb'}))">` : `<span class="thumb"></span>`}
      <span class="t"><b>${esc(s.name)}</b><span>${[s.country, s.codec, s.bitrate ? s.bitrate + "k" : ""].filter(Boolean).join(" · ") || "&nbsp;"}</span></span></button>`).join("")
    || `<p class="muted">No stations.</p>`;
  $("#rd-list").onclick = async e => {
    const b = e.target.closest("[data-i]"); if (!b) return;
    const s = stations[+b.dataset.i];
    const station = { name: s.name, url: s.url, favicon: s.favicon };
    radioStarting = { station, at: Date.now() };
    S.radio = { ...S.radio, playing: true, buffering: true, now: null, station };
    S.radioBrowse = null; v.dataset.mode = "";
    RENDER.radio();
    try { await api("/api/radio/play", { body: s, timeout: 15000 }); }
    catch (err) {
      radioStarting = null; toast("Radio: " + err.message);
      await pollRadio(); if (S.view === "radio" && !S.radio.playing) { S.radioBrowse = "favorites"; RENDER.radio(true); }
      return;
    }
    await pollRadio(); if (S.view === "radio" && !S.radioBrowse) RENDER.radio();
  };
}

// ------------------------------------------------------------------ weather
// A scrolling column (now -> next hours -> 7 days); tap a day for its breakdown.
async function pollWeather() { try { S.weather = await api("/api/weather", { timeout: 12000 }); } catch (e) { S.weather = S.weather || { error: e.message }; } }

let wxDay = null;   // index into daily, or null for the overview
const hourLabel = (d) => { const h = d.getHours(); return (h % 12 || 12) + (h < 12 ? "a" : "p"); };
const fmtClock = (iso) => { const d = new Date(iso); return (d.getHours() % 12 || 12) + ":" + String(d.getMinutes()).padStart(2, "0") + (d.getHours() < 12 ? " am" : " pm"); };
const dayName = (iso, i, long) => i === 0 ? "Today" : i === 1 && long ? "Tomorrow" : new Date(iso + "T12:00").toLocaleDateString(undefined, { weekday: long ? "long" : "short" });

RENDER.weather = (fresh) => {
  const v = $("#v-weather"), w = S.weather;
  if (fresh) wxDay = null;
  if (!w || !w.current) { v.innerHTML = `<div class="label">Weather</div><p class="muted">${w && w.error ? esc(w.error) : "Loading…"}</p>`; return; }
  const keep = v.querySelector(".wscroll") && v.dataset.day === String(wxDay) ? v.querySelector(".wscroll").scrollTop : 0;
  v.dataset.day = String(wxDay);
  v.innerHTML = `<div class="wscroll" id="wx-scroll">${wxDay === null ? wxOverview(w) : wxDetail(w, wxDay)}</div>`;
  $("#wx-scroll").scrollTop = keep;
  if ($("#wx-days")) $("#wx-days").onclick = e => { const b = e.target.closest("[data-d]"); if (!b) return; wxDay = +b.dataset.d; RENDER.weather(); };
  if ($("#wx-back")) $("#wx-back").onclick = () => { wxDay = null; RENDER.weather(); };
};

function nowIndex(w) {
  const now = Date.now();
  let i = w.hourly.time.findIndex(t => new Date(t).getTime() > now);
  return Math.max(0, (i < 0 ? w.hourly.time.length : i) - 1);
}

function wxOverview(w) {
  const cur = w.current, u = w.units || "F", d = w.daily, h = w.hourly;
  const [ico, desc] = wmo(cur.weather_code, cur.is_day);
  const i0 = nowIndex(w);
  const hours = [];
  for (let i = i0 + 1; i <= i0 + 12 && i < h.time.length; i += 2) {
    const p = h.precipitation_probability[i];
    hours.push(`<div><span>${hourLabel(new Date(h.time[i]))}</span><span class="i">${wmo(h.weather_code[i], h.is_day[i])[0]}</span><b>${Math.round(h.temperature_2m[i])}°</b><em>${p >= 20 ? p + "%" : ""}</em></div>`);
  }
  const n = d.time.length;
  const lo = Math.min(...d.temperature_2m_min), hi = Math.max(...d.temperature_2m_max), span = Math.max(1, hi - lo);
  const days = d.time.map((t, i) => {
    const l = (d.temperature_2m_min[i] - lo) / span * 100, r = (hi - d.temperature_2m_max[i]) / span * 100;
    const p = d.precipitation_probability_max[i];
    return `<button class="wday" data-d="${i}"><span class="n">${dayName(t, i)}</span><span>${wmo(d.weather_code[i])[0]}</span>
      <span class="p">${p >= 20 ? p + "%" : ""}</span>
      <span class="lo">${Math.round(d.temperature_2m_min[i])}°</span>
      <span class="track"><i class="bar" style="left:${l}%;right:${r}%"></i></span>
      <span class="hi">${Math.round(d.temperature_2m_max[i])}°</span></button>`;
  }).join("");
  return `<div class="label">${esc(w.place || "Weather")}</div>
    <div class="now"><span class="ico">${ico}</span><span class="temp">${Math.round(cur.temperature_2m)}°</span></div>
    <div class="muted" style="font-size:17px">${esc(desc)} · feels ${Math.round(cur.apparent_temperature)}°</div>
    <div class="muted" style="font-size:15px;margin-top:4px">💧 ${cur.relative_humidity_2m}% · 💨 ${Math.round(cur.wind_speed_10m)} ${u === "F" ? "mph" : "km/h"} · 🌅 ${fmtClock(d.sunrise[0])} · 🌇 ${fmtClock(d.sunset[0])}</div>
    <div class="hours">${hours.join("")}</div>
    <div class="label" style="margin:10px 0 6px">${n} days · tap one</div>
    <div class="wdays" id="wx-days">${days}</div>`;
}

function wxDetail(w, i) {
  const d = w.daily, h = w.hourly, u = w.units || "F";
  const [ico, desc] = wmo(d.weather_code[i]);
  const day = d.time[i];
  const cells = [];
  h.time.forEach((t, k) => {
    if (!t.startsWith(day)) return;
    const hr = new Date(t).getHours();
    if (hr % 3) return;
    const p = h.precipitation_probability[k];
    cells.push(`<div><span>${hourLabel(new Date(t))}</span><span class="i">${wmo(h.weather_code[k], h.is_day[k])[0]}</span><b>${Math.round(h.temperature_2m[k])}°</b><em>${p >= 10 ? p + "%" : ""}</em></div>`);
  });
  const rain = d.precipitation_sum[i];
  return `${backHead("wx-back", dayName(day, i, true), 0)}
    <div class="muted" style="font-size:15px;margin-top:6px">${new Date(day + "T12:00").toLocaleDateString(undefined, { month: "long", day: "numeric" })}</div>
    <div class="now" style="margin-top:4px"><span class="ico">${ico}</span><span class="temp" style="font-size:76px">${Math.round(d.temperature_2m_max[i])}°</span>
      <span class="muted" style="font-size:30px;font-weight:300">/ ${Math.round(d.temperature_2m_min[i])}°</span></div>
    <div style="font-size:18px">${esc(desc)}</div>
    <div class="wstats">
      <span>☔ ${d.precipitation_probability_max[i]}%${rain ? ` · ${rain} ${u === "F" ? "in" : "mm"}` : ""}</span>
      <span>💨 up to ${Math.round(d.wind_speed_10m_max[i])} ${u === "F" ? "mph" : "km/h"}</span>
      <span>☀️ UV ${Math.round(d.uv_index_max[i] ?? 0)}</span>
      <span>🌅 ${fmtClock(d.sunrise[i])} · 🌇 ${fmtClock(d.sunset[i])}</span>
    </div>
    <div class="hours grid">${cells.join("")}</div>`;
}

// ------------------------------------------------------------------ timers
async function pollTimers() { try { S.timers = (await api("/api/timers", { timeout: 3000 })).timers; } catch {} }

const PRESETS = [1, 2, 3, 5, 10, 15, 20, 30];
const TMR_R = 54, TMR_LEN = 2 * Math.PI * TMR_R;
RENDER.timers = (fresh) => {
  const v = $("#v-timers");
  if (fresh || v.dataset.built !== "1") {
    v.dataset.built = "1";
    v.innerHTML = `<div class="label">Timers</div>
      <div class="presets" id="tm-presets">${PRESETS.map(m => `<button data-m="${m}">${m}<small>min</small></button>`).join("")}</div>
      <div class="active" id="tm-active"></div>`;
    $("#tm-presets").onclick = async e => {
      const b = e.target.closest("[data-m]"); if (!b) return;
      await post("/api/timers", { seconds: +b.dataset.m * 60, label: b.dataset.m + " min" });
      await pollTimers(); RENDER.timers();
    };
    $("#tm-active").onclick = async e => {
      const b = e.target.closest("[data-id]"); if (!b) return;
      if (b.dataset.armed !== "1") { b.dataset.armed = "1"; toast("Tap again to cancel"); setTimeout(() => { b.dataset.armed = ""; }, 2500); return; }
      await api("/api/timers/" + b.dataset.id, { method: "DELETE" }); await pollTimers(); RENDER.timers();
    };
  }
  const act = $("#tm-active");
  const live = S.timers.filter(t => !t.done);
  if (!live.length) { act.innerHTML = `<p class="muted" style="font-size:16px">Tap a time to start a timer.</p>`; return; }
  const ids = live.map(t => t.id).join();
  if (act.dataset.ids !== ids) {
    act.dataset.ids = ids;
    act.innerHTML = live.map(t => `<button class="tmr" data-id="${t.id}"><svg viewBox="0 0 120 120"><circle class="bg" cx="60" cy="60" r="${TMR_R}"/>
      <circle class="fg" cx="60" cy="60" r="${TMR_R}" stroke-dasharray="${TMR_LEN}"/></svg><span class="txt"><span></span><small>${esc(t.label)}</small></span></button>`).join("");
  }
  live.forEach(t => {
    const b = act.querySelector(`[data-id="${t.id}"]`); if (!b) return;
    b.querySelector(".txt span").textContent = mmss(t.remaining);
    b.querySelector(".fg").style.strokeDashoffset = TMR_LEN * (1 - t.remaining / t.total);
  });
};

function localTick() {   // keep countdowns smooth between polls
  S.timers.forEach(t => { if (!t.done) t.remaining = Math.max(0, t.remaining - 1); });
}

function renderAlarm() {
  const ringing = S.timers.filter(t => t.done);
  $("#alarm").classList.toggle("shown", ringing.length > 0);
  if (ringing.length) { $("#alarm-label").textContent = ringing.map(t => t.label || "Timer").join(" · "); wake(); }
}
$("#alarm-stop").onclick = async () => {
  for (const t of S.timers.filter(t => t.done)) await api("/api/timers/" + t.id, { method: "DELETE" }).catch(() => {});
  await pollTimers(); renderAlarm();
};

// ------------------------------------------------------------------ phone audio (bluetooth)
// The Satellite as a Bluetooth speaker for his phone (Audible, anything). Shows
// the phone's AVRCP track info and controls; pairing opens only on request.
async function pollBt() { try { S.bt = await api("/api/bt/status", { timeout: 4000 }); } catch { S.bt = S.bt || null; } }
function btIsPlaying() { return !!(S.bt && S.bt.player && S.bt.player.status === "playing"); }
const btCmd = (action, path) => post("/api/bt/cmd", { action, path }).catch(e => toast("Bluetooth: " + e.message));

RENDER.phone = async (fresh) => {
  const v = $("#v-phone");
  if (fresh) await pollBt();
  const b = S.bt;
  if (!b) { v.innerHTML = `<div class="label">Phone audio</div><p class="muted">Bluetooth isn't responding.</p>`; return; }
  const p = b.player;
  const key = JSON.stringify([p && [p.title, p.artist, p.status], b.devices.map(d => [d.name, d.connected]), b.pairing_left > 0]);
  if (v.dataset.key === key && !fresh) {                       // only the countdown moved
    const c = v.querySelector(".pair-left"); if (c) c.textContent = mmss(b.pairing_left);
    return;
  }
  v.dataset.key = key;
  if (p) {
    v.innerHTML = `<div class="label">${esc(p.app || p.device || "Phone audio")}</div>
      <div class="art" style="width:150px;height:150px;border-radius:50%;display:grid;place-items:center;margin:14px 0;background:var(--band);font-size:64px">🎧</div>
      <div class="track" style="font-size:22px;font-weight:600;max-width:400px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.title || "Playing from " + (p.device || "your phone"))}</div>
      <div class="muted" style="font-size:17px;max-width:380px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc([p.artist, p.album].filter(Boolean).join(" · "))}</div>
      <div class="controls" style="display:flex;gap:22px;margin-top:16px;align-items:center">
        <button class="round" data-a="Previous">${I.prev}</button>
        <button class="round primary" data-a="${p.status === "playing" ? "Pause" : "Play"}">${p.status === "playing" ? I.pause : I.play}</button>
        <button class="round" data-a="Next">${I.next}</button>
      </div>
      <p class="muted" style="font-size:14px;margin-top:12px">Volume follows your phone</p>`;
    v.querySelector(".controls").onclick = e => { const x = e.target.closest("[data-a]"); if (x) btCmd(x.dataset.a, p.path).then(() => setTimeout(() => RENDER.phone(true), 500)); };
    return;
  }
  const connected = b.devices.find(d => d.connected);
  v.innerHTML = `<div class="label" style="margin-top:${b.devices.length ? 40 : 0}px">Phone audio</div>
    <p style="font-size:20px;margin:12px 0 4px">${connected ? `Connected to ${esc(connected.name)}` : "No phone connected"}</p>
    <p class="muted" style="font-size:16px;max-width:340px;margin:0 0 12px">${connected ? "Play something on your phone — podcasts, anything." : "Connect from your phone's Bluetooth settings, or tap a phone below."}</p>
    ${b.devices.length ? `<div class="list" id="bt-devs" style="max-height:170px">${b.devices.map((d, i) => `
      <div class="row${d.connected ? " on" : ""}" style="padding-right:8px">
        <button class="t" data-i="${i}" style="border:0;background:none;color:inherit;font:inherit;text-align:left;padding:0">
          <b>${esc(d.name)}</b><span>${d.connected ? "Connected · tap to disconnect" : "Tap to connect"}</span></button>
        <button class="corner-btn" data-f="${i}" style="position:static;width:44px;height:44px" aria-label="Forget">✕</button>
      </div>`).join("")}</div>` : ""}
    ${b.pairing_left > 0 ? `<p class="muted" style="font-size:16px;max-width:340px;margin:10px 0 0">Discoverable as <b>${esc(b.alias || "Satellite")}</b> — pick it in your phone's Bluetooth settings · <span class="pair-left">${mmss(b.pairing_left)}</span></p>`
      : `<button class="pill" id="bt-pair" style="margin-top:12px">Pair a phone</button>`}`;
  if ($("#bt-pair")) $("#bt-pair").onclick = async () => { try { await post("/api/bt/pair"); } catch (e) { toast(e.message); } RENDER.phone(true); };
  if ($("#bt-devs")) $("#bt-devs").onclick = async e => {
    const c = e.target.closest("[data-i]"), f = e.target.closest("[data-f]");
    if (f) {
      if (f.dataset.armed !== "1") { f.dataset.armed = "1"; toast("Tap ✕ again to forget"); setTimeout(() => { f.dataset.armed = ""; }, 2500); return; }
      await btCmd("Forget", b.devices[+f.dataset.f].path); return RENDER.phone(true);
    }
    if (c) { const d = b.devices[+c.dataset.i]; toast(d.connected ? "Disconnecting…" : "Connecting…"); await btCmd(d.connected ? "Disconnect" : "Connect", d.path); RENDER.phone(true); }
  };
};

// ------------------------------------------------------------------ calendar
// His Google calendar, via Home Assistant (so Claude reads the same thing).
// Overview: a scrolling list grouped by day. Tap a day heading or an event to
// open that day; "‹ DAY" goes back to the overview where he left it.
async function pollCalendar() { try { S.cal = await api("/api/calendar", { timeout: 10000 }); } catch { S.cal = S.cal || null; } }

function calDayLabel(d, long) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - today) / 86400e3);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return d.toLocaleDateString(undefined, long ? { weekday: "long" } : { weekday: "long", month: "short", day: "numeric" });
}
const calTime = d => (d.getHours() % 12 || 12) + (d.getMinutes() ? ":" + String(d.getMinutes()).padStart(2, "0") : "") + (d.getHours() < 12 ? "a" : "p");
const calStart = e => e.all_day ? new Date(e.start + "T00:00") : new Date(e.start);
const calEnd = e => e.all_day ? new Date(e.end + "T00:00") : new Date(e.end || e.start);
const calKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function nextEvent() {
  const now = Date.now();
  return ((S.cal && S.cal.events) || []).find(e => !e.all_day && new Date(e.end || e.start).getTime() > now);
}

let calDay = null;          // "YYYY-MM-DD" when a day is open, else null
let calScroll = 0;          // overview scroll position, restored on the way back

function calUpcoming() {
  const now = Date.now();
  return ((S.cal && S.cal.events) || []).filter(e => calEnd(e).getTime() > now);
}

RENDER.calendar = async (fresh) => {
  const v = $("#v-calendar");
  if (fresh) { calDay = null; calScroll = 0; }
  if (fresh || !S.cal) await pollCalendar();
  const c = S.cal;
  if (!c || !c.configured) {
    v.innerHTML = `<div class="label">Calendar</div><p class="muted" style="font-size:17px;max-width:340px">Your calendar isn't connected yet.</p>`;
    return;
  }
  const events = calUpcoming();
  if (!events.length) { v.innerHTML = `<div class="label">Calendar</div><p style="font-size:20px">Nothing in the next week.</p>`; return; }
  calDay ? calRenderDay(v, events) : calRenderOverview(v, events);
};

function calRow(e, i, detailed) {
  const s = calStart(e), en = calEnd(e);
  const when = e.all_day ? "All day" : calTime(s);
  const range = !e.all_day && detailed && e.end ? `${calTime(s)} – ${calTime(en)}` : "";
  const soon = !e.all_day && s.getTime() - Date.now() < 3600e3 && en.getTime() > Date.now();
  return `<button class="row calev${soon ? " on" : ""}" data-e="${i}" style="min-height:54px">
      <span style="width:64px;flex:none;font-weight:600;font-size:16px;color:var(--turq)">${when}</span>
      <span class="t"><b style="${detailed ? "white-space:normal" : ""}">${esc(e.summary)}</b>
        ${range ? `<span>${range}</span>` : ""}
        ${e.location ? `<span class="${detailed ? "loc" : ""}">${esc(e.location)}</span>` : ""}</span></button>`;
}

function calRenderOverview(v, events) {
  let html = "", lastKey = "";
  const counts = {};
  events.forEach(e => { const k = calKey(calStart(e)); counts[k] = (counts[k] || 0) + 1; });
  events.slice(0, 40).forEach((e, i) => {
    const s = calStart(e), k = calKey(s);
    if (k !== lastKey) {
      html += `<button class="calday" data-day="${k}"><span>${esc(calDayLabel(s))}</span><small>${counts[k]} ›</small></button>`;
      lastKey = k;
    }
    html += calRow(e, i, false);
  });
  v.innerHTML = `<div class="wscroll" id="cal-scroll" style="padding-top:90px"><div class="label">Calendar</div><div style="width:400px">${html}</div></div>`;
  const sc = $("#cal-scroll");
  sc.scrollTop = calScroll;
  sc.onclick = ev => {
    const d = ev.target.closest("[data-day]"), r = ev.target.closest("[data-e]");
    if (!d && !r) return;
    calScroll = sc.scrollTop;
    calDay = d ? d.dataset.day : calKey(calStart(events[+r.dataset.e]));
    calRenderDay(v, events);
  };
}

function calRenderDay(v, events) {
  const day = events.filter(e => calKey(calStart(e)) === calDay);
  const date = new Date(calDay + "T12:00");
  const rows = day.map((e, i) => calRow(e, i, true)).join("")
    || `<p class="muted" style="font-size:17px">Nothing on this day.</p>`;
  v.innerHTML = `<div class="wscroll" style="padding-top:84px">
      ${backHead("cal-back", calDayLabel(date, true), 0)}
      <div class="muted" style="font-size:15px;margin:6px 0 10px">${date.toLocaleDateString(undefined, { month: "long", day: "numeric" })} · ${day.length} event${day.length === 1 ? "" : "s"}</div>
      <div style="width:400px">${rows}</div></div>`;
  $("#cal-back").onclick = () => { calDay = null; calRenderOverview(v, calUpcoming()); };
}

// ------------------------------------------------------------------ clock
function clockFace(size, saver) {
  const d = new Date(), c = size / 2, r = c - 6;
  const hrs = d.getHours() % 12 + d.getMinutes() / 60, min = d.getMinutes() + d.getSeconds() / 60, sec = d.getSeconds();
  const hand = (deg, len, w, col, tail = 0) => {
    const a = (deg - 90) * Math.PI / 180;
    return `<line x1="${c - tail * Math.cos(a)}" y1="${c - tail * Math.sin(a)}" x2="${c + len * Math.cos(a)}" y2="${c + len * Math.sin(a)}" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
  };
  let marks = "";
  for (let i = 0; i < 60; i++) {
    const a = (i * 6 - 90) * Math.PI / 180, big = i % 5 === 0;
    if (big) {   // atomic-age starburst markers
      const x = c + (r - 26) * Math.cos(a), y = c + (r - 26) * Math.sin(a);
      marks += i % 15 === 0
        ? `<circle cx="${x}" cy="${y}" r="${size / 52}" fill="${saver ? "#45b5aa88" : "var(--turq)"}"/>`
        : `<polygon points="${[0, 1, 2, 3].map(k => { const b = a + k * Math.PI / 2, rr = k % 2 ? size / 160 : size / 48; return (x + rr * Math.cos(b)) + "," + (y + rr * Math.sin(b)); }).join(" ")}" fill="${saver ? "#f1e7cf66" : "var(--ivory)"}"/>`;
    } else {
      marks += `<circle cx="${c + (r - 26) * Math.cos(a)}" cy="${c + (r - 26) * Math.sin(a)}" r="1.6" fill="#f1e7cf${saver ? "33" : "55"}"/>`;
    }
  }
  const ivory = saver ? "#f1e7cfaa" : "var(--ivory)";
  return `<svg viewBox="0 0 ${size} ${size}">
    ${marks}
    ${hand(hrs * 30, r * .5, size / 42, ivory, r * .08)}
    ${hand(min * 6, r * .74, size / 64, ivory, r * .08)}
    ${saver ? "" : hand(sec * 6, r * .8, size / 200, "var(--red)", r * .16)}
    <circle cx="${c}" cy="${c}" r="${size / 70}" fill="${saver ? "#d2553f99" : "var(--red)"}"/>
  </svg>`;
}
RENDER.clock = () => {
  const d = new Date();
  $("#v-clock").innerHTML = clockFace(470, false) + `<div class="muted" style="position:absolute;bottom:96px;font-size:16px;letter-spacing:.14em;text-transform:uppercase">${d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</div>`;
};

// ------------------------------------------------------------------ home assistant
// Rooms first (HA areas), then a room: its Hue scenes as chips, its lights as toggles.
let haRoom = null, haData = null;
const haCall = (domain, service, entity_id) => post("/api/ha/service", { domain, service, entity_id });
const haLightState = l => l.on ? "On" + (l.brightness ? " · " + Math.max(1, Math.round(l.brightness / 2.55)) + "%" : "") : "Off";

async function haLoad() {
  haData = await api("/api/ha/rooms", { timeout: 12000 });
  return haData;
}

RENDER.ha = async (fresh) => {
  const v = $("#v-ha");
  if (fresh) { haRoom = null; v.innerHTML = `<div class="label">Home</div><p class="muted">Loading…</p>`; }
  let d;
  try { d = await haLoad(); } catch (e) { v.innerHTML = `<div class="label">Home</div><p class="muted">${esc(e.message)}</p>`; return; }
  if (!d.configured) {
    v.innerHTML = `<div class="label">Home</div><p class="muted" style="font-size:17px;padding:0 60px">Home Assistant isn't connected yet.<br><br>Add <b>ha_token</b> to <b>/etc/satd.json</b>.</p>`;
    return;
  }
  if (S.view !== "ha") return;
  haRoom ? haRenderRoom(v, d) : haRenderRooms(v, d);
};

function haRenderRooms(v, d) {
  v.innerHTML = `<div class="label" style="margin-top:46px">Home</div>
    <div class="muted" style="font-size:16px;margin:6px 0 10px">${d.lights_on ? d.lights_on + " light" + (d.lights_on > 1 ? "s" : "") + " on" : "All lights off"}</div>
    ${d.lights_on ? `<button class="pill" id="ha-alloff" style="margin-bottom:8px">All off</button>` : ""}
    <div class="list" id="ha-rooms" style="max-height:${d.lights_on ? 260 : 320}px">${d.rooms.map((r, i) => `
      <button class="row${r.on ? " on" : ""}" data-i="${i}">
        <span class="thumb" style="display:grid;place-items:center;font-size:22px">${r.on ? "💡" : "◌"}</span>
        <span class="t"><b>${esc(r.area)}</b><span>${r.lights.length ? `${r.on} of ${r.lights.length} on` : ""}${r.scenes.length ? `${r.lights.length ? " · " : ""}${r.scenes.length} scenes` : ""}</span></span>
      </button>`).join("")}</div>`;
  $("#ha-rooms").onclick = e => { const b = e.target.closest("[data-i]"); if (!b) return; haRoom = d.rooms[+b.dataset.i].area; haRenderRoom(v, d); };
  if ($("#ha-alloff")) $("#ha-alloff").onclick = async () => {
    const ids = d.rooms.flatMap(r => r.lights.filter(l => l.on).map(l => l.entity_id));
    try { await haCall("light", "turn_off", ids); toast("All lights off"); } catch (err) { toast(err.message); }
    setTimeout(() => S.view === "ha" && RENDER.ha(), 700);
  };
}

function haRenderRoom(v, d) {
  const r = d.rooms.find(x => x.area === haRoom);
  if (!r) { haRoom = null; return haRenderRooms(v, d); }
  const scenes = r.scenes.slice(0, 9);
  v.innerHTML = `${backHead("ha-back", r.area, scenes.length ? 30 : 80)}
    ${r.lights.length ? `<button class="pill${r.on ? " on" : ""}" id="ha-room" style="margin:10px 0 8px">${r.on ? "Turn off" : "Turn on"}</button>` : ""}
    ${scenes.length ? `<div class="chips" id="ha-scenes" style="width:400px;margin-bottom:8px">${scenes.map((s, i) => `<button data-s="${i}">${esc(s.name)}</button>`).join("")}</div>` : ""}
    <div class="list" id="ha-lights" style="max-height:${scenes.length ? 190 : 300}px">${r.lights.map((l, i) => {
      const pct = l.brightness ? Math.max(1, Math.round(l.brightness / 2.55)) : 50;
      return `<div class="lrow${l.on ? " on" : ""}">
      <button class="row" data-l="${i}">
        <span class="thumb" style="display:grid;place-items:center;font-size:22px">${l.on ? "💡" : "◌"}</span>
        <span class="t"><b>${esc(l.name)}</b><span>${haLightState(l)}</span></span>
      </button>${l.dimmable ? `<input type="range" class="dim" min="1" max="100" value="${pct}" data-d="${i}" aria-label="${esc(l.name)} brightness">` : ""}</div>`;
    }).join("")}</div>`;
  const resync = () => setTimeout(() => S.view === "ha" && RENDER.ha(), 700);
  $("#ha-back").onclick = () => { haRoom = null; haRenderRooms(v, d); };
  if ($("#ha-room")) $("#ha-room").onclick = async () => {
    try { await haCall("light", r.on ? "turn_off" : "turn_on", r.lights.map(l => l.entity_id)); } catch (err) { toast(err.message); }
    resync();
  };
  if ($("#ha-scenes")) $("#ha-scenes").onclick = async e => {
    const b = e.target.closest("[data-s]"); if (!b) return;
    const s = scenes[+b.dataset.s];
    try { await haCall("scene", "turn_on", s.entity_id); toast(`${r.area}: ${s.name}`); } catch (err) { toast(err.message); }
    resync();
  };
  const lights = $("#ha-lights");
  lights.onclick = async e => {
    const b = e.target.closest("button[data-l]"); if (!b) return;
    const l = r.lights[+b.dataset.l];
    l.on = !l.on;                                                   // optimistic
    b.parentElement.classList.toggle("on", l.on);
    b.querySelector(".t span").textContent = haLightState(l);
    b.querySelector(".thumb").textContent = l.on ? "💡" : "◌";
    try { await haCall("light", "toggle", l.entity_id); } catch (err) { toast(err.message); }
    resync();
  };
  // Brightness: label follows the finger, the light changes on release.
  lights.oninput = e => {
    const s = e.target.closest("input[data-d]"); if (!s) return;
    const l = r.lights[+s.dataset.d];
    s.parentElement.querySelector(".t span").textContent = `${l.on ? "On" : "Off"} · ${s.value}%`;
  };
  lights.onchange = async e => {
    const s = e.target.closest("input[data-d]"); if (!s) return;
    const l = r.lights[+s.dataset.d];
    l.on = true; l.brightness = s.value * 2.55;
    s.parentElement.classList.add("on");
    s.parentElement.querySelector(".thumb").textContent = "💡";
    s.parentElement.querySelector(".t span").textContent = haLightState(l);
    try { await post("/api/ha/service", { domain: "light", service: "turn_on", entity_id: l.entity_id, brightness_pct: +s.value }); }
    catch (err) { toast(err.message); }
    resync();
  };
}

// ------------------------------------------------------------------ knob
// The radio dial. satd streams turn / click / double / hold; what they mean
// depends on what the screen is doing. First match wins:
//   alarm ringing   any press stops it
//   screensaver     anything just wakes the screen
//   hold            talk to the assistant, from anywhere
//   media mode      turn = volume, click = play/pause, double = menu mode
//   menu mode       turn moves the highlight, click presses it, double = back
// Media mode = something is playing, or was paused under 2 minutes ago (so a
// click resumes instead of opening an app). A double click asks for the menu
// over it; that lapses after 5 s untouched and the dial is volume again.
const KNOB_MEDIA_GRACE = 2 * 60e3, KNOB_MENU_MS = 5e3, KNOB_SHOW_MS = 8e3;
const K = { vol: null, lastTurn: 0, menuUntil: 0, el: null, shownUntil: 0, last: null, volT: null, volHide: null };

function playingSource() {
  if (spotifyIsPlaying()) return "spotify";
  if (S.radio.playing) return "radio";
  if (typeof audIsPlaying === "function" && audIsPlaying()) return "audible";
  if (btIsPlaying()) return "phone";
  return null;
}

// Also called from fastPoll, so "last played" stays fresh while it plays.
function knobMedia() {
  const src = playingSource();
  if (src) { K.last = { src, at: Date.now(), station: src === "radio" ? S.radio.station : (K.last && K.last.station) }; return src; }
  return K.last && Date.now() - K.last.at < KNOB_MEDIA_GRACE ? K.last.src : null;
}

async function knobPlayPause(src) {
  const playing = playingSource() === src;
  try {
    if (src === "spotify" && SP.player) await SP.player.togglePlay();
    else if (src === "radio") {
      if (playing) await post("/api/radio/stop");
      else if (K.last && K.last.station) {
        radioStarting = { station: K.last.station, at: Date.now() };
        await api("/api/radio/play", { body: K.last.station, timeout: 15000 });
      }
      await pollRadio();
      if (S.view === "radio") { S.radioBrowse = S.radio.playing ? null : "favorites"; RENDER.radio(true); }
    }
    else if (src === "audible") await post("/api/audible/cmd", { action: "playpause" });
    else if (src === "phone" && S.bt && S.bt.player) await btCmd(playing ? "Pause" : "Play", S.bt.player.path);
  } catch (e) { toast(e.message); }
  K.last = { ...K.last, at: Date.now() };       // a pause starts the grace period now
  markLive();
}

function showVolume(v) {
  const arc = $("#vol-arc");
  arc.setAttribute("d", v > 0 ? arcPath(392, 0, Math.min(359.9, v * 3.6)) : "");
  $("#vol-ring").classList.add("shown");
  toast(`Volume ${v}%`);
  clearTimeout(K.volHide); K.volHide = setTimeout(() => $("#vol-ring").classList.remove("shown"), 1500);
}

// One volume: the knob, the on-screen -/+ and HA all move satd's master.
function volLabels() {
  for (const el of document.querySelectorAll(".vol span")) el.textContent = K.vol != null ? K.vol + "%" : "";
}

function volumeTo(v) {
  K.vol = Math.max(0, Math.min(100, v));
  K.volLocal = Date.now();
  showVolume(K.vol);
  volLabels();
  clearTimeout(K.volT);
  K.volT = setTimeout(() => post("/api/volume", { set: K.vol }).catch(e => toast("Volume: " + e.message)), 40);
}

function knobVolume(d) {
  const now = Date.now();
  const step = now - K.lastTurn < 70 ? 4 : 2;          // spin it for big moves
  K.lastTurn = now;
  volumeTo((K.vol ?? 50) + d * step);
}

function masterStep(d) { volumeTo(Math.round(((K.vol ?? 50) + d) / 5) * 5); }

// satd echoes every change; our own echoes lag a spin, so only take others'.
function volRemote(v) {
  if (Date.now() - (K.volLocal || 0) < 600 || v === K.vol) return;
  K.vol = v; volLabels();
  if (!S.saver) showVolume(v);
}

// What the highlight walks: the ring on the home screen, else the buttons of
// the open view in reading order (rows, chips, the back header, controls).
function knobTargets() {
  if (S.view === "home") return [...document.querySelectorAll(".app-btn")];
  const v = $("#v-" + S.view);
  return v ? [...v.querySelectorAll("button")].filter(b => b.offsetParent && !b.disabled) : [];
}

function knobShow(el) {
  document.querySelectorAll(".kfocus").forEach(x => x.classList.remove("kfocus"));
  K.el = el;
  if (!el) return;
  el.classList.add("kfocus");
  el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  K.shownUntil = Date.now() + KNOB_SHOW_MS;
}

function knobMove(d) {
  const t = knobTargets();
  if (!t.length) return;
  let i = t.indexOf(K.el);
  const hidden = !document.querySelector(".kfocus");
  if (i < 0) i = S.view === "home" ? Math.max(0, APPS.findIndex(a => a.id === K.lastApp)) : 0;
  else if (!hidden) i = (i + d + t.length) % t.length;   // a hidden highlight reappears before it moves
  knobShow(t[i]);
}

function knobBack() {
  const back = $("#v-" + S.view + " .back-head");
  if (back && back.offsetParent) { back.click(); K.el = null; setTimeout(() => knobMove(0), 350); return; }
  K.lastApp = S.view;
  openApp("home");
  K.el = null; knobMove(0);
}

function knobEvent(ev) {
  const wasSaver = S.saver;
  wake();
  if (S.timers.some(t => t.done)) { if (ev.t !== "turn") $("#alarm-stop").click(); return; }
  if (wasSaver) return;
  if (ev.t === "hold") { toast("Listening…"); post("/api/knob/talk").catch(e => toast("Talk: " + e.message)); return; }
  const media = knobMedia();
  const menu = !media || Date.now() < K.menuUntil;
  if (menu && media) K.menuUntil = Date.now() + KNOB_MENU_MS;
  if (!menu) {
    if (ev.t === "turn") return knobVolume(ev.d);
    if (ev.t === "click") return knobPlayPause(media);
    if (ev.t === "double") { K.menuUntil = Date.now() + KNOB_MENU_MS; K.el = null; return knobMove(0); }
    return;
  }
  if (ev.t === "turn") return knobMove(ev.d);
  if (ev.t === "click") {
    const el = document.querySelector(".kfocus");
    if (!el) return knobMove(0);
    if (S.view === "home") K.lastApp = el.dataset.app;
    el.click();
    if (S.view !== "home" && el.classList.contains("app-btn")) { K.el = null; setTimeout(() => knobMove(0), 400); }
    return;
  }
  if (ev.t === "double") {
    if (S.view !== "home") return knobBack();
    K.menuUntil = 0; knobShow(null);                   // home + double: leave the menu
  }
}

function knobTick() {       // from everySecond: drop a stale highlight
  const lapsed = K.shownUntil && Date.now() > K.shownUntil;
  const menuOver = knobMedia() && Date.now() > K.menuUntil;
  if (document.querySelector(".kfocus") && (lapsed || menuOver)) {
    document.querySelectorAll(".kfocus").forEach(x => x.classList.remove("kfocus"));
    K.shownUntil = 0;
  }
}

function knobConnect() {
  api("/api/volume").then(j => { if (j && j.volume != null) { K.vol = j.volume; volLabels(); } }).catch(() => {});
  const es = new EventSource("/api/knob/stream");        // reconnects by itself
  es.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.t === "sp-reconnect") spReconnect();          // satd, on HA's behalf (not the dial)
      else if (ev.t === "open") remoteOpen(ev.app);
      else if (ev.t === "vol") volRemote(ev.v);
      else knobEvent(ev);
    } catch (err) { report("knob: " + (err.stack || err.message)); }
  };
}

// ------------------------------------------------------------------ idle, screensaver, backlight
function nightTime() { const h = new Date().getHours(); return h >= 22 || h < 7; }
function backlight(level) { post("/api/backlight", { level }).catch(() => {}); }

function wake() {
  S.lastTouch = Date.now();
  if (S.saver) { S.saver = false; $("#saver").classList.remove("shown"); backlight(255); }
}
document.addEventListener("pointerdown", e => {
  const wasSaver = S.saver;
  wake();
  if (wasSaver) { e.stopPropagation(); e.preventDefault(); }   // the waking tap does nothing else
}, true);

function idleCheck() {
  const idle = Date.now() - S.lastTouch;
  if (!S.saver && idle > IDLE_SAVER_MS && !S.timers.some(t => t.done)) {
    S.saver = true; $("#saver").classList.add("shown"); backlight(nightTime() ? 25 : 90);
  }
  if (S.view !== "home" && idle > IDLE_HOME_MS) openApp("home");
  if (S.saver) $("#saver").innerHTML = clockFace(640, true);
}

// ------------------------------------------------------------------ loops
let btWasPlaying = false;
async function fastPoll() {
  const audible = typeof pollAudible === "function";
  await Promise.all([pollRadio(), pollTimers(), pollBt(),
                     audible && (S.view === "audible" || AUD.st.active) ? pollAudible() : null]);
  // Phone audio starting takes the speaker: radio stops, Spotify and Audible pause.
  const btNow = btIsPlaying();
  if (btNow && !btWasPlaying) {
    if (S.radio.playing) post("/api/radio/stop").catch(() => {});
    if (spotifyIsPlaying() && SP.player) SP.player.pause();
    if (audible && audIsPlaying()) post("/api/audible/cmd", { action: "pause" }).catch(() => {});
  }
  btWasPlaying = btNow;
  knobMedia();
  const src = playingSource();      // satd turns the satellite's wake word off while this is set
  post("/api/audio/state", { playing: !!src, source: src }).catch(() => {});
  markLive(); renderAlarm();
  if (S.view === "home") RENDER.home();
  else if (S.view === "spotify" && !S.spotifyBrowse) RENDER.spotify();
  else if (S.view === "radio" && !S.radioBrowse) RENDER.radio();
  else if (S.view === "timers") RENDER.timers();
  else if (S.view === "phone") RENDER.phone();
  else if (S.view === "audible" && audible && !AUD.browse) RENDER.audible();
}

function everySecond() {
  localTick();
  if (S.view === "home") RENDER.home();
  else if (S.view === "clock") RENDER.clock();
  else if (S.view === "timers") RENDER.timers();
  else if (S.view === "spotify" && $("#sp-prog") && SP.state && SP.state.duration) {
    $("#sp-prog").style.strokeDashoffset = PROG_LEN * (1 - spotifyPosition() / SP.state.duration);
  }
  idleCheck();
  knobTick();
}

buildRing();
markActive();
RENDER.home();
// Deep links for screenshots: #weather, #ha, #ha=Living Room
if (location.hash.length > 1) setTimeout(() => {
  const [view, arg] = decodeURIComponent(location.hash.slice(1)).split("=");
  openApp(view);
  if (view === "ha" && arg) haLoad().then(d => { haRoom = arg; haRenderRoom($("#v-ha"), d); });
  if (view === "weather" && arg) (S.weather ? Promise.resolve() : pollWeather()).then(() => { wxDay = +arg; RENDER.weather(); });
  if (view === "calendar" && arg) pollCalendar().then(() => { calDay = arg; RENDER.calendar(); });
}, 300);
pollWeather().then(() => { if (S.view === "home") RENDER.home(); if (S.view === "weather") RENDER.weather(); });
setInterval(() => pollWeather().then(() => S.view === "weather" && RENDER.weather()), 10 * 60e3);
setInterval(fastPoll, 2000);
pollCalendar().then(() => S.view === "home" && RENDER.home());
setInterval(() => pollCalendar().then(() => S.view === "calendar" && RENDER.calendar()), 5 * 60e3);
initSpotify();
knobConnect();
setInterval(everySecond, 1000);
fastPoll();
