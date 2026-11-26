#!/usr/bin/env python3
"""Usage: python patch_update5.py path/to/index.html
Run AFTER patch_update4.py.

What it does:
  1. Avatar borders: 6 Discord avatar decorations (image overlays) replace the old CSS borders in the shop.
     Old borders stay for players who already own them (and for milestone rewards).
  2. New shop category "Profile Effects": 4 animated Discord profile effects that play over the
     profile card (preview, leaderboard popup and editor preview all show them).
     New "Profile Effect" picker in Edit Profile. The equipped effect is saved to the leaderboard doc.
  3. Avatar can now also be set by pasting an image / GIF URL (same as the banner).

Edit names / prices / URLs in the P5_BORDERS and P5_EFFECTS arrays (inside JS below) if you want.
"""
import sys, shutil

CSS = r"""
/* ===== Update 5 patch ===== */
.profile-fx{position:absolute;inset:0;background-repeat:no-repeat;background-size:cover;background-position:top center;pointer-events:none;z-index:6}
.hdr-pfp-wrap{position:relative;display:inline-flex;align-items:center}
.shop-thumb{width:44px;height:44px;object-fit:contain;display:block}
"""

JS = r"""
/* =========================================================
   PATCH 5: Discord avatar decorations, profile effects, avatar URL
   ========================================================= */
const P5_BORDERS = [
  { key: 'border-deco-1', name: 'Avatar Decoration 1', cost: 25_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1538991362601656420/animated' },
  { key: 'border-deco-2', name: 'Avatar Decoration 2', cost: 28_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1462116613645144185/animated' },
  { key: 'border-deco-3', name: 'Avatar Decoration 3', cost: 32_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1556799118427553842/animated' },
  { key: 'border-deco-4', name: 'Avatar Decoration 4', cost: 36_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1144307257807491094/animated' },
  { key: 'border-deco-5', name: 'Avatar Decoration 5', cost: 40_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1541454236456456232/animated' },
  { key: 'border-deco-6', name: 'Avatar Decoration 6', cost: 45_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/1343751617362661526/animated' }
];
const P5_EFFECTS = [
  { key: 'fx-1', name: 'Profile Effect 1', cost: 30_000_000, url: 'https://cdn.discordapp.com/assets/content/4d89d846e27e98e767e31222a16adb13cdf0fa8e55431827fb728a38b230d229' },
  { key: 'fx-2', name: 'Profile Effect 2', cost: 35_000_000, url: 'https://cdn.discordapp.com/media/v1/collectibles-shop/f5a896de812973336955d653b836be862fa38346cc03efec3485eedcaff454c1' },
  { key: 'fx-3', name: 'Profile Effect 3', cost: 40_000_000, url: 'https://cdn.discordapp.com/assets/content/5aa83fd157054febd903d172107b857020c4acf020293ea308124ee381bd8fda' },
  { key: 'fx-4', name: 'Profile Effect 4', cost: 45_000_000, url: 'https://cdn.discordapp.com/assets/content/714daf4880f0d210b59075841c1a431d5df26922226ecfaf99cc052d29227dc4' }
];
const P5_BORDER_LABELS = {};
P5_BORDERS.forEach(b => { P5_BORDER_LABELS[b.key] = '✨ ' + b.name; });

/* ---------- Avatar decorations: overlay drawn around any avatar that has the class ---------- */
(function () {
  const st = document.createElement('style');
  st.textContent = P5_BORDERS.map(b => {
    const sel = `:has(> .${b.key}:not([style*="none"]))`;
    return `${sel}{position:relative}\n${sel}::after{content:'';position:absolute;inset:-10%;background:url("${b.url}") center/contain no-repeat;pointer-events:none;z-index:4}`;
  }).join('\n');
  document.head.appendChild(st);

  const img = document.getElementById('userHeaderPfp');
  if (img && !img.parentNode.classList.contains('hdr-pfp-wrap')) {
    const w = document.createElement('span');
    w.className = 'hdr-pfp-wrap';
    img.parentNode.insertBefore(w, img);
    w.appendChild(img);
  }
})();

/* ---------- State ---------- */
const p5Def = getDefaultGameState;
getDefaultGameState = function () {
  return { ...p5Def(), equipped_effect: '', unlocked_effects: [] };
};

/* ---------- Profile effect overlay ---------- */
function p5EffectHtml(key) {
  const e = P5_EFFECTS.find(x => x.key === key);
  return e ? `<div class="profile-fx" style="background-image:url('${e.url}')"></div>` : '';
}
function p5AddEffect(root, key) {
  const card = root && root.querySelector('.discord-profile-card');
  if (!card) return;
  const old = card.querySelector(':scope > .profile-fx');
  if (old) old.remove();
  const h = p5EffectHtml(key);
  if (h) card.insertAdjacentHTML('afterbegin', h);
}

const p5OPPM = openPlayerProfileModal;
openPlayerProfileModal = function (uid, row) {
  p5OPPM(uid, row);
  p5AddEffect(document.getElementById('playerProfileContent'), row && row.equipped_effect);
};

const p5OSP = openShopPreview;
openShopPreview = function (id) {
  p5OSP(id);
  const it = SHOP_ITEMS.find(i => i.id === id);
  const key = it && it.cat === 'EFFECTS' ? it.unlockKey : gameState.equipped_effect;
  p5AddEffect(document.getElementById('shopPreviewContent'), key);
};

const p5UPLP = updateProfileLivePreview;
updateProfileLivePreview = function () {
  p5UPLP();
  const s = document.getElementById('editEffectInput');
  p5AddEffect(document.getElementById('profilePreviewHost'), s ? s.value : gameState.equipped_effect);
};

/* ---------- Leaderboard: publish the equipped effect ---------- */
const p5Save = saveState;
saveState = function () {
  p5Save();
  try {
    if (!useFirebase || !isCloudStateLoaded || !firebaseDb) return;
    const uid = (firebaseAuth && firebaseAuth.currentUser) ? firebaseAuth.currentUser.uid : userSession.token;
    if (!uid) return;
    firebaseDb.collection('leaderboard').doc(uid).set({ equipped_effect: gameState.equipped_effect || '' }, { merge: true }).catch(() => {});
  } catch (e) {}
};

/* ---------- Shop: new borders replace the old ones, new Profile Effects category ---------- */
for (let i = SHOP_ITEMS.length - 1; i >= 0; i--) if (SHOP_ITEMS[i].cat === 'BORDERS') SHOP_ITEMS.splice(i, 1);
P5_BORDERS.forEach(b => SHOP_ITEMS.push({
  id: 'border_' + b.key.replace(/-/g, '_'), cat: 'BORDERS', name: b.name, desc: 'Animated Discord avatar decoration.',
  icon: `<img class="shop-thumb" src="${b.url}" alt="">`, cost: b.cost, color: '#a78bfa', unlockKey: b.key
}));
P5_EFFECTS.forEach(e => SHOP_ITEMS.push({
  id: 'effect_' + e.key.replace(/-/g, '_'), cat: 'EFFECTS', name: e.name, desc: 'Animated effect that plays over your profile card.',
  icon: '✨', cost: e.cost, color: '#f472b6', unlockKey: e.key
}));

(function () {
  const bb = [...document.querySelectorAll('#shopFilters .filter-tab')].find(b => /Borders/i.test(b.textContent));
  if (!bb) return;
  const nb = document.createElement('button');
  nb.className = 'filter-tab';
  nb.textContent = 'Profile Effects';
  nb.onclick = () => filterShop('EFFECTS');
  bb.after(nb);
})();

const p5Own = isShopItemOwned;
isShopItemOwned = function (item) {
  if (item.cat === 'EFFECTS') return (gameState.unlocked_effects || []).includes(item.unlockKey);
  return p5Own(item);
};

const p5Buy = buyShopItem;
buyShopItem = function (id) {
  const it = SHOP_ITEMS.find(i => i.id === id);
  if (!it || it.cat !== 'EFFECTS') return p5Buy(id);
  if (!userSession.token) { showToast('Sign In Required', 'Please sign in to use the shop.'); return; }
  if (gameState.coins < it.cost) { showToast('Not Enough Coins', `You need ${formatAbbrev(it.cost)} coins.`); return; }
  gameState.coins -= it.cost;
  gameState.unlocked_effects = gameState.unlocked_effects || [];
  if (!gameState.unlocked_effects.includes(it.unlockKey)) gameState.unlocked_effects.push(it.unlockKey);
  showToast('Effect Unlocked!', `${it.name} is now available in your profile.`);
  updateHeaderStats();
  saveState();
  renderShopView();
  if (typeof confetti === 'function') confetti({ particleCount: 60, spread: 70, origin: { y: 0.6 } });
};

/* ---------- Profile editor: border labels, effect picker, avatar URL ---------- */
const p5RBD = renderBorderDropdown;
renderBorderDropdown = function (cur, labels) {
  return p5RBD(cur, Object.assign({}, labels || BORDER_LABELS, P5_BORDER_LABELS));
};

function p5PfpUrl(v) {
  v = (v || '').trim();
  const hidden = document.getElementById('editPfpInput');
  if (v && !/^https?:\/\//i.test(v)) {
    p3Prog('pfpUploadProgress', 'Paste a full link starting with http(s)://', '#f87171');
    return;
  }
  hidden.value = v;
  document.getElementById('editPfpFileName').textContent = v ? 'Image from URL' : 'No file chosen';
  if (v) p3Prog('pfpUploadProgress', '✓ URL set. Press Save Changes.', '#34d399');
  else document.getElementById('pfpUploadProgress').style.display = 'none';
  updateProfileLivePreview();
}

function p5InjectEditor() {
  const form = document.querySelector('#profileModal .pe-form');
  if (!form || document.getElementById('editPfpUrlInput')) return;
  const prog = document.getElementById('pfpUploadProgress');
  prog.insertAdjacentHTML('beforebegin',
    `<input type="text" id="editPfpUrlInput" placeholder="…or paste an image / gif URL" oninput="p5PfpUrl(this.value)" style="text-overflow:ellipsis; margin-top:0.5rem;"/>`);
  const save = form.querySelector(':scope > .btn-action');
  save.insertAdjacentHTML('beforebegin',
    `<div class="form-field-clean"><label>Profile Effect</label><select id="editEffectInput" onchange="updateProfileLivePreview()"></select></div>`);
}

function p5FillEditor() {
  const own = gameState.unlocked_effects || [];
  const sel = document.getElementById('editEffectInput');
  sel.innerHTML = '<option value="">No effect</option>' +
    P5_EFFECTS.filter(e => own.includes(e.key)).map(e => `<option value="${e.key}">${e.name}</option>`).join('');
  sel.value = own.includes(gameState.equipped_effect) ? gameState.equipped_effect : '';
  const pfp = userSession.pfp || '';
  document.getElementById('editPfpUrlInput').value = /^https?:\/\//i.test(pfp) ? pfp : '';
}

const p5OPM = openProfileModal;
openProfileModal = function () {
  p5OPM();
  if (!userSession.token) return;
  p5InjectEditor();
  p5FillEditor();
  updateProfileLivePreview();
};

const p5Ca = clearAvatar;
clearAvatar = function () {
  p5Ca();
  const u = document.getElementById('editPfpUrlInput');
  if (u) u.value = '';
};

const p5Hp = handlePfpFileSelect;
handlePfpFileSelect = async function (ev) {
  await p5Hp(ev);
  const u = document.getElementById('editPfpUrlInput');
  const h = document.getElementById('editPfpInput').value;
  if (u) u.value = /^https?:\/\//i.test(h) ? h : '';
};

const p5Spc = saveProfileChanges;
saveProfileChanges = function () {
  const s = document.getElementById('editEffectInput');
  if (s) gameState.equipped_effect = s.value || '';
  return p5Spc();
};
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    p = sys.argv[1]

    src = open(p, encoding="utf-8").read()
    if "PATCH 5: Discord avatar decorations" in src:
        sys.exit("Already patched.")
    if "PATCH 4: 20 dungeons" not in src:
        sys.exit("Run patch_update4.py first.")

    i = src.rfind("</body>")
    if i < 0:
        sys.exit("No </body> found.")
    src = src[:i] + "<style>" + CSS + "</style>\n<script>" + JS + "</script>\n" + src[i:]

    shutil.copy(p, p + ".bak5")
    open(p, "w", encoding="utf-8").write(src)
    print("Patched. Backup:", p + ".bak5")