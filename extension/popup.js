// This file runs every time the popup UI is opened by the user
document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons securely
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Handle the premium loan button click securely
  const loanBtn = document.getElementById('btn-loans');
  if (loanBtn) {
    loanBtn.addEventListener('click', () => {
      chrome.tabs.create({ url: 'https://somebank.com/loans_agent' });
    });
  }
});