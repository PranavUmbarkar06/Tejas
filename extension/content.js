// Quick heuristic hook to detect checkout intent
document.addEventListener('click', (event) => {
  const target = event.target;
  const text = target.innerText ? target.innerText.toLowerCase() : '';
  
  if (text.includes('buy now') || text.includes('add to cart') || text.includes('checkout')) {
    chrome.runtime.sendMessage({ action: 'detect_buy_intent' });
  }
});

// Receive instruction from background engine to halt and evaluate
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'prompt_policy_check') {
    renderPolicyModal(message.visitCount);
  }
});

function renderPolicyModal(visitCount) {
  // Prevent duplicate modals
  if (document.getElementById('policy-check-overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'policy-check-overlay';
  overlay.style.cssText = 'position:fixed; top:20px; right:20px; z-index:99999; background:white; padding:16px; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); border-left:4px solid #ffc107; font-family:sans-serif;';
  
  overlay.innerHTML = `
    <div style="font-weight:bold; margin-bottom:8px;">⚠️ Optimal Purchase Policy Rule Triggered</div>
    <div style="font-size:13px; margin-bottom:12px;">This is visit #${visitCount} to this domain. Please verify your current asset balance before completing this order.</div>
    <button id="policy-btn-ok" style="background:#007bff; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;">Acknowledge Balance & Proceed</button>
  `;
  
  document.body.appendChild(overlay);

  document.getElementById('policy-btn-ok').addEventListener('click', () => {
    overlay.remove();
  });
} 