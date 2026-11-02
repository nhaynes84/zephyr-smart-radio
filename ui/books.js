"use strict";

// ------------------------------------------------------------------- Books app
// His audiobooks: Audiobookshelf on talos, played by satd (books.py). Now
// playing: cover, chapter ring, ±30, chapters, speed. Library: in-progress
// first; tap to resume. Position syncs with his phone, so either picks up where
// the other stopped. (Internal names still say "aud"/"audible": same routes.)
const AUD = { st: { active: false }, lib: null, browse: false, starting: null };
const AUD_RATES = [1, 1.25, 1.5, 1.75, 2, 0.8];

async function pollAudible() {
  try { AUD.st = await api("/api/audible/status", { timeout: 6000 }); } catch { AUD.st = { active: false }; }
}
function audIsPlaying() { return !!(AUD.st && AUD.st.active && !AUD.st.paused); }
const audCmd = (action, value) => post("/api/audible/cmd", { action, value })
  .then(() => setTimeout(async () => { await pollAudible(); S.view === "audible" && RENDER.audible(); }, 300))
  .catch(e => toast("Books: " + e.message));

function hms(sec) { sec = Math.max(0, Math.floor(sec)); const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60; return h ? `${h}h ${m}m` : `${m}m`; }

RENDER.audible = async (fresh) => {
  const v = $("#v-audible");
  if (fresh) { AUD.browse = false; await pollAudible(); }
  if (AUD.browse || (!AUD.st.active && !AUD.starting)) return audLibrary(v, fresh);
  if (AUD.starting && !AUD.st.active) {
    if (v.dataset.mode !== "starting") {
      v.dataset.mode = "starting";
      v.innerHTML = `<div class="label">Books</div><p style="font-size:20px;margin-top:14px">Opening ${esc(AUD.starting)}…</p>`;
    }
    return;
  }
  const s = AUD.st, ch = s.chapter;
  if (v.dataset.mode !== "playing" || v.dataset.asin !== s.asin) {
    v.dataset.mode = "playing"; v.dataset.asin = s.asin;
    v.innerHTML = `${progressSvg("aud-prog")}
      <button class="corner-btn" id="aud-lib" style="left:120px;top:96px" aria-label="Library">${I.list}</button>
      <button class="corner-btn" id="aud-rate" style="right:112px;top:100px;width:auto;padding:0 12px;font:700 17px Inter,sans-serif;color:var(--ivory)"></button>
      <img class="art" id="aud-art" alt="" style="width:200px;height:200px">
      <div class="track" id="aud-title" style="margin-top:14px"></div>
      <div class="artist" id="aud-ch"></div>
      <div class="controls" style="margin-top:12px">
        <button class="corner-btn" id="aud-prevch" style="position:static" aria-label="Previous chapter">${I.prev}</button>
        <button class="round" id="aud-b30" style="font:700 17px Inter,sans-serif">⟲30</button>
        <button class="round primary" id="aud-pp"></button>
        <button class="round" id="aud-f30" style="font:700 17px Inter,sans-serif">30⟳</button>
        <button class="corner-btn" id="aud-nextch" style="position:static" aria-label="Next chapter">${I.next}</button>
      </div>
      <div class="muted" id="aud-left" style="font-size:15px;margin-top:10px"></div>`;
    $("#aud-art").src = s.cover || "";
    $("#aud-title").textContent = s.title || "Books";
    $("#aud-lib").onclick = () => { AUD.browse = true; audLibrary(v, true); };
    $("#aud-pp").onclick = () => audCmd("playpause");
    $("#aud-b30").onclick = () => audCmd("back30");
    $("#aud-f30").onclick = () => audCmd("fwd30");
    $("#aud-prevch").onclick = () => audCmd("prevch");
    $("#aud-nextch").onclick = () => audCmd("nextch");
    $("#aud-rate").onclick = () => {
      const i = AUD_RATES.findIndex(r => Math.abs(r - (AUD.st.rate || 1)) < 0.01);
      audCmd("rate", AUD_RATES[(i + 1) % AUD_RATES.length]);
    };
  }
  $("#aud-pp").innerHTML = s.paused ? I.play : I.pause;
  $("#aud-art").classList.toggle("spin", !s.paused);
  $("#aud-rate").textContent = `${+(s.rate || 1).toFixed(2)}×`;
  $("#aud-ch").textContent = ch ? `Chapter ${ch.index + 1} of ${ch.count} · ${ch.title}` : (s.author || "");
  let frac = s.dur ? s.t / s.dur : 0, left = `${hms(s.dur - s.t)} left in the book`;
  if (ch) {
    const into = s.t * 1000 - ch.start_ms;
    frac = Math.min(1, Math.max(0, into / ch.length_ms));
    left = `${hms((ch.length_ms - into) / 1000)} left in chapter · ${hms(s.dur - s.t)} in book`;
  }
  $("#aud-prog").style.strokeDashoffset = PROG_LEN * (1 - frac);
  $("#aud-left").textContent = left;
};

async function audLibrary(v, fresh) {
  if (!fresh && v.dataset.mode === "library") return;
  v.dataset.mode = "library";
  v.innerHTML = `${AUD.st.active ? backHead("aud-back", "Now playing", 40) : `<div class="label" style="margin-top:56px">Books</div>`}
    <div class="list" id="aud-list" style="max-height:330px;margin-top:8px"><p class="muted">Loading your library…</p></div>`;
  if ($("#aud-back")) $("#aud-back").onclick = () => { AUD.browse = false; v.dataset.mode = ""; RENDER.audible(); };
  let d;
  try { d = AUD.lib && !fresh ? AUD.lib : (AUD.lib = await api("/api/audible/library", { timeout: 90000 })); }
  catch (e) { $("#aud-list").innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  if (v.dataset.mode !== "library") return;
  if (!d.signed_in) {
    $("#aud-list").innerHTML = `<p style="font-size:19px">Can't reach your audiobooks.</p>
      <p class="muted" style="font-size:15px">Zephyr needs an Audiobookshelf key (abs_token).</p>`;
    return;
  }
  const books = d.books || [];
  $("#aud-list").innerHTML = books.map((b, i) => `<button class="row" data-i="${i}">
      ${b.cover ? `<img src="${esc(b.cover)}" alt="">` : `<span class="thumb"></span>`}
      <span class="t"><b>${esc(b.title)}</b><span>${esc([b.author, b.left].filter(Boolean).join(" · "))}</span></span></button>`).join("")
    || `<p class="muted">No books in your library.</p>`;
  $("#aud-list").onclick = async e => {
    const b = e.target.closest("[data-i]"); if (!b) return;
    const book = books[+b.dataset.i];
    AUD.browse = false; AUD.starting = book.title; v.dataset.mode = "";
    RENDER.audible();
    try { await post("/api/audible/play", { asin: book.asin }); }
    catch (err) { toast("Books: " + err.message); }
    AUD.starting = null;
    await pollAudible(); S.view === "audible" && RENDER.audible();
  };
}
