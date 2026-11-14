'use strict';

/* =====================================================================
   CLI Music — desktop music app
   Library + player, playlists, tag editing, search with song/video
   previews, and one-click downloads into the library.
   ===================================================================== */

// The access token arrives in the URL fragment (#t=...), which browsers never send to the
// server, so the served page holds no secret. sessionStorage keeps it across reloads.
const TOKEN = (() => {
  const fromHash = new URLSearchParams(location.hash.slice(1)).get('t');
  if (fromHash) {
    try { sessionStorage.setItem('cm.token', fromHash); } catch { /* storage blocked */ }
    history.replaceState(null, '', location.pathname);
    return fromHash;
  }
  try { return sessionStorage.getItem('cm.token') || ''; } catch { return ''; }
})();
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
const icon = (name, cls = '') => `<svg class="ic ${cls}"><use href="#i-${name}"/></svg>`;
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
const withToken = (url) => url + (url.includes('?') ? '&' : '?') + 't=' + encodeURIComponent(TOKEN);
const artUrl = (id, size = 300) => withToken(`/api/art/${id}?s=${size}`);

function store(key, fallback) {
  try { const v = localStorage.getItem('cm.' + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
}
function save(key, value) { try { localStorage.setItem('cm.' + key, JSON.stringify(value)); } catch { /* private mode */ } }

function fmtTime(sec) {
  if (!isFinite(sec) || sec < 0) sec = 0;
  sec = Math.floor(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}
function fmtLong(sec) {
  const m = Math.round(sec / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} hr${h > 1 ? 's' : ''} ${m % 60} min`;
}
function fmtSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(1) + ' GB';
  if (bytes > 1e6) return (bytes / 1e6).toFixed(1) + ' MB';
  return Math.round(bytes / 1e3) + ' KB';
}
const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;
const norm = (s) => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/\s*[\(\[][^\)\]]*(feat|ft\.|with|remaster|version|edit|live)[^\)\]]*[\)\]]/g, '')
  .replace(/[^a-z0-9]+/g, ' ').trim();
const songKey = (artist, title) => norm(artist).split(' ').slice(0, 3).join(' ') + '|' + norm(title);

function hue(str) { let h = 0; for (const c of String(str)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
function placeholder(label, iconName = 'note', round = false, extra = '') {
  const h = hue(label || '?');
  return `<div class="art ${extra}" style="--c1:hsl(${h} 45% 38%);--c2:hsl(${(h + 40) % 360} 50% 22%);${round ? 'border-radius:50%' : ''}">${icon(iconName)}</div>`;
}
function songArt(song, size = 120, extra = '') {
  if (!song) return placeholder('?', 'note', false, extra);
  if (!song.has_art) return placeholder(song.album || song.title, 'note', false, extra);
  return `<div class="art ${extra}"><img loading="lazy" src="${artUrl(song.id, size)}" alt=""></div>`;
}
function remoteArt(url, label, extra = '') {
  if (!url) return placeholder(label, 'note', false, extra);
  return `<div class="art ${extra}"><img loading="lazy" src="${esc(url)}" alt="" referrerpolicy="no-referrer"></div>`;
}

async function api(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  const opts = { method, headers: { 'X-Token': TOKEN, ...headers } };
  if (body !== undefined) {
    if (raw) opts.body = body;
    else { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
  return data;
}

/* ===================================================================== state */

const S = {
  songs: new Map(),
  list: [],
  libVersion: -1,
  root: '',
  rootExists: true,
  playlists: [],
  plays: {},
  loved: new Set(),
  settings: {},
  jobs: [],
  dlVersion: -1,
  active: 0,
  desktop: false,
  ffmpeg: true,
  view: store('view', { name: 'recent' }),
  back: [],
  sel: new Set(),
  lastSel: null,
  tableIds: [],
  tableCtx: null,
  sorts: store('sorts', {}),
  filters: {},
  searchQ: '',
  search: { songs: null, videos: null, songsErr: '', videosErr: '', q: '' },
  foryou: null,
  foryouStatus: '',
  dzArt: new Map(),
  lyricsCache: new Map(),
  drawer: store('drawer', null),
  organizeMoves: null,
};

const DEFAULT_SORTS = { recent: { key: 'added', dir: -1 }, songs: { key: 'artist', dir: 1 } };
function sortFor(view) { return S.sorts[view] || DEFAULT_SORTS[view] || { key: 'artist', dir: 1 }; }

function setLibrary(lib) {
  S.libVersion = lib.version;
  S.root = lib.root;
  S.rootExists = lib.exists;
  S.songs = new Map(lib.songs.map((s) => [s.id, s]));
  S.list = lib.songs;
  for (const id of [...S.sel]) if (!S.songs.has(id)) S.sel.delete(id);
}

function albumKey(s) { return (s.album_artist || s.artist || '').toLowerCase() + '\u0001' + (s.album || '').toLowerCase(); }
function albums() {
  const map = new Map();
  for (const s of S.list) {
    const k = albumKey(s);
    let a = map.get(k);
    if (!a) { a = { key: k, name: s.album || 'Unknown Album', artist: s.album_artist || s.artist, songs: [], art: null, year: '', genre: '', added: 0 }; map.set(k, a); }
    a.songs.push(s);
    if (!a.art && s.has_art) a.art = s;
    if (!a.year && s.year) a.year = s.year;
    if (!a.genre && s.genre) a.genre = s.genre;
    a.added = Math.max(a.added, s.added);
  }
  for (const a of map.values()) a.songs.sort((x, y) => (x.disc - y.disc) || (x.track - y.track) || collator.compare(x.title, y.title));
  return [...map.values()];
}
function artists() {
  const map = new Map();
  for (const s of S.list) {
    const name = s.album_artist || s.artist || 'Unknown Artist';
    const k = name.toLowerCase();
    let a = map.get(k);
    if (!a) { a = { name, songs: [], art: null }; map.set(k, a); }
    a.songs.push(s);
    if (!a.art && s.has_art) a.art = s;
  }
  return [...map.values()].sort((x, y) => collator.compare(x.name, y.name));
}

const plays = (id) => (S.plays[id] && S.plays[id].count) || 0;

function sortIds(ids, sort) {
  const get = {
    title: (s) => s.title, artist: (s) => s.artist, album: (s) => s.album, genre: (s) => s.genre,
    year: (s) => s.year, time: (s) => s.duration, plays: (s) => plays(s.id), added: (s) => s.added,
  }[sort.key] || ((s) => s.artist);
  const songs = ids.map((id) => S.songs.get(id)).filter(Boolean);
  songs.sort((a, b) => {
    const va = get(a), vb = get(b);
    let c = typeof va === 'number' ? va - vb : collator.compare(va || '￿', vb || '￿');
    if (!c && (sort.key === 'artist' || sort.key === 'album')) {
      c = collator.compare(a.album, b.album) || (a.disc - b.disc) || (a.track - b.track) || collator.compare(a.title, b.title);
    }
    if (!c) c = collator.compare(a.title, b.title);
    return c * sort.dir;
  });
  return songs.map((s) => s.id);
}

function matchesFilter(s, q) {
  if (!q) return true;
  const hay = norm(`${s.title} ${s.artist} ${s.album} ${s.genre} ${s.album_artist}`);
  return norm(q).split(' ').every((t) => hay.includes(t));
}

/* ===================================================================== toasts & menus & modals */

function toast(message, kind = '', iconName = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.innerHTML = `${icon(kind === 'ok' ? 'check' : kind === 'bad' ? 'x' : iconName)}<div>${message}</div>`;
  $('#toasts').append(el);
  setTimeout(() => { el.style.transition = 'opacity .3s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 320); }, 3800);
}

const menu = $('#menu');
let menuStack = [];
function showMenu(x, y, items) {
  menuStack = [items];
  drawMenu(items);
  menu.hidden = false;
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, window.innerWidth - r.width - 8) + 'px';
  menu.style.top = Math.min(y, window.innerHeight - r.height - 8) + 'px';
}
function drawMenu(items) {
  menu.innerHTML = '';
  if (menuStack.length > 1) {
    const back = document.createElement('button');
    back.innerHTML = `${icon('back')}<span>Back</span>`;
    back.onclick = (e) => { e.stopPropagation(); menuStack.pop(); drawMenu(menuStack[menuStack.length - 1]); };
    menu.append(back, document.createElement('hr'));
  }
  for (const it of items) {
    if (!it) continue;
    if (it.sep) { menu.append(document.createElement('hr')); continue; }
    if (it.label && it.header) { const l = document.createElement('div'); l.className = 'label'; l.textContent = it.label; menu.append(l); continue; }
    const b = document.createElement('button');
    if (it.danger) b.className = 'danger';
    b.innerHTML = `${icon(it.icon || 'chevron')}<span>${esc(it.label)}</span>${it.sub ? icon('chevron', 'sub-arrow') : ''}`;
    b.onclick = (e) => {
      e.stopPropagation();
      if (it.sub) { menuStack.push(it.sub()); drawMenu(menuStack[menuStack.length - 1]); return; }
      hideMenu();
      it.act();
    };
    menu.append(b);
  }
}
function hideMenu() { menu.hidden = true; }
document.addEventListener('mousedown', (e) => { if (!menu.hidden && !menu.contains(e.target)) hideMenu(); });
window.addEventListener('blur', hideMenu);

function modal({ title, body, buttons = [], left = [], wide = false, onClose }) {
  const root = document.createElement('div');
  root.className = 'backdrop';
  root.innerHTML = `<div class="modal ${wide ? 'wide' : ''}" role="dialog">
      <div class="modal-h"><h3>${esc(title)}</h3><button class="icon-btn" data-close title="Close">${icon('x')}</button></div>
      <div class="modal-b">${body}</div>
      ${buttons.length || left.length ? `<div class="modal-f"><div class="left"></div></div>` : ''}
    </div>`;
  const close = () => { root.remove(); document.removeEventListener('keydown', onKey, true); onClose && onClose(); };
  const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  document.addEventListener('keydown', onKey, true);
  root.addEventListener('mousedown', (e) => { if (e.target === root) close(); });
  $('[data-close]', root).onclick = close;
  const foot = $('.modal-f', root);
  const mk = (b) => {
    const el = document.createElement('button');
    el.className = `btn ${b.primary ? 'primary' : ''} ${b.danger ? 'danger' : ''}`;
    el.innerHTML = (b.icon ? icon(b.icon) : '') + esc(b.label);
    el.onclick = () => b.act(close, root, el);
    return el;
  };
  if (foot) {
    left.forEach((b) => $('.left', foot).append(mk(b)));
    buttons.forEach((b) => foot.append(mk(b)));
  }
  $('#modal-root').append(root);
  const first = $('input:not([type=checkbox]), textarea', root);
  if (first) setTimeout(() => first.focus(), 30);
  return { root, close };
}

function confirmDialog(message, okLabel = 'OK', danger = false) {
  return new Promise((resolve) => {
    let done = false;
    modal({
      title: 'Please confirm', body: `<div>${message}</div>`,
      onClose: () => { if (!done) resolve(false); },
      buttons: [
        { label: 'Cancel', act: (close) => { done = true; close(); resolve(false); } },
        { label: okLabel, primary: !danger, danger, act: (close) => { done = true; close(); resolve(true); } },
      ],
    });
  });
}

function promptDialog(title, label, value = '', okLabel = 'OK') {
  return new Promise((resolve) => {
    let done = false;
    const m = modal({
      title, body: `<div class="form"><label class="k">${esc(label)}</label><input class="field" id="prompt-v" value="${esc(value)}"></div>`,
      onClose: () => { if (!done) resolve(null); },
      buttons: [
        { label: 'Cancel', act: (close) => { done = true; close(); resolve(null); } },
        { label: okLabel, primary: true, act: (close, root) => { done = true; const v = $('#prompt-v', root).value; close(); resolve(v); } },
      ],
    });
    $('#prompt-v', m.root).addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { done = true; const v = e.target.value; m.close(); resolve(v); }
    });
  });
}

/* ===================================================================== player */

const audio = $('#audio');
const P = {
  queue: [],
  index: -1,
  original: null,
  shuffle: store('shuffle', false),
  repeat: store('repeat', 'off'),
  transient: null, // a preview (search result, suggestion, video audio) playing over the queue
  resume: null,
  counted: false,
  seeking: false,
};

const current = () => (P.transient ? null : S.songs.get(P.queue[P.index]));

function shuffled(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

function playIds(ids, start = 0, { shuffle = null } = {}) {
  ids = ids.filter((id) => S.songs.has(id));
  if (!ids.length) return;
  if (shuffle !== null) { P.shuffle = shuffle; save('shuffle', P.shuffle); }
  start = Math.max(0, Math.min(start, ids.length - 1));
  P.original = ids.slice();
  if (P.shuffle) {
    const first = ids[shuffle === true && start === 0 ? Math.floor(Math.random() * ids.length) : start];
    P.queue = [first, ...shuffled(ids.filter((id) => id !== first))];
    P.index = 0;
  } else {
    P.queue = ids.slice();
    P.index = start;
  }
  loadCurrent(true);
}

function loadCurrent(autoplay, startAt = 0) {
  P.transient = null;
  P.resume = null;
  const song = current();
  if (!song) { stopPlayback(); return; }
  audio.src = withToken(`/api/audio/${song.id}`);
  P.counted = false;
  if (startAt) audio.addEventListener('loadedmetadata', () => { audio.currentTime = startAt; }, { once: true });
  if (autoplay) audio.play().catch(() => {});
  updateNowPlaying();
  persistQueue();
}

function stopPlayback() {
  audio.pause();
  audio.removeAttribute('src');
  audio.load();
  P.transient = null;
  updateNowPlaying();
}

function next(auto = false) {
  if (P.transient) { endPreview(true); return; }
  if (!P.queue.length) return;
  if (auto && P.repeat === 'one') { audio.currentTime = 0; audio.play(); P.counted = false; return; }
  if (P.index + 1 < P.queue.length) P.index += 1;
  else if (P.repeat === 'all') P.index = 0;
  else { audio.pause(); audio.currentTime = 0; updateNowPlaying(); return; }
  loadCurrent(true);
}

function prev() {
  if (P.transient) { audio.currentTime = 0; return; }
  if (audio.currentTime > 3 || P.index <= 0) { audio.currentTime = 0; return; }
  P.index -= 1;
  loadCurrent(true);
}

function togglePlay() {
  if (!audio.src || audio.src === location.href) {
    if (P.queue.length && P.index >= 0) { loadCurrent(true, P.resumeAt || 0); P.resumeAt = 0; return; }
    if (S.tableIds.length) playIds(S.tableIds, 0);
    return;
  }
  if (audio.paused) audio.play().catch((e) => toast(esc(e.message), 'bad')); else audio.pause();
}

function playNext(ids) {
  ids = ids.filter((id) => S.songs.has(id));
  if (!ids.length) return;
  if (P.index < 0 || !P.queue.length) { playIds(ids); return; }
  P.queue.splice(P.index + 1, 0, ...ids);
  if (P.original) P.original.push(...ids);
  persistQueue(); renderDrawer();
  toast(`Playing next: ${esc(ids.length === 1 ? S.songs.get(ids[0]).title : plural(ids.length, 'song'))}`);
}
function addToQueue(ids) {
  ids = ids.filter((id) => S.songs.has(id));
  if (!ids.length) return;
  if (P.index < 0 || !P.queue.length) { P.queue = ids.slice(); P.index = 0; loadCurrent(false); }
  else { P.queue.push(...ids); if (P.original) P.original.push(...ids); }
  persistQueue(); renderDrawer();
  toast(`Added ${esc(ids.length === 1 ? S.songs.get(ids[0]).title : plural(ids.length, 'song'))} to Up Next`);
}

function setShuffle(on) {
  P.shuffle = on;
  save('shuffle', on);
  const cur = P.queue[P.index];
  if (on && P.queue.length) {
    P.original = P.queue.slice();
    P.queue = [...P.queue.slice(0, P.index + 1), ...shuffled(P.queue.slice(P.index + 1))];
  } else if (!on && P.original) {
    P.queue = P.original.slice();
    P.index = Math.max(0, P.queue.indexOf(cur));
  }
  persistQueue(); updateControls(); renderDrawer();
}

/** Play a preview (30 s catalog clip, suggestion, or a YouTube video's audio) over the queue. */
function playPreview(item) {
  if (P.transient && P.transient.key === item.key) {
    if (audio.paused) audio.play(); else audio.pause();
    return;
  }
  if (!P.transient) {
    const song = current();
    P.resume = song ? { time: audio.currentTime, wasPlaying: !audio.paused } : null;
  }
  P.transient = item;
  audio.src = item.src;
  audio.play().catch((e) => { toast(`Could not play preview: ${esc(e.message)}`, 'bad'); });
  updateNowPlaying();
}

function endPreview(resumeQueue = false) {
  const resume = P.resume;
  P.transient = null;
  if (current()) {
    loadCurrent(resumeQueue || (resume && resume.wasPlaying) ? false : false, resume ? resume.time : 0);
    if (resumeQueue) audio.play().catch(() => {});
  } else {
    stopPlayback();
  }
}

function persistQueue() {
  save('queue', { queue: P.queue.slice(0, 2000), index: P.index, time: P.transient ? 0 : audio.currentTime || 0 });
}

function updateNowPlaying() {
  const song = current();
  const t = P.transient;
  const artEl = $('#np-art');
  $('#preview-pill').hidden = !t;
  $('#preview-pill').textContent = t ? (t.label || 'Preview') : '';
  const love = $('#np-love');
  if (t) {
    artEl.innerHTML = remoteArt(t.art, t.title);
    $('#np-title').textContent = t.title;
    $('#np-sub').innerHTML = esc(t.artist) + (t.origin ? ` <span class="faint">· ${esc(t.origin)}</span>` : '');
    love.hidden = true;
  } else if (song) {
    artEl.innerHTML = songArt(song, 160);
    $('#np-title').textContent = song.title;
    $('#np-sub').innerHTML = `<span class="link" data-goto-artist="${esc(song.artist)}">${esc(song.artist)}</span>` +
      (song.album ? ` — <span class="link" data-goto-album="${esc(albumKey(song))}">${esc(song.album)}</span>` : '');
    love.hidden = false;
    love.classList.toggle('on', S.loved.has(song.id));
    love.innerHTML = icon(S.loved.has(song.id) ? 'heart-fill' : 'heart');
  } else {
    artEl.innerHTML = placeholder('', 'note');
    $('#np-title').textContent = 'Not playing';
    $('#np-sub').textContent = 'Pick a song from your library, or search to preview anything';
    love.hidden = true;
  }
  document.title = t ? `${t.title} — Preview` : song ? `${song.title} — ${song.artist}` : 'CLI Music';
  updateControls();
  markPlaying();
  if (S.drawer) renderDrawer();
  if ('mediaSession' in navigator) {
    try {
      const m = t || song;
      navigator.mediaSession.metadata = m ? new MediaMetadata({
        title: m.title, artist: m.artist, album: (song && song.album) || '',
        artwork: song && song.has_art ? [{ src: location.origin + artUrl(song.id, 512), sizes: '512x512', type: 'image/jpeg' }]
          : t && t.art ? [{ src: t.art }] : [],
      }) : null;
    } catch { /* not supported */ }
  }
}

function updateControls() {
  const playing = !audio.paused && !!audio.src;
  $('#btn-play').innerHTML = icon(playing ? 'pause' : 'play');
  $('#btn-play').title = playing ? 'Pause (Space)' : 'Play (Space)';
  $('#btn-shuffle').classList.toggle('on', P.shuffle);
  const rep = $('#btn-repeat');
  rep.classList.toggle('on', P.repeat !== 'off');
  rep.innerHTML = icon(P.repeat === 'one' ? 'repeat-one' : 'repeat');
  rep.title = { off: 'Repeat: off', all: 'Repeat: all', one: 'Repeat: one' }[P.repeat];
  $('#btn-queue').classList.toggle('on', S.drawer === 'queue');
  $('#btn-lyrics').classList.toggle('on', S.drawer === 'lyrics');
  $$('[data-preview-key]').forEach((el) => {
    const on = P.transient && P.transient.key === el.dataset.previewKey && playing;
    el.innerHTML = icon(on ? 'pause' : el.dataset.icon || 'play');
    el.closest('.result, .card')?.classList.toggle('playing', !!(P.transient && P.transient.key === el.dataset.previewKey));
  });
}

function markPlaying() {
  const id = current()?.id;
  $$('tr.row.playing').forEach((r) => r.classList.remove('playing'));
  if (id) $$(`tr.row[data-id="${id}"]`).forEach((r) => r.classList.add('playing'));
}

function setFill(input) {
  const pct = ((input.value - input.min) / (input.max - input.min)) * 100;
  input.style.setProperty('--fill', pct + '%');
}

audio.addEventListener('play', updateControls);
audio.addEventListener('pause', () => { updateControls(); persistQueue(); });
audio.addEventListener('ended', () => {
  if (P.transient) { endPreview(false); return; }
  next(true);
});
audio.addEventListener('error', () => {
  if (!audio.src || audio.src === location.href) return;
  if (P.transient) { toast(`Preview unavailable: ${esc(P.transient.title)}`, 'bad'); endPreview(false); return; }
  const song = current();
  toast(`Could not play ${esc(song ? song.title : 'this file')}`, 'bad');
});
let lastPersist = 0;
audio.addEventListener('timeupdate', () => {
  const seek = $('#seek');
  const dur = audio.duration || (P.transient ? 30 : current()?.duration) || 0;
  if (!P.seeking) {
    seek.value = dur ? Math.round((audio.currentTime / dur) * 1000) : 0;
    setFill(seek);
  }
  $('#t-cur').textContent = fmtTime(audio.currentTime);
  $('#t-dur').textContent = fmtTime(dur);
  const song = current();
  if (song && !P.counted && (audio.currentTime > 30 || (dur && audio.currentTime > dur * 0.5))) {
    P.counted = true;
    api(`/api/play/${song.id}`, { method: 'POST' }).then((entry) => { S.plays[song.id] = entry; }).catch(() => {});
  }
  if (Date.now() - lastPersist > 5000) { lastPersist = Date.now(); persistQueue(); }
});

const seekEl = $('#seek');
seekEl.addEventListener('input', () => {
  P.seeking = true; setFill(seekEl);
  const dur = audio.duration || 0;
  $('#t-cur').textContent = fmtTime((seekEl.value / 1000) * dur);
});
seekEl.addEventListener('change', () => {
  const dur = audio.duration || 0;
  if (dur) audio.currentTime = (seekEl.value / 1000) * dur;
  P.seeking = false;
});
const volEl = $('#volume');
volEl.value = store('volume', 80);
audio.volume = Math.pow(volEl.value / 100, 1.6);
setFill(volEl);
volEl.addEventListener('input', () => {
  audio.volume = Math.pow(volEl.value / 100, 1.6);
  audio.muted = false;
  setFill(volEl); save('volume', +volEl.value); updateMute();
});
function updateMute() { $('#btn-mute').innerHTML = icon(audio.muted || +volEl.value === 0 ? 'mute' : 'volume'); }

$('#btn-play').onclick = togglePlay;
$('#btn-next').onclick = () => next(false);
$('#btn-prev').onclick = prev;
$('#btn-shuffle').onclick = () => setShuffle(!P.shuffle);
$('#btn-repeat').onclick = () => {
  P.repeat = { off: 'all', all: 'one', one: 'off' }[P.repeat];
  save('repeat', P.repeat); updateControls();
};
$('#btn-mute').onclick = () => { audio.muted = !audio.muted; updateMute(); };
$('#btn-queue').onclick = () => toggleDrawer('queue');
$('#btn-lyrics').onclick = () => toggleDrawer('lyrics');
$('#drawer-close').onclick = () => toggleDrawer(null);
$$('[data-drawer]').forEach((b) => { b.onclick = () => toggleDrawer(b.dataset.drawer, true); });
$('#np-love').onclick = () => { const s = current(); if (s) setLoved([s.id], !S.loved.has(s.id)); };
$('#np-art').onclick = () => { const s = current(); if (s && s.album) go('album', albumKey(s)); };
$('#np-sub').addEventListener('click', (e) => {
  const a = e.target.closest('[data-goto-artist]');
  if (a) go('artists', a.dataset.gotoArtist);
  const al = e.target.closest('[data-goto-album]');
  if (al) go('album', al.dataset.gotoAlbum);
});

if ('mediaSession' in navigator) {
  try {
    navigator.mediaSession.setActionHandler('play', () => audio.play());
    navigator.mediaSession.setActionHandler('pause', () => audio.pause());
    navigator.mediaSession.setActionHandler('nexttrack', () => next(false));
    navigator.mediaSession.setActionHandler('previoustrack', prev);
  } catch { /* partial support */ }
}

/* ===================================================================== drawer: up next & lyrics */

function toggleDrawer(which, force = false) {
  S.drawer = which && (force || S.drawer !== which) ? which : null;
  save('drawer', S.drawer);
  $('#drawer').hidden = !S.drawer;
  renderDrawer();
  updateControls();
}

function queueRow(id, i, isCurrent) {
  const s = S.songs.get(id);
  if (!s) return '';
  return `<div class="q-item ${isCurrent ? 'current' : ''}" data-qi="${i}">
    ${songArt(s, 80)}
    <div class="q-text"><div class="q-t">${esc(s.title)}</div><div class="q-s">${esc(s.artist)}</div></div>
    ${isCurrent ? '' : `<button class="icon-btn small" data-q-remove="${i}" title="Remove">${icon('x')}</button>`}
  </div>`;
}

async function renderDrawer() {
  if (!S.drawer) return;
  $$('[data-drawer]').forEach((b) => b.classList.toggle('on', b.dataset.drawer === S.drawer));
  const body = $('#drawer-body');
  if (S.drawer === 'queue') {
    const t = P.transient;
    let html = '';
    if (t) {
      html += `<div class="q-h">Previewing</div><div class="q-item current">${remoteArt(t.art, t.title)}<div class="q-text"><div class="q-t">${esc(t.title)}</div><div class="q-s">${esc(t.artist)}</div></div></div>`;
    }
    if (P.index >= 0 && P.queue[P.index]) html += `<div class="q-h">Now Playing</div>` + queueRow(P.queue[P.index], P.index, !t);
    const upcoming = P.queue.slice(P.index + 1, P.index + 301);
    html += `<div class="q-h"><span>Up Next${P.shuffle ? ' · Shuffled' : ''}</span>${upcoming.length ? '<button data-q-clear>Clear</button>' : ''}</div>`;
    html += upcoming.length ? upcoming.map((id, k) => queueRow(id, P.index + 1 + k, false)).join('')
      : `<div class="faint" style="padding:8px">Nothing queued. Right-click songs to add them.</div>`;
    if (P.queue.length - P.index - 1 > 300) html += `<div class="faint" style="padding:8px">and ${plural(P.queue.length - P.index - 301, 'more song')}</div>`;
    body.innerHTML = html;
  } else {
    const t = P.transient;
    const song = current();
    if (t || !song) {
      body.innerHTML = `<div class="empty">${icon('lyrics')}<div>${t ? 'Lyrics are shown for songs in your library.' : 'Play a song to see its lyrics.'}</div></div>`;
      return;
    }
    const id = song.id;
    body.innerHTML = `<div class="lyrics-head"><b>${esc(song.title)}</b> · ${esc(song.artist)}</div><div class="loading-row" style="padding:12px"><span class="spinner"></span></div>`;
    let lyrics = S.lyricsCache.get(id);
    if (lyrics === undefined) {
      try { lyrics = (await api(`/api/lyrics/${id}`)).lyrics || ''; } catch { lyrics = ''; }
      S.lyricsCache.set(id, lyrics);
    }
    if (S.drawer !== 'lyrics' || current()?.id !== id) return;
    body.innerHTML = `<div class="lyrics-head"><b>${esc(song.title)}</b> · ${esc(song.artist)}</div>` + (lyrics
      ? `<div class="lyrics">${esc(lyrics)}</div>`
      : `<div class="empty" style="padding:40px 10px">${icon('lyrics')}<div>No lyrics in this file.</div>
         <button class="btn" style="margin-top:12px" data-fix-one="${id}">${icon('wand')}Look up lyrics</button></div>`);
  }
}

$('#drawer-body').addEventListener('dblclick', (e) => {
  const row = e.target.closest('[data-qi]');
  if (!row) return;
  P.index = +row.dataset.qi;
  loadCurrent(true);
});
$('#drawer-body').addEventListener('click', (e) => {
  const rm = e.target.closest('[data-q-remove]');
  if (rm) { P.queue.splice(+rm.dataset.qRemove, 1); persistQueue(); renderDrawer(); return; }
  if (e.target.closest('[data-q-clear]')) { P.queue = P.queue.slice(0, P.index + 1); P.original = null; persistQueue(); renderDrawer(); return; }
  const fix = e.target.closest('[data-fix-one]');
  if (fix) { fixSongs([fix.dataset.fixOne]); S.lyricsCache.delete(fix.dataset.fixOne); }
});

/* ===================================================================== navigation */

const NAV = [
  { h: 'Discover' },
  { view: 'search', label: 'Search', icon: 'search' },
  { view: 'foryou', label: 'For You', icon: 'spark' },
  { h: 'Library' },
  { view: 'recent', label: 'Recently Added', icon: 'clock' },
  { view: 'songs', label: 'Songs', icon: 'note' },
  { view: 'albums', label: 'Albums', icon: 'album' },
  { view: 'artists', label: 'Artists', icon: 'mic' },
  { view: 'genres', label: 'Genres', icon: 'tag' },
  { view: 'loved', label: 'Loved', icon: 'heart' },
  { view: 'mostplayed', label: 'Most Played', icon: 'headphones' },
  { h: 'Manage' },
  { view: 'downloads', label: 'Downloads', icon: 'download' },
  { view: 'organizer', label: 'Organizer', icon: 'wand' },
  { view: 'settings', label: 'Settings', icon: 'gear' },
];

function renderNav() {
  const v = S.view;
  let html = '';
  for (const n of NAV) {
    if (n.h) { html += `<div class="nav-h">${n.h}</div>`; continue; }
    const active = v.name === n.view || (n.view === 'albums' && v.name === 'album') || (n.view === 'organizer' && v.name === 'smart');
    let extra = '';
    if (n.view === 'downloads' && S.active) extra = `<span class="badge">${S.active}</span>`;
    if (n.view === 'songs') extra = `<span class="badge muted">${S.list.length.toLocaleString()}</span>`;
    html += `<button class="nav-item ${active ? 'active' : ''}" data-nav="${n.view}">${icon(n.icon)}<span class="lbl">${n.label}</span>${extra}</button>`;
  }
  html += `<div class="nav-h">Playlists <button data-new-playlist title="New playlist">${icon('plus')}</button></div>`;
  for (const pl of S.playlists) {
    const active = v.name === 'playlist' && v.param === pl.id;
    html += `<button class="nav-item ${active ? 'active' : ''}" data-nav="playlist" data-param="${pl.id}" data-drop-playlist="${pl.id}">${icon('list')}<span class="lbl">${esc(pl.name)}</span></button>`;
  }
  if (!S.playlists.length) html += `<div class="faint" style="padding:4px 10px 8px;font-size:12px">Drag songs here or click + to make a playlist.</div>`;
  $('#nav').innerHTML = html;
}

$('#nav').addEventListener('click', async (e) => {
  if (e.target.closest('[data-new-playlist]')) { newPlaylist([]); return; }
  const b = e.target.closest('[data-nav]');
  if (b) go(b.dataset.nav, b.dataset.param);
});
$('#nav').addEventListener('contextmenu', (e) => {
  const b = e.target.closest('[data-drop-playlist]');
  if (!b) return;
  e.preventDefault();
  const pl = S.playlists.find((p) => p.id === b.dataset.dropPlaylist);
  showMenu(e.clientX, e.clientY, [
    { label: 'Play', icon: 'play', act: () => playIds(pl.songs) },
    { label: 'Shuffle', icon: 'shuffle', act: () => playIds(pl.songs, 0, { shuffle: true }) },
    { sep: true },
    { label: 'Rename…', icon: 'tag', act: () => renamePlaylist(pl) },
    { label: 'Delete Playlist', icon: 'trash', danger: true, act: () => deletePlaylist(pl) },
  ]);
});
// Drag songs onto a playlist in the sidebar.
$('#nav').addEventListener('dragover', (e) => {
  const b = e.target.closest('[data-drop-playlist]');
  if (b && e.dataTransfer.types.includes('text/x-song-ids')) { e.preventDefault(); b.classList.add('drop'); }
});
$('#nav').addEventListener('dragleave', (e) => { e.target.closest('[data-drop-playlist]')?.classList.remove('drop'); });
$('#nav').addEventListener('drop', async (e) => {
  const b = e.target.closest('[data-drop-playlist]');
  if (!b) return;
  e.preventDefault();
  b.classList.remove('drop');
  const ids = JSON.parse(e.dataTransfer.getData('text/x-song-ids') || '[]');
  addToPlaylist(b.dataset.dropPlaylist, ids);
});

function go(name, param, { push = true } = {}) {
  if (push && (S.view.name !== name || S.view.param !== param)) S.back.push(S.view);
  S.view = { name, param };
  if (['album', 'playlist'].includes(name) || name !== 'search') save('view', S.view);
  S.sel.clear();
  render();
  $('#main').scrollTop = 0;
}
function goBack() { const v = S.back.pop(); if (v) go(v.name, v.param, { push: false }); }

/* ===================================================================== rendering */

const VIEWS = {};
let renderToken = 0;

function render() {
  renderNav();
  const v = S.view;
  const fn = VIEWS[v.name] || VIEWS.recent;
  renderToken += 1;
  const main = $('#main');
  main.innerHTML = '';
  const html = fn(v.param);
  if (typeof html === 'string') main.innerHTML = html;
  afterRender();
}

/** Re-render the current view in place (keeps scroll position and the focused filter box). */
function rerender() {
  const main = $('#main');
  const scroll = main.scrollTop;
  const focused = document.activeElement && document.activeElement.id && main.contains(document.activeElement)
    ? { id: document.activeElement.id, start: document.activeElement.selectionStart } : null;
  render();
  main.scrollTop = scroll;
  if (focused) {
    const el = document.getElementById(focused.id);
    if (el) { el.focus(); try { el.setSelectionRange(focused.start, focused.start); } catch { /* not a text box */ } }
  }
}

function afterRender() {
  markPlaying();
  updateControls();
  $$('img', $('#main')).forEach((img) => {
    img.addEventListener('error', () => {
      const box = img.parentElement;
      if (box) box.outerHTML = placeholder(box.closest('[data-label]')?.dataset.label || '', 'note', false, box.className.replace('art', '').trim());
    }, { once: true });
  });
}

function viewHead(title, sub = '', actions = '') {
  return `<div class="view-head"><h1>${title}${sub ? `<div class="sub">${sub}</div>` : ''}</h1><div class="actions">${actions}</div></div>`;
}
function summary(ids) {
  const total = ids.reduce((t, id) => t + (S.songs.get(id)?.duration || 0), 0);
  return `${plural(ids.length, 'song')}, ${fmtLong(total)}`;
}
function playButtons(ctx) {
  return `<button class="btn primary" data-play-table>${icon('play')}Play</button><button class="btn" data-shuffle-table>${icon('shuffle')}Shuffle</button>`;
}
function filterBox(view) {
  return `<label class="search-box" style="margin:0;width:220px">${icon('search')}<input id="filter-${view}" data-filter="${view}" type="search" placeholder="Filter" value="${esc(S.filters[view] || '')}"></label>`;
}

/* ------------------------------------------------------------------ song table */

const COLS = {
  num: { label: '#', cls: 'c-num' },
  title: { label: 'Title', cls: 'c-title', sort: 'title' },
  artist: { label: 'Artist', cls: 'c-artist', sort: 'artist' },
  album: { label: 'Album', cls: 'c-album', sort: 'album' },
  genre: { label: 'Genre', cls: 'c-genre', sort: 'genre' },
  year: { label: 'Year', cls: 'c-year', sort: 'year' },
  time: { label: icon('clock'), cls: 'c-time', sort: 'time' },
  plays: { label: 'Plays', cls: 'c-plays', sort: 'plays' },
  love: { label: '', cls: 'c-love' },
  more: { label: '', cls: 'c-more' },
};
const WIDTHS = { title: '32%', artist: '19%', album: '21%', genre: '11%' };

/**
 * ids: songs in display order (already sorted for unsortable tables)
 * opts.sortView: view name whose sort applies (makes headers clickable)
 * opts.ctx: {playlist} for playlist-specific actions
 */
function songTable(ids, { sortView = null, cols = null, numbered = 'index', ctx = null, art = true } = {}) {
  cols = cols || ['num', 'title', 'artist', 'album', 'genre', 'year', 'time', 'plays', 'love', 'more'];
  const sort = sortView ? sortFor(sortView) : null;
  if (sort) ids = sortIds(ids, sort);
  S.tableIds = ids;
  S.tableCtx = ctx;
  if (!ids.length) return `<div class="empty">${icon('note')}<h3>No songs</h3><div>Nothing matches here yet.</div></div>`;
  const head = cols.map((c) => {
    const col = COLS[c];
    const sorted = sort && col.sort === sort.key;
    const w = WIDTHS[c] ? ` style="width:${WIDTHS[c]}"` : '';
    return `<th class="${col.cls} ${sorted ? 'sorted' : ''}" ${sortView && col.sort ? `data-sort="${col.sort}"` : ''}${w}>${col.label}${sorted ? `<span class="dir">${sort.dir > 0 ? '▲' : '▼'}</span>` : ''}</th>`;
  }).join('');
  const rows = ids.map((id, i) => {
    const s = S.songs.get(id);
    if (!s) return '';
    const cells = cols.map((c) => {
      switch (c) {
        case 'num': return `<td class="c-num">${numbered === 'track' ? (s.track || '') : i + 1}</td>`;
        case 'title': return `<td class="c-title"><div class="title-cell">${art ? songArt(s, 80) : ''}<span class="t">${esc(s.title)}</span></div></td>`;
        case 'artist': return `<td>${esc(s.artist)}</td>`;
        case 'album': return `<td>${esc(s.album)}</td>`;
        case 'genre': return `<td class="c-genre">${esc(s.genre)}</td>`;
        case 'year': return `<td class="c-year">${esc(s.year)}</td>`;
        case 'time': return `<td class="c-time">${fmtTime(s.duration)}</td>`;
        case 'plays': return `<td class="c-plays">${plays(id) || ''}</td>`;
        case 'love': {
          const on = S.loved.has(id);
          return `<td class="c-love"><button class="icon-btn small row-love ${on ? 'on' : ''}" data-love="${id}" title="${on ? 'Unlove' : 'Love'}">${icon(on ? 'heart-fill' : 'heart')}</button></td>`;
        }
        case 'more': return `<td class="c-more"><button class="icon-btn small row-more" data-row-menu title="More">${icon('more')}</button></td>`;
        default: return '<td></td>';
      }
    }).join('');
    return `<tr class="row ${S.sel.has(id) ? 'sel' : ''}" data-id="${id}" data-i="${i}" draggable="true">${cells}</tr>`;
  }).join('');
  return `<div class="table-wrap"><table class="songs"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function selectedOr(id) { return S.sel.has(id) ? S.tableIds.filter((x) => S.sel.has(x)) : [id]; }
function refreshSelection() { $$('tr.row').forEach((r) => r.classList.toggle('sel', S.sel.has(r.dataset.id))); }

const main = $('#main');
main.addEventListener('click', (e) => {
  const th = e.target.closest('th[data-sort]');
  if (th) {
    const view = S.view.name === 'genres' ? 'genre' : S.view.name;
    const cur = sortFor(view);
    S.sorts[view] = { key: th.dataset.sort, dir: cur.key === th.dataset.sort ? -cur.dir : (['added', 'plays', 'year', 'time'].includes(th.dataset.sort) ? -1 : 1) };
    save('sorts', S.sorts);
    rerender();
    return;
  }
  const love = e.target.closest('[data-love]');
  if (love) { e.stopPropagation(); const id = love.dataset.love; setLoved(selectedOr(id), !S.loved.has(id)); return; }
  const more = e.target.closest('[data-row-menu]');
  if (more) {
    const row = more.closest('tr.row');
    if (!S.sel.has(row.dataset.id)) { S.sel = new Set([row.dataset.id]); refreshSelection(); }
    const r = more.getBoundingClientRect();
    songMenu(r.left, r.bottom, selectedOr(row.dataset.id));
    return;
  }
  const row = e.target.closest('tr.row');
  if (row) {
    const id = row.dataset.id;
    if (e.metaKey || e.ctrlKey) { S.sel.has(id) ? S.sel.delete(id) : S.sel.add(id); S.lastSel = id; }
    else if (e.shiftKey && S.lastSel) {
      const a = S.tableIds.indexOf(S.lastSel), b = S.tableIds.indexOf(id);
      const [lo, hi] = a < b ? [a, b] : [b, a];
      S.sel = new Set(S.tableIds.slice(lo, hi + 1));
    } else { S.sel = new Set([id]); S.lastSel = id; }
    refreshSelection();
    return;
  }
  handleAction(e);
});
main.addEventListener('dblclick', (e) => {
  const row = e.target.closest('tr.row');
  if (row && !e.target.closest('button')) playIds(S.tableIds, +row.dataset.i, { shuffle: false });
});
main.addEventListener('contextmenu', (e) => {
  const row = e.target.closest('tr.row');
  if (!row) return;
  e.preventDefault();
  if (!S.sel.has(row.dataset.id)) { S.sel = new Set([row.dataset.id]); S.lastSel = row.dataset.id; refreshSelection(); }
  songMenu(e.clientX, e.clientY, selectedOr(row.dataset.id));
});
main.addEventListener('input', (e) => {
  const f = e.target.closest('[data-filter]');
  if (f) { S.filters[f.dataset.filter] = f.value; rerender(); }
});

// Dragging rows: onto sidebar playlists, or to reorder inside a playlist.
let dragIds = null;
main.addEventListener('dragstart', (e) => {
  const row = e.target.closest('tr.row');
  if (!row) return;
  if (!S.sel.has(row.dataset.id)) { S.sel = new Set([row.dataset.id]); refreshSelection(); }
  dragIds = selectedOr(row.dataset.id);
  e.dataTransfer.setData('text/x-song-ids', JSON.stringify(dragIds));
  e.dataTransfer.effectAllowed = 'copyMove';
});
main.addEventListener('dragend', () => { dragIds = null; $$('.drag-over').forEach((r) => r.classList.remove('drag-over')); });
main.addEventListener('dragover', (e) => {
  if (!S.tableCtx?.playlist || !dragIds) return;
  const row = e.target.closest('tr.row');
  if (!row) return;
  e.preventDefault();
  $$('.drag-over').forEach((r) => r.classList.remove('drag-over'));
  row.classList.add('drag-over');
});
main.addEventListener('drop', async (e) => {
  const pl = S.tableCtx?.playlist;
  const row = e.target.closest('tr.row');
  if (!pl || !row || !dragIds) return;
  e.preventDefault();
  const moving = new Set(dragIds);
  const rest = pl.songs.filter((id) => !moving.has(id));
  let at = rest.indexOf(row.dataset.id);
  if (at < 0) at = rest.length;
  const songs = [...rest.slice(0, at), ...dragIds, ...rest.slice(at)];
  await savePlaylist(pl.id, { songs });
});

/* ------------------------------------------------------------------ song menu & actions */

function songMenu(x, y, ids) {
  const one = ids.length === 1 ? S.songs.get(ids[0]) : null;
  const allLoved = ids.every((id) => S.loved.has(id));
  const pl = S.tableCtx?.playlist;
  showMenu(x, y, [
    { label: ids.length > 1 ? `Play ${ids.length} Songs` : 'Play', icon: 'play', act: () => playIds(ids, 0, { shuffle: false }) },
    { label: 'Play Next', icon: 'next', act: () => playNext(ids) },
    { label: 'Add to Up Next', icon: 'queue', act: () => addToQueue(ids) },
    { label: 'Add to Playlist', icon: 'list', sub: () => [
      { label: 'New Playlist…', icon: 'plus', act: () => newPlaylist(ids) },
      S.playlists.length ? { sep: true } : null,
      ...S.playlists.map((p) => ({ label: p.name, icon: 'list', act: () => addToPlaylist(p.id, ids) })),
    ] },
    { sep: true },
    { label: allLoved ? 'Unlove' : 'Love', icon: allLoved ? 'heart' : 'heart-fill', act: () => setLoved(ids, !allLoved) },
    { label: ids.length > 1 ? `Get Info (${ids.length} songs)` : 'Get Info', icon: 'info', act: () => (one ? songInfo(one.id) : multiInfo(ids)) },
    { label: 'Look Up Missing Metadata', icon: 'wand', act: () => fixSongs(ids) },
    one ? { label: 'Show in Finder', icon: 'folder', act: () => api(`/api/songs/${one.id}/reveal`, { method: 'POST' }) } : null,
    one && one.album ? { label: 'Go to Album', icon: 'album', act: () => go('album', albumKey(one)) } : null,
    one ? { label: 'Go to Artist', icon: 'mic', act: () => go('artists', one.album_artist || one.artist) } : null,
    { sep: true },
    pl ? { label: 'Remove from Playlist', icon: 'x', act: () => savePlaylist(pl.id, { remove: ids }) } : null,
    { label: ids.length > 1 ? `Delete ${ids.length} Songs…` : 'Delete from Library…', icon: 'trash', danger: true, act: () => deleteSongs(ids) },
  ]);
}

async function setLoved(ids, loved) {
  for (const id of ids) {
    try { S.loved = new Set((await api(`/api/love/${id}`, { method: 'POST', body: { loved } })).loved); } catch (e) { toast(esc(e.message), 'bad'); }
  }
  updateNowPlaying();
  if (S.view.name === 'loved') rerender();
  else $$('[data-love]').forEach((b) => {
    const on = S.loved.has(b.dataset.love);
    b.classList.toggle('on', on); b.innerHTML = icon(on ? 'heart-fill' : 'heart');
  });
}

async function deleteSongs(ids) {
  const what = ids.length === 1 ? `“${esc(S.songs.get(ids[0])?.title)}”` : plural(ids.length, 'song');
  if (!await confirmDialog(`Move ${what} to the Trash? The file${ids.length > 1 ? 's' : ''} can be restored from the Trash in Finder.`, 'Move to Trash', true)) return;
  let ok = 0;
  for (const id of ids) {
    try { await api(`/api/songs/${id}`, { method: 'DELETE' }); ok += 1; S.songs.delete(id); P.queue = P.queue.filter((q, i) => q !== id || i === P.index); } catch (e) { toast(esc(e.message), 'bad'); }
  }
  S.list = [...S.songs.values()];
  S.sel.clear();
  toast(`Moved ${plural(ok, 'song')} to the Trash`, 'ok');
  await refreshState();
  rerender();
}

async function fixSongs(ids) {
  if (ids.length === 1) await api(`/api/songs/${ids[0]}/fix`, { method: 'POST' });
  else await api('/api/fix-missing', { method: 'POST', body: { ids } });
  toast(`Looking up artwork, lyrics and details for ${plural(ids.length, 'song')} — see Downloads`, '', 'wand');
  pollNow();
}

/* ------------------------------------------------------------------ playlists */

async function refreshState() {
  const b = await api('/api/bootstrap');
  S.playlists = b.state.playlists; S.plays = b.state.plays; S.loved = new Set(b.state.loved); S.settings = b.state.settings;
}
async function newPlaylist(ids) {
  const name = await promptDialog('New Playlist', 'Name', ids.length === 1 ? '' : '', 'Create');
  if (name === null) return;
  const { playlist } = await api('/api/playlists', { method: 'POST', body: { name, songs: ids } });
  S.playlists.push(playlist);
  go('playlist', playlist.id);
}
async function savePlaylist(pid, body) {
  const { playlist } = await api(`/api/playlists/${pid}`, { method: 'PUT', body });
  S.playlists = S.playlists.map((p) => (p.id === pid ? playlist : p));
  if (S.view.name === 'playlist' && S.view.param === pid) rerender(); else renderNav();
  return playlist;
}
async function addToPlaylist(pid, ids) {
  const pl = await savePlaylist(pid, { add: ids });
  toast(`Added ${plural(ids.length, 'song')} to ${esc(pl.name)}`, 'ok');
}
async function renamePlaylist(pl) {
  const name = await promptDialog('Rename Playlist', 'Name', pl.name, 'Rename');
  if (name !== null && name.trim()) await savePlaylist(pl.id, { name });
}
async function deletePlaylist(pl) {
  if (!await confirmDialog(`Delete the playlist “${esc(pl.name)}”? The songs stay in your library.`, 'Delete', true)) return;
  await api(`/api/playlists/${pl.id}`, { method: 'DELETE' });
  S.playlists = S.playlists.filter((p) => p.id !== pl.id);
  if (S.view.name === 'playlist' && S.view.param === pl.id) go('songs'); else renderNav();
}

/* ------------------------------------------------------------------ get info */

async function songInfo(id) {
  const s = S.songs.get(id);
  if (!s) return;
  const organize = S.settings.organize_on_edit !== false;
  const f = (key, label, type = 'text') => `<label class="k">${label}</label><input class="field" data-k="${key}" type="${type}" value="${esc(key === 'track' || key === 'disc' ? (s[key] || '') : s[key])}">`;
  const m = modal({
    title: 'Get Info',
    body: `<div class="info-top">${songArt(s, 300)}<div><div class="it">${esc(s.title)}</div><div class="muted">${esc(s.artist)}${s.album ? ' — ' + esc(s.album) : ''}</div>
        <div class="faint" style="margin-top:4px">${fmtTime(s.duration)} · ${s.ext.slice(1).toUpperCase()} ${s.bitrate ? s.bitrate + ' kbps' : ''} · ${fmtSize(s.size)} · ${plural(plays(id), 'play')}</div></div></div>
      <div class="form">
        ${f('title', 'Title')}${f('artist', 'Artist')}${f('album', 'Album')}${f('album_artist', 'Album Artist')}
        ${f('genre', 'Genre')}${f('year', 'Year')}${f('track', 'Track #', 'number')}${f('disc', 'Disc #', 'number')}
        <label class="k">Lyrics</label><textarea class="field" id="info-lyrics" placeholder="Loading…"></textarea>
        <label class="k">File</label><div class="faint" style="user-select:text;-webkit-user-select:text;word-break:break-all">${esc(s.path)}</div>
        ${s.source_url ? `<label class="k">Source</label><div class="faint" style="word-break:break-all">${esc(s.source_url)}</div>` : ''}
        <label class="k"></label><label class="row-flex"><input type="checkbox" id="info-organize" ${organize ? 'checked' : ''}> Rename and move the file to Artist/Title</label>
      </div>`,
    left: [
      { label: 'Look Up Metadata', icon: 'wand', act: (close) => { close(); fixSongs([id]); } },
      { label: 'Show in Finder', icon: 'folder', act: () => api(`/api/songs/${id}/reveal`, { method: 'POST' }) },
    ],
    buttons: [
      { label: 'Cancel', act: (close) => close() },
      { label: 'Save', primary: true, act: async (close, root, btn) => {
        const changes = {};
        $$('[data-k]', root).forEach((inp) => {
          const k = inp.dataset.k;
          const old = k === 'track' || k === 'disc' ? String(s[k] || '') : String(s[k] || '');
          if (inp.value.trim() !== old) changes[k] = inp.value.trim();
        });
        const lyr = $('#info-lyrics', root);
        const body = { changes, organize: $('#info-organize', root).checked };
        if (lyr.dataset.loaded && lyr.value !== lyr.dataset.orig) body.lyrics = lyr.value;
        if (!Object.keys(changes).length && !body.lyrics && !body.organize) { close(); return; }
        btn.disabled = true;
        try {
          const res = await api(`/api/songs/${id}`, { method: 'PUT', body });
          replaceSong(res.old_id, res.song);
          S.lyricsCache.delete(res.old_id);
          close();
          toast('Saved', 'ok');
          rerender(); updateNowPlaying();
        } catch (e) { btn.disabled = false; toast(esc(e.message), 'bad'); }
      } },
    ],
  });
  try {
    const { lyrics } = await api(`/api/lyrics/${id}`);
    const ta = $('#info-lyrics', m.root);
    if (ta) { ta.value = lyrics || ''; ta.dataset.orig = lyrics || ''; ta.dataset.loaded = '1'; ta.placeholder = 'No lyrics'; }
  } catch { /* closed */ }
}

function replaceSong(oldId, song) {
  S.songs.delete(oldId);
  S.songs.set(song.id, song);
  S.list = [...S.songs.values()];
  P.queue = P.queue.map((q) => (q === oldId ? song.id : q));
  if (P.original) P.original = P.original.map((q) => (q === oldId ? song.id : q));
  S.playlists.forEach((pl) => { pl.songs = pl.songs.map((q) => (q === oldId ? song.id : q)); });
  if (S.loved.has(oldId)) { S.loved.delete(oldId); S.loved.add(song.id); }
  if (S.plays[oldId]) { S.plays[song.id] = S.plays[oldId]; delete S.plays[oldId]; }
  if (S.sel.has(oldId)) { S.sel.delete(oldId); S.sel.add(song.id); }
}

function multiInfo(ids) {
  const songs = ids.map((id) => S.songs.get(id)).filter(Boolean);
  const keys = [['artist', 'Artist'], ['album', 'Album'], ['album_artist', 'Album Artist'], ['genre', 'Genre'], ['year', 'Year']];
  const shared = (k) => { const v = songs[0][k] || ''; return songs.every((s) => (s[k] || '') === v) ? v : null; };
  modal({
    title: `Get Info — ${plural(songs.length, 'song')}`,
    body: `<div class="form">${keys.map(([k, l]) => {
      const v = shared(k);
      return `<label class="k">${l}</label><input class="field" data-k="${k}" value="${esc(v ?? '')}" placeholder="${v === null ? 'Mixed — leave empty to keep' : ''}" data-orig="${esc(v ?? '')}">`;
    }).join('')}
      <label class="k"></label><label class="row-flex"><input type="checkbox" id="multi-organize" ${S.settings.organize_on_edit !== false ? 'checked' : ''}> Rename and move files to Artist/Title</label></div>`,
    buttons: [
      { label: 'Cancel', act: (close) => close() },
      { label: 'Save', primary: true, act: async (close, root, btn) => {
        const changes = {};
        $$('[data-k]', root).forEach((inp) => { if (inp.value.trim() && inp.value.trim() !== inp.dataset.orig) changes[inp.dataset.k] = inp.value.trim(); });
        if (!Object.keys(changes).length) { close(); return; }
        btn.disabled = true;
        const organize = $('#multi-organize', root).checked;
        let ok = 0;
        for (const s of songs) {
          try { const res = await api(`/api/songs/${s.id}`, { method: 'PUT', body: { changes, organize } }); replaceSong(res.old_id, res.song); ok += 1; } catch (e) { toast(esc(e.message), 'bad'); }
        }
        close(); toast(`Updated ${plural(ok, 'song')}`, 'ok'); rerender(); updateNowPlaying();
      } },
    ],
  });
}

/* ===================================================================== library views */

VIEWS.recent = () => {
  const q = S.filters.recent || '';
  const ids = S.list.filter((s) => matchesFilter(s, q)).map((s) => s.id);
  const recentIds = sortIds(ids, { key: 'added', dir: -1 }).slice(0, 300);
  if (!S.list.length) return emptyLibrary();
  return `<div class="view">${viewHead('Recently Added', summary(recentIds), filterBox('recent') + playButtons())}${songTable(recentIds, { sortView: 'recent' })}</div>`;
};

VIEWS.songs = () => {
  if (!S.list.length) return emptyLibrary();
  const q = S.filters.songs || '';
  const ids = S.list.filter((s) => matchesFilter(s, q)).map((s) => s.id);
  return `<div class="view">${viewHead('Songs', summary(ids), filterBox('songs') + playButtons())}${songTable(ids, { sortView: 'songs' })}</div>`;
};

function emptyLibrary() {
  return `<div class="view"><div class="empty">${icon('note')}<h3>${S.rootExists ? 'Your library is empty' : 'Library folder not found'}</h3>
    <div>${S.rootExists ? `Songs you download are saved to <b>${esc(S.root)}</b> as Artist/Title.mp3.` : `<b>${esc(S.root)}</b> does not exist. Choose another folder in Settings.`}</div>
    <div class="actions" style="justify-content:center;margin-top:16px"><button class="btn primary" data-act="nav" data-view="search">${icon('search')}Find music</button>
    <button class="btn" data-act="nav" data-view="settings">${icon('gear')}Settings</button></div></div></div>`;
}

VIEWS.albums = () => {
  if (!S.list.length) return emptyLibrary();
  const mode = store('albumSort', 'artist');
  let list = albums();
  if (mode === 'title') list.sort((a, b) => collator.compare(a.name, b.name));
  else if (mode === 'recent') list.sort((a, b) => b.added - a.added);
  else list.sort((a, b) => collator.compare(a.artist, b.artist) || collator.compare(a.name, b.name));
  const seg = `<div class="seg">${[['artist', 'Artist'], ['title', 'Title'], ['recent', 'Recently Added']].map(([k, l]) => `<button class="${mode === k ? 'on' : ''}" data-act="album-sort" data-mode="${k}">${l}</button>`).join('')}</div>`;
  S.tableIds = list.flatMap((a) => a.songs.map((s) => s.id));
  return `<div class="view">${viewHead('Albums', plural(list.length, 'album'), seg)}
    <div class="grid">${list.map((a) => albumCard(a)).join('')}</div></div>`;
};

function albumCard(a) {
  return `<div class="card" data-act="open-album" data-key="${esc(a.key)}" data-label="${esc(a.name)}">
    <div style="position:relative">${a.art ? songArt(a.art, 400) : placeholder(a.name, 'album')}
      <div class="overlay"><span></span><button class="fab" data-act="play-album" data-key="${esc(a.key)}" title="Play">${icon('play')}</button></div></div>
    <div class="c-t">${esc(a.name)}</div><div class="c-s">${esc(a.artist)}${a.year ? ' · ' + esc(a.year) : ''}</div></div>`;
}

VIEWS.album = (key) => {
  const a = albums().find((x) => x.key === key);
  if (!a) return `<div class="view"><div class="empty">${icon('album')}<h3>Album not found</h3></div></div>`;
  const ids = a.songs.map((s) => s.id);
  const total = a.songs.reduce((t, s) => t + s.duration, 0);
  return `<div class="view">
    <button class="btn back" data-act="back">${icon('back')}Back</button>
    <div class="hero">${a.art ? songArt(a.art, 600) : placeholder(a.name, 'album')}
      <div><h1>${esc(a.name)}</h1><div class="h-artist" data-act="open-artist" data-name="${esc(a.artist)}">${esc(a.artist)}</div>
        <div class="h-meta">${[a.genre, a.year].filter(Boolean).map(esc).join(' · ')}${a.genre || a.year ? ' · ' : ''}${plural(ids.length, 'song')}, ${fmtLong(total)}</div>
        <div class="actions">${playButtons()}</div></div></div>
    ${songTable(ids, { cols: ['num', 'title', 'artist', 'time', 'plays', 'love', 'more'], numbered: 'track', art: false })}</div>`;
};

VIEWS.artists = (param) => {
  if (!S.list.length) return emptyLibrary();
  const list = artists();
  const sel = list.find((a) => a.name.toLowerCase() === String(param || '').toLowerCase()) || list[0];
  const left = list.map((a) => `<div class="list-item ${a === sel ? 'active' : ''}" data-act="open-artist" data-name="${esc(a.name)}">
      ${a.art ? songArt(a.art, 80).replace('class="art', 'style="border-radius:50%" class="art') : placeholder(a.name, 'mic', true)}
      <div class="li-t">${esc(a.name)}</div><div class="li-c">${a.songs.length}</div></div>`).join('');
  const theirAlbums = albums().filter((al) => al.songs.some((s) => (s.album_artist || s.artist).toLowerCase() === sel.name.toLowerCase()));
  const ids = sel.songs.map((s) => s.id);
  const right = `<div class="view">${viewHead(esc(sel.name), `${plural(theirAlbums.length, 'album')}, ${summary(ids)}`, playButtons())}
    ${theirAlbums.length > 1 || (theirAlbums[0] && theirAlbums[0].name !== 'Unknown Album') ? `<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr));margin-bottom:24px">${theirAlbums.map(albumCard).join('')}</div>` : ''}
    <h2 class="sec">Songs</h2>${songTable(ids, { sortView: 'artistsongs', cols: ['num', 'title', 'album', 'year', 'time', 'plays', 'love', 'more'] })}</div>`;
  return `<div class="split" style="height:100%"><div class="list">${left}</div><div class="detail">${right}</div></div>`;
};

VIEWS.genres = (param) => {
  if (!S.list.length) return emptyLibrary();
  const counts = new Map();
  for (const s of S.list) { const g = s.genre || 'Unknown'; counts.set(g, (counts.get(g) || 0) + 1); }
  const genres = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  if (param) {
    const ids = S.list.filter((s) => (s.genre || 'Unknown') === param).map((s) => s.id);
    return `<div class="view"><button class="btn back" data-act="nav" data-view="genres">${icon('back')}All Genres</button>
      ${viewHead(esc(param), summary(ids), playButtons())}${songTable(ids, { sortView: 'genre' })}</div>`;
  }
  return `<div class="view">${viewHead('Genres', plural(genres.length, 'genre'))}
    <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">${genres.map(([g, n]) => {
      const h = hue(g);
      return `<div class="card" data-act="nav" data-view="genres" data-param="${esc(g)}">
        <div class="art" style="aspect-ratio:16/9;--c1:hsl(${h} 55% 45%);--c2:hsl(${(h + 50) % 360} 60% 25%);align-items:flex-end;justify-content:flex-start;padding:12px;color:#fff;font-weight:750;font-size:17px">${esc(g)}</div>
        <div class="c-s" style="margin-top:6px">${plural(n, 'song')}</div></div>`;
    }).join('')}</div></div>`;
};

VIEWS.loved = () => {
  const ids = S.list.filter((s) => S.loved.has(s.id)).map((s) => s.id);
  if (!ids.length) return `<div class="view">${viewHead('Loved')}<div class="empty">${icon('heart')}<h3>No loved songs yet</h3><div>Click the heart next to a song to love it.</div></div></div>`;
  return `<div class="view">${viewHead('Loved', summary(ids), playButtons())}${songTable(ids, { sortView: 'loved' })}</div>`;
};

VIEWS.mostplayed = () => {
  const ids = S.list.filter((s) => plays(s.id) > 0).sort((a, b) => plays(b.id) - plays(a.id)).slice(0, 100).map((s) => s.id);
  if (!ids.length) return `<div class="view">${viewHead('Most Played')}<div class="empty">${icon('headphones')}<h3>Nothing played yet</h3><div>Songs you listen to show up here.</div></div></div>`;
  return `<div class="view">${viewHead('Most Played', 'Your top ' + plural(ids.length, 'song'), playButtons())}${songTable(ids)}</div>`;
};

VIEWS.playlist = (pid) => {
  const pl = S.playlists.find((p) => p.id === pid);
  if (!pl) return `<div class="view"><div class="empty">${icon('list')}<h3>Playlist not found</h3></div></div>`;
  const ids = pl.songs.filter((id) => S.songs.has(id));
  const acts = `${ids.length ? playButtons() : ''}<button class="icon-btn" data-act="pl-menu" data-id="${pl.id}" title="More">${icon('more')}</button>`;
  const body = ids.length ? songTable(ids, { ctx: { playlist: pl } })
    : `<div class="empty">${icon('list')}<h3>This playlist is empty</h3><div>Drag songs onto “${esc(pl.name)}” in the sidebar, or right-click a song → Add to Playlist.</div></div>`;
  return `<div class="view">${viewHead(esc(pl.name), ids.length ? summary(ids) + ' · drag to reorder' : '', acts)}${body}</div>`;
};

VIEWS.smart = (kind) => {
  const defs = {
    noart: ['Missing Artwork', (s) => !s.has_art],
    nolyrics: ['Missing Lyrics', (s) => !s.has_lyrics],
    nodetails: ['Missing Album, Genre or Year', (s) => !s.album || !s.genre || !s.year],
    lowbit: ['Low Quality (under 128 kbps)', (s) => s.bitrate && s.bitrate < 128],
    dupes: ['Possible Duplicates', null],
  };
  const [title, pred] = defs[kind] || defs.noart;
  let ids;
  if (kind === 'dupes') ids = duplicates().flat().map((s) => s.id);
  else ids = S.list.filter(pred).map((s) => s.id);
  const fix = ['noart', 'nolyrics', 'nodetails'].includes(kind) && ids.length
    ? `<button class="btn primary" data-act="fix-list">${icon('wand')}Look Up All</button>` : '';
  return `<div class="view"><button class="btn back" data-act="nav" data-view="organizer">${icon('back')}Organizer</button>
    ${viewHead(title, summary(ids), fix + (ids.length ? playButtons() : ''))}
    ${songTable(ids, kind === 'dupes' ? {} : { sortView: 'smart-' + kind })}</div>`;
};

function duplicates() {
  const groups = new Map();
  for (const s of S.list) {
    const k = songKey(s.artist, s.title);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(s);
  }
  return [...groups.values()].filter((g) => g.length > 1);
}

/* ===================================================================== search (store) */

function parseTerm(q) {
  let m = q.match(/^(.+?)\s+[-–—]\s+(.+)$/);
  if (m) return { artist: m[1].trim(), title: m[2].trim() };
  m = q.match(/^(.+?)\s+by\s+(.+)$/i);
  if (m) return { artist: m[2].trim(), title: m[1].trim() };
  return { artist: '', title: q.trim() };
}

async function runSearch(q) {
  q = q.trim();
  S.searchQ = q;
  S.search = { songs: null, videos: null, songsErr: '', videosErr: '', q };
  if (S.view.name !== 'search') go('search'); else rerender();
  if (!q) return;
  const mine = S.search;
  api(`/api/search/songs?q=${encodeURIComponent(q)}`)
    .then((r) => { mine.songs = r.results; })
    .catch((e) => { mine.songs = []; mine.songsErr = e.message; })
    .finally(() => { if (S.search === mine && S.view.name === 'search') rerender(); });
  api(`/api/search/videos?q=${encodeURIComponent(q)}`)
    .then((r) => { mine.videos = r.results; })
    .catch((e) => { mine.videos = []; mine.videosErr = e.message; })
    .finally(() => { if (S.search === mine && S.view.name === 'search') rerender(); });
}

const searchInput = $('#search');
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { runSearch(searchInput.value); searchInput.blur(); }
  if (e.key === 'Escape') { searchInput.value = ''; searchInput.blur(); }
});

function jobFor(artist, title, kind = null) {
  const a = norm(artist), t = norm(title);
  return S.jobs.find((j) => (!kind || j.kind === kind) && j.kind !== 'fix' && norm(j.title) === t && (!a || !norm(j.artist) || norm(j.artist) === a));
}
function dlButton(item, act, i) {
  const job = jobFor(item.artist, item.title);
  const owned = item.owned || (job && ['done', 'exists'].includes(job.status));
  if (owned) return `<button class="round ok" title="In your library">${icon('check')}</button>`;
  if (job && ['queued', 'running'].includes(job.status)) {
    const pct = job.progress != null ? Math.round(job.progress * 100) + '%' : '';
    return `<button class="round busy" title="${esc(job.stage)} ${pct}" data-act="nav" data-view="downloads"><span class="spinner"></span></button>`;
  }
  return `<button class="round" data-act="${act}" data-i="${i}" title="${job && job.status === 'failed' ? 'Failed — try again' : 'Download to library'}">${icon(job && job.status === 'failed' ? 'refresh' : 'download')}</button>`;
}

VIEWS.search = () => {
  const q = S.searchQ;
  if (!q) {
    return `<div class="view">${viewHead('Search', 'Find any song or video, preview it, and download it straight into your library.')}
      <div class="empty">${icon('search')}<h3>Search for music</h3>
      <div>Type in the search box at the top left and press Return.<br>Try an artist, a song, or “Artist - Title”.</div></div></div>`;
  }
  const r = S.search;
  const lib = S.list.filter((s) => matchesFilter(s, q)).map((s) => s.id);
  const term = parseTerm(q);
  let html = `<div class="view">${viewHead(`Results for “${esc(q)}”`)}`;
  const quickJob = jobFor(term.artist, term.title);
  html += `<div class="quick-dl">${icon('download')}<div class="q"><b>Download “${esc(term.artist ? term.artist + ' - ' + term.title : term.title)}”</b>
      <div class="faint">Finds the best studio version on YouTube Music, YouTube, SoundCloud or Audius and adds artwork, lyrics and tags.</div></div>
      ${quickJob && ['queued', 'running'].includes(quickJob.status) ? `<span class="spinner"></span>` : `<button class="btn primary" data-act="quick-dl">${icon('download')}Download</button>`}</div>`;
  if (lib.length) {
    html += `<h2 class="sec">In Your Library <span class="count">${lib.length}</span></h2>${songTable(lib.slice(0, 12), { cols: ['num', 'title', 'artist', 'album', 'time', 'love', 'more'] })}`;
    if (lib.length > 12) html += `<div style="margin-top:8px"><button class="btn" data-act="lib-all">Show all ${lib.length} in Songs</button></div>`;
  } else S.tableIds = [];

  html += `<h2 class="sec">Songs ${r.songs ? `<span class="count">${r.songs.length}</span>` : ''}</h2>`;
  if (!r.songs) html += `<div class="loading-row"><span class="spinner"></span>Searching the catalog…</div>`;
  else if (r.songsErr) html += `<div class="faint">Catalog search failed: ${esc(r.songsErr)}</div>`;
  else if (!r.songs.length) html += `<div class="faint">No catalog matches.</div>`;
  else {
    html += `<div class="results">${r.songs.map((s, i) => `
      <div class="result" data-label="${esc(s.album || s.title)}">
        <div style="position:relative;cursor:pointer" data-act="preview-song" data-i="${i}">${remoteArt(s.artwork, s.title)}</div>
        <div class="r-text"><div class="r-t">${esc(s.title)}${s.explicit ? '<span class="explicit">E</span>' : ''}</div>
          <div class="r-s">${esc(s.artist)}${s.album ? ' · ' + esc(s.album) : ''}${s.year ? ' · ' + esc(s.year) : ''}</div></div>
        <span class="r-time">${s.duration ? fmtTime(s.duration) : ''}</span>
        ${s.preview ? `<button class="round" data-act="preview-song" data-i="${i}" data-preview-key="song:${i}:${esc(r.q)}" title="Preview 30 seconds">${icon('play')}</button>` : ''}
        ${dlButton(s, 'dl-song', i)}
      </div>`).join('')}</div>`;
  }

  html += `<h2 class="sec">Videos ${r.videos ? `<span class="count">${r.videos.length}</span>` : ''}</h2>`;
  if (!r.videos) html += `<div class="loading-row"><span class="spinner"></span>Searching YouTube…</div>`;
  else if (r.videosErr) html += `<div class="faint">YouTube search failed: ${esc(r.videosErr)}<br>If YouTube keeps refusing, set “Use cookies from browser” in Settings.</div>`;
  else if (!r.videos.length) html += `<div class="faint">No videos found.</div>`;
  else {
    html += `<div class="grid videos">${r.videos.map((v, i) => {
      const owned = v.owned || ['done', 'exists'].includes(jobFor(v.artist, v.title)?.status);
      return `<div class="card" data-label="${esc(v.title)}">
        <div style="position:relative" data-act="watch" data-i="${i}">${remoteArt(v.thumbnail, v.title)}
          ${v.duration ? `<span class="dur-badge">${fmtTime(v.duration)}</span>` : ''}
          <div class="overlay"><button class="fab" data-act="watch" data-i="${i}" title="Watch video">${icon('video')}</button>
            <span style="display:flex;gap:8px"><button class="fab ghost" data-act="listen-video" data-i="${i}" data-preview-key="yt:${v.id}" data-icon="headphones" title="Listen (audio only)">${icon('headphones')}</button>
            ${owned ? `<button class="fab ok" title="In your library">${icon('check')}</button>` : `<button class="fab ghost" data-act="dl-video" data-i="${i}" title="Download this version">${icon('download')}</button>`}</span></div></div>
        <div class="c-t" title="${esc(v.video_title)}">${esc(v.video_title)}</div>
        <div class="c-s">${owned ? `<span class="owned-tag">${icon('check')}In library</span> · ` : ''}${esc(v.artist || v.channel)}${v.views ? ' · ' + Number(v.views).toLocaleString() + ' views' : ''}</div></div>`;
    }).join('')}</div>`;
  }
  return html + '</div>';
};

async function previewYouTubeAudio(v, btn) {
  const key = `yt:${v.id}`;
  if (P.transient && P.transient.key === key) { playPreview({ key }); return; }
  if (btn) btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>';
  try {
    const st = await api(`/api/youtube/${v.id}`);
    playPreview({ key, src: withToken(`/api/proxy/${st.token}`), title: v.title || st.title, artist: v.artist || st.channel, art: v.thumbnail, origin: 'YouTube', label: 'YouTube' });
  } catch (e) {
    toast(`Could not stream that video: ${esc(e.message)}`, 'bad');
    updateControls();
  }
}

function watchVideo(v) {
  const wasPlaying = !audio.paused;
  audio.pause();
  const m = modal({
    title: v.video_title || v.title, wide: true,
    body: `<div class="video-box" id="vbox"><div class="loading-row"><span class="spinner"></span>Loading video…</div></div>
      <div class="video-meta"><div class="vt"><div>${esc(v.title)}</div><div class="faint">${esc(v.artist || v.channel)}${v.duration ? ' · ' + fmtTime(v.duration) : ''}</div></div>
        <button class="btn" id="v-embed">Use YouTube player</button></div>`,
    left: [
      { label: 'Open on YouTube', icon: 'external', act: () => openExternal(v.url) },
    ],
    buttons: [
      { label: 'Listen in Player', icon: 'headphones', act: (close) => { close(); previewYouTubeAudio(v); } },
      { label: 'Download…', icon: 'download', primary: true, act: (close) => { close(); downloadVideoDialog(v); } },
    ],
    onClose: () => { const vid = $('#vbox video'); if (vid) { vid.pause(); vid.removeAttribute('src'); vid.load(); } if (wasPlaying && !P.transient) audio.play().catch(() => {}); },
  });
  const box = $('#vbox', m.root);
  const embed = () => {
    box.innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(v.id)}?autoplay=1&rel=0" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
    $('#v-embed', m.root).hidden = true;
  };
  $('#v-embed', m.root).onclick = embed;
  const probe = document.createElement('video');
  if (!probe.canPlayType('application/vnd.apple.mpegurl')) { embed(); return; }
  api(`/api/youtube/${v.id}?kind=video`).then((st) => {
    if (!box.isConnected) return;
    box.innerHTML = `<video controls autoplay playsinline src="${esc(withToken(`/api/hls/${st.hls_token}.m3u8`))}" poster="${esc(v.thumbnail)}"></video>`;
    const vid = $('video', box);
    vid.volume = audio.volume;
    vid.addEventListener('error', embed, { once: true });
  }).catch(() => { if (box.isConnected) embed(); });
}

function openExternal(url) {
  if (S.desktop) api('/api/open-url', { method: 'POST', body: { url } }).catch((e) => toast(esc(e.message), 'bad'));
  else window.open(url, '_blank', 'noopener');
}

function downloadVideoDialog(v) {
  modal({
    title: 'Download This Video’s Audio',
    body: `<div class="muted" style="margin-bottom:14px">Saved as <b>Artist/Title.mp3</b>. Album, artwork, genre and lyrics are filled in from the catalog when the song is found there.</div>
      <div class="form"><label class="k">Artist</label><input class="field" id="dv-artist" value="${esc(v.artist)}">
      <label class="k">Title</label><input class="field" id="dv-title" value="${esc(v.title)}">
      <label class="k">Album</label><input class="field" id="dv-album" placeholder="Optional"></div>
      <div class="faint" style="margin-top:12px;font-size:12px">Source: ${esc(v.video_title)}</div>`,
    buttons: [
      { label: 'Cancel', act: (close) => close() },
      { label: 'Download', primary: true, icon: 'download', act: async (close, root) => {
        const artist = $('#dv-artist', root).value.trim(), title = $('#dv-title', root).value.trim();
        if (!title) { toast('A title is required', 'bad'); return; }
        close();
        await queueDownload({ kind: 'video', artist, title, album: $('#dv-album', root).value.trim(), video_url: v.url, video_title: v.video_title, duration: v.duration, artwork: v.thumbnail });
      } },
    ],
  });
}

async function queueDownload(body) {
  try {
    const { job } = await api('/api/downloads', { method: 'POST', body });
    S.jobs = [job, ...S.jobs.filter((j) => j.id !== job.id)];
    S.active = S.jobs.filter((j) => ['queued', 'running'].includes(j.status)).length;
    toast(`Downloading ${esc(job.artist ? job.artist + ' – ' : '')}${esc(job.title)}`, '', 'download');
    renderNav();
    if (['search', 'foryou', 'downloads'].includes(S.view.name)) rerender();
    pollNow();
  } catch (e) { toast(esc(e.message), 'bad'); }
}

/* ===================================================================== for you */

VIEWS.foryou = () => {
  const fy = S.foryou;
  if (!fy || fy.status === 'idle' || (fy.status === 'running' && !fy.items.length)) {
    if (!fy) loadForYou();
    return `<div class="view">${viewHead('For You', 'Songs picked from the artists in your library')}
      <div class="loading-row"><span class="spinner"></span>${esc(fy?.message || 'Reading your library')}…</div></div>`;
  }
  if (fy.status === 'error' || !fy.items.length) {
    return `<div class="view">${viewHead('For You', '', `<button class="btn" data-act="fy-refresh">${icon('refresh')}Try Again</button>`)}
      <div class="empty">${icon('spark')}<h3>No suggestions right now</h3><div>${esc(fy.message || 'Check your internet connection.')}</div></div></div>`;
  }
  const todo = fy.items.filter((s) => !s.owned && !jobFor(s.artist, s.title));
  const acts = `${fy.status === 'running' ? '<span class="spinner"></span>' : ''}
    <button class="btn" data-act="fy-refresh" ${fy.status === 'running' ? 'disabled' : ''}>${icon('refresh')}New Picks</button>
    ${todo.length ? `<button class="btn primary" data-act="fy-dlall">${icon('download')}Download All (${todo.length})</button>` : ''}`;
  return `<div class="view">${viewHead('For You', `${plural(fy.items.length, 'song')} you don’t have yet, based on your library`, acts)}
    <div class="grid">${fy.items.map((s, i) => {
      const art = S.dzArt.get(s.deezer_id);
      const job = jobFor(s.artist, s.title);
      const owned = s.owned || (job && ['done', 'exists'].includes(job.status));
      const busy = job && ['queued', 'running'].includes(job.status);
      return `<div class="card" data-label="${esc(s.title)}" data-dz="${s.deezer_id}">
        <div style="position:relative" data-act="fy-preview" data-i="${i}">${art ? remoteArt(art, s.title) : placeholder(s.title, 'note')}
          <div class="overlay"><button class="fab" data-act="fy-preview" data-i="${i}" data-preview-key="dz:${s.deezer_id}" title="Preview">${icon('play')}</button>
          <span style="display:flex;gap:8px"><button class="fab ghost" data-act="fy-dismiss" data-i="${i}" title="Not for me">${icon('x')}</button>
          ${owned ? `<button class="fab ok" title="In your library">${icon('check')}</button>` : busy ? `<button class="fab ghost" data-act="nav" data-view="downloads"><span class="spinner" style="width:15px;height:15px"></span></button>` : `<button class="fab ghost" data-act="fy-dl" data-i="${i}" title="Download">${icon('download')}</button>`}</span></div></div>
        <div class="c-t">${esc(s.title)}${s.explicit ? '<span class="explicit">E</span>' : ''}</div>
        <div class="c-s">${esc(s.artist)}${s.length ? ' · ' + s.length : ''}</div>
        <div class="reason" title="${esc(s.reason)}">${esc(s.reason)}</div></div>`;
    }).join('')}</div></div>`;
};

async function loadForYou(refresh = false) {
  try {
    S.foryou = await api(`/api/foryou${refresh ? '?refresh=1' : ''}`);
    if (refresh) S.foryou.status = 'running';
  } catch (e) { S.foryou = { status: 'error', message: e.message, items: [] }; }
  S.foryouStatus = S.foryou.status;
  if (S.view.name === 'foryou') { rerender(); fetchDeezerArt(); }
}

let dzBusy = false;
async function fetchDeezerArt() {
  if (dzBusy || !S.foryou) return;
  dzBusy = true;
  const missing = S.foryou.items.filter((s) => s.deezer_id && !S.dzArt.has(s.deezer_id));
  const worker = async () => {
    while (missing.length) {
      const s = missing.shift();
      try {
        const d = await api(`/api/deezer/${s.deezer_id}`);
        S.dzArt.set(s.deezer_id, d.artwork || '');
        if (d.artwork) {
          $$(`[data-dz="${s.deezer_id}"] .art`).forEach((el) => { el.outerHTML = remoteArt(d.artwork, s.title); });
        }
      } catch { S.dzArt.set(s.deezer_id, ''); }
    }
  };
  await Promise.all([worker(), worker(), worker()]);
  dzBusy = false;
}

async function previewSuggestion(s) {
  const key = `dz:${s.deezer_id}`;
  if (P.transient && P.transient.key === key) { playPreview({ key }); return; }
  try {
    const d = await api(`/api/deezer/${s.deezer_id}`);
    if (!d.preview) throw new Error('no preview available');
    playPreview({ key, src: d.preview, title: s.title, artist: s.artist, art: d.artwork || S.dzArt.get(s.deezer_id), origin: s.reason, label: 'Preview' });
  } catch (e) { toast(`Could not preview ${esc(s.title)}: ${esc(e.message)}`, 'bad'); }
}

/* ===================================================================== downloads */

VIEWS.downloads = () => {
  const jobs = S.jobs;
  const active = jobs.filter((j) => ['queued', 'running'].includes(j.status)).length;
  const failed = jobs.filter((j) => j.status === 'failed').length;
  const acts = `<button class="btn" data-act="import-list">${icon('upload')}Import Song List…</button>
    ${S.desktop ? `<button class="btn" data-act="add-files">${icon('plus')}Add Audio Files…</button>` : ''}
    ${jobs.some((j) => !['queued', 'running'].includes(j.status)) ? `<button class="btn" data-act="clear-jobs">Clear Finished</button>` : ''}`;
  let html = `<div class="view">${viewHead('Downloads', active ? `${plural(active, 'song')} in progress${failed ? ` · ${failed} failed` : ''}` : 'Everything you download lands in your library with artwork, lyrics and tags.', acts)}
    <div class="quick-dl" style="margin-bottom:18px">${icon('download')}<input class="field q" id="dl-input" placeholder="Artist - Title" style="flex:1">
      <button class="btn primary" data-act="dl-typed">${icon('download')}Download</button></div>`;
  if (!jobs.length) {
    return html + `<div class="empty">${icon('download')}<h3>No downloads yet</h3><div>Search for a song, pick a suggestion in For You, or import a song list (Apple Music PDF, CSV, or a text file with one “Artist - Title” per line).</div></div></div>`;
  }
  html += `<div class="jobs">${jobs.map((j) => {
    const art = j.song_id && S.songs.get(j.song_id)?.has_art ? songArt(S.songs.get(j.song_id), 120) : j.artwork ? remoteArt(j.artwork, j.title) : placeholder(j.title, j.kind === 'fix' ? 'wand' : 'note');
    const running = j.status === 'running';
    const label = { queued: 'Waiting', running: j.stage, done: j.kind === 'fix' ? j.stage : 'Downloaded', exists: 'Already in library', failed: 'Failed', cancelled: 'Cancelled' }[j.status];
    const bar = running ? `<div class="bar ${j.progress == null ? 'indeterminate' : ''}"><div style="width:${Math.round((j.progress || 0) * 100)}%"></div></div>` : '';
    const btns = [];
    if (['queued', 'running'].includes(j.status)) btns.push(`<button class="icon-btn" data-act="job-cancel" data-id="${j.id}" title="Cancel">${icon('x')}</button>`);
    if (['failed', 'cancelled'].includes(j.status)) btns.push(`<button class="btn" data-act="job-retry" data-id="${j.id}">${icon('refresh')}Retry</button>`);
    if (['done', 'exists'].includes(j.status) && j.song_id && S.songs.has(j.song_id)) btns.push(`<button class="icon-btn" data-act="job-play" data-id="${j.song_id}" title="Play">${icon('play')}</button>`);
    return `<div class="job">${art}<div style="min-width:0"><div class="j-t">${esc(j.title)}${j.artist ? ` <span class="muted" style="font-weight:400">— ${esc(j.artist)}</span>` : ''}</div>
      <div class="j-s"><span class="status ${j.status}">${esc(label)}${running && j.progress != null ? ` ${Math.round(j.progress * 100)}%` : ''}</span>
      ${j.kind === 'video' ? `<span>${icon('video')}</span>` : ''}${j.kind === 'fix' ? '<span>metadata</span>' : ''}<span class="faint">${esc(j.message)}</span></div>${bar}</div>
      <div class="actions">${btns.join('')}</div></div>`;
  }).join('')}</div></div>`;
  return html;
};

async function importList() {
  if (S.desktop) {
    try {
      const r = await api('/api/dialog', { method: 'POST', body: { kind: 'list' } });
      if (r.queued) { toast(`Queued ${plural(r.queued, 'song')} from the list`, 'ok'); pollNow(); }
    } catch (e) { toast(esc(e.message), 'bad'); }
    return;
  }
  $('#list-file').click();
}
$('#list-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (file) uploadList(file);
});
async function uploadList(file) {
  try {
    const r = await api('/api/import-list', { method: 'POST', body: file, raw: true, headers: { 'X-Filename': file.name } });
    toast(`Queued ${plural(r.queued, 'song')} from ${esc(file.name)}`, 'ok');
    if (S.view.name !== 'downloads') go('downloads');
    pollNow();
  } catch (err) { toast(esc(err.message), 'bad'); }
}
document.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('Files')) e.preventDefault(); });
document.addEventListener('drop', (e) => {
  const file = [...(e.dataTransfer.files || [])].find((f) => /\.(pdf|csv|txt)$/i.test(f.name));
  if (!file) return;
  e.preventDefault();
  uploadList(file);
});

/* ===================================================================== organizer */

VIEWS.organizer = () => {
  const songs = S.list;
  const total = songs.reduce((t, s) => t + s.duration, 0);
  const size = songs.reduce((t, s) => t + s.size, 0);
  const count = (pred) => songs.filter(pred).length;
  const noart = count((s) => !s.has_art), nolyr = count((s) => !s.has_lyrics);
  const nodet = count((s) => !s.album || !s.genre || !s.year), low = count((s) => s.bitrate && s.bitrate < 128);
  const dupes = duplicates();
  const moves = S.organizeMoves;
  if (moves === null) api('/api/organize').then((r) => { S.organizeMoves = r.moves; if (S.view.name === 'organizer') rerender(); }).catch(() => {});
  const card = (n, label, kind, extra = '') => `<div class="stat"><div class="n ${n ? 'warn' : 'good'}">${n.toLocaleString()}</div><div class="l">${label}</div>
    ${n ? `<div class="row-flex">${kind ? `<button class="btn" data-act="nav" data-view="smart" data-param="${kind}">Show</button>` : ''}${extra}</div>` : '<div class="faint">All good</div>'}</div>`;
  return `<div class="view">${viewHead('Organizer', `${esc(S.root)}`, `<button class="btn" data-act="rescan">${icon('refresh')}Rescan Library</button>`)}
    <div class="cards">
      <div class="stat"><div class="n">${songs.length.toLocaleString()}</div><div class="l">songs · ${plural(artists().length, 'artist')} · ${plural(albums().length, 'album')}</div><div class="faint">${fmtLong(total)} · ${fmtSize(size)}</div></div>
      ${card(noart, 'songs without artwork', 'noart', `<button class="btn primary" data-act="fix" data-what="noart">${icon('wand')}Find Artwork</button>`)}
      ${card(nolyr, 'songs without lyrics', 'nolyrics', `<button class="btn primary" data-act="fix" data-what="nolyrics">${icon('wand')}Find Lyrics</button>`)}
      ${card(nodet, 'songs missing album, genre or year', 'nodetails', `<button class="btn primary" data-act="fix" data-what="nodetails">${icon('wand')}Fill In</button>`)}
      ${card(dupes.length, 'songs that may be duplicates', 'dupes')}
      ${card(low, 'low-quality files (under 128 kbps)', 'lowbit')}
    </div>
    <h2 class="sec">File Layout</h2>
    <div class="stat" style="max-width:900px">
      ${moves === null ? '<div class="loading-row"><span class="spinner"></span>Checking file names…</div>'
        : moves.length ? `<div><b>${plural(moves.length, 'file')}</b> ${moves.length === 1 ? 'is' : 'are'} not stored as <code>Artist/Title.mp3</code>.</div>
          <div class="mini-list">${moves.slice(0, 200).map((m) => `<div>${esc(m.from)}  →  <b>${esc(m.to)}</b></div>`).join('')}</div>
          <button class="btn primary" data-act="organize">${icon('folder')}Organize ${plural(moves.length, 'File')}</button>`
        : `<div class="row-flex">${icon('check')}<span>Every file is stored as <code>Artist/Title.mp3</code>, named from its tags.</span></div>`}
    </div></div>`;
};

/* ===================================================================== settings */

VIEWS.settings = () => {
  const st = S.settings;
  const sources = [['ytmusic', 'YouTube Music'], ['youtube', 'YouTube'], ['soundcloud', 'SoundCloud'], ['audius', 'Audius']];
  const q = [['0', 'Best (VBR ~245 kbps)'], ['2', 'High (VBR ~190 kbps)'], ['4', 'Medium (VBR ~165 kbps)'], ['320', '320 kbps CBR'], ['256', '256 kbps CBR'], ['192', '192 kbps CBR']];
  const browsers = [['', 'None'], ['chrome', 'Chrome'], ['safari', 'Safari'], ['firefox', 'Firefox'], ['edge', 'Edge'], ['brave', 'Brave']];
  const sel = (key, opts) => `<select class="field" data-setting="${key}">${opts.map(([v, l]) => `<option value="${v}" ${String(st[key]) === v ? 'selected' : ''}>${l}</option>`).join('')}</select>`;
  return `<div class="view">${viewHead('Settings')}
    <div class="form">
      <label class="k">Library folder</label>
      <div class="row-flex"><input class="field" id="set-library" value="${esc(st.library)}">${S.desktop ? `<button class="btn" data-act="choose-folder">Choose…</button>` : ''}<button class="btn" data-act="apply-library">Apply</button></div>
      <div class="hint">Your music is read from here, and downloads are saved here as Artist/Title.mp3.</div>
      <label class="k">Download sources</label>
      <div class="chips">${sources.map(([v, l]) => `<label class="chip"><input type="checkbox" data-source="${v}" ${(st.sources || []).includes(v) ? 'checked' : ''}>${l}</label>`).join('')}</div>
      <div class="hint">Tried in this order until a confident match is found. Covers, live and remixed versions are skipped.</div>
      <label class="k">MP3 quality</label>${sel('quality', q)}
      <label class="k">Simultaneous downloads</label>${sel('workers', [['1', '1'], ['2', '2'], ['3', '3'], ['4', '4']])}
      <label class="k">Lyrics</label><label class="row-flex"><input type="checkbox" data-setting-bool="lyrics" ${st.lyrics ? 'checked' : ''}> Embed lyrics from LRCLIB when available</label>
      <label class="k">Editing tags</label><label class="row-flex"><input type="checkbox" data-setting-bool="organize_on_edit" ${st.organize_on_edit !== false ? 'checked' : ''}> Rename and move files to Artist/Title when tags change</label>
      <label class="k">YouTube sign-in</label>${sel('cookies_from_browser', browsers)}
      <div class="hint">Use your browser’s YouTube cookies when YouTube rate-limits requests or a song is age-restricted.</div>
      <label class="k">About</label><div class="faint">CLI Music ${esc(document.querySelector('meta[name=version]').content)} · ffmpeg ${S.ffmpeg ? 'found' : '<b style="color:var(--bad)">missing — install with: brew install ffmpeg</b>'} · ${S.desktop ? 'desktop app' : 'browser mode'}</div>
    </div></div>`;
};

async function saveSettings(changes) {
  try {
    const { settings } = await api('/api/settings', { method: 'PUT', body: changes });
    const libChanged = settings.library !== S.settings.library;
    S.settings = settings;
    toast(libChanged ? 'Library folder changed — scanning…' : 'Settings saved', 'ok');
    if (libChanged) { S.organizeMoves = null; S.foryou = null; }
  } catch (e) { toast(esc(e.message), 'bad'); }
}
main.addEventListener('change', (e) => {
  const s = e.target.closest('[data-setting]');
  if (s) { saveSettings({ [s.dataset.setting]: s.value }); return; }
  const b = e.target.closest('[data-setting-bool]');
  if (b) { saveSettings({ [b.dataset.settingBool]: b.checked }); return; }
  if (e.target.closest('[data-source]')) {
    const order = ['ytmusic', 'youtube', 'soundcloud', 'audius'];
    const on = $$('[data-source]', main).filter((c) => c.checked).map((c) => c.dataset.source);
    if (!on.length) { toast('Keep at least one source', 'bad'); e.target.checked = true; return; }
    saveSettings({ sources: order.filter((x) => on.includes(x)) });
  }
});
main.addEventListener('keydown', (e) => {
  if (e.target.id === 'dl-input' && e.key === 'Enter') $('[data-act="dl-typed"]', main)?.click();
});

/* ===================================================================== actions (event delegation) */

async function handleAction(e) {
  if (e.target.closest('[data-play-table]')) { playIds(S.tableIds, 0, { shuffle: false }); return; }
  if (e.target.closest('[data-shuffle-table]')) { playIds(S.tableIds, 0, { shuffle: true }); return; }
  const el = e.target.closest('[data-act]');
  if (!el) return;
  e.stopPropagation();
  const act = el.dataset.act;
  const i = el.dataset.i !== undefined ? +el.dataset.i : null;
  const r = S.search;
  switch (act) {
    case 'nav': go(el.dataset.view, el.dataset.param); break;
    case 'back': goBack(); break;
    case 'album-sort': save('albumSort', el.dataset.mode); rerender(); break;
    case 'open-album': go('album', el.dataset.key); break;
    case 'play-album': { const a = albums().find((x) => x.key === el.dataset.key); if (a) playIds(a.songs.map((s) => s.id), 0, { shuffle: false }); break; }
    case 'open-artist': go('artists', el.dataset.name, { push: S.view.name !== 'artists' }); break;
    case 'pl-menu': {
      const pl = S.playlists.find((p) => p.id === el.dataset.id);
      const rect = el.getBoundingClientRect();
      showMenu(rect.left, rect.bottom, [
        { label: 'Rename…', icon: 'tag', act: () => renamePlaylist(pl) },
        { label: 'Delete Playlist', icon: 'trash', danger: true, act: () => deletePlaylist(pl) },
      ]);
      break;
    }
    case 'lib-all': S.filters.songs = S.searchQ; go('songs'); break;
    case 'quick-dl': { const t = parseTerm(S.searchQ); queueDownload({ kind: 'song', ...t }); break; }
    case 'preview-song': {
      const s = r.songs[i];
      if (!s.preview) { toast('No preview for this song', 'bad'); break; }
      playPreview({ key: `song:${i}:${r.q}`, src: s.preview, title: s.title, artist: s.artist, art: s.artwork, origin: s.album, label: 'Preview' });
      break;
    }
    case 'dl-song': { const s = r.songs[i]; queueDownload({ kind: 'song', title: s.title, artist: s.artist, album: s.album, duration: s.duration, artwork: s.artwork }); break; }
    case 'watch': watchVideo(r.videos[i]); break;
    case 'listen-video': previewYouTubeAudio(r.videos[i], el); break;
    case 'dl-video': downloadVideoDialog(r.videos[i]); break;
    case 'fy-preview': previewSuggestion(S.foryou.items[i]); break;
    case 'fy-dl': { const s = S.foryou.items[i]; queueDownload({ kind: 'song', title: s.title, artist: s.artist, album: s.album, duration: s.duration, artwork: S.dzArt.get(s.deezer_id) || '' }); break; }
    case 'fy-dismiss': {
      const s = S.foryou.items[i];
      await api('/api/foryou/dismiss', { method: 'POST', body: { key: s.key } });
      S.foryou.items.splice(i, 1);
      rerender();
      break;
    }
    case 'fy-refresh': loadForYou(true); break;
    case 'fy-dlall': {
      const todo = S.foryou.items.filter((s) => !s.owned && !jobFor(s.artist, s.title));
      if (!await confirmDialog(`Download ${plural(todo.length, 'suggested song')} into your library?`, 'Download All')) break;
      for (const s of todo) await queueDownload({ kind: 'song', title: s.title, artist: s.artist, album: s.album, duration: s.duration, artwork: S.dzArt.get(s.deezer_id) || '' });
      break;
    }
    case 'dl-typed': {
      const inp = $('#dl-input');
      const t = parseTerm(inp.value);
      if (!t.title) { toast('Type a song as “Artist - Title”', 'bad'); break; }
      inp.value = '';
      queueDownload({ kind: 'song', ...t });
      break;
    }
    case 'job-cancel': await api(`/api/downloads/${el.dataset.id}/cancel`, { method: 'POST' }); pollNow(); break;
    case 'job-retry': await api(`/api/downloads/${el.dataset.id}/retry`, { method: 'POST' }); pollNow(); break;
    case 'job-play': playIds([el.dataset.id]); break;
    case 'clear-jobs': await api('/api/downloads/clear', { method: 'POST' }); pollNow(); break;
    case 'import-list': importList(); break;
    case 'add-files': {
      try { const res = await api('/api/dialog', { method: 'POST', body: { kind: 'audio' } }); if (res.imported) toast(`Copied ${plural(res.imported, 'file')} into your library`, 'ok'); pollNow(); } catch (err) { toast(esc(err.message), 'bad'); }
      break;
    }
    case 'fix': {
      const pred = { noart: (s) => !s.has_art, nolyrics: (s) => !s.has_lyrics, nodetails: (s) => !s.album || !s.genre || !s.year }[el.dataset.what];
      const ids = S.list.filter(pred).map((s) => s.id);
      if (ids.length && await confirmDialog(`Look up ${plural(ids.length, 'song')} in the catalog and add whatever is missing? Existing tags are never overwritten.`, 'Look Up')) fixSongs(ids);
      break;
    }
    case 'fix-list': fixSongs(S.tableIds); break;
    case 'organize': {
      if (!await confirmDialog(`Move ${plural(S.organizeMoves.length, 'file')} into Artist/Title.mp3 folders? Playlists and play counts follow the files.`, 'Organize')) break;
      const res = await api('/api/organize', { method: 'POST' });
      toast(`Moved ${plural(res.moved, 'file')}`, 'ok');
      S.organizeMoves = null;
      await refreshState();
      await refreshLibrary();
      break;
    }
    case 'rescan': await api('/api/library/rescan', { method: 'POST' }); S.organizeMoves = null; await refreshLibrary(); toast('Library rescanned', 'ok'); break;
    case 'choose-folder': {
      try { const res = await api('/api/dialog', { method: 'POST', body: { kind: 'folder' } }); if (res.paths && res.paths[0]) { $('#set-library').value = res.paths[0]; saveSettings({ library: res.paths[0] }); } } catch (err) { toast(esc(err.message), 'bad'); }
      break;
    }
    case 'apply-library': saveSettings({ library: $('#set-library').value.trim() }); break;
    default: break;
  }
}

/* ===================================================================== keyboard */

document.addEventListener('keydown', (e) => {
  const typing = e.target.closest('input, textarea, select') && e.target.type !== 'range' && e.target.type !== 'checkbox';
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); searchInput.focus(); searchInput.select(); return; }
  if (typing || $('#modal-root').children.length) return;
  if (e.key === ' ') { e.preventDefault(); togglePlay(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === 'ArrowRight') { e.preventDefault(); next(false); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === 'ArrowLeft') { e.preventDefault(); prev(); return; }
  if (e.key === 'ArrowRight' && audio.src) { audio.currentTime = Math.min((audio.duration || 0), audio.currentTime + 10); return; }
  if (e.key === 'ArrowLeft' && audio.src) { audio.currentTime = Math.max(0, audio.currentTime - 10); return; }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'a' && S.tableIds.length) { e.preventDefault(); S.sel = new Set(S.tableIds); refreshSelection(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i' && S.sel.size) {
    e.preventDefault();
    const ids = S.tableIds.filter((x) => S.sel.has(x));
    ids.length === 1 ? songInfo(ids[0]) : multiInfo(ids);
    return;
  }
  if (e.key === 'Enter' && S.sel.size) { const i = S.tableIds.findIndex((x) => S.sel.has(x)); if (i >= 0) playIds(S.tableIds, i, { shuffle: false }); return; }
  if ((e.key === 'Backspace' || e.key === 'Delete') && S.sel.size) {
    const ids = S.tableIds.filter((x) => S.sel.has(x));
    if (S.tableCtx?.playlist) savePlaylist(S.tableCtx.playlist.id, { remove: ids }); else deleteSongs(ids);
    return;
  }
  if (e.key === 'Escape') { S.sel.clear(); refreshSelection(); }
  if ((e.metaKey || e.ctrlKey) && e.key === '[') goBack();
});

/* ===================================================================== sync with the server */

async function refreshLibrary() {
  const lib = await api('/api/library');
  setLibrary(lib);
  if (S.foryou) S.foryou = null;
  if (!$('#modal-root').children.length) rerender(); else renderNav();
  updateNowPlaying();
}

async function refreshDownloads() {
  const { version, jobs } = await api('/api/downloads');
  const before = new Map(S.jobs.map((j) => [j.id, j.status]));
  S.dlVersion = version;
  S.jobs = jobs;
  S.active = jobs.filter((j) => ['queued', 'running'].includes(j.status)).length;
  for (const j of jobs) {
    const was = before.get(j.id);
    if (!was || was === j.status || ['queued', 'running'].includes(j.status)) continue;
    if (j.status === 'done') toast(j.kind === 'fix' ? `${esc(j.title)}: ${esc(j.message || j.stage)}` : `Added <b>${esc(j.title)}</b> by ${esc(j.artist)} to your library`, 'ok');
    else if (j.status === 'failed') toast(`Couldn’t download <b>${esc(j.title)}</b>: ${esc(j.message)}`, 'bad');
  }
  renderNav();
  if (['downloads', 'search', 'foryou'].includes(S.view.name) && !$('#modal-root').children.length) rerender();
}

let pollTimer = null;
async function poll() {
  clearTimeout(pollTimer);
  try {
    const p = await api('/api/poll');
    if (p.library !== S.libVersion) await refreshLibrary();
    if (p.downloads !== S.dlVersion) await refreshDownloads();
    if (S.foryou && p.foryou !== S.foryouStatus && p.foryou !== 'idle') {
      S.foryouStatus = p.foryou;
      loadForYou();
    } else if (S.foryou && p.foryou === 'running' && S.view.name === 'foryou') {
      loadForYou();
    }
  } catch { /* server restarting */ }
  pollTimer = setTimeout(poll, S.active ? 900 : 2000);
}
function pollNow() { setTimeout(poll, 150); }

/* ===================================================================== boot */

async function boot() {
  const b = await api('/api/bootstrap');
  S.desktop = b.desktop;
  S.ffmpeg = b.ffmpeg;
  S.settings = b.state.settings;
  S.playlists = b.state.playlists;
  S.plays = b.state.plays;
  S.loved = new Set(b.state.loved);
  setLibrary(b.library);
  S.dlVersion = b.downloads.version;
  S.jobs = b.downloads.jobs;
  S.active = S.jobs.filter((j) => ['queued', 'running'].includes(j.status)).length;
  if (S.view.name === 'search' || !VIEWS[S.view.name]) S.view = { name: S.list.length ? 'recent' : 'search' };

  const saved = store('queue', null);
  if (saved && saved.queue && saved.queue.length) {
    P.queue = saved.queue.filter((id) => S.songs.has(id));
    P.index = Math.min(Math.max(0, P.queue.indexOf(saved.queue[saved.index])), P.queue.length - 1);
    P.resumeAt = saved.time || 0;
    if (P.queue.length) {
      const song = current();
      audio.src = withToken(`/api/audio/${song.id}`);
      audio.addEventListener('loadedmetadata', () => { if (P.resumeAt) audio.currentTime = P.resumeAt; P.resumeAt = 0; }, { once: true });
    }
  }
  $('#drawer').hidden = !S.drawer;
  render();
  updateNowPlaying();
  updateMute();
  if (!S.ffmpeg) toast('ffmpeg is not installed, so downloads will fail. Install it with: brew install ffmpeg', 'bad');
  poll();
}

boot().catch((e) => {
  $('#main').innerHTML = `<div class="view"><div class="empty">${icon('x')}<h3>Could not start</h3><div>${esc(e.message)}</div></div></div>`;
});
