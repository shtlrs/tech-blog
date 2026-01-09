// Theme toggle functionality
(function() {
  const THEME_KEY = 'theme-preference';
  const DARK_CLASS = 'latex-dark';
  const LIGHT_CLASS = '';

  const themeToggle = document.getElementById('theme-toggle');
  const lightIcon = document.getElementById('theme-toggle-light-icon');
  const darkIcon = document.getElementById('theme-toggle-dark-icon');

  // Get saved preference or default to system preference
  function getThemePreference() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) {
      return saved;
    }
    // Check system preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  // Apply theme to body
  function applyTheme(theme) {
    if (theme === 'dark') {
      document.body.className = DARK_CLASS;
      lightIcon.style.display = 'inline';
      darkIcon.style.display = 'none';
    } else {
      document.body.className = LIGHT_CLASS;
      lightIcon.style.display = 'none';
      darkIcon.style.display = 'inline';
    }
  }

  // Toggle theme
  function toggleTheme() {
    const currentTheme = getThemePreference();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, newTheme);
    applyTheme(newTheme);
  }

  // Initialize on page load
  const currentTheme = getThemePreference();
  applyTheme(currentTheme);

  // Add click listener
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }

  // Listen for system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    // Only apply if user hasn't set a preference
    if (!localStorage.getItem(THEME_KEY)) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
})();
