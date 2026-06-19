// Pure contact-extraction helpers — ported from runner/tools/web.py::_extract_business_contact_info.
// No external deps so they can be unit-tested offline (node --input-type=module).

const ASSET_RE = /\.(?:png|jpe?g|gif|webp|svg|css|js|ico|woff2?|ttf)$/i;
const EMAIL_DENY = ["example.com", "domain.com", "email.com", "user@", "sentry.io", "wixpress.com"];
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
// US phone; area code can't start 0/1; digit lookarounds stop a longer run yielding an inner match.
const PHONE_RE = /(?<!\d)(?:\+?1[-.\s]?)?\(?([2-9]\d\d)\)?[-.\s]?(\d\d\d)[-.\s]?(\d\d\d\d)(?!\d)/g;
const IG_URL_RE = /(?:https?:\/\/)?(?:www\.)?instagram\.com\/([A-Za-z0-9_.]{3,30})\/?/gi;
const IG_PAREN_RE = /\(@([A-Za-z0-9_.]{3,30})\)/g;
const IG_LABEL_RE = /\b(?:instagram|ig)\b[:\s]+@?([A-Za-z0-9_.]{3,30})/gi;
const FB_RE = /(?:https?:\/\/)?(?:www\.)?facebook\.com\/([A-Za-z0-9.]{3,50})\/?/gi;
const LI_RE = /(?:https?:\/\/)?(?:www\.)?linkedin\.com\/(?:in|company)\/([A-Za-z0-9-]{3,100})\/?/gi;

// IG path/segment noise that is never a real business handle.
const IG_STOPWORDS = new Set([
  "p", "reel", "reels", "tv", "explore", "stories", "story", "accounts", "about", "developer",
  "legal", "privacy", "terms", "directory", "web", "help", "press", "api", "sharer", "share",
  "home", "login", "signup", "emailsignup", "instagram",
]);

function _emails(text) {
  const out = [];
  const seen = new Set();
  for (let e of text.match(EMAIL_RE) || []) {
    e = e.trim().replace(/[,.;:]+$/, "");
    const low = e.toLowerCase();
    if (seen.has(low)) continue;
    const [local, domain = ""] = low.split("@");
    // Glued extractions fuse a zip/phone/word onto the local part (e.g. 01608617-359-6800shop@…);
    // reject leading digit-runs and over-long locals (RFC max 64).
    if (/^\d{5,}/.test(local) || local.length > 64) continue;
    if (ASSET_RE.test(domain)) continue; // hero@2x.png etc.
    if (EMAIL_DENY.some((d) => low.includes(d))) continue;
    seen.add(low);
    out.push(e);
  }
  return out;
}

function _phones(text) {
  const out = [];
  const seen = new Set();
  for (const m of text.matchAll(PHONE_RE)) {
    const f = `(${m[1]}) ${m[2]}-${m[3]}`;
    if (!seen.has(f)) {
      seen.add(f);
      out.push(f);
    }
  }
  return out;
}

function _ig(text, links) {
  const out = [];
  const add = (handle, score) => {
    const h = handle.replace(/^[_.@]+|[_.@]+$/g, "").toLowerCase();
    if (h.length < 3 || h.length > 30 || IG_STOPWORDS.has(h)) return;
    out.push({ score, handle: h });
  };
  for (const src of links || []) for (const m of (src || "").matchAll(IG_URL_RE)) add(m[1], 100);
  for (const m of text.matchAll(IG_URL_RE)) add(m[1], 80);
  for (const m of text.matchAll(IG_PAREN_RE)) add(m[1], 60);
  for (const m of text.matchAll(IG_LABEL_RE)) add(m[1], 40);
  return out;
}

function _grp1(re, text) {
  const out = [];
  // Trim surrounding dots: the FB char class allows '.', so trailing sentence punctuation
  // (facebook.com/Page.) would otherwise be captured into the handle.
  for (const m of text.matchAll(re)) out.push(m[1].replace(/^\.+|\.+$/g, ""));
  return out;
}

// One page's raw (per-page-deduped, uncapped) signals.
export function extractSignals(text, links = []) {
  return {
    emails: _emails(text),
    phones: _phones(text),
    ig: _ig(text, links),
    fb: _grp1(FB_RE, text),
    li: _grp1(LI_RE, text),
  };
}

export function newAcc() {
  return { emails: [], phones: [], ig: [], fb: [], li: [], raw: [], pages: 0, status: "ok" };
}

export function merge(acc, sig) {
  acc.emails.push(...sig.emails);
  acc.phones.push(...sig.phones);
  acc.ig.push(...sig.ig);
  acc.fb.push(...sig.fb);
  acc.li.push(...sig.li);
}

function _uniq(arr, n) {
  const out = [];
  const seen = new Set();
  for (const x of arr) {
    const k = String(x).toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(x);
    if (out.length >= n) break;
  }
  return out;
}

function _igFinal(ig) {
  const best = new Map();
  for (const { score, handle } of ig) {
    if (!best.has(handle) || best.get(handle) < score) best.set(handle, score);
  }
  return [...best.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([h]) => `@${h}`);
}

// Final per-url item — caps 3/2/3/2/2, raw_text 2000; shape consumed verbatim by apify.py::_map_item.
export function finalizeItem(url, acc) {
  let status = acc.status;
  if (acc.pages === 0 && status === "ok") status = "no_pages";
  return {
    url,
    emails: _uniq(acc.emails, 3),
    phones: _uniq(acc.phones, 2),
    instagram_handles: _igFinal(acc.ig),
    facebook_pages: _uniq(acc.fb, 2),
    linkedin_profiles: _uniq(acc.li, 2),
    raw_text: acc.raw.join(" ").slice(0, 2000),
    fetch_status: status,
    pages_fetched: acc.pages,
  };
}
