// site-contact-extractor — crawl each business website (home + /contact + /about) and return
// contacts in the exact shape runner/tools/apify.py::_map_item consumes. Extraction logic lives in
// ./extract.js (ported from web.py) so it is dependency-free and unit-testable.
import { Actor } from "apify";
import { CheerioCrawler, Dataset } from "crawlee";

import { extractSignals, newAcc, merge, finalizeItem } from "./extract.js";

await Actor.init();

const input = (await Actor.getInput()) || {};
const urls = (input.urls || []).filter(Boolean);
const maxPagesPerSite = input.maxPagesPerSite ?? 3;
const respectRobots = input.respectRobots ?? true;
const maxConcurrency = input.maxConcurrency ?? 5;

// One accumulator per INPUT url; sub-pages (/contact, /about) merge into their root.
const accs = new Map(urls.map((u) => [u, newAcc()]));
const SUBPAGES = ["/contact", "/about", "/contact-us", "/about-us"];

const crawler = new CheerioCrawler({
  maxConcurrency,
  maxRequestRetries: 1,
  requestHandlerTimeoutSecs: 30,
  respectRobotsTxtFile: respectRobots,
  async requestHandler({ request, $, log }) {
    const root = request.userData.rootUrl;
    const acc = accs.get(root);
    if (!acc) return;

    $("script, style, noscript").remove();
    const text = $("body").text().replace(/\s+/g, " ").trim();
    const links = $("a[href]")
      .map((_, a) => $(a).attr("href"))
      .get();
    // Include hrefs (mailto:, instagram.com/...) in the blob so contact data in attributes is caught.
    const blob = `${text} ${links.join(" ")}`;

    merge(acc, extractSignals(blob, links));
    acc.raw.push(text);
    acc.pages += 1;

    if (request.userData.isRoot && acc.pages < maxPagesPerSite) {
      const reqs = [];
      for (const p of SUBPAGES) {
        if (reqs.length >= maxPagesPerSite - 1) break;
        try {
          reqs.push({ url: new URL(p, root).toString(), userData: { rootUrl: root, isRoot: false } });
        } catch {
          /* skip malformed */
        }
      }
      if (reqs.length) await crawler.addRequests(reqs);
    }
    log.info(`extracted ${request.url} (root=${root})`);
  },
  failedRequestHandler({ request, log }, error) {
    // Only the ROOT failing changes status; a 404 on /contact is normal and must not flip a good site.
    const root = request.userData?.rootUrl;
    const acc = root && accs.get(root);
    if (acc && request.userData?.isRoot) {
      const msg = String(error?.message || "").toLowerCase();
      acc.status = /403|blocked|robots|429/.test(msg) ? "blocked" : "error";
    }
    log.warning(`failed: ${request.url} (${error?.message || error})`);
  },
});

await crawler.addRequests(urls.map((u) => ({ url: u, userData: { rootUrl: u, isRoot: true } })));
await crawler.run();

// Always push exactly one item per input url so the consumer can map every url back.
for (const u of urls) {
  await Dataset.pushData(finalizeItem(u, accs.get(u) || newAcc()));
}

await Actor.exit();
