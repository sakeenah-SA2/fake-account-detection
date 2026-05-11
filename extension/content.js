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

function isProfilePage() {
  const excluded = ["home", "explore", "notifications", "messages", "i", "settings", "search"];
  const parts    = window.location.pathname.split("/").filter(Boolean);
  return parts.length >= 1 && parts.length <= 2 && !excluded.includes(parts[0]);
}

// ── Scrape visible profile data ───────────────────────────────────────────

function scrapeProfile() {
  const data = {};

  // Screen name from URL
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length > 0) data.screen_name = parts[0];

  // Display name
  const nameEl = document.querySelector('[data-testid="UserName"] span span');
  if (nameEl) data.name = nameEl.innerText.trim();

  // Bio
  const bioEl = document.querySelector('[data-testid="UserDescription"]');
  data.has_description = !!(bioEl && bioEl.innerText.trim().length > 0);

  // Location
  const locEl = document.querySelector('[data-testid="UserLocation"]');
  data.has_location = !!(locEl && locEl.innerText.trim().length > 0);

  // Website URL
  const urlEl = document.querySelector('[data-testid="UserUrl"]');
  data.has_url = !!urlEl;

  // Join date
  const joinEl = document.querySelector('[data-testid="UserJoinDate"]');
  if (joinEl) {
    const joinText = joinEl.innerText.replace("Joined", "").trim();
    try {
      const d = new Date(joinText);
      if (!isNaN(d)) data.join_date = d.toISOString().split("T")[0];
      else data.join_date = joinText;
    } catch (e) {
      data.join_date = joinText;
    }
  }

  // Followers / following — only accept pure count spans
  const allLinks = document.querySelectorAll('a[href]');
  allLinks.forEach(link => {
    const href        = link.getAttribute('href') || '';
    const isFollowing = href.endsWith('/following');
    const isFollowers = href.endsWith('/followers') || href.endsWith('/verified_followers');
    if (!isFollowing && !isFollowers) return;

    const spans = link.querySelectorAll('span');
    for (const span of spans) {
      const text = span.innerText.trim();
      if (isCountText(text)) {
        const val = parseCount(text);
        if (val > 0) {
          if (isFollowing) data.friends_count  = val;
          if (isFollowers) data.followers_count = val;
          break;
        }
      }
    }
  });

  // Tweet / post count
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