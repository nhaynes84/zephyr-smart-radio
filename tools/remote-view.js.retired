// Remote view: a live picture of a BACKGROUND browser tab (Audible), driven over
// the kiosk's loopback DevTools port. Taps become clicks, drags scroll, and a
// round-screen keyboard types -- so sign-in and the web player never need the
// satellite UI to leave the front, or a USB keyboard.
"use strict";

const RV = { ws: null, id: 0, pending: new Map(), timer: null, kbd: false, layer: "abc", shift: false,
             scale: 1, offX: 0, offY: 0, onClose: null, busy: false };

function rvSend(method, params = {}) {
  return new Promise((resolve, reject) => {
    if (!RV.ws || RV.ws.readyState !== 1) return reject(new Error("not connected"));
    const id = ++RV.id;
    RV.pending.set(id, { resolve, reject });
    RV.ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { if (RV.pending.delete(id)) reject(new Error(method + " timed out")); }, 8000);
  });
}

async function rvOpen(onClose) {
  const tab = await api("/api/audible/tab", { timeout: 15000 });
  RV.onClose = onClose || null;
  await new Promise((resolve, reject) => {
    RV.ws = new WebSocket(tab.ws);
    RV.ws.onopen = resolve;
    RV.ws.onerror = () => reject(new Error("couldn't attach to the browser tab"));
    RV.ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      const p = m.id && RV.pending.get(m.id);
      if (p) { RV.pending.delete(m.id); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result); }
    };
    RV.ws.onclose = () => { RV.ws = null; };
  });
  await rvSend("Emulation.setFocusEmulationEnabled", { enabled: true }).catch(() => {});
  $("#remote").classList.add("shown");
  rvLayout();
  rvFrameLoop();
}

function rvClose() {
  clearTimeout(RV.timer); RV.timer = null;
  if (RV.ws) RV.ws.close();
  RV.ws = null; RV.kbd = false;
  $("#remote").classList.remove("shown");
  $("#rv-kbd").classList.remove("shown");
  if (RV.onClose) RV.onClose();
}

async function rvFrameLoop() {
  if (!RV.ws) return;
  if (!RV.busy) {
    RV.busy = true;
    try {
      const r = await rvSend("Page.captureScreenshot", { format: "jpeg", quality: 70 });
      $("#rv-img").src = "data:image/jpeg;base64," + r.data;
    } catch {}
    RV.busy = false;
  }
  RV.timer = setTimeout(rvFrameLoop, 300);
}

// The page renders at the window size (800x800). Full view: 1:1. With the
// keyboard up, it shrinks into the upper part of the circle.
function rvLayout() {
  if (RV.kbd) { RV.scale = 0.56; RV.offX = (800 - 800 * RV.scale) / 2; RV.offY = 70; }
  else { RV.scale = 1; RV.offX = 0; RV.offY = 0; }
  const img = $("#rv-img");
  img.style.transform = `translate(${RV.offX}px, ${RV.offY}px) scale(${RV.scale})`;
  $("#rv-kbd").classList.toggle("shown", RV.kbd);
}

const rvPage = (x, y) => [Math.round((x - RV.offX) / RV.scale), Math.round((y - RV.offY) / RV.scale)];

async function rvClick(x, y) {
  const [px, py] = rvPage(x, y);
  if (px < 0 || py < 0 || px > 800 || py > 800) return;
  await rvSend("Input.dispatchMouseEvent", { type: "mouseMoved", x: px, y: py });
  await rvSend("Input.dispatchMouseEvent", { type: "mousePressed", x: px, y: py, button: "left", clickCount: 1 });
  await rvSend("Input.dispatchMouseEvent", { type: "mouseReleased", x: px, y: py, button: "left", clickCount: 1 });
  setTimeout(rvFrameLoop, 120);
}

function rvWheel(x, y, dy) {
  const [px, py] = rvPage(x, y);
  rvSend("Input.dispatchMouseEvent", { type: "mouseWheel", x: px, y: py, deltaX: 0, deltaY: dy }).catch(() => {});
}

// --- touch on the picture: tap = click, drag = scroll
(function wirePicture() {
  let start = null, lastY = 0, scrolled = false;
  const surf = () => $("#rv-surface");
  window.addEventListener("load", () => {
    surf().addEventListener("pointerdown", e => { start = { x: e.clientX, y: e.clientY }; lastY = e.clientY; scrolled = false; });
    surf().addEventListener("pointermove", e => {
      if (!start) return;
      if (Math.abs(e.clientY - start.y) > 12) scrolled = true;
      if (scrolled) { rvWheel(start.x, start.y, (lastY - e.clientY) / RV.scale); lastY = e.clientY; }
    });
    surf().addEventListener("pointerup", e => {
      if (start && !scrolled) rvClick(e.clientX, e.clientY).catch(err => toast(err.message));
      start = null;
    });
  });
})();

// --- keyboard
const RV_KEYS = {
  abc: [["q","w","e","r","t","y","u","i","o","p"], ["a","s","d","f","g","h","j","k","l"],
        ["⇧","z","x","c","v","b","n","m","⌫"], ["123","@",".","space","⏎"]],
  sym: [["1","2","3","4","5","6","7","8","9","0"], ["@","#","$","%","&","*","-","_","+"],
        ["!","?","/",":",";","'","\"","(","⌫"], ["abc",",",".","space","⏎"]],
};

function rvBuildKbd() {
  const rows = RV_KEYS[RV.layer];
  $("#rv-kbd").innerHTML = rows.map(r => `<div class="kr">${r.map(k => {
    const label = k === "space" ? "space" : (RV.shift && k.length === 1 ? k.toUpperCase() : k);
    const cls = k === "space" ? "wide" : (["⇧", "⌫", "⏎", "123", "abc"].includes(k) ? "mod" : "");
    return `<button class="key ${cls}${k === "⇧" && RV.shift ? " on" : ""}" data-k="${esc(k)}">${esc(label)}</button>`;
  }).join("")}</div>`).join("");
}

async function rvKey(k) {
  if (k === "⇧") { RV.shift = !RV.shift; return rvBuildKbd(); }
  if (k === "123" || k === "abc") { RV.layer = k === "123" ? "sym" : "abc"; return rvBuildKbd(); }
  if (k === "⌫") {
    for (const type of ["rawKeyDown", "keyUp"])
      await rvSend("Input.dispatchKeyEvent", { type, key: "Backspace", code: "Backspace", windowsVirtualKeyCode: 8 });
  } else if (k === "⏎") {
    await rvSend("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
    await rvSend("Input.dispatchKeyEvent", { type: "char", key: "Enter", text: "\r" });
    await rvSend("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  } else {
    let t = k === "space" ? " " : k;
    if (RV.shift && t.length === 1) { t = t.toUpperCase(); RV.shift = false; rvBuildKbd(); }
    await rvSend("Input.insertText", { text: t });
  }
  setTimeout(rvFrameLoop, 80);
}

window.addEventListener("load", () => {
  rvBuildKbd();
  $("#rv-kbd").addEventListener("pointerdown", e => {
    const b = e.target.closest("[data-k]"); if (!b) return;
    e.preventDefault();
    b.classList.add("down"); setTimeout(() => b.classList.remove("down"), 120);
    rvKey(b.dataset.k).catch(err => toast(err.message));
  });
  $("#rv-close").onclick = rvClose;
  $("#rv-kb").onclick = () => { RV.kbd = !RV.kbd; rvLayout(); };
  $("#rv-home").onclick = () => rvSend("Page.navigate", { url: "https://www.audible.com/library/titles" }).catch(e => toast(e.message));
});

// ------------------------------------------------------------------ Audible app
// Native round-screen app over satd's Audible driver (the web player runs in a
// hidden tab). Now playing: cover, chapter ring, ±30, chapters, speed. Library:
// his books; tap to resume. The remote view stays for sign-in only.
const AUD = { st: { active: false }, lib: null, browse: false, starting: null };
const AUD_RATES = [1, 1.25, 1.5, 1.75, 2, 0.8];

async function pollAudible() {
  try { AUD.st = await api("/api/audible/status", { timeout: 6000 }); } catch { AUD.st = { active: false }; }
}
function audIsPlaying() { return !!(AUD.st && AUD.st.active && !AUD.st.paused); }
const audCmd = (action, value) => post("/api/audible/cmd", { action, value })
  .then(() => setTimeout(async () => { await pollAudible(); S.view === "audible" && RENDER.audible(); }, 300))
  .catch(e => toast("Audible: " + e.message));

function hms(sec) { sec = Math.max(0, Math.floor(sec)); const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60; return h ? `${h}h ${m}m` : `${m}m`; }

RENDER.audible = async (fresh) => {
  const v = $("#v-audible");
  if (fresh) { AUD.browse = false; await pollAudible(); }
  if (AUD.browse || (!AUD.st.active && !AUD.starting)) return audLibrary(v, fresh);
  if (AUD.starting && !AUD.st.active) {
    if (v.dataset.mode !== "starting") {
      v.dataset.mode = "starting";
      v.innerHTML = `<div class="label">Audible</div><p style="font-size:20px;margin-top:14px">Opening ${esc(AUD.starting)}…</p>
        <p class="muted" style="font-size:15px">Audible takes a few seconds to load.</p>`;
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
    $("#aud-title").textContent = s.title || "Audible";
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
  v.innerHTML = `${AUD.st.active ? backHead("aud-back", "Now playing", 40) : `<div class="label" style="margin-top:56px">Audible</div>`}
    <div class="list" id="aud-list" style="max-height:330px;margin-top:8px"><p class="muted">Loading your library…</p></div>`;
  if ($("#aud-back")) $("#aud-back").onclick = () => { AUD.browse = false; v.dataset.mode = ""; RENDER.audible(); };
  let d;
  try { d = AUD.lib && !fresh ? AUD.lib : (AUD.lib = await api("/api/audible/library", { timeout: 90000 })); }
  catch (e) { $("#aud-list").innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  if (v.dataset.mode !== "library") return;
  if (!d.signed_in) {
    $("#aud-list").innerHTML = `<p style="font-size:19px">Sign in to Audible once.</p>
      <p class="muted" style="font-size:15px">Use ⌨ for the on-screen keyboard.</p>
      <button class="pill on" id="aud-signin" style="margin-top:8px">Sign in</button>`;
    $("#aud-signin").onclick = () => rvOpen(() => { AUD.lib = null; S.view === "audible" && RENDER.audible(true); }).catch(e => toast(e.message));
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
    catch (err) { toast("Audible: " + err.message); }
    AUD.starting = null;
    await pollAudible(); S.view === "audible" && RENDER.audible();
  };
}
