// content.js — runs on twitter.com / x.com
// Auto-scrapes, estimates missing values, and triggers prediction on every profile visit

// ── Helpers ───────────────────────────────────────────────────────────────

function parseCount(text) {
  if (!text) return 0;
  const clean = text.replace(/,/g, "").trim();
  if (clean.toUpperCase().endsWith("K")) return Math.round(parseFloat(clean) * 1000);
  if (clean.toUpperCase().endsWith("M")) return Math.round(parseFloat(clean) * 1000000);
  if (clean.toUpperCase().endsWith("B")) return Math.round(parseFloat(clean) * 1000000000);
  return parseInt(clean) || 0;
}

function isCountText(text) {
  return /^[\d,]+\.?\d*[KMBkmb]?$/.test(text.trim());
}

// Pull a numeric count out of an element, trying the most reliable source first.
function extractCount(el) {
  if (!el) return 0;

  // 1. Exact value from a title attribute — X puts the full number here when it
  //    abbreviates the visible text (shows "1.2M", title="1,234,567").
  for (const titled of el.querySelectorAll('[title]')) {
    const t = (titled.getAttribute('title') || '').replace(/\s/g, '');
    if (isCountText(t)) {
      const v = parseCount(t);
      if (v > 0) return v;
    }
  }

  // 2. First span whose text is a clean standalone count.
  for (const span of el.querySelectorAll('span')) {
    const text = (span.textContent || '').trim();
    if (isCountText(text)) {
      const v = parseCount(text);
      if (v > 0) return v;
    }
  }

  // 3. Leading number in the element's full text ("1,234 Followers").
  const m = (el.textContent || '').trim().match(/^[\d.,]+\s*[KMBkmb]?/);
  if (m) {
    const v = parseCount(m[0].replace(/\s/g, ''));
    if (v > 0) return v;
  }

  return 0;
}

function isProfilePage() {
  const excluded = ["home", "explore", "notifications", "messages", "i", "settings", "search"];
  const parts    = window.location.pathname.split("/").filter(Boolean);
  return parts.length >= 1 && parts.length <= 2 && !excluded.includes(parts[0]);
}

// ── New X layout helpers (class-based, no data-testid) ─────────────────────
// The newer profile DOM drops data-testid and instead marks each metadata field
// with an <svg data-icon="..."> next to the value, plus a dir="auto" bio div.
// We anchor on the Following/Followers links (stable hrefs) to scope the search
// to the profile card and avoid matching tweet/bio content elsewhere.

function findProfileCard() {
  const followLink = document.querySelector(
    'a[href$="/following"], a[href$="/followers"], a[href$="/verified_followers"]'
  );
  const row = followLink && followLink.parentElement;       // Following/Followers row
  return (row && row.parentElement) || null;                // the profile card
}

// Text shown next to a metadata icon, e.g. "Netherlands" or "Joined October 2017".
function textBesideIcon(root, iconSelector) {
  const icon = (root || document).querySelector(iconSelector);
  const item = icon && icon.parentElement;                  // <div class="flex items-center gap-1">
  return item ? (item.textContent || "").trim() : "";
}

// The <a> shown next to a metadata icon (the dedicated website field).
function linkBesideIcon(root, iconSelector) {
  const icon = (root || document).querySelector(iconSelector);
  const item = icon && icon.parentElement;
  return item ? item.querySelector('a[href]') : null;
}

// Display name in the new layout: the leaf text block that isn't the @handle.
function findDisplayName(card, screenName) {
  const handle = ("@" + screenName).toLowerCase();
  let handleEl = null;
  for (const el of card.querySelectorAll('div')) {
    if (el.children.length === 0 && (el.textContent || '').trim().toLowerCase() === handle) {
      handleEl = el; break;
    }
  }
  const wrapper = handleEl && handleEl.parentElement && handleEl.parentElement.parentElement;
  if (!wrapper) return "";
  for (const d of wrapper.querySelectorAll('div')) {
    const t = (d.textContent || '').trim();
    if (t && d.children.length === 0 && t.toLowerCase() !== handle) return t;
  }
  return "";
}

// ── Scrape visible profile data ───────────────────────────────────────────

function scrapeProfile() {
  const data = {};

  // Screen name from URL
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length > 0) data.screen_name = parts[0];

  // Profile header card — scope fallbacks here to avoid matching bio/tweet text.
  // Classic layout exposes a testid; the new layout is found via the follow links.
  const headerItems = document.querySelector('[data-testid="UserProfileHeader_Items"]');
  const card        = findProfileCard();

  // Display name — testid first, then the new-layout name block.
  const nameEl = document.querySelector('[data-testid="UserName"] span span');
  if (nameEl) {
    data.name = nameEl.innerText.trim();
  } else if (card && data.screen_name) {
    data.name = findDisplayName(card, data.screen_name) || data.name;
  }

  // Bio — testid first, then the dir="auto" bio div inside the profile card.
  let bioEl = document.querySelector('[data-testid="UserDescription"]');
  if (!bioEl && card) bioEl = card.querySelector(':scope > div[dir="auto"]');
  data.has_description = !!(bioEl && bioEl.textContent.trim().length > 0);

  // Location — testid first, then text beside the location icon.
  const locEl = document.querySelector('[data-testid="UserLocation"]');
  const locText = locEl ? locEl.textContent.trim()
                        : textBesideIcon(card, 'svg[data-icon^="icon-location"]');
  data.has_location = !!locText;

  // Website URL — testid, then the link beside the link icon, then any external
  // link in the classic header card. (Bio links are excluded by using the icon.)
  let urlEl = document.querySelector('[data-testid="UserUrl"]');
  if (!urlEl) urlEl = linkBesideIcon(card, 'svg[data-icon^="icon-link"]');
  if (!urlEl && headerItems) {
    urlEl = headerItems.querySelector('a[href^="https://t.co/"], a[href^="http"][target="_blank"]');
  }
  data.has_url = !!urlEl;

  // Join date — testid, then text beside the calendar icon, then any
  // "Joined <Month> <Year>" text in the header.
  let joinText = "";
  const joinEl = document.querySelector('[data-testid="UserJoinDate"]');
  if (joinEl) {
    joinText = joinEl.textContent;
  } else {
    joinText = textBesideIcon(card, 'svg[data-icon^="icon-calendar"]');
  }
  if (!/Joined/i.test(joinText)) {
    const scope = card || headerItems || document.querySelector('[data-testid="primaryColumn"]') || document.body;
    for (const el of scope.querySelectorAll('span, div')) {
      const t = (el.textContent || '').trim();
      if (/^Joined\s+[A-Za-z]+\s+\d{4}$/.test(t)) { joinText = t; break; }
    }
  }
  if (joinText) {
    const clean = joinText.replace(/Joined/i, "").trim();
    const d = new Date(clean);
    data.join_date = isNaN(d) ? clean : d.toISOString().split("T")[0];
  }

  // Followers / following — match the header links by their href.
  // X uses /following and /followers (or /verified_followers).
  const allLinks = document.querySelectorAll('a[href]');
  allLinks.forEach(link => {
    const href        = link.getAttribute('href') || '';
    const isFollowing = /\/following\/?$/.test(href);
    const isFollowers = /\/(verified_)?followers\/?$/.test(href);
    if (!isFollowing && !isFollowers) return;

    const val = extractCount(link);
    if (val > 0) {
      if (isFollowing && !data.friends_count)   data.friends_count   = val;
      if (isFollowers && !data.followers_count) data.followers_count = val;
    }
  });

  // Tweet / post count — shown in the header as "1,234 posts".
  const primary = document.querySelector('[data-testid="primaryColumn"]') || document.body;
  for (const el of primary.querySelectorAll('div, span')) {
    const t = (el.textContent || '').trim();
    const m = t.match(/^([\d.,]+\s*[KMBkmb]?)\s*posts?$/i);
    if (m) {
      const val = parseCount(m[1].replace(/\s/g, ''));
      if (val > 0) { data.statuses_count = val; break; }
    }
  }

  // Fallback selectors if the "X posts" label wasn't found.
  if (!data.statuses_count) {
    const postSelectors = [
      '[data-testid="primaryColumn"] h2 + div span',
      '[data-testid="primaryColumn"] h2 ~ div span',
      'div[aria-label*="posts"] span',
      'div[aria-label*="Posts"] span',
    ];
    for (const sel of postSelectors) {
      const el = document.querySelector(sel);
      if (el) {
        const val = parseCount(el.innerText.trim());
        if (val > 0) { data.statuses_count = val; break; }
      }
    }
  }

  return data;
}

// ── Estimate missing fields from scraped signals ──────────────────────────
// Based on dataset averages:
// Real: tweet_freq=9.18/day, fav_per_tweet=0.678, listed_per_follower=0.015
// Fake: tweet_freq=0.49/day, fav_per_tweet=0.010, listed_per_follower=0.011

function addEstimates(data) {
  // Work on a copy so we never mutate the original
  const d = Object.assign({}, data);

  // Account age in days
  let accountAgeDays = 1433; // dataset median fallback
  if (d.join_date) {
    const created = new Date(d.join_date);
    if (!isNaN(created)) {
      accountAgeDays = Math.max(1, Math.floor((Date.now() - created.getTime()) / 86400000));
    }
  }

  // Legitimacy score 0–5 from signals we can see
  const followers = d.followers_count || 0;
  const friends   = d.friends_count   || 0;
  const ratio     = friends > 0 ? followers / friends : 0;

  let score = 0;
  if (ratio > 1)        score++;
  if (ratio > 3)        score++;
  if (d.has_description) score++;
  if (d.has_url)         score++;
  if (d.has_location)    score++;

  // Blend between fake and real averages
  const blend = score / 5;
  function lerp(a, b, t) { return a + (b - a) * t; }

  const tweetFreq   = lerp(0.49,  9.18,  blend);
  const favPerTweet = lerp(0.010, 0.678, blend);
  const listedPerF  = lerp(0.011, 0.015, blend);

  // Only estimate what wasn't scraped
  if (!d.statuses_count || d.statuses_count === 0) {
    d.statuses_count = Math.max(1, Math.round(tweetFreq * accountAgeDays));
  }

  if (!d.favourites_count || d.favourites_count === 0) {
    d.favourites_count = Math.max(0, Math.round(d.statuses_count * favPerTweet));
  }

  if (!d.listed_count || d.listed_count === 0) {
    d.listed_count = Math.max(0, Math.round(followers * listedPerF));
  }

  return d;
}

// ── Auto-predict on profile visit ─────────────────────────────────────────

let lastPath  = "";
let autoTimer = null;

function tryAutoPredict() {
  if (!isProfilePage()) return;

  const currentPath = window.location.pathname;
  if (currentPath === lastPath) return;
  lastPath = currentPath;

  // Wait for Twitter to finish rendering the profile DOM
  clearTimeout(autoTimer);
  autoTimer = setTimeout(() => {
    const raw       = scrapeProfile();
    const estimated = addEstimates(raw); // use let-equivalent via new object

    if (estimated.screen_name) {
      chrome.runtime.sendMessage({
        action: "auto_predict",
        data:   estimated
      });
    }
  }, 1800);
}

// ── Watch for Twitter SPA navigation ──────────────────────────────────────
// Twitter uses the History API so we need multiple detection strategies

// 1. MutationObserver — catches DOM changes when Twitter renders new content
const observer = new MutationObserver(() => tryAutoPredict());
observer.observe(document.body, { childList: true, subtree: true });

// 2. URL polling — catches History API pushState/replaceState that MutationObserver misses
setInterval(tryAutoPredict, 1000);

// 3. popstate — catches browser back/forward navigation
window.addEventListener("popstate", tryAutoPredict);

// 4. Run immediately in case the page is already a profile on load
tryAutoPredict();

// ── Handle manual scrape request from popup ────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "scrape") {
    try {
      sendResponse(scrapeProfile());
    } catch (err) {
      sendResponse({ error: err.message });
    }
  }
  return true;
});