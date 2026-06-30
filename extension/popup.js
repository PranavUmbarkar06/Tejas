document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('actionBtn');
  
  if (button) {
    button.addEventListener('click', () => {
      // Basic testing confirmation
      console.log('Button clicked inside extension popup.');
      alert('Extension connection verified!');
    });
  }
});