// Shared mock data for all three mockups
window.APP = (() => {
  const STEPS = ["Dynamic range", "ReplayGain", "Fingerprints", "Tags & cover", "Lyrics", "Filenames"];
  const ALBUMS = [
    { id: 1, title: "True", edition: "1984 Reissue · CP35-3123", artist: "Spandau Ballet", year: 1983,
      discogs: "4555850", mb: "bbdc3aba", status: "ready", done: 0, tracks: 8, dr: null, lyrics: 0, hue: 18, age: "2m" },
    { id: 2, title: "True", edition: "SACD · 2003", artist: "Spandau Ballet", year: 1983,
      discogs: "16167173", mb: "d8732410", status: "fixed", done: 6, tracks: 8, dr: 10, lyrics: 8, hue: 352, age: "6m",
      newTitle: "Spandau_Ballet/True_2003_DR09_SACD_7243_537127_2_3" },
    { id: 3, title: "A Very Special Christmas", edition: "MFSL UDCD", artist: "Various Artists", year: 1987,
      discogs: null, mb: null, status: "needs", done: 0, tracks: 15, dr: null, lyrics: 0, hue: 140, age: "1h" },
    { id: 4, title: "Back To Black", edition: "20th Anniversary", artist: "Amy Winehouse", year: 2006,
      discogs: null, mb: null, status: "needs", done: 0, tracks: 11, dr: null, lyrics: 0, hue: 45, age: "1h" },
    { id: 5, title: "The All-Time Greatest Hits", edition: "DCC Gold", artist: "Roy Orbison", year: 1972,
      discogs: "2546786", mb: "dc5a4813", status: "ready", done: 0, tracks: 20, dr: null, lyrics: 0, hue: 215, age: "3h" },
    { id: 6, title: "A Woman's Heart", edition: "1992 · Dara", artist: "Various Artists", year: 1992,
      discogs: null, mb: null, status: "needs", done: 0, tracks: 12, dr: null, lyrics: 0, hue: 280, age: "1d" },
  ];
  const TRACKS = ["Pleasure", "Communication", "Code Of Love", "Gold", "Lifeline",
                  "Heaven Is A Secret", "Foundation", "True"];
  const LENGTHS = ["3:24", "4:44", "4:21", "4:52", "3:35", "4:22", "3:55", "6:30"];
  const LOG = [
    ["11:10:12", "info", "Measuring dynamic range… DR10"],
    ["11:10:13", "info", "ReplayGain album -7.42 dB, peak 0.98"],
    ["11:10:15", "info", "AcoustID matched 8/8 tracks"],
    ["11:10:16", "info", "Tags written, cover 1200×1200 embedded"],
    ["11:10:17", "info", "Fetching lyrics for 8 tracks with 8 workers"],
    ["11:10:17", "ok",   "LRC: 8 · TXT: 0 · Instrumental: 0 · Failed: 0"],
    ...TRACKS.map((t, i) => ["11:10:17", "file",
      `${String(i + 1).padStart(2, "0")} - ${t}.flac → 01_${String(i + 1).padStart(2, "0")}_${t.replace(/ /g, "_")}.flac`]),
    ["11:10:18", "ok", "Pipeline finished"],
  ];
  const STATUS = { needs: "Needs IDs", ready: "Ready", fixed: "Fixed" };

  // Abstract generated cover art (placeholder, not real artwork)
  function cover(a, cls = "") {
    const h = a.hue, init = a.artist.split(" ").map(w => w[0]).slice(0, 2).join("");
    return `<svg class="${cls}" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs><linearGradient id="c${a.id}${cls.length}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="hsl(${h} 70% 62%)"/><stop offset="1" stop-color="hsl(${(h + 40) % 360} 60% 30%)"/></linearGradient></defs>
      <rect width="100" height="100" fill="url(#c${a.id}${cls.length})"/>
      <circle cx="${30 + (a.id * 13) % 40}" cy="${35 + (a.id * 7) % 30}" r="${18 + a.id * 2}" fill="hsl(${h} 90% 90% / .22)"/>
      <rect x="${55 + a.id % 3 * 5}" y="12" width="9" height="76" rx="2" fill="hsl(${h} 30% 10% / .25)"/>
      <text x="8" y="92" font-family="system-ui,sans-serif" font-weight="700" font-size="13" fill="#fff" opacity=".85">${init}</text></svg>`;
  }
  return { STEPS, ALBUMS, TRACKS, LENGTHS, LOG, STATUS, cover };
})();
