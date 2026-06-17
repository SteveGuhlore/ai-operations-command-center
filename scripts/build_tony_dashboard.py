#!/usr/bin/env python3
"""
build_tony_dashboard.py
Regenerates dashboard/tony.html from the Tony-standalone.html design artifact.
Run: python3 scripts/build_tony_dashboard.py [--source /path/to/Tony-standalone.html]
"""

import re
import json
import sys
import pathlib
import argparse

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# The approved design artifact is vendored in-repo so the build is reproducible on the VM/CI.
# (Falls back to the original /tmp unzip path if someone is iterating on a fresh export.)
DEFAULT_SOURCE = REPO_ROOT / "dashboard" / "design" / "Tony-standalone.html"
if not DEFAULT_SOURCE.exists():
    DEFAULT_SOURCE = pathlib.Path("/tmp/tony_design_unzip/handoff/Tony-standalone.html")
OUTPUT = REPO_ROOT / "dashboard" / "tony.html"


def patch_report(name: str, count: int, required: bool = True):
    status = "OK" if count > 0 else ("ERROR" if required else "WARN/SIM")
    print(f"  [{status}] {name}: {count} replacement(s)")
    if required and count == 0:
        raise RuntimeError(f"PRIORITY anchor missing: {name}")


def fmt_horizon(horizon_days) -> str:
    """Format horizonDays [lo, hi] as '8–12d', or '—' if null."""
    if not horizon_days or len(horizon_days) < 2:
        return "—"
    lo, hi = horizon_days[0], horizon_days[1]
    if lo is None or hi is None:
        return "—"
    return f"{lo}–{hi}d"


def build(source_path: pathlib.Path, output_path: pathlib.Path):
    print(f"Source : {source_path}")
    print(f"Output : {output_path}")

    src = source_path.read_text(encoding="utf-8")

    # ---- extract bundler template block ----
    tpl_match = re.search(
        r'(<script\b[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)',
        src,
        re.S,
    )
    if not tpl_match:
        raise RuntimeError(
            "Could not find <script type='__bundler/template'> in source"
        )

    tag_open = tpl_match.group(1)
    tpl_raw = tpl_match.group(2)
    tag_close = tpl_match.group(3)

    # The template script is a RAW-TEXT element holding a JSON-encoded string (literal <, &;
    # newlines as \n). Do NOT html.unescape/escape it — that decodes embedded &quot;/&amp;
    # (closing the JSON string early -> "non-whitespace after JSON") and re-escapes < to &lt;,
    # corrupting the bundle. Patch the raw text directly.
    tpl = tpl_raw
    print(f"\nTemplate extracted: {len(tpl)} chars (raw)")
    print("\n=== Applying patches ===")

    # ================================================================
    # PRIORITY A1: TONY_FEED script injection in outer <head>
    # ================================================================
    tony_feed_script = (
        "<script>window.TONY_FEED={"
        "proxyUrl:'/api/spx',"
        "marksUrl:'/api/marks',"
        "proxyName:'cc-vm'"
        "};</script>"
    )
    # Inject right after the first <head...> tag in the OUTER document
    outer_head_match = re.search(r"<head[^>]*>", src)
    if not outer_head_match:
        raise RuntimeError("PRIORITY-A1: <head> not found in outer document")
    inject_pos = outer_head_match.end()
    src = src[:inject_pos] + "\n  " + tony_feed_script + src[inject_pos:]
    # Recalculate tpl_match positions in the modified src (do template work on tpl separately)
    a1_count = src.count("window.TONY_FEED")
    patch_report("A1 TONY_FEED inject", a1_count, required=True)

    # ================================================================
    # PRIORITY A2a: updateMarks — guard with marksUrl proxy
    # ================================================================
    OLD_A2A = "if (!cfg.alpacaKey || !cfg.alpacaSecret) return;"
    NEW_A2A = "if (!cfg.marksUrl && (!cfg.alpacaKey || !cfg.alpacaSecret)) return;"
    count_a2a = tpl.count(OLD_A2A)
    tpl = tpl.replace(OLD_A2A, NEW_A2A)
    patch_report("A2a marksUrl guard", count_a2a, required=True)

    # ================================================================
    # PRIORITY A2b: updateMarks — proxy-aware fetch
    # ================================================================
    # The JS is minified with literal \n (backslash-n, 2 chars) between statements,
    # not real newlines, so we must use \\n in the Python string.
    OLD_A2B = (
        "const url = 'https://data.alpaca.markets/v2/stocks/trades/latest?symbols=' + syms + '&feed=iex';\\n"
        "      const r = await fetch(url, { headers:{ 'APCA-API-KEY-ID':cfg.alpacaKey, 'APCA-API-SECRET-KEY':cfg.alpacaSecret } });"
    )
    NEW_A2B = (
        "const url = cfg.marksUrl ? (cfg.marksUrl + '?syms=' + encodeURIComponent(syms)) : ('https://data.alpaca.markets/v2/stocks/trades/latest?symbols=' + syms + '&feed=iex');\\n"
        "      const r = await fetch(url, cfg.marksUrl ? {} : { headers:{ 'APCA-API-KEY-ID':cfg.alpacaKey, 'APCA-API-SECRET-KEY':cfg.alpacaSecret } });"
    )
    count_a2b = tpl.count(OLD_A2B)
    tpl = tpl.replace(OLD_A2B, NEW_A2B)
    patch_report("A2b proxy-aware fetch", count_a2b, required=True)

    # ================================================================
    # PRIORITY B1: _hydrateLive method (insert before async initFeed)
    # ================================================================
    # buildChart signature: buildChart(dates, tony, bot, index, label)
    # The '2wk' chart call: buildChart([labels], [tony], [bot], [index], '2 wks')
    # We match that: buildChart(labels, tony_arr, bot_arr, index_arr, label)
    # For hydration we use the same 4-array + label form:
    #   buildChart(labels, tony, bot, bot (as index proxy), '2 wks')
    # NOTE: the live feed returns equity.labels, equity.tony, equity.bot
    # We pass bot as the 4th (index) arg since we lack a real SPY series there.

    HYDRATE_METHOD = r"""
  async _hydrateLive(){
    let json;
    try {
      const res = await fetch('/api/tony/live');
      if (!res.ok) return;
      json = await res.json();
    } catch(e) { return; }
    if (!json || json.status === 'error') return;
    this.live = json;  // for _patchStatics (masthead + 2nd-pass quadrant)
    // Per-section hydration — EACH block guarded so one failure can't abort the others, and
    // crucially can't skip the forceUpdate() that paints the live data onto the page.
    try {
      if (json.book && json.book.length) {
        this.book = json.book.map(function(b){
          return { sym:b.sym, qty:String(b.qty), entry:String(b.entry), last:String(b.last), unreal:String(b.unreal), up:!!b.up };
        });
      }
    } catch(e) {}
    try {
      if (json.calls && json.calls.length) {
        this.calls = json.calls.map(function(c){
          return { sym:c.sym, verb:c.verb, note:c.note, time:c.time, day:c.day, grade:c.grade };
        });
      }
    } catch(e) {}
    try {
      if (json.projections) {
        const self = this;
        Object.keys(json.projections).forEach(function(sym){
          if (!self.tickers[sym]) return;
          const proj = json.projections[sym];
          self.tickers[sym].projection = proj;
          if (proj.target != null) self.tickers[sym].targetLvl = proj.target;
          self.tickers[sym].horizon = (function(hd){
            if (!hd || hd.length < 2 || hd[0] == null || hd[1] == null) return '—';
            return hd[0] + '–' + hd[1] + 'd';
          })(proj.horizonDays);
          self.enrich(self.tickers[sym]);
        });
      }
    } catch(e) {}
    // Honesty pass: the artifact ships a fixed SIM ticker universe (AXON/DHR/…) that collides
    // with real positions. Clear their baked verdict/bracket unless a REAL projection exists,
    // so a live position never shows a Tony call he didn't actually make today.
    try {
      const projs = json.projections || {};
      const selfN = this;
      Object.keys(this.tickers).forEach(function(sym){
        if (projs[sym]) return;
        const t = selfN.tickers[sym];
        if (!t) return;
        if (t.tony) t.tony.verb = '';
        t.verb = ''; t.stop = ''; t.target = ''; t.rmult = ''; t.targetGap = ''; t.horizon = '—';
      });
    } catch(e) {}
    try {
      const eq = json.equity;
      if (eq && eq.tony && eq.tony.length && eq.bot && eq.bot.length) {
        // Live curve is normalized-to-100; buildChart wants percent-from-base, so subtract 100.
        // Downsample (index-based, equal length) and feed ALL ranges (only ~10 days exist).
        const N = eq.tony.length, step = Math.max(1, Math.floor(N/60));
        const ds = function(a){ if(!a||!a.length) return []; const o=[]; for(let i=0;i<a.length;i+=step) o.push(a[i]); if((a.length-1)%step!==0) o.push(a[a.length-1]); return o; };
        const pct = function(a){ return ds(a).map(function(v){ return +(v-100).toFixed(2); }); };
        const labs = ds(eq.labels).map(function(t){ try{ const d=new Date(t); return (d.getMonth()+1)+'/'+d.getDate(); }catch(e){ return ''; } });
        const tonyP = pct(eq.tony), botP = pct(eq.bot);
        const self2 = this;
        const mk = function(lbl){ return self2.buildChart(labs, tonyP, botP, botP, lbl); };
        this.charts['2wk'] = mk('2 wks');
        this.charts['1mo'] = mk('1 mo');
        this.charts['inception'] = mk('since inception');
      }
    } catch(e) {}
    try { this.forceUpdate(); } catch(e) {}
    setTimeout(()=>{ try{ this._patchStatics(); }catch(e){} }, 60);
  }

  _patchStatics(){
    // Post-render DOM patch for the masthead aggregates + the "Does the 2nd pass help?"
    // quadrant, which the design artifact renders as static HTML (no template-literal seam).
    // Only override SIM when we genuinely have graded outcomes (status 'scored'); otherwise
    // leave the illustrative SIM numbers rather than wipe the panel to misleading zeros.
    try {
      const L = this.live;
      if (!L || L.status !== 'scored') return;
      const setByLabel = (label, value, fmt) => {
        if (value == null) return;
        const nodes = document.querySelectorAll('div');
        for (let i=0;i<nodes.length;i++){
          const t = nodes[i].textContent;
          if (t && t.trim() === label){
            const n = nodes[i].previousElementSibling;
            if (n) n.textContent = fmt ? fmt(value) : String(value);
            return;
          }
        }
      };
      const q = L.quadrant || {};
      setByLabel('agreed · right', q.agreed_right);
      setByLabel('agreed · wrong', q.agreed_wrong);
      setByLabel('tony saved', q.tony_saved);
      setByLabel('tony missed', q.tony_missed);
      const s = L.stats || {};
      setByLabel('Call accuracy', s.call_accuracy_pct, v => Math.round(v<=1 ? v*100 : v) + '%');
      setByLabel('Graded calls', s.graded);
      setByLabel('Open positions', s.open_positions);
      if (s.equity != null) {
        const eqNode = document.querySelector('[data-count][data-prefix="$"]');
        if (eqNode) eqNode.textContent = '$' + Math.round(s.equity).toLocaleString();
      }
      const cal = L.calibration || {};
      const pctFmt = function(v){ return Math.round(v <= 1 ? v * 100 : v) + '%'; };
      setByLabel('low conf', cal.low, pctFmt);
      setByLabel('med conf', cal.medium, pctFmt);
      setByLabel('high conf', cal.high, pctFmt);
    } catch(e) {
      // swallow — leave SIM values in place
    }
  }

"""

    INITFEED_ANCHOR = "async initFeed(){"
    count_b1 = tpl.count(INITFEED_ANCHOR)
    # The template is a JSON string, so the inserted method must be JSON-escaped (real
    # newlines -> \n, quotes/unicode handled) — json.dumps(...)[1:-1] is the escaped inner text.
    method_encoded = json.dumps(HYDRATE_METHOD)[1:-1]
    tpl = tpl.replace(INITFEED_ANCHOR, method_encoded + "  " + INITFEED_ANCHOR, 1)
    patch_report("B1 _hydrateLive method insert", count_b1, required=True)

    # ================================================================
    # PRIORITY B2a: call _hydrateLive at end of constructor
    # ================================================================
    # Constructor ends just before verbColor — use sectors array close as anchor
    # JS is minified with literal \n (backslash-n) between statements — use \\n in Python
    CONS_END_ANCHOR = (
        "{ name:'Cons. disc.', pct:1, col:'#7e8a82' }\\n    ];\\n  }\\n\\n  verbColor"
    )
    CONS_END_REPLACE = "{ name:'Cons. disc.', pct:1, col:'#7e8a82' }\\n    ];\\n    this._hydrateLive();\\n  }\\n\\n  verbColor"
    count_b2a = tpl.count(CONS_END_ANCHOR)
    tpl = tpl.replace(CONS_END_ANCHOR, CONS_END_REPLACE)
    patch_report("B2a _hydrateLive() at end of constructor", count_b2a, required=True)

    # ================================================================
    # PRIORITY B2b: setInterval for _hydrateLive in componentDidMount
    # ================================================================
    MOUNT_ANCHOR = "this.initFeed();\\n    this._feed = setInterval(()=>this.initFeed(), 60000);\\n  }"
    MOUNT_REPLACE = "this.initFeed();\\n    this._feed = setInterval(()=>this.initFeed(), 60000);\\n    this._liveFeed = setInterval(()=>this._hydrateLive(), 60000);\\n    this._statics = setInterval(()=>this._patchStatics(), 5000);\\n  }"
    count_b2b = tpl.count(MOUNT_ANCHOR)
    tpl = tpl.replace(MOUNT_ANCHOR, MOUNT_REPLACE)
    patch_report(
        "B2b setInterval _hydrateLive in componentDidMount", count_b2b, required=True
    )

    # ================================================================
    # B3: paper-book render must tolerate LIVE symbols absent from the SIM tickers map.
    # renderVals maps this.book through this.tickers[b.sym] for decorations (name, spark,
    # target/stop, horizon); a real Alpaca position whose symbol isn't a SIM ticker made
    # `t` undefined -> "Cannot read properties of undefined (reading 'name')". Guard with a
    # complete default so the row still shows the live b.* fields (sym/qty/entry/last/unreal).
    # ================================================================
    OLD_B3 = "const t = this.tickers[b.sym]; return {"
    NEW_B3 = (
        "const t = this.tickers[b.sym] || { name:b.sym, stop:'', target:'', rmult:'', "
        "rCol:'#7e8a82', tony:{verb:''}, verbCol:'#7e8a82', day:'', dayCol:'#7e8a82', "
        "sparkPts:'', sparkArea:'', sparkColor:'#37e0ff', targetGap:'', targetGapCol:'#7e8a82', "
        "horizon:'—' }; return {"
    )
    count_b3 = tpl.count(OLD_B3)
    tpl = tpl.replace(OLD_B3, NEW_B3)
    patch_report("B3 book render tolerates live symbols", count_b3, required=True)

    # ================================================================
    # B4: updateMarks parses b.entry for P&L but only strips commas, not the '$' our live rows
    # carry ("$185.55") -> parseFloat NaN -> "Unreal −NaN" on the bracketed positions. Strip $ too.
    # ================================================================
    OLD_B4 = "parseFloat(String(b.entry).replace(/,/g,''))"
    NEW_B4 = "parseFloat(String(b.entry).replace(/[$,]/g,''))"
    count_b4 = tpl.count(OLD_B4)
    tpl = tpl.replace(OLD_B4, NEW_B4)
    patch_report("B4 updateMarks strips $ from entry", count_b4, required=True)

    # ================================================================
    # PRIORITY C: masthead aggregates — NO template literals found (0 backticks)
    # The HTML is static markup in the template, not a JS template-literal render.
    # Priority C panels are LEFT AS SIM — reporting below.
    # ================================================================
    print("\n=== Priority C (post-render DOM patch via _patchStatics) ===")
    print(
        "  [LIVE] quadrant (agreed·right/wrong, tony saved/missed) + Call accuracy / Graded calls /"
    )
    print(
        "         Open positions — patched from /api/tony/live by label, ONLY when status=='scored'"
    )
    print(
        "         (else SIM baked values kept, re-applied every 5s to survive re-renders)."
    )
    print(
        "  [SIM]  Avg outcome (R) and calibration buckets — left SIM (no clean live metric yet)."
    )

    # ================================================================
    # Re-escape tpl and splice back into the template block in the source
    # ================================================================
    # Raw-text JSON string: splice the patched template back verbatim, NO entity escaping.
    new_block = tag_open + tpl + tag_close

    # Replace the original bundler block in the (already A1-patched) src.
    # Use a split/join approach instead of re.sub so the replacement string is
    # treated literally (new_block may contain \u sequences that re.sub would
    # misinterpret as regex escapes).
    m2 = re.search(
        r'<script\b[^>]*type="__bundler/template"[^>]*>.*?</script>',
        src,
        re.S,
    )
    if not m2:
        raise RuntimeError("Could not re-locate bundler script block for splice-back")
    new_src = src[: m2.start()] + new_block + src[m2.end() :]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(new_src, encoding="utf-8")

    size = output_path.stat().st_size
    print(f"\n=== Output ===")
    print(f"  Written: {output_path}")
    print(f"  Size   : {size:,} bytes")

    # Quick assertions
    content = output_path.read_text(encoding="utf-8")
    assert "window.TONY_FEED" in content, "ASSERT FAIL: window.TONY_FEED missing"
    assert "marksUrl" in content, "ASSERT FAIL: marksUrl missing"
    assert "_hydrateLive" in content, "ASSERT FAIL: _hydrateLive missing"
    assert content.lower().count("research simulation") >= 1, (
        "ASSERT FAIL: disclaimer missing"
    )
    print(
        "  Assertions: window.TONY_FEED OK | marksUrl OK | _hydrateLive OK | disclaimer OK"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build dashboard/tony.html from design artifact"
    )
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.source, args.output)
