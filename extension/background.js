const TARGET_DOMAINS = ["tesla.com", "autotrader.com", "godaddy.com", "carvana.com"];
const VISIT_THRESHOLD = 2; // Prompt triggers when visits > 2 (i.e., on the 3rd visit)
const LOAN_URL = "http://localhost:5173/";

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // Catching 'complete' status ensures we only count full page loads, not background resource adjustments
  if (changeInfo.status === 'complete' && tab.url) {
    try {
      const url = new URL(tab.url);
      const domain = url.hostname.replace('www.', '');

      if (TARGET_DOMAINS.includes(domain)) {
        handleVisit(domain, tabId);
      }
    } catch (e) {
      // Safely catch and discard malformed URLs or internal chrome:// lines
    }
  }
});

function handleVisit(domain, tabId) {
  chrome.storage.local.get([domain], (result) => {
    let visits = result[domain] || 0;
    visits++;

    if (visits > VISIT_THRESHOLD) {
      // Reset immediately before prompting to prevent race conditions or double-triggering on fast clicks
      chrome.storage.local.set({ [domain]: 0 }, () => {
        triggerPromptAndRedirect(tabId);
      });
    } else {
      chrome.storage.local.set({ [domain]: visits });
      console.log(`${domain} visit count incremented to: ${visits}`);
    }
  });
}

function triggerPromptAndRedirect(tabId) {
  chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: () => {
      // This displays the native browser modal directly over the current website
      return confirm("Are you planning a big purchase?");
    }
  }, (results) => {
    if (!results || !results[0]) return;

    const userClickedYes = results[0].result;
    if (userClickedYes) {
      chrome.tabs.update(tabId, { url: LOAN_URL });
    }
  });
}