// Initialize or update tracking data on tab navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    try {
      const url = new URL(tab.url);
      const domain = url.hostname;

      chrome.storage.local.get(['visited_domains'], (result) => {
        const data = result.visited_domains || {};
        data[domain] = (data[domain] || 0) + 1;

        chrome.storage.local.set({ visited_domains: data }, () => {
          console.log(`Updated tracker for ${domain}: ${data[domain]} visits`);
        });
      });
    } catch (e) {
      console.error("Error parsing URL: ", e);
    }
  }
});

// Listen for buy intent signals from the content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'detect_buy_intent' && sender.tab) {
    const domain = new URL(sender.tab.url).hostname;

    chrome.storage.local.get(['visited_domains'], (result) => {
      const data = result.visited_domains || {};
      const currentVisits = data[domain] || 1;

      // Policy Rule: Intervene if user is trying to buy on the 2nd or 3rd visit
      if (currentVisits >= 2 && currentVisits <= 3) {
        console.log(`Policy Triggered for ${domain} on visit #${currentVisits}`);
        
        // Notify the content script to execute the balance check and policy prompt
        chrome.tabs.sendMessage(sender.tab.id, { 
          action: 'prompt_policy_check', 
          visitCount: currentVisits 
        });
      }
    });
  }
});