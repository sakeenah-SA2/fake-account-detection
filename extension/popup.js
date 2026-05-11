// popup.js

const FLASK_URL = "http://127.0.0.1:5000/predict-json";
let screenName = "";
let currentTabId = null;

document.addEventListener("DOMContentLoaded", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url   = tab.url || "";
  currentTabId = tab.id;

  const isTwitter = url.includes("twitter.com/") || url.includes("x.com/");
  const excluded  = ["home", "explore", "notifications", "messages", "i", "settings"];
  const parts     = new URL(url).pathname.split("/").filter(Boolean);
  const isProfile = isTwitter && parts.length >= 1 && !excluded.includes(parts[0]);

  if (!isProfile) {
    document.getElementById("not-twitter").style.display = "block";
    return;
  }

  document.getElementById("main").style.display = "block";
  document.getElementById("status").textContent = "Loading…";

  // Check if background already has a cached result
  chrome.runtime.sendMessage({ action: "get_cached", tabId: tab.id }, cached => {
    if (cached && cached.result) {
      populateFromScrape(cached.data || {});
      showResult(cached.result);
      document.getElementById("status").textContent = "Done";
    } else if (cached && cached.error) {
      document.getElementById("status").textContent = "Flask offline";
      showError("Cannot reach Flask server. Make sure it is running on http://127.0.0.1:5000");
    } else {
      // No cached result yet — scrape and show form
      document.getElementById("status").textContent = "Scraping…";
      chrome.tabs.sendMessage(tab.id, { action: "scrape" }, data => {
        if (data) populateFromScrape(data);
        document.getElementById("status").textContent = "Ready";
      });
    }
  });

  // Listen for prediction result from background (in case it finishes while popup is open)
  chrome.runtime.onMessage.addListener(msg => {
    if (msg.action === "prediction_ready" && msg.tabId === tab.id) {
      showResult(msg.result);
      document.getElementById("status").textContent = "Done";
    }
  });

  document.getElementById("suggest-btn").addEventListener("click", suggestMissing);
  document.getElementById("analyse-btn").addEventListener("click", runManualPredict);
});


// ── Populate form ─────────────────────────────────────────────────────────

function populateFromScrape(data) {
  screenName = data.screen_name || "";
  document.getElementById("screen-name-label").textContent = `@${screenName}`;

  function setField(id, value, badgeId) {
    if (value !== undefined && value !== null && value !== 0) {
      document.getElementById(id).value = value;
      if (badgeId) document.getElementById(badgeId).style.display = "inline";
    }
  }

  setField("followers_count", data.followers_count, "fol-badge");
  setField("friends_count",   data.friends_count,   "fri-badge");
  setField("statuses_count",  data.statuses_count,  "stat-badge");

  if (data.has_description) document.getElementById("has_description").checked = true;
  if (data.has_location)    document.getElementById("has_location").checked    = true;
  if (data.has_url)         document.getElementById("has_url").checked         = true;
  if (data.join_date)       document.getElementById("created_at").value        = data.join_date;
}


// ── Suggest missing values ────────────────────────────────────────────────

function suggestMissing() {
  const followers = parseInt(document.getElementById("followers_count").value) || 0;
  const friends   = parseInt(document.getElementById("friends_count").value)   || 0;
  const statuses  = parseInt(document.getElementById("statuses_count").value)  || 0;
  const joinDate  = document.getElementById("created_at").value.trim();
  const hasBio    = document.getElementById("has_description").checked;
  const hasUrl    = document.getElementById("has_url").checked;
  const hasLoc    = document.getElementById("has_location").checked;

  let accountAgeDays = 1433;
  if (joinDate) {
    const d = new Date(joinDate);
    if (!isNaN(d)) accountAgeDays = Math.max(1, Math.floor((new Date() - d) / 86400000));
  }

  const ratio = friends > 0 ? followers / friends : 0;
  let score = 0;
  if (ratio > 1)  score++;
  if (ratio > 3)  score++;
  if (hasBio)     score++;
  if (hasUrl)     score++;
  if (hasLoc)     score++;

  const blend = score / 5;
  function lerp(a, b, t) { return a + (b - a) * t; }

  const tweetFreq   = lerp(0.49,  9.18,  blend);
  const favPerTweet = lerp(0.010, 0.678, blend);
  const listedPerF  = lerp(0.011, 0.015, blend);

  if (!statuses) setEstimated("statuses_count", Math.max(1, Math.round(tweetFreq * accountAgeDays)));
  const currentStatuses = parseInt(document.getElementById("statuses_count").value) || 1;
  setEstimated("favourites_count", Math.max(0, Math.round(currentStatuses * favPerTweet)));
  setEstimated("listed_count",     Math.max(0, Math.round(followers * listedPerF)));

  const label = score >= 4 ? "genuine-looking" : score >= 2 ? "mixed signals" : "suspicious-looking";
  const note  = document.getElementById("suggest-note");
  note.textContent  = `Estimates based on ${label} profile (score ${score}/5). Edit if you know the real values.`;
  note.style.display = "block";
}

function setEstimated(id, value) {
  document.getElementById(id).value = value;
  const badge = document.getElementById(id + "-est-badge");
  if (badge) badge.style.display = "inline";
}


// ── Manual re-predict (after user edits values) ───────────────────────────

async function runManualPredict() {
  const btn = document.getElementById("analyse-btn");
  btn.disabled = true;
  btn.textContent = "Analysing…";
  document.getElementById("result-box").style.display = "none";
  document.getElementById("error-box").style.display  = "none";

  function getInt(id) { return Math.max(0, parseInt(document.getElementById(id).value) || 0); }

  const data = {
    screen_name:      screenName,
    name:             screenName,
    followers_count:  getInt("followers_count"),
    friends_count:    getInt("friends_count"),
    statuses_count:   getInt("statuses_count"),
    favourites_count: getInt("favourites_count"),
    listed_count:     getInt("listed_count"),
    has_description:  document.getElementById("has_description").checked,
    has_url:          document.getElementById("has_url").checked,
    has_location:     document.getElementById("has_location").checked,
    join_date:        document.getElementById("created_at").value.trim() || null
  };

  chrome.runtime.sendMessage({ action: "manual_predict", tabId: currentTabId, data }, response => {
    if (response && response.result) {
      showResult(response.result);
    } else {
      showError(response?.error || "Unknown error");
    }
    btn.disabled    = false;
    btn.textContent = "Analyse account";
  });
}


// ── Show result ───────────────────────────────────────────────────────────

function showResult(r) {
  const pct       = Math.round(r.bot_probability * 100);
  const cls       = r.verdict === "FAKE" ? "fake" : "real";
  const confClass = r.confidence === "High" ? "conf-high"
                  : r.confidence === "Medium" ? "conf-med" : "conf-low";

  const signalsHTML = r.top_signals.slice(0, 4).map(s =>
    `<div class="signal-row">
      <span>${s[0]}</span>
      <span class="signal-val">${s[1]}</span>
    </div>`
  ).join("");

  document.getElementById("result-box").innerHTML = `
    <div class="result ${cls}">
      <div class="verdict-row">
        <span class="verdict ${cls}">${r.verdict}</span>
        <span class="confidence ${confClass}">${r.confidence} confidence</span>
      </div>
      <div class="score-row">
        <div class="bar-wrap">
          <div class="bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
        <span class="score-pct">${pct}%</span>
      </div>
      <div class="signals">${signalsHTML}</div>
    </div>`;
  document.getElementById("result-box").style.display = "block";
}

function showError(msg) {
  const box = document.getElementById("error-box");
  box.textContent   = msg;
  box.style.display = "block";
}