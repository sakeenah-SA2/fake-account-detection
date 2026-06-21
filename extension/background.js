// background.js — service worker
// Listens for scraped profile data, calls Flask, updates the icon

const LOCAL_URL  = "http://127.0.0.1:5000/predict-json";
const HOSTED_URL = "https://botwatch-6qpn.onrender.com/predict-json";

// Pick the endpoint from the saved choice. Defaults to local.
async function getEndpoint() {
  const { apiMode = "local" } = await chrome.storage.sync.get("apiMode");
  return apiMode === "hosted" ? HOSTED_URL : LOCAL_URL;
}

// Store last result per tab so popup can read it instantly
const tabResults = {};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  if (message.action === "auto_predict") {
    const tabId = sender.tab.id;

    // Set icon to loading immediately
    setIcon(tabId, "loading");

    const payload = buildPayload(message.data);

    getEndpoint().then(url => fetch(url, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload)
    }))
    .then(res => {
      if (!res.ok) throw new Error("Server error");
      return res.json();
    })
    .then(result => {
      result.top_signals = result.top_signals.map(s => Array.isArray(s) ? s : [s[0], s[1]]);
      tabResults[tabId]  = { result, data: message.data };

      const iconState = result.verdict === "FAKE" ? "fake"
                      : result.verdict === "REAL" ? "real"
                      : "default";
      setIcon(tabId, iconState);

      // Send result to popup if it's open
      chrome.runtime.sendMessage({ action: "prediction_ready", result, tabId })
        .catch(() => {}); // popup might not be open — ignore error
    })
    .catch(err => {
      console.warn("BotWatch: prediction failed —", err.message);
      setIcon(tabId, "default");
      tabResults[tabId] = { error: err.message };
    });

    return true; // keep message channel open
  }

  // Popup asking for the cached result for the current tab
  if (message.action === "get_cached") {
    const result = tabResults[message.tabId] || null;
    sendResponse(result);
    return true;
  }

  // Popup asking to re-run prediction with updated (manual) values
  if (message.action === "manual_predict") {
    const tabId  = message.tabId;
    const payload = buildPayload(message.data);

    setIcon(tabId, "loading");

    getEndpoint().then(url => fetch(url, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload)
    }))
    .then(res => res.json())
    .then(result => {
      result.top_signals = result.top_signals.map(s => Array.isArray(s) ? s : [s[0], s[1]]);
      tabResults[tabId]  = { result, data: message.data };

      const iconState = result.verdict === "FAKE" ? "fake"
                      : result.verdict === "REAL" ? "real"
                      : "default";
      setIcon(tabId, iconState);
      sendResponse({ result });
    })
    .catch(err => {
      setIcon(tabId, "default");
      sendResponse({ error: err.message });
    });

    return true;
  }
});

// Reset icon when tab navigates away from a profile
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading") {
    const url = tab.url || "";
    if (!url.includes("twitter.com") && !url.includes("x.com")) {
      setIcon(tabId, "default");
      delete tabResults[tabId];
    }
  }
});

function setIcon(tabId, state) {
  const icons = {
    default: { 16: "icon-default.png", 48: "icon-default.png", 128: "icon-default.png" },
    real:    { 16: "icon-real.png",    48: "icon-real.png",    128: "icon-real.png"    },
    fake:    { 16: "icon-fake.png",    48: "icon-fake.png",    128: "icon-fake.png"    },
    loading: { 16: "icon-loading.png", 48: "icon-loading.png", 128: "icon-loading.png" }
  };
  chrome.action.setIcon({ tabId, path: icons[state] || icons.default })
    .catch(() => {});
}

function buildPayload(data) {
  return {
    screen_name:      data.screen_name      || "",
    name:             data.name             || data.screen_name || "",
    followers_count:  parseInt(data.followers_count)  || 0,
    friends_count:    parseInt(data.friends_count)    || 0,
    statuses_count:   parseInt(data.statuses_count)   || 0,
    favourites_count: parseInt(data.favourites_count) || 0,
    listed_count:     parseInt(data.listed_count)     || 0,
    description:      data.has_description ? "yes" : "",
    url:              data.has_url          ? "yes" : null,
    location:         data.has_location     ? "yes" : "",
    created_at:       data.join_date        || null
  };
}