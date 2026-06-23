// Offline unit test for the extraction logic (no network, no Apify/Crawlee). Run: node test/extract.test.mjs
import { extractSignals, newAcc, merge, finalizeItem } from "../src/extract.js";

let failures = 0;
const ok = (cond, msg) => {
  console.log(`${cond ? "ok  " : "FAIL"} - ${msg}`);
  if (!cond) failures += 1;
};

const text =
  "Call us at (617) 555-0142 or email Info@AcmePlumbing.com. " +
  "Follow https://www.instagram.com/acmeplumbing/ and facebook.com/AcmePlumbingMA. " +
  "Logo hero@2x.png. Spam john@example.com. Bad area code (123) 555-0000.";
const links = ["mailto:info@acmeplumbing.com", "https://instagram.com/acmeplumbing/"];

const acc = newAcc();
merge(acc, extractSignals(`${text} ${links.join(" ")}`, links));
acc.raw.push(text);
acc.pages = 1;
const item = finalizeItem("https://acmeplumbing.com", acc);

const WANT_KEYS = [
  "url", "emails", "phones", "instagram_handles", "facebook_pages",
  "linkedin_profiles", "raw_text", "fetch_status", "pages_fetched",
];
ok(WANT_KEYS.every((k) => k in item), "item has the 9 contract keys");
ok(item.emails.includes("Info@AcmePlumbing.com") || item.emails.includes("info@acmeplumbing.com"),
   "real email captured");
ok(!item.emails.some((e) => e.toLowerCase().includes("hero@2x.png")), "asset 'email' filtered");
ok(!item.emails.some((e) => e.toLowerCase().includes("example.com")), "denylisted email filtered");
ok(item.emails.length === 1, `emails deduped to one (got ${JSON.stringify(item.emails)})`);
ok(item.phones.includes("(617) 555-0142"), "valid US phone formatted");
ok(!item.phones.includes("(123) 555-0000"), "area code starting 1 rejected");
ok(item.instagram_handles[0] === "@acmeplumbing", "IG handle ranked from URL");
ok(item.facebook_pages.includes("AcmePlumbingMA"), "facebook page captured");
ok(item.raw_text.length <= 2000, "raw_text capped at 2000");
ok(item.fetch_status === "ok" && item.pages_fetched === 1, "status ok / pages counted");

// Never-fetched url -> one item, empty lists, no_pages.
const empty = finalizeItem("https://nope.example", newAcc());
ok(empty.fetch_status === "no_pages" && empty.emails.length === 0, "unfetched url -> no_pages, empty");

// Glued local-part: a zip/phone fused onto the address is dropped, but a clean address in the
// same blob survives (regression for the greedy email local-part class).
const glued = extractSignals("zip 01608617-359-6800shop@gmail.com or shop@gmail.com").emails;
ok(!glued.some((e) => e.toLowerCase().startsWith("01608")), "glued digit-run email dropped");
ok(glued.includes("shop@gmail.com"), "clean email kept alongside glued one");

// Over-long local part (RFC 5321 64-char ceiling) dropped.
const longLocal = `${"a".repeat(65)}@gmail.com`;
ok(extractSignals(`contact ${longLocal}`).emails.length === 0, "over-64-char local part dropped");

console.log(failures ? `\n${failures} FAILURE(S)` : "\nALL PASS");
process.exit(failures ? 1 : 0);
