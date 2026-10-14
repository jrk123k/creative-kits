/* Uncompressed ZIP (store method). No dependencies. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.pixelZip = api;
})(typeof self !== "undefined" ? self : this, function () {
  var CRC_TABLE = new Uint32Array(256);
  for (var n = 0; n < 256; n++) {
    var c = n;
    for (var k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    CRC_TABLE[n] = c >>> 0;
  }

  function crc32(bytes) {
    var crc = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) {
      crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  // 2026-10-11 12:00 local DOS timestamp.
  var DOS_TIME = (12 << 11);
  var DOS_DATE = ((2026 - 1980) << 9) | (10 << 5) | 11;

  function makeZip(files) {
    var enc = new TextEncoder();
    var locals = [];
    var centrals = [];
    var offset = 0;
    for (var f = 0; f < files.length; f++) {
      var name = enc.encode(files[f].name);
      var data = files[f].data;
      var crc = crc32(data);
      var local = new Uint8Array(30 + name.length + data.length);
      var view = new DataView(local.buffer);
      view.setUint32(0, 0x04034b50, true);
      view.setUint16(4, 20, true);
      view.setUint16(8, 0, true);
      view.setUint16(10, DOS_TIME, true);
      view.setUint16(12, DOS_DATE, true);
      view.setUint32(14, crc, true);
      view.setUint32(18, data.length, true);
      view.setUint32(22, data.length, true);
      view.setUint16(26, name.length, true);
      local.set(name, 30);
      local.set(data, 30 + name.length);
      locals.push(local);

      var central = new Uint8Array(46 + name.length);
      var cv = new DataView(central.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);
      cv.setUint16(6, 20, true);
      cv.setUint16(12, DOS_TIME, true);
      cv.setUint16(14, DOS_DATE, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, data.length, true);
      cv.setUint32(24, data.length, true);
      cv.setUint16(28, name.length, true);
      cv.setUint32(42, offset, true);
      central.set(name, 46);
      centrals.push(central);
      offset += local.length;
    }
    var cdSize = 0;
    for (var i = 0; i < centrals.length; i++) cdSize += centrals[i].length;
    var eocd = new Uint8Array(22);
    var ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, files.length, true);
    ev.setUint16(10, files.length, true);
    ev.setUint32(12, cdSize, true);
    ev.setUint32(16, offset, true);
    var out = new Uint8Array(offset + cdSize + 22);
    var p = 0;
    for (var a = 0; a < locals.length; a++) {
      out.set(locals[a], p);
      p += locals[a].length;
    }
    for (var b = 0; b < centrals.length; b++) {
      out.set(centrals[b], p);
      p += centrals[b].length;
    }
    out.set(eocd, p);
    return out;
  }

  return { makeZip: makeZip, crc32: crc32 };
});
