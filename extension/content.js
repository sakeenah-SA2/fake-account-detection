// content.js — runs on twitter.com / x.com
// Scrapes profile data and triggers auto-prediction on every profile visit

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
  return parts.length >= 1 && !excluded.includes(parts[0]) && parts.length <= 2;
}

function scrapeProfile() {
  const data = {};

  // Screen name
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

  // URL
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
    } catch (e) { data.join_date = joinText; }
  }

  // Followers / following
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

  // Tweet count
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

// ── Auto-predict on page visit ─────────────────────────────────────────────

let lastPath = "";
let autoTimer = null;

function tryAutoPredict() {
  if (!isProfilePage()) return;
  const currentPath = window.location.pathname;
  if (currentPath === lastPath) return;
  lastPath = currentPath;

  // Small delay to let Twitter finish rendering the profile DOM
  clearTimeout(autoTimer);
  autoTimer = setTimeout(() => {
    const data = scrapeProfile();
    if (data.screen_name) {
      // Add estimated values for missing fields (same logic as popup suggest)
      data = addEstimates(data);
      chrome.runtime.sendMessage({ action: "auto_predict", data });
    }
  }, 1800);
}

function addEstimates(data) {
  let accountAgeDays = 1433;
  if (data.join_date) {
    const d = new Date(data.join_date);
    if (!isNaN(d)) {
      accountAgeDays = Math.max(1, Math.floor((new Date() - d) / 86400000));
    }
  }

  const followers = data.followers_count || 0;
  const friends   = data.friends_count   || 0;
  const ratio     = friends > 0 ? followers / friends : 0;

  let score = 0;
  if (ratio > 1)          score++;
  if (ratio > 3)          score++;
  if (data.has_description) score++;
  if (data.has_url)         score++;
  if (data.has_location)    score++;

  const blend = score / 5;

  function lerp(a, b, t) { return a + (b - a) * t; }

  const tweetFreq   = lerp(0.49,  9.18,  blend);
  const favPerTweet = lerp(0.010, 0.678, blend);
  const listedPerF  = lerp(0.011, 0.015, blend);

  if (!data.statuses_count) {
    data.statuses_count = Math.max(1, Math.round(tweetFreq * accountAgeDays));
  }
  if (!data.favourites_count) {
    data.favourites_count = Math.max(0, Math.round((data.statuses_count || 1) * favPerTweet));
  }
  if (!data.listed_count) {
    data.listed_count = Math.max(0, Math.round(followers * listedPerF));
  }

  return data;
}

// Watch for Twitter's SPA URL changes using MutationObserver
const observer = new MutationObserver(() => tryAutoPredict());
observer.observe(document.body, { childList: true, subtree: true });

// Also try immediately on load
tryAutoPredict();

// ── Handle messages from popup ─────────────────────────────────────────────

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