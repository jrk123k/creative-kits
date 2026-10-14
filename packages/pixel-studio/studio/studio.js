/* Pixel Studio. No build step. OKLab snap matches palette_snap/snap.py. */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var UNDO_CAP = 40;
  var LEVELS = [0, 36, 72, 109, 145, 182, 218, 255];
  var BAYER_8 = [
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21]
  ];

  var state = {
    w: 256,
    h: 224,
    frames: [],
    frameIndex: 0,
    tool: "pencil",
    brush: 1,
    zoom: 2,
    grid: true,
    editorOnion: false,
    palette: [],
    paletteLabel: "TG16",
    colorIndex: 0,
    previewScale: 1,
    fps: 12,
    playing: false,
    playOrigin: 0,
    lastTick: -1,
    raf: 0,
    onion: true,
    onionOpacity: 0.4,
    mouth: false,
    mouthClosed: 0,
    mouthOpen: 1,
    mouthHold: 4,
    background: null,
    offsetX: 0,
    offsetY: 0,
    hover: null,
    drawing: false,
    lastPixel: null
  };

  var scratch = {
    frame: document.createElement("canvas"),
    ghost: document.createElement("canvas"),
    comp: document.createElement("canvas")
  };

  function current() {
    return state.frames[state.frameIndex] || null;
  }

  function setStatus(msg, kind) {
    var el = $("#status");
    el.textContent = msg;
    if (kind) el.dataset.kind = kind;
    else delete el.dataset.kind;
  }

  function shotName() {
    var raw = ($("#shot").value || "frame").trim();
    var clean = raw.replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
    return clean || "frame";
  }

  function sanitize(name) {
    var clean = String(name || "frame").replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
    return clean || "frame";
  }

  function downloadBlob(blob, name) {
    var a = document.createElement("a");
    var url = URL.createObjectURL(blob);
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2500);
  }

  function putData(canvas, data, w, h) {
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    var ctx = canvas.getContext("2d");
    var img = ctx.createImageData(w, h);
    img.data.set(data);
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function srgbToOklab(r, g, b) {
    function lin(u) {
      var c = u / 255;
      return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }
    var R = lin(r), G = lin(g), B = lin(b);
    var l = 0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B;
    var m = 0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B;
    var s = 0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B;
    var l_ = Math.cbrt(Math.max(l, 0));
    var m_ = Math.cbrt(Math.max(m, 0));
    var s_ = Math.cbrt(Math.max(s, 0));
    return [
      0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
      1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
      0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    ];
  }

  function clampTg16(r, g, b) {
    function q(v) {
      var i = Math.round(v * 7 / 255);
      if (i < 0) i = 0;
      if (i > 7) i = 7;
      return LEVELS[i];
    }
    return [q(r), q(g), q(b)];
  }

  function median(values) {
    if (!values.length) return 0;
    var s = values.slice().sort(function (a, b) { return a - b; });
    var mid = Math.floor(s.length / 2);
    if (s.length % 2) return s[mid];
    return (s[mid - 1] + s[mid]) / 2;
  }

  function snapData(src, dither, tg16) {
    var cols = state.palette.map(function (c) { return { r: c.r, g: c.g, b: c.b }; });
    if (tg16) {
      var seen = new Set();
      var next = [];
      cols.forEach(function (c) {
        var rgb = clampTg16(c.r, c.g, c.b);
        var key = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2];
        if (seen.has(key)) return;
        seen.add(key);
        next.push({ r: rgb[0], g: rgb[1], b: rgb[2] });
      });
      cols = next;
    }
    if (!cols.length) return new Uint8ClampedArray(src);
    var labs = cols.map(function (c) { return srgbToOklab(c.r, c.g, c.b); });
    var step = 0;
    if (dither && labs.length > 1) {
      var nn = labs.map(function (lab, i) {
        var best = Infinity;
        for (var j = 0; j < labs.length; j++) {
          if (i === j) continue;
          var dL = lab[0] - labs[j][0];
          var dA = lab[1] - labs[j][1];
          var dB = lab[2] - labs[j][2];
          var d = Math.sqrt(dL * dL + dA * dA + dB * dB);
          if (d < best) best = d;
        }
        return best;
      });
      step = median(nn);
    }
    var out = new Uint8ClampedArray(src);
    var w = state.w;
    var h = state.h;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        var i = (y * w + x) * 4;
        if (src[i + 3] === 0) continue;
        var lab = srgbToOklab(src[i], src[i + 1], src[i + 2]);
        if (dither && step > 0) {
          var thresh = (BAYER_8[y & 7][x & 7] + 0.5) / 64 - 0.5;
          lab[0] += thresh * step * 0.5;
        }
        var best = 0;
        var bestD = Infinity;
        for (var p = 0; p < labs.length; p++) {
          var dl = lab[0] - labs[p][0];
          var da = lab[1] - labs[p][1];
          var db = lab[2] - labs[p][2];
          var dist = dl * dl + da * da + db * db;
          if (dist < bestD) { bestD = dist; best = p; }
        }
        var chosen = cols[best];
        var rr = chosen.r, gg = chosen.g, bb = chosen.b;
        if (tg16) {
          var clamped = clampTg16(rr, gg, bb);
          rr = clamped[0]; gg = clamped[1]; bb = clamped[2];
        }
        out[i] = rr;
        out[i + 1] = gg;
        out[i + 2] = bb;
        out[i + 3] = src[i + 3];
      }
    }
    return out;
  }

  function nearestPaletteIndex(r, g, b) {
    var lab = srgbToOklab(r, g, b);
    var best = 0;
    var bestD = Infinity;
    for (var i = 0; i < state.palette.length; i++) {
      var c = state.palette[i];
      var p = srgbToOklab(c.r, c.g, c.b);
      var d = (lab[0] - p[0]) * (lab[0] - p[0]) + (lab[1] - p[1]) * (lab[1] - p[1]) + (lab[2] - p[2]) * (lab[2] - p[2]);
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  function offPaletteCount(frame) {
    var keys = new Set();
    state.palette.forEach(function (c) {
      keys.add((c.r << 16) | (c.g << 8) | c.b);
    });
    var n = 0;
    var d = frame.data;
    for (var i = 0; i < d.length; i += 4) {
      if (d[i + 3] === 0) continue;
      var key = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2];
      if (!keys.has(key)) n++;
    }
    return n;
  }

  function renderPalette() {
    var box = $("#swatches");
    box.innerHTML = "";
    $("#palette-empty").hidden = state.palette.length > 0;
    $("#palette-count").textContent = state.palette.length + " color" + (state.palette.length === 1 ? "" : "s");
    $("#palette-label").textContent = "Locked · " + (state.paletteLabel || "palette");
    state.palette.forEach(function (c, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "swatch";
      btn.style.background = "rgb(" + c.r + "," + c.g + "," + c.b + ")";
      btn.title = c.name + "  " + c.r + "," + c.g + "," + c.b;
      btn.setAttribute("aria-pressed", i === state.colorIndex ? "true" : "false");
      btn.addEventListener("click", function () { selectColor(i); });
      box.appendChild(btn);
    });
    if (state.palette.length) selectColor(Math.min(state.colorIndex, state.palette.length - 1));
  }

  function selectColor(i) {
    if (!state.palette.length) return;
    state.colorIndex = i;
    var nodes = document.querySelectorAll(".swatch");
    for (var n = 0; n < nodes.length; n++) nodes[n].setAttribute("aria-pressed", n === i ? "true" : "false");
    var c = state.palette[i];
    $("#swatch-current").style.background = "rgb(" + c.r + "," + c.g + "," + c.b + ")";
    $("#swatch-name").textContent = c.name;
    $("#swatch-rgb").textContent = c.r + " " + c.g + " " + c.b;
  }

  function preferColor() {
    var names = ["cyan", "amber", "lip"];
    for (var n = 0; n < names.length; n++) {
      for (var i = 0; i < state.palette.length; i++) {
        if (state.palette[i].name === names[n]) return i;
      }
    }
    return 0;
  }

  function setPalette(colors, label) {
    state.palette = colors.slice(0, 256);
    state.paletteLabel = label;
    state.colorIndex = preferColor();
    renderPalette();
    updateMeta();
  }

  function parsePaletteJSON(text, label) {
    var data = JSON.parse(text);
    var list = Array.isArray(data) ? data : data.colors;
    if (!list || !list.length) throw new Error("palette JSON needs a colors array");
    var colors = [];
    list.forEach(function (entry, i) {
      var rgb;
      var name;
      if (typeof entry === "string") {
        rgb = hexToRgb(entry);
        name = entry;
      } else if (Array.isArray(entry)) {
        rgb = entry;
        name = "c" + i;
      } else {
        rgb = entry.rgb || [entry.r, entry.g, entry.b];
        name = entry.name || ("c" + i);
      }
      var r = rgb[0] | 0, g = rgb[1] | 0, b = rgb[2] | 0;
      if (r < 0 || g < 0 || b < 0 || r > 255 || g > 255 || b > 255) return;
      colors.push({ r: r, g: g, b: b, name: name });
    });
    if (!colors.length) throw new Error("no colors in palette");
    var extra = "";
    if (colors.length > 256) {
      extra = " Showing 256 of " + colors.length + ".";
      colors = colors.slice(0, 256);
    }
    setPalette(colors, (data && data.name) || label || "palette");
    return extra;
  }

  function hexToRgb(hex) {
    var h = hex.replace("#", "").trim();
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }

  async function loadPaletteFile(file) {
    var bmp = await createImageBitmap(file);
    var canvas = document.createElement("canvas");
    canvas.width = bmp.width;
    canvas.height = bmp.height;
    var ctx = canvas.getContext("2d");
    ctx.drawImage(bmp, 0, 0);
    var data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    bmp.close();
    var map = new Map();
    for (var i = 0, p = 0; i < data.length; i += 4, p++) {
      if (data[i + 3] === 0) continue;
      var key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
      var prev = map.get(key);
      if (prev) prev.count += 1;
      else map.set(key, { count: 1, first: p, r: data[i], g: data[i + 1], b: data[i + 2] });
    }
    var entries = Array.from(map.values()).sort(function (a, b) {
      return b.count - a.count || a.first - b.first;
    });
    var total = entries.length;
    if (!total) throw new Error(file.name + " has no opaque pixels");
    if (total > 256) entries = entries.slice(0, 256);
    setPalette(entries.map(function (e, i) {
      return { r: e.r, g: e.g, b: e.b, name: "c" + i };
    }), file.name);
    setStatus(
      total > 256
        ? "Locked 256 of " + total + " colors from " + file.name + ". palette_snap can pick a smaller set."
        : "Locked " + total + " colors from " + file.name + ".",
      "ok"
    );
  }

  function paintThumb(canvas, frame) {
    canvas.width = state.w;
    canvas.height = state.h;
    var ctx = canvas.getContext("2d");
    var img = ctx.createImageData(state.w, state.h);
    img.data.set(frame.data);
    ctx.putImageData(img, 0, 0);
  }

  function renderStrip() {
    var strip = $("#strip");
    strip.innerHTML = "";
    state.frames.forEach(function (frame, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "thumb";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", i === state.frameIndex ? "true" : "false");
      var canvas = document.createElement("canvas");
      paintThumb(canvas, frame);
      var cap = document.createElement("span");
      cap.textContent = frame.name;
      btn.appendChild(canvas);
      btn.appendChild(cap);
      btn.addEventListener("click", function () { selectFrame(i); });
      strip.appendChild(btn);
    });
    fillMouthSelects();
    var frame = current();
    if (frame) $("#frame-name").value = frame.name;
  }

  function refreshThumb(i) {
    var btn = $("#strip").children[i];
    if (!btn) return;
    paintThumb(btn.querySelector("canvas"), state.frames[i]);
    btn.querySelector("span").textContent = state.frames[i].name;
  }

  function selectFrame(i) {
    if (!state.frames.length) return;
    state.frameIndex = Math.max(0, Math.min(state.frames.length - 1, i));
    var tabs = document.querySelectorAll(".thumb");
    for (var n = 0; n < tabs.length; n++) tabs[n].setAttribute("aria-selected", n === state.frameIndex ? "true" : "false");
    $("#frame-name").value = current().name;
    updateUndoButtons();
    updateMeta();
    presentEditor();
    if (!state.playing) presentPreview();
  }

  function fillMouthSelects() {
    ["mouth-closed", "mouth-open"].forEach(function (id) {
      var sel = $("#" + id);
      var keep = id === "mouth-closed" ? state.mouthClosed : state.mouthOpen;
      sel.innerHTML = "";
      state.frames.forEach(function (frame, i) {
        var opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = frame.name;
        sel.appendChild(opt);
      });
      if (state.frames.length) sel.value = String(Math.max(0, Math.min(keep, state.frames.length - 1)));
    });
  }

  function newDocument(w, h, name) {
    state.w = w;
    state.h = h;
    state.frames = [{
      name: name || (w === 256 && h === 224 ? "plate_256" : "sprite"),
      data: new Uint8ClampedArray(w * h * 4),
      undo: [],
      redo: []
    }];
    state.frameIndex = 0;
    state.mouthClosed = 0;
    state.mouthOpen = 0;
    state.background = null;
    $("#bg-name").textContent = "None";
    renderStrip();
    updateMeta();
    updatePatchReadout();
    presentEditor();
    presentPreview();
    setStatus(w + "×" + h + " transparent canvas.", "ok");
  }

  function rasterize(bitmap, w, h) {
    var canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    var ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(bitmap, 0, 0, w, h);
    return new Uint8ClampedArray(ctx.getImageData(0, 0, w, h).data);
  }

  async function loadFrameFiles(fileList) {
    var files = Array.from(fileList).filter(function (f) {
      return /^image\//.test(f.type) || /\.(png|gif|webp|bmp)$/i.test(f.name);
    });
    if (!files.length) {
      setStatus("No images in that selection.", "error");
      return;
    }
    files.sort(function (a, b) {
      return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
    });
    setStatus("Reading " + files.length + " frame" + (files.length === 1 ? "" : "s") + "…");
    var bitmaps = [];
    for (var i = 0; i < files.length; i++) {
      var bmp = await createImageBitmap(files[i]);
      bitmaps.push({ name: files[i].name.replace(/\.[^.]+$/, ""), bmp: bmp });
    }
    var w = bitmaps[0].bmp.width;
    var h = bitmaps[0].bmp.height;
    if (w < 1 || h < 1 || w > 2048 || h > 2048) {
      bitmaps.forEach(function (b) { b.bmp.close(); });
      setStatus("Frames must be between 1 and 2048 pixels.", "error");
      return;
    }
    var resized = 0;
    var frames = bitmaps.map(function (item) {
      if (item.bmp.width !== w || item.bmp.height !== h) resized += 1;
      var data = rasterize(item.bmp, w, h);
      item.bmp.close();
      return { name: sanitize(item.name), data: data, undo: [], redo: [] };
    });
    state.w = w;
    state.h = h;
    state.frames = frames;
    state.frameIndex = 0;
    state.mouthClosed = 0;
    state.mouthOpen = frames.length > 1 ? 1 : 0;
    renderStrip();
    updateMeta();
    updatePatchReadout();
    presentEditor();
    presentPreview();
    var note = resized ? " " + resized + " resampled to " + w + "×" + h + " (nearest)." : "";
    setStatus("Loaded " + frames.length + " frame" + (frames.length === 1 ? "" : "s") + " at " + w + "×" + h + "." + note, "ok");
  }

  async function loadBackground(file) {
    var bmp = await createImageBitmap(file);
    if (bmp.width > 2048 || bmp.height > 2048) {
      bmp.close();
      setStatus("Background is larger than 2048.", "error");
      return;
    }
    var canvas = document.createElement("canvas");
    canvas.width = bmp.width;
    canvas.height = bmp.height;
    canvas.getContext("2d").drawImage(bmp, 0, 0);
    bmp.close();
    state.background = { canvas: canvas, w: canvas.width, h: canvas.height, name: file.name };
    $("#bg-name").textContent = file.name;
    presentPreview();
    setStatus("Background " + file.name + " (" + canvas.width + "×" + canvas.height + ").", "ok");
  }

  function clearBackground() {
    state.background = null;
    $("#bg-name").textContent = "None";
    presentPreview();
  }

  function pushUndo() {
    var frame = current();
    if (!frame) return;
    frame.undo.push(new Uint8ClampedArray(frame.data));
    if (frame.undo.length > UNDO_CAP) frame.undo.shift();
    frame.redo.length = 0;
    updateUndoButtons();
  }

  function undo() {
    var frame = current();
    if (!frame || !frame.undo.length) return;
    frame.redo.push(new Uint8ClampedArray(frame.data));
    frame.data = frame.undo.pop();
    afterPixels();
  }

  function redo() {
    var frame = current();
    if (!frame || !frame.redo.length) return;
    frame.undo.push(new Uint8ClampedArray(frame.data));
    frame.data = frame.redo.pop();
    afterPixels();
  }

  function updateUndoButtons() {
    var frame = current();
    $("#btn-undo").disabled = !frame || !frame.undo.length;
    $("#btn-redo").disabled = !frame || !frame.redo.length;
  }

  function updateMeta() {
    $("#size-badge").textContent = state.w + "×" + state.h;
    var frame = current();
    var off = frame ? offPaletteCount(frame) : 0;
    var badge = $("#off-badge");
    badge.textContent = off ? off + " off palette" : "On palette";
    badge.dataset.kind = off ? "warn" : "ok";
    updateUndoButtons();
    updateNames();
  }

  function frameFilenames() {
    var shot = shotName();
    var mode = $("#naming").value;
    var names = state.frames.map(function (frame, i) {
      if (mode === "plate") {
        if (i === state.mouthClosed && state.mouthClosed !== state.mouthOpen) return shot + "_256.png";
        if (i === state.mouthOpen && state.mouthClosed !== state.mouthOpen) return shot + "_open_256.png";
        if (i === state.mouthClosed) return shot + "_256.png";
        return shot + "_" + sanitize(frame.name) + ".png";
      }
      if (mode === "sprite") {
        if (state.frames.length === 1) return shot + "_sprite.png";
        return shot + "_sprite_" + i + ".png";
      }
      return shot + "_" + String(i).padStart(2, "0") + ".png";
    });
    var seen = new Map();
    return names.map(function (name) {
      if (!seen.has(name)) {
        seen.set(name, 1);
        return name;
      }
      var n = seen.get(name);
      seen.set(name, n + 1);
      return name.replace(/\.png$/, "_" + n + ".png");
    });
  }

  function updateNames() {
    $("#file-names").textContent = frameFilenames().join("   ");
  }

  function mouthDiff() {
    var a = state.frames[state.mouthClosed];
    var b = state.frames[state.mouthOpen];
    if (!a || !b) return null;
    var w = state.w;
    var h = state.h;
    var minx = w, miny = h, maxx = -1, maxy = -1, n = 0;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        var i = (y * w + x) * 4;
        if (a.data[i] !== b.data[i] || a.data[i + 1] !== b.data[i + 1] || a.data[i + 2] !== b.data[i + 2] || a.data[i + 3] !== b.data[i + 3]) {
          n++;
          if (x < minx) minx = x;
          if (y < miny) miny = y;
          if (x > maxx) maxx = x;
          if (y > maxy) maxy = y;
        }
      }
    }
    if (!n) return { n: 0 };
    return { n: n, x: minx, y: miny, w: maxx - minx + 1, h: maxy - miny + 1 };
  }

  function updatePatchReadout() {
    var diff = mouthDiff();
    var shot = shotName();
    var pre = $("#yaml");
    if (!diff) {
      pre.textContent = "Load a closed plate and an open plate.";
      return;
    }
    if (!diff.n) {
      pre.textContent = "Closed and open are the same picture.\nPaint the open mouth, then export the patch.";
      return;
    }
    pre.textContent = [
      "mouths:",
      "  " + shot + ":",
      "    closed: art/" + shot + "_256.png",
      "    open: art/" + shot + "_open_256.png",
      "    patch:",
      "      image: art/" + shot + "_open_patch.png",
      "      x: " + diff.x,
      "      y: " + diff.y,
      "# " + diff.n + " pixels, " + diff.w + "×" + diff.h + ". Pasting this rectangle on the closed plate reproduces the open still."
    ].join("\n");
  }

  function previewFrameIndex() {
    if (!state.playing || !state.frames.length) return state.frameIndex;
    var t = Math.max(0, state.lastTick);
    if (state.mouth) {
      var phase = Math.floor(t / state.mouthHold) % 2;
      return phase ? state.mouthOpen : state.mouthClosed;
    }
    return t % state.frames.length;
  }

  function onionFrameIndex() {
    var cur = previewFrameIndex();
    if (state.mouth) {
      if (cur === state.mouthClosed) return state.mouthOpen;
      if (cur === state.mouthOpen) return state.mouthClosed;
    }
    return (cur - 1 + state.frames.length) % state.frames.length;
  }

  function editorGhostIndex() {
    if (state.mouth) {
      if (state.frameIndex === state.mouthClosed) return state.mouthOpen;
      if (state.frameIndex === state.mouthOpen) return state.mouthClosed;
    }
    return (state.frameIndex - 1 + state.frames.length) % state.frames.length;
  }

  function updatePreviewLabel() {
    var el = $("#preview-label");
    if (!state.frames.length) {
      el.textContent = "No frames";
      return;
    }
    if (!state.playing) {
      el.textContent = "Paused · " + current().name;
      return;
    }
    var t = Math.max(0, state.lastTick);
    if (state.mouth) {
      var within = (t % state.mouthHold) + 1;
      var phase = Math.floor(t / state.mouthHold) % 2;
      el.textContent = (phase ? "OPEN" : "CLOSED") + " · " + within + "/" + state.mouthHold;
      return;
    }
    var i = t % state.frames.length;
    el.textContent = state.frames[i].name + " · " + (i + 1) + "/" + state.frames.length;
  }

  function presentEditor() {
    var frame = current();
    var view = $("#view");
    if (!frame) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cssW = state.w * state.zoom;
    var cssH = state.h * state.zoom;
    var bw = Math.max(1, Math.round(cssW * dpr));
    var bh = Math.max(1, Math.round(cssH * dpr));
    if (view.width !== bw || view.height !== bh) {
      view.width = bw;
      view.height = bh;
    }
    view.style.width = cssW + "px";
    view.style.height = cssH + "px";
    var ctx = view.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, bw, bh);
    putData(scratch.frame, frame.data, state.w, state.h);
    ctx.drawImage(scratch.frame, 0, 0, bw, bh);
    if (state.editorOnion && state.frames.length > 1) {
      var ghost = state.frames[editorGhostIndex()];
      if (ghost && ghost !== frame) {
        putData(scratch.ghost, ghost.data, state.w, state.h);
        ctx.save();
        ctx.globalAlpha = state.onionOpacity;
        ctx.drawImage(scratch.ghost, 0, 0, bw, bh);
        ctx.restore();
      }
    }
    if (state.grid && state.zoom >= 4) {
      ctx.save();
      ctx.strokeStyle = "rgba(243, 236, 223, 0.16)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      var z = bw / state.w;
      for (var x = 1; x < state.w; x++) {
        var px = Math.round(x * z) + 0.5;
        ctx.moveTo(px, 0);
        ctx.lineTo(px, bh);
      }
      for (var y = 1; y < state.h; y++) {
        var py = Math.round(y * z) + 0.5;
        ctx.moveTo(0, py);
        ctx.lineTo(bw, py);
      }
      ctx.stroke();
      ctx.restore();
    }
    if (state.hover) {
      var hz = bw / state.w;
      ctx.save();
      ctx.strokeStyle = state.tool === "eraser" ? "#e23b3b" : "#3dffd6";
      ctx.lineWidth = Math.max(1, dpr);
      ctx.strokeRect(
        Math.round(state.hover[0] * hz) + 0.5,
        Math.round(state.hover[1] * hz) + 0.5,
        Math.max(1, Math.round(state.brush * hz) - 1),
        Math.max(1, Math.round(state.brush * hz) - 1)
      );
      ctx.restore();
    }
  }

  function presentPreview() {
    if (!state.frames.length) return;
    var frame = state.frames[previewFrameIndex()];
    if (!frame) return;
    var bg = state.background;
    var cw = bg ? bg.w : state.w;
    var ch = bg ? bg.h : state.h;
    var c = scratch.comp.getContext("2d");
    if (scratch.comp.width !== cw || scratch.comp.height !== ch) {
      scratch.comp.width = cw;
      scratch.comp.height = ch;
    }
    c.imageSmoothingEnabled = false;
    c.clearRect(0, 0, cw, ch);
    if (bg) c.drawImage(bg.canvas, 0, 0);
    putData(scratch.frame, frame.data, state.w, state.h);
    c.drawImage(scratch.frame, state.offsetX | 0, state.offsetY | 0);
    if (state.onion && state.frames.length > 1) {
      var prev = state.frames[onionFrameIndex()];
      if (prev) {
        putData(scratch.ghost, prev.data, state.w, state.h);
        c.save();
        c.globalAlpha = state.onionOpacity;
        c.drawImage(scratch.ghost, state.offsetX | 0, state.offsetY | 0);
        c.restore();
      }
    }
    var scale = state.previewScale;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cssW = cw * scale;
    var cssH = ch * scale;
    var view = $("#preview");
    var bw = Math.max(1, Math.round(cssW * dpr));
    var bh = Math.max(1, Math.round(cssH * dpr));
    if (view.width !== bw || view.height !== bh) {
      view.width = bw;
      view.height = bh;
    }
    view.style.width = cssW + "px";
    view.style.height = cssH + "px";
    var pctx = view.getContext("2d");
    pctx.imageSmoothingEnabled = false;
    pctx.clearRect(0, 0, bw, bh);
    pctx.drawImage(scratch.comp, 0, 0, bw, bh);
    updatePreviewLabel();
  }

  function setPlaying(on) {
    state.playing = on;
    $("#btn-play").setAttribute("aria-pressed", on ? "true" : "false");
    $("#btn-play").textContent = on ? "Pause" : "Play";
    if (state.raf) cancelAnimationFrame(state.raf);
    if (!on) {
      presentPreview();
      return;
    }
    state.playOrigin = performance.now();
    state.lastTick = -1;
    var step = function (now) {
      if (!state.playing) return;
      var t = Math.floor((now - state.playOrigin) / 1000 * state.fps);
      if (t !== state.lastTick) {
        state.lastTick = t;
        presentPreview();
      }
      state.raf = requestAnimationFrame(step);
    };
    state.raf = requestAnimationFrame(step);
  }

  function setTool(name) {
    state.tool = name;
    document.querySelectorAll("[data-tool]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.tool === name ? "true" : "false");
    });
    var labels = { pencil: "Pencil", eraser: "Eraser", fill: "Fill", eyedropper: "Eyedropper" };
    $("#tool-name").textContent = labels[name] || name;
  }

  function setBrush(size) {
    state.brush = size;
    document.querySelectorAll("[data-brush]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", Number(btn.dataset.brush) === size ? "true" : "false");
    });
    presentEditor();
  }

  function setZoom(zoom) {
    state.zoom = zoom;
    document.querySelectorAll("[data-zoom]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", Number(btn.dataset.zoom) === zoom ? "true" : "false");
    });
    presentEditor();
  }

  function setScale(scale) {
    state.previewScale = scale;
    document.querySelectorAll("[data-scale]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", Number(btn.dataset.scale) === scale ? "true" : "false");
    });
    presentPreview();
  }

  function eventToPixel(e) {
    var rect = $("#view").getBoundingClientRect();
    if (!rect.width || !rect.height) return [-1, -1];
    return [
      Math.floor((e.clientX - rect.left) / rect.width * state.w),
      Math.floor((e.clientY - rect.top) / rect.height * state.h)
    ];
  }

  function bresenham(x0, y0, x1, y1, plot) {
    var dx = Math.abs(x1 - x0);
    var sx = x0 < x1 ? 1 : -1;
    var dy = -Math.abs(y1 - y0);
    var sy = y0 < y1 ? 1 : -1;
    var err = dx + dy;
    for (;;) {
      plot(x0, y0);
      if (x0 === x1 && y0 === y1) break;
      var e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  function plot(x, y) {
    var frame = current();
    if (!frame) return;
    var erase = state.tool === "eraser";
    var color = erase ? null : state.palette[state.colorIndex];
    if (!erase && !color) return;
    for (var yy = y; yy < y + state.brush; yy++) {
      if (yy < 0 || yy >= state.h) continue;
      for (var xx = x; xx < x + state.brush; xx++) {
        if (xx < 0 || xx >= state.w) continue;
        var i = (yy * state.w + xx) * 4;
        if (erase) frame.data[i + 3] = 0;
        else {
          frame.data[i] = color.r;
          frame.data[i + 1] = color.g;
          frame.data[i + 2] = color.b;
          frame.data[i + 3] = 255;
        }
      }
    }
  }

  function floodFill(x, y) {
    var frame = current();
    var color = state.palette[state.colorIndex];
    if (!frame || !color) return;
    var w = state.w;
    var h = state.h;
    var data = frame.data;
    var start = (y * w + x) * 4;
    var tr = data[start], tg = data[start + 1], tb = data[start + 2], ta = data[start + 3];
    if (tr === color.r && tg === color.g && tb === color.b && ta === 255) return;
    var seen = new Uint8Array(w * h);
    var stack = [x, y];
    while (stack.length) {
      var cy = stack.pop();
      var cx = stack.pop();
      if (cx < 0 || cy < 0 || cx >= w || cy >= h) continue;
      var pi = cy * w + cx;
      if (seen[pi]) continue;
      seen[pi] = 1;
      var di = pi * 4;
      if (data[di] !== tr || data[di + 1] !== tg || data[di + 2] !== tb || data[di + 3] !== ta) continue;
      data[di] = color.r;
      data[di + 1] = color.g;
      data[di + 2] = color.b;
      data[di + 3] = 255;
      stack.push(cx + 1, cy, cx - 1, cy, cx, cy + 1, cx, cy - 1);
    }
  }

  function pick(x, y) {
    var frame = current();
    if (!frame) return;
    var i = (y * state.w + x) * 4;
    if (frame.data[i + 3] === 0) {
      setStatus("Transparent pixel.", "warn");
      $("#coord").textContent = x + ", " + y + "  alpha 0";
      return;
    }
    var r = frame.data[i], g = frame.data[i + 1], b = frame.data[i + 2];
    var exact = -1;
    for (var n = 0; n < state.palette.length; n++) {
      var c = state.palette[n];
      if (c.r === r && c.g === g && c.b === b) { exact = n; break; }
    }
    if (exact >= 0) {
      selectColor(exact);
      setTool("pencil");
      setStatus("Picked " + state.palette[exact].name + ".", "ok");
    } else if (state.palette.length) {
      var near = nearestPaletteIndex(r, g, b);
      selectColor(near);
      setTool("pencil");
      setStatus("Off-palette pixel. Nearest swatch is " + state.palette[near].name + ".", "warn");
    }
  }

  function afterPixels() {
    refreshThumb(state.frameIndex);
    updateMeta();
    updatePatchReadout();
    presentEditor();
    if (!state.playing) presentPreview();
  }

  function onPointerDown(e) {
    if (!current()) return;
    var pix = eventToPixel(e);
    var x = pix[0], y = pix[1];
    if (x < 0 || y < 0 || x >= state.w || y >= state.h) return;
    if (e.button === 2 || state.tool === "eyedropper") {
      pick(x, y);
      return;
    }
    if (e.button !== 0) return;
    if (state.tool !== "eraser" && !state.palette.length) {
      setStatus("Load a palette before painting.", "error");
      return;
    }
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    pushUndo();
    if (state.tool === "fill") {
      floodFill(x, y);
      afterPixels();
      return;
    }
    state.drawing = true;
    state.lastPixel = [x, y];
    plot(x, y);
    presentEditor();
  }

  function onPointerMove(e) {
    var pix = eventToPixel(e);
    var x = pix[0], y = pix[1];
    var inside = x >= 0 && y >= 0 && x < state.w && y < state.h;
    state.hover = inside ? [x, y] : null;
    if (inside) {
      var frame = current();
      var a = 0;
      if (frame) a = frame.data[(y * state.w + x) * 4 + 3];
      $("#coord").textContent = x + ", " + y + (a === 0 ? "  ·" : "");
    } else $("#coord").textContent = "—";
    if (state.drawing && state.lastPixel) {
      var pts = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
      for (var i = 0; i < pts.length; i++) {
        var p = eventToPixel(pts[i]);
        bresenham(state.lastPixel[0], state.lastPixel[1], p[0], p[1], plot);
        state.lastPixel = p;
      }
    }
    presentEditor();
  }

  function onPointerUp() {
    if (!state.drawing) return;
    state.drawing = false;
    state.lastPixel = null;
    afterPixels();
  }

  function addFrame(copy) {
    var frame = current();
    var data = new Uint8ClampedArray(state.w * state.h * 4);
    var name = "frame_" + state.frames.length;
    if (copy && frame) {
      data.set(frame.data);
      name = frame.name + "_copy";
    }
    state.frames.splice(state.frameIndex + 1, 0, { name: name, data: data, undo: [], redo: [] });
    state.frameIndex += 1;
    renderStrip();
    updateMeta();
    presentEditor();
    if (!state.playing) presentPreview();
  }

  function deleteFrame() {
    if (state.frames.length <= 1) {
      setStatus("Keep at least one frame.", "warn");
      return;
    }
    state.frames.splice(state.frameIndex, 1);
    state.frameIndex = Math.min(state.frameIndex, state.frames.length - 1);
    state.mouthClosed = Math.min(state.mouthClosed, state.frames.length - 1);
    state.mouthOpen = Math.min(state.mouthOpen, state.frames.length - 1);
    renderStrip();
    updateMeta();
    updatePatchReadout();
    presentEditor();
    presentPreview();
  }

  function moveFrame(dir) {
    var i = state.frameIndex;
    var j = i + dir;
    if (j < 0 || j >= state.frames.length) return;
    var frame = state.frames.splice(i, 1)[0];
    state.frames.splice(j, 0, frame);
    function swap(idx) {
      if (idx === i) return j;
      if (idx === j) return i;
      return idx;
    }
    state.mouthClosed = swap(state.mouthClosed);
    state.mouthOpen = swap(state.mouthOpen);
    state.frameIndex = j;
    renderStrip();
    updateNames();
    updatePatchReadout();
  }

  function frameToBlob(frame) {
    var canvas = document.createElement("canvas");
    canvas.width = state.w;
    canvas.height = state.h;
    var ctx = canvas.getContext("2d");
    var img = ctx.createImageData(state.w, state.h);
    img.data.set(frame.data);
    ctx.putImageData(img, 0, 0);
    return new Promise(function (resolve) { canvas.toBlob(function (blob) { resolve(blob); }, "image/png"); });
  }

  async function downloadCurrent() {
    var frame = current();
    if (!frame) return;
    var blob = await frameToBlob(frame);
    downloadBlob(blob, frameFilenames()[state.frameIndex]);
    setStatus("Saved " + frameFilenames()[state.frameIndex] + ".", "ok");
  }

  async function downloadAll() {
    var names = frameFilenames();
    var files = [];
    setStatus("Packing " + names.length + " PNGs…");
    for (var i = 0; i < state.frames.length; i++) {
      var blob = await frameToBlob(state.frames[i]);
      files.push({ name: names[i], data: new Uint8Array(await blob.arrayBuffer()) });
    }
    var zip = window.pixelZip.makeZip(files);
    downloadBlob(new Blob([zip], { type: "application/zip" }), shotName() + "_frames.zip");
    setStatus("Saved " + shotName() + "_frames.zip.", "ok");
  }

  async function downloadSheet() {
    var w = state.w, h = state.h, n = state.frames.length;
    var cols = Math.max(1, Math.min(n, Math.floor(4096 / w)));
    var rows = Math.ceil(n / cols);
    var canvas = document.createElement("canvas");
    canvas.width = cols * w;
    canvas.height = rows * h;
    var ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    for (var i = 0; i < n; i++) {
      var src = document.createElement("canvas");
      src.width = w;
      src.height = h;
      var sctx = src.getContext("2d");
      var img = sctx.createImageData(w, h);
      img.data.set(state.frames[i].data);
      sctx.putImageData(img, 0, 0);
      ctx.drawImage(src, (i % cols) * w, Math.floor(i / cols) * h);
    }
    var blob = await new Promise(function (resolve) { canvas.toBlob(function (b) { resolve(b); }, "image/png"); });
    downloadBlob(blob, shotName() + "_sheet.png");
    setStatus("Saved " + shotName() + "_sheet.png (" + canvas.width + "×" + canvas.height + ").", "ok");
  }

  async function downloadPatch() {
    var diff = mouthDiff();
    if (!diff || !diff.n) {
      setStatus("Closed and open match. Nothing to export.", "warn");
      return;
    }
    var openFrame = state.frames[state.mouthOpen];
    var src = document.createElement("canvas");
    src.width = state.w;
    src.height = state.h;
    var sctx = src.getContext("2d");
    var img = sctx.createImageData(state.w, state.h);
    img.data.set(openFrame.data);
    sctx.putImageData(img, 0, 0);
    var canvas = document.createElement("canvas");
    canvas.width = diff.w;
    canvas.height = diff.h;
    var ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(src, diff.x, diff.y, diff.w, diff.h, 0, 0, diff.w, diff.h);
    var blob = await new Promise(function (resolve) { canvas.toBlob(function (b) { resolve(b); }, "image/png"); });
    var name = shotName() + "_open_patch.png";
    downloadBlob(blob, name);
    setStatus("Saved " + name + " at " + diff.x + "," + diff.y + " (" + diff.w + "×" + diff.h + ").", "ok");
  }

  function snapFrames(all) {
    if (!state.palette.length) {
      setStatus("Load a palette before snapping.", "error");
      return;
    }
    var targets = all ? state.frames : [current()];
    var dither = $("#opt-dither").checked;
    var tg16 = $("#opt-tg16").checked;
    targets.forEach(function (frame) {
      if (!frame) return;
      frame.undo.push(new Uint8ClampedArray(frame.data));
      if (frame.undo.length > UNDO_CAP) frame.undo.shift();
      frame.redo.length = 0;
      frame.data = snapData(frame.data, dither, tg16);
    });
    renderStrip();
    afterPixels();
    setStatus(all ? "Snapped every frame onto the locked palette." : "Snapped this frame onto the locked palette.", "ok");
  }

  async function loadSample(which) {
    var res = await fetch("samples/manifest.json");
    if (!res.ok) throw new Error("missing samples");
    var manifest = await res.json();
    var spec = manifest[which];
    var files = [];
    for (var i = 0; i < spec.frames.length; i++) {
      var fr = await fetch("samples/" + spec.frames[i]);
      if (!fr.ok) throw new Error("missing " + spec.frames[i]);
      files.push(new File([await fr.blob()], spec.frames[i], { type: "image/png" }));
    }
    await loadFrameFiles(files);
    $("#shot").value = spec.shot;
    $("#naming").value = spec.naming;
    state.fps = spec.fps || 12;
    $("#fps").value = String(state.fps);
    $("#fps-val").textContent = String(state.fps);
    state.mouthHold = spec.hold || 4;
    $("#hold").value = String(state.mouthHold);
    $("#hold-val").textContent = String(state.mouthHold);
    if (spec.mouth) {
      state.mouth = true;
      state.mouthClosed = spec.mouth[0];
      state.mouthOpen = spec.mouth[1];
    } else {
      state.mouth = false;
      state.mouthClosed = 0;
      state.mouthOpen = Math.min(1, state.frames.length - 1);
    }
    $("#mouth").checked = state.mouth;
    fillMouthSelects();
    state.offsetX = spec.offset[0];
    state.offsetY = spec.offset[1];
    $("#off-x").value = String(state.offsetX);
    $("#off-y").value = String(state.offsetY);
    setZoom(spec.editorZoom || 2);
    setScale(spec.scale || 1);
    if (spec.background) {
      var bg = await fetch("samples/" + spec.background);
      await loadBackground(new File([await bg.blob()], spec.background, { type: "image/png" }));
    } else clearBackground();
    updateNames();
    updatePatchReadout();
    presentEditor();
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setPlaying(!reduce);
    setStatus(spec.note || "Sample loaded.", "ok");
  }

  async function loadBundledPalette(kind) {
    if (kind === "png") {
      var res = await fetch("palettes/tg16.png");
      await loadPaletteFile(new File([await res.blob()], "tg16.png", { type: "image/png" }));
      return;
    }
    var json = await fetch("palettes/tg16.json");
    var extra = parsePaletteJSON(await json.text(), "tg16");
    setStatus("Locked the TG16 master palette." + extra, "ok");
  }

  function exportPalette() {
    var payload = {
      name: state.paletteLabel || shotName(),
      locked: true,
      colors: state.palette.map(function (c) {
        return { name: c.name, rgb: [c.r, c.g, c.b] };
      })
    };
    downloadBlob(new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" }), shotName() + "_palette.json");
  }

  function bind() {
    document.querySelectorAll("[data-tool]").forEach(function (btn) {
      btn.addEventListener("click", function () { setTool(btn.dataset.tool); });
    });
    document.querySelectorAll("[data-brush]").forEach(function (btn) {
      btn.addEventListener("click", function () { setBrush(Number(btn.dataset.brush)); });
    });
    document.querySelectorAll("[data-zoom]").forEach(function (btn) {
      btn.addEventListener("click", function () { setZoom(Number(btn.dataset.zoom)); });
    });
    document.querySelectorAll("[data-scale]").forEach(function (btn) {
      btn.addEventListener("click", function () { setScale(Number(btn.dataset.scale)); });
    });
    $("#btn-undo").addEventListener("click", undo);
    $("#btn-redo").addEventListener("click", redo);
    $("#btn-grid").addEventListener("click", function () {
      state.grid = !state.grid;
      $("#btn-grid").setAttribute("aria-pressed", state.grid ? "true" : "false");
      presentEditor();
    });
    $("#btn-editor-onion").addEventListener("click", function () {
      state.editorOnion = !state.editorOnion;
      $("#btn-editor-onion").setAttribute("aria-pressed", state.editorOnion ? "true" : "false");
      presentEditor();
    });
    $("#btn-new").addEventListener("click", function () { $("#new-dialog").showModal(); });
    document.querySelectorAll("[data-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pair = btn.dataset.preset.split(",");
        $("#new-w").value = pair[0];
        $("#new-h").value = pair[1];
      });
    });
    $("#new-create").addEventListener("click", function () {
      var w = Math.max(1, Math.min(2048, parseInt($("#new-w").value, 10) || 256));
      var h = Math.max(1, Math.min(2048, parseInt($("#new-h").value, 10) || 224));
      newDocument(w, h);
    });
    $("#btn-load").addEventListener("click", function () { $("#file-frames").click(); });
    $("#btn-folder").addEventListener("click", function () { $("#file-folder").click(); });
    $("#file-frames").addEventListener("change", function (e) {
      if (e.target.files.length) loadFrameFiles(e.target.files).catch(function (err) { setStatus(err.message, "error"); });
      e.target.value = "";
    });
    $("#file-folder").addEventListener("change", function (e) {
      if (e.target.files.length) loadFrameFiles(e.target.files).catch(function (err) { setStatus(err.message, "error"); });
      e.target.value = "";
    });
    $("#btn-mouth-sample").addEventListener("click", function () {
      loadSample("mouth").catch(function (err) { setStatus(err.message, "error"); });
    });
    $("#btn-walk-sample").addEventListener("click", function () {
      loadSample("walk").catch(function (err) { setStatus(err.message, "error"); });
    });
    var view = $("#view");
    view.addEventListener("pointerdown", onPointerDown);
    view.addEventListener("pointermove", onPointerMove);
    view.addEventListener("pointerup", onPointerUp);
    view.addEventListener("pointercancel", onPointerUp);
    view.addEventListener("pointerleave", function () {
      state.hover = null;
      $("#coord").textContent = "—";
      if (!state.drawing) presentEditor();
    });
    view.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    $("#stage").addEventListener("dragover", function (e) { e.preventDefault(); });
    $("#stage").addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer.files.length) {
        loadFrameFiles(e.dataTransfer.files).catch(function (err) { setStatus(err.message, "error"); });
      }
    });
    $("#stage").addEventListener("wheel", function (e) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      var levels = [1, 2, 3, 4, 6, 8];
      var i = levels.indexOf(state.zoom);
      if (i < 0) i = 1;
      i = Math.min(levels.length - 1, Math.max(0, i + (e.deltaY > 0 ? -1 : 1)));
      setZoom(levels[i]);
    }, { passive: false });

    $("#btn-pal-png").addEventListener("click", function () { $("#file-palette-png").click(); });
    $("#btn-pal-json").addEventListener("click", function () { $("#file-palette-json").click(); });
    $("#file-palette-png").addEventListener("change", function (e) {
      var file = e.target.files[0];
      if (file) loadPaletteFile(file).catch(function (err) { setStatus(err.message, "error"); });
      e.target.value = "";
    });
    $("#file-palette-json").addEventListener("change", function (e) {
      var file = e.target.files[0];
      if (!file) return;
      file.text().then(function (text) {
        var extra = parsePaletteJSON(text, file.name);
        setStatus("Locked palette from " + file.name + "." + extra, "ok");
      }).catch(function (err) { setStatus(err.message, "error"); });
      e.target.value = "";
    });
    $("#btn-tg16").addEventListener("click", function () {
      loadBundledPalette("json").catch(function (err) { setStatus(err.message, "error"); });
    });
    $("#btn-tg16-png").addEventListener("click", function () {
      loadBundledPalette("png").catch(function (err) { setStatus(err.message, "error"); });
    });
    $("#btn-pal-save").addEventListener("click", exportPalette);
    $("#btn-snap").addEventListener("click", function () { snapFrames(false); });
    $("#btn-snap-all").addEventListener("click", function () { snapFrames(true); });

    $("#fps").addEventListener("input", function () {
      state.fps = parseInt($("#fps").value, 10);
      $("#fps-val").textContent = String(state.fps);
      state.playOrigin = performance.now();
      state.lastTick = -1;
    });
    $("#onion").addEventListener("change", function () {
      state.onion = $("#onion").checked;
      presentPreview();
    });
    $("#onion-op").addEventListener("input", function () {
      state.onionOpacity = parseInt($("#onion-op").value, 10) / 100;
      $("#onion-val").textContent = $("#onion-op").value + "%";
      presentPreview();
      if (state.editorOnion) presentEditor();
    });
    $("#btn-play").addEventListener("click", function () { setPlaying(!state.playing); });
    $("#btn-bg").addEventListener("click", function () { $("#file-bg").click(); });
    $("#btn-bg-clear").addEventListener("click", clearBackground);
    $("#file-bg").addEventListener("change", function (e) {
      var file = e.target.files[0];
      if (file) loadBackground(file).catch(function (err) { setStatus(err.message, "error"); });
      e.target.value = "";
    });
    $("#off-x").addEventListener("input", function () {
      state.offsetX = parseInt($("#off-x").value, 10) || 0;
      presentPreview();
    });
    $("#off-y").addEventListener("input", function () {
      state.offsetY = parseInt($("#off-y").value, 10) || 0;
      presentPreview();
    });
    $("#mouth").addEventListener("change", function () {
      state.mouth = $("#mouth").checked;
      state.playOrigin = performance.now();
      state.lastTick = -1;
      updatePatchReadout();
      presentPreview();
    });
    $("#mouth-closed").addEventListener("change", function () {
      state.mouthClosed = parseInt($("#mouth-closed").value, 10);
      updateNames();
      updatePatchReadout();
      presentPreview();
    });
    $("#mouth-open").addEventListener("change", function () {
      state.mouthOpen = parseInt($("#mouth-open").value, 10);
      updateNames();
      updatePatchReadout();
      presentPreview();
    });
    $("#hold").addEventListener("input", function () {
      state.mouthHold = parseInt($("#hold").value, 10);
      $("#hold-val").textContent = String(state.mouthHold);
      state.playOrigin = performance.now();
      state.lastTick = -1;
    });
    $("#naming").addEventListener("change", updateNames);
    $("#shot").addEventListener("input", function () {
      updateNames();
      updatePatchReadout();
    });
    $("#btn-png").addEventListener("click", function () { downloadCurrent().catch(function (err) { setStatus(err.message, "error"); }); });
    $("#btn-zip").addEventListener("click", function () { downloadAll().catch(function (err) { setStatus(err.message, "error"); }); });
    $("#btn-sheet").addEventListener("click", function () { downloadSheet().catch(function (err) { setStatus(err.message, "error"); }); });
    $("#btn-patch").addEventListener("click", function () { downloadPatch().catch(function (err) { setStatus(err.message, "error"); }); });
    $("#btn-copy").addEventListener("click", function () {
      var text = $("#yaml").textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          setStatus("Copied the mouth YAML.", "ok");
        }).catch(function () { setStatus("Could not copy. Select the YAML block.", "warn"); });
      } else setStatus("Select the YAML block and copy it.", "warn");
    });
    $("#btn-add").addEventListener("click", function () { addFrame(false); });
    $("#btn-dup").addEventListener("click", function () { addFrame(true); });
    $("#btn-del").addEventListener("click", deleteFrame);
    $("#btn-left").addEventListener("click", function () { moveFrame(-1); });
    $("#btn-right").addEventListener("click", function () { moveFrame(1); });
    $("#frame-name").addEventListener("change", function () {
      var frame = current();
      if (!frame) return;
      frame.name = sanitize($("#frame-name").value);
      $("#frame-name").value = frame.name;
      refreshThumb(state.frameIndex);
      fillMouthSelects();
      updateNames();
    });

    document.addEventListener("keydown", function (e) {
      var tag = document.activeElement && document.activeElement.tagName;
      var typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      var key = e.key.toLowerCase();
      if ((e.metaKey || e.ctrlKey) && key === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && key === "y") {
        e.preventDefault();
        redo();
        return;
      }
      if (typing) return;
      if (e.key === " ") {
        e.preventDefault();
        setPlaying(!state.playing);
      } else if (key === "b") setTool("pencil");
      else if (key === "e") setTool("eraser");
      else if (key === "g") setTool("fill");
      else if (key === "i") setTool("eyedropper");
      else if (e.key === "[") {
        var down = [1, 2, 4];
        var di = down.indexOf(state.brush);
        setBrush(down[Math.max(0, di - 1)] || 1);
      } else if (e.key === "]") {
        var up = [1, 2, 4];
        var ui = up.indexOf(state.brush);
        setBrush(up[Math.min(up.length - 1, ui + 1)] || 4);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        selectFrame(state.frameIndex - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        selectFrame(state.frameIndex + 1);
      }
    });
    window.addEventListener("resize", function () {
      presentEditor();
      presentPreview();
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        if (state.raf) cancelAnimationFrame(state.raf);
        return;
      }
      if (state.playing) setPlaying(true);
    });
  }

  async function init() {
    bind();
    try {
      await loadBundledPalette("json");
    } catch (err) {
      setStatus("Could not load the TG16 palette. " + err.message, "error");
    }
    try {
      await loadSample("mouth");
    } catch (err) {
      newDocument(256, 224);
      setStatus("Palette is ready. Load PNGs to start a shot. " + err.message, "error");
    }
  }

  init();
})();
