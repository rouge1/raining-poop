# Plan — Issue #5: Bitcoin data in Raining Poop

## Summary of the constraint that drives everything

`bitcoin_widget/price_fetcher.py` cannot be imported from `poop.py`. Two independent hard blockers:

1. **Line 4 is `from gi.repository import GLib`.** PyGObject is an apt-installed system package living in `/usr/lib/python3/dist-packages`. Verified on this machine: the only conda env that has `pygame` (`~/miniconda3/envs/venv`) has **no `gi` and no `requests`**; the interpreter that has `gi` (`/usr/bin/python3`) has **no `pygame`**. The two projects are on mutually exclusive interpreters. `bitcoin_widget/CLAUDE.md` says this outright ("Use the **system** `python3` … a bare `python3` may resolve to a conda/venv interpreter without PyGObject").
2. **All callbacks are delivered via `GLib.idle_add`** (`price_fetcher.py:71, 80, 84`). `idle_add` queues onto the GLib default main context. A pygame app never iterates that context, so *even with `gi` installed the callbacks would never fire*. Making them fire would mean pumping `GLib.MainContext.default().iteration(False)` every frame inside the game loop — running a GTK event loop inside a pygame loop to receive one float.

So the useful thing to take from `bitcoin_widget` is its **knowledge** (which endpoints, which fields, which fallback order, which gotchas), not its code object.

---

## 1. Integration options

### Option A — import `PriceFetcher` directly
Mechanically it would be:
```python
sys.path.insert(0, "/data/python/bitcoin_widget")   # not a package: no __init__.py,
from price_fetcher import PriceFetcher              # and it does a bare `import config`
```
`price_fetcher` does a top-level `import config`, so the sibling directory must be on `sys.path` regardless — there is no `pip install -e` path without adding packaging to `bitcoin_widget`, which is out of scope.

Costs: the two blockers above; a hardcoded absolute path to an unrelated checkout that makes the game un-runnable anywhere else; and `_fetch_all()` unconditionally pulls **288 history candles** every poll (`_fetch_history`, line 82) plus the `mempool.space` block height — data the game has no use for. **Rejected.**

### Option B — vendor a minimal fetcher into `raining-poop` ✅ **RECOMMENDED**
A new ~70-line `btc_feed.py` in this repo: a daemon thread, `urllib.request` from the stdlib, Coinbase stats → Kraken ticker fallback, results handed to the main loop through a `queue.Queue`.

Reuses `bitcoin_widget`'s *research*, copying only the two URLs and their parse shape:

| Source | URL (from `bitcoin_widget/config.py`) | Parse |
|---|---|---|
| Coinbase (primary) | `api.exchange.coinbase.com/products/BTC-USD/stats` | `last`, `open` → `change = (last-open)/open*100` |
| Kraken (fallback) | `api.kraken.com/0/public/Ticker?pair=XBTUSD` | `result.<any>.c[0]`, `.o` |

Also inherit its documented pitfall: **do not add Binance** — it returns HTTP 200 with `{"code":0,"msg":"Service unavailable from a restricted location"}`, so a naive `raise_for_status()` fallback silently accepts garbage.

Costs: ~25 lines of duplicated URL/parse logic across two repos. If Coinbase changes its schema, it gets fixed twice.

Benefits: no `gi`, no GLib, no GTK main loop, no cross-repo path, **no new pip dependency at all** (`requests` is absent from the pygame env; `urllib.request` is not), works headless and offline, and `poop.py` stays a self-contained single-repo pygame app.

### Option C — read the widget's diag Unix socket
`bitcoin_widget.py` can expose `~/.config/bitcoin-widget/diag.sock`; connecting and sending nothing returns state JSON including `api: {price, change, source, updated}` (`bitcoin_widget.py:305-326`). No network from the game at all.

Costs: requires the widget to be **running** *and* launched with `--diag`, which is opt-in and off by default; it is explicitly a *diagnostic* interface, not a stable API, so it can change without notice; the socket read is still blocking I/O that needs the same worker-thread + queue plumbing anyway; and the game shows nothing whenever the widget isn't up. **Rejected as primary.** Worth keeping as a *pluggable source* behind the same `BtcFeed` interface in a later phase (try socket → fall back to HTTP), since it costs ~15 lines once the interface exists.

### Decision
**Option B.** The deciding factor is not taste — Option A does not run on this machine and would not deliver callbacks even if it did. Option B buys total decoupling and a zero-dependency-delta for the price of ~25 duplicated lines, which is the right trade for a 178-line toy.

---

## 2. Thread safety

pygame's loop is single-threaded and `poop.py` has no locking today. The rules:

- **`btc_feed.py` must never `import pygame`.** That is the enforcement mechanism, not a comment. No `pygame.event.post`, no `pygame.time.get_ticks`, no surface work off the main thread.
- The worker's only output channel is a `queue.Queue`, drained non-blockingly once per frame from `run()`.

Worker side:
```python
class BtcFeed:
    def __init__(self, interval=20.0):
        self._interval = interval
        self._stop = threading.Event()
        self.samples = queue.Queue(maxsize=8)     # (price, change_pct) tuples
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self): self._thread.start()
    def stop(self):  self._stop.set()

    def _run(self):
        delay = 0.0
        while not self._stop.wait(delay):          # interruptible sleep; wakes on stop()
            sample = _fetch_coinbase() or _fetch_kraken()
            if sample:
                delay = self._interval * random.uniform(0.9, 1.1)   # jitter
                try:
                    self.samples.put_nowait(sample)
                except queue.Full:
                    pass                            # main loop is behind; next sample wins
            else:
                delay = min(max(delay, self._interval) * 2, 300.0)  # backoff, cap 5 min
```

Main-loop side, called once per frame from `run()` before `animate_poop()`:
```python
def _drain_feed(self):
    while True:
        try:
            price, change = self.feed.samples.get_nowait()   # never blocks
        except queue.Empty:
            break
        if self.btc_price is not None and price != self.btc_price:
            self.btc_dir = 1 if price > self.btc_price else -1
            self.btc_flash = self.BTC_FLASH_FRAMES
        self.btc_price, self.btc_change = price, change
```

**Why a queue rather than a shared attribute.** A sample is *two* values. A worker assigning `self.price = p` then `self.change = c` can be read between the two statements, rendering a new price beside a stale change. A queue moves one immutable tuple, so a partial read is impossible — and the arrival of an item *is* the edge detection that "show when the price is changing" needs, for free. A single-slot alternative works only if it is one atomic tuple assignment (`self._latest = (price, change)`, atomic under CPython's GIL) *plus* a separate sequence counter for edge detection — strictly more moving parts for no gain.

**Shutdown.** Call `self.feed.stop()` in the existing `finally:` in `run()` (line 91), before `pygame.quit()`. The thread is a daemon, so even a `urlopen` stuck at its 8s timeout cannot delay process exit; `stop()` is for the clean case.

---

## 3. Failure, offline, and startup behavior

The app currently needs no network. That property must survive: **with the network unplugged, the game must be indistinguishable from today.**

| Situation | Behavior |
|---|---|
| Before the first sample | `btc_price is None`. HUD renders a dim `BTC ——` placeholder (or nothing, see Q1). **No bitcoin sprites spawn** — spawn mix stays 100% poop until a price exists, so a doomed fetch never changes the game. |
| DNS fails / no route / offline | `urlopen` raises inside the worker; caught, sample dropped, backoff doubles. Main loop never notices. |
| Slow API | Bounded by `timeout=8` on every `urlopen` (same value `bitcoin_widget` uses). Costs the worker up to 16s across both sources; costs the render loop zero. |
| Rate-limited / 429 / 5xx | Same path as any failure → Kraken fallback → backoff `20s → 40s → 80s → … → 300s` cap, with ±10% jitter. Resets to base interval on the first success. |
| Malformed JSON / schema change | Each parse wrapped in `try/except Exception` returning `None`, mirroring `price_fetcher._coinbase_price`. Never propagates. |
| Price goes stale mid-session | Track `last_ok` monotonic timestamp. Older than ~3 poll intervals → grey the HUD out and stop spawning new BTC sprites; already-falling ones finish their fall. |
| User doesn't want network | `--no-btc` flag / `POOP_NO_BTC=1` skips `feed.start()` entirely; no thread, no socket. |

Non-negotiable invariant: **no network call, socket read, or blocking `queue.get()` on the render thread.** Only `get_nowait()`.

---

## 4. Feature design

Sized for a 400×600 window whose dead center is already occupied by the counter.

### 4a. Price readout (HUD)
A single line pinned to the **top-left** at `(HUD_MARGIN, HUD_MARGIN)` = `(8, 8)`, in a second smaller font (`pygame.font.Font(None, 22)`), reading `BTC $118,432  +1.24%`. Top-left is the right spot: the counter owns the center, sprites spawn along the top edge and fall *past* the text (which looks intentional), and the bottom edge is where sprites despawn.

Two rendering cautions:
- **Do not use `▲`/`▼`.** pygame's built-in font (`Font(None, …)` → `freesansbold.ttf`) has no glyph for U+25B2/U+25BC and will render tofu. Use `+`/`-` on the percentage, or draw a 3-point `pygame.draw.polygon` triangle.
- **Do not assume a white background** (see §6). Blit a translucent pill behind the text — `pygame.Surface(size, pygame.SRCALPHA)` filled `(0, 0, 0, 120)` — and draw the text in near-white. That keeps it legible over the white fill today *and* over whatever image issue #4 lands.

Colors: neutral off-white when flat, and on change, tint the delta green/red. Reuse `bitcoin_widget/config.py`'s palette for continuity: `GRAPH_POS = #37D6A0` (mint), `GRAPH_NEG = #FB6E7E` (coral), `GRAPH_LINE_COLOR = #F7931A` (bitcoin orange, for the "BTC" label and the coin sprite).

### 4b. "Price is changing" — the flash
On each new sample where `price != previous`, set `self.btc_flash = BTC_FLASH_FRAMES` (~30, i.e. half a second at 60fps) and `self.btc_dir = ±1`. `draw()` decrements it and, while non-zero, renders the whole HUD line in mint or coral and nudges the pill's alpha up. This is the cheapest possible honest answer to the issue's second idea, and it works on the very first price change with no assets and no gameplay coupling.

(Frame-counting is fine at `clock.tick(60)`; if wall-clock accuracy ever matters, store a `pygame.time.get_ticks()` deadline instead.)

### 4c. Bitcoin sprites
Add a `"kind"` key to the dicts already in `self.poops` — `"poop"` or `"btc"`. Nothing about the motion machinery changes: `create_poop` still picks `pattern`/`speed`/`rotating` the same way, `animate_poop` is untouched, and `draw()` just looks the image set up by kind. That is the whole point of reusing the existing list rather than adding a parallel one — zigzag, spiral, rotation and the `self.half` margin/cull math all come along free.

Sprite loading: generalize `_load_poop_images()` into `_load_sprite(path, key_white=True)` returning `(base_image, rotations)`, and store `self.sprites = {"poop": (...), "btc": (...)}`. `self.half` must then be the max over the images of **all** kinds, not just poop.

**Asset — draw it, don't download it.** Render the coin procedurally once at startup onto a 30×30 `SRCALPHA` surface: a `pygame.draw.circle` in `#F7931A` plus a white `B` from the existing font with two short `pygame.draw.line` verticals through it. Then feed that surface through the same `smoothscale` + 36-angle rotation path. This sidesteps logo licensing entirely (see §6) and adds no file.

There is a concrete trap if a PNG is used instead: `_load_poop_images` hardcodes a white-key (`threshold = 230`, lines 53-60) that turns every near-white pixel transparent. The standard Bitcoin logo is a **white ₿ on orange** — the key would punch the glyph straight out of the coin. Hence the `key_white=False` parameter on the generalized loader.

### 4d. What the price actually drives
Keep exactly one mechanic in phase 2 — **the spawn mix**:

```
btc_share = 0.0                       if btc_price is None or stale
          = clamp(|change_24h| / 4, 0, 0.5)   otherwise
```
and in `create_poop`, `kind = "btc" if random.random() < btc_share else "poop"`. A flat day is nearly all poop; a ±4% day is half coins. Direction rides on the readout color and (optionally) a coral tint blitted over the coin when `change < 0` — so a crashing price literally rains more poop, which is the joke the issue is reaching for.

Deliberately **not** in the first two phases: modulating the spawn *rate*. It is a phase-3 item because of a real trap — `pygame.time.set_timer(USEREVENT+1, ms)` **restarts** the countdown on every call. Called once per frame (16ms) with a 500ms interval, the spawn timer would never fire at all and the rain would stop. Re-arm only inside the `if` where the interval actually changed.

---

## 5. Concrete change list

**New file `btc_feed.py`** (~70 lines): `BtcFeed` (`start`/`stop`/`samples` queue), `_fetch_coinbase()`, `_fetch_kraken()`, both `try/except`-wrapped with `timeout=8`. Stdlib only: `json`, `queue`, `random`, `threading`, `urllib.request`. No `import pygame`.

**`poop.py`** — every touched site:

| Site | Change |
|---|---|
| constants block (11-19) | `+ BTC_POLL_SECONDS = 20`, `BTC_FLASH_FRAMES = 30`, `BTC_SHARE_MAX = 0.5`, `BTC_STALE_SECONDS = 60`, `HUD_FONT_SIZE = 22`, `HUD_MARGIN = 8` |
| `__init__` (21-45) | `+ self.hud_font = pygame.font.Font(None, HUD_FONT_SIZE)`; `+ self.btc_price = self.btc_change = None`, `self.btc_dir = 0`, `self.btc_flash = 0`, `self.btc_last_ok = None`; build `self.sprites` dict; `self.half` computed across all kinds; construct `BtcFeed` and `start()` it **last**, after the pygame-init `try/except`, so a display failure can't leave a thread behind |
| `_load_poop_images` (47-74) | → `_load_sprite(path_or_surface, key_white=True)`; add `_make_coin_surface()`; both return `(base, rotations)` |
| `run` (76-92) | `+ self._drain_feed()` immediately before `self.animate_poop()`; `+ self.feed.stop()` as the first line of the existing `finally:` |
| `create_poop` (99-115) | `+ "kind": "btc" if random.random() < self._btc_share() else "poop"` in the dict |
| `animate_poop` (117-137) | **no change** |
| `draw` (139-156) | image lookup becomes `base, rots = self.sprites[poop["kind"]]`; `+ self._draw_btc_hud()` after the counter blit so the HUD sits on top |
| new methods | `_drain_feed()`, `_btc_share()`, `_draw_btc_hud()`, `_make_coin_surface()` |
| `main` (159-173) | `+ argparse` for `--no-btc` (or read `POOP_NO_BTC`) |

**`requirements.txt`: no change.** Stdlib-only fetcher, deliberately. Worth a one-line comment there noting the app now makes optional outbound HTTPS.

**`README.md`**: a short "Bitcoin ticker" section — what it shows, that it needs no new packages, that it degrades to today's behavior offline, and the `--no-btc` escape hatch.

**Assets**: none (coin is procedural). Optional `bitcoin_coin.png` later.

---

## 6. Coordination with issue #4 (background image)

Another branch is currently rewriting `draw()`. **Do not assume `self.screen.fill((255, 255, 255))` (line 140) still exists** — it is being replaced by a background blit. Consequences:

- `draw()` is the one guaranteed merge conflict. Land this work *after* #4, or rebase onto it and re-apply the two `draw()` edits (sprite-kind lookup, HUD call) by hand.
- The HUD must be legible over an arbitrary image, not over white. That is exactly why §4a specifies a translucent dark pill with light text rather than the black text the counter currently uses. The counter itself renders `(0, 0, 0)` on line 151 and will have the same legibility problem — #4's business, but worth flagging to that author.
- `_load_poop_images` may also be touched if #4 adds an asset-loading helper; check at rebase time whether a shared loader already exists before adding `_load_sprite`.

---

## 7. Risks and open questions

1. **Does the user want a toy app touching the network at all?** *(needs a decision before coding)* Today `poop.py` is fully offline and deterministic. Adding a poller means outbound HTTPS every 20s for the life of the window. Proposal: default **on**, with `--no-btc` to opt out. The alternative (default off, `--btc` to opt in) is more conservative but makes the feature invisible to anyone who doesn't read the README. This is the one item that should be settled before implementation.
2. **Bitcoin logo licensing.** The orange-circle-₿ mark is widely treated as public domain, but any specific PNG pulled off the web may carry its own terms, and this repo is MIT-licensed. The procedural-draw approach in §4c avoids the question entirely; revisit only if the drawn coin looks bad.
3. **Coupling two unrelated repos.** Vendoring accepts ~25 duplicated lines to avoid a hard path dependency. If the user would rather have one source of truth, the correct fix is for `bitcoin_widget` to grow a `gi`-free core (a `btc_price.py` with plain callbacks/returns and no `GLib.idle_add`) that both projects consume — but that means editing `bitcoin_widget` plus a real packaging story, both out of scope here.
4. **`bitcoin_widget` is not a stable dependency.** No version, no packaging, no `__init__.py`, no tests, and an active refactor history (most recent commit rebuilt the entire popup as a WebKit page). `PriceFetcher.__init__` already grew an optional third callback. Its diag socket is documented as opt-in diagnostics. It is a private, moving module — fine to *read*, wrong to *depend on*.
5. **Endpoint terms and shared rate limits.** Coinbase/Kraken public endpoints are unauthenticated and not documented for third-party polling. At 20s with jitter the load is negligible, but if the tray widget is also running, one IP now polls twice. Both back off independently, so this is a note rather than a problem.
6. **Unverified: does the machine running the game have network when it runs?** Untested here. The offline path in §3 is designed so the answer doesn't matter.
7. **Sprite legibility at 30px.** A procedurally drawn coin with a `B` glyph may read as mush at `SPRITE_SIZE = 30`, especially rotating. Mitigation: draw it at 4× and `smoothscale` down (the same trick the existing loader uses on the 800px source), and consider excluding coins from `rotating` if the spin makes it unreadable.

---

## 8. Phasing

**Phase 1 — ticker only (~90 lines, ships alone).**
`btc_feed.py`, the queue drain in `run()`, the HUD readout, and the green/red change flash. No sprite work, no asset, no gameplay change, `requirements.txt` untouched. Offline behavior is byte-identical to today apart from a dim `BTC ——`. This alone satisfies the issue's second idea ("show when bitcoin is changing price") and is independently reviewable.

**Phase 2 — bitcoin sprites.**
`kind` field, `self.sprites` dict, `_load_sprite` generalization, procedural coin, spawn mix driven by `|change_24h|`. Touches `create_poop` and `draw` only.

**Phase 3 — polish, if wanted.**
Spawn-rate/speed modulation (with the `set_timer` re-arm guard), the diag-socket source adapter as a zero-network alternative, a real PNG coin asset, a small sparkline or trend strip along the bottom edge.

Phase 1 is the natural stopping point if the appetite is small; phases 2-3 are each a single self-contained follow-up.
