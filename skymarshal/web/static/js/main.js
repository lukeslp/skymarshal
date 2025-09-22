// Utility functions for Skymarshal Web

const THEME_STORAGE_KEY = 'skymarshal-theme';

function readStoredTheme() {
    try {
        const stored = localStorage.getItem(THEME_STORAGE_KEY);
        if (stored === 'light' || stored === 'dark') {
            return stored;
        }
    } catch (error) {
        console.warn('Unable to read theme preference', error);
    }
    return null;
}

function writeStoredTheme(theme) {
    try {
        localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (error) {
        console.warn('Unable to persist theme preference', error);
    }
}

function applyThemePreference(theme) {
    const normalized = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = normalized;
    document.documentElement.style.colorScheme = normalized;
    if (document.body) {
        document.body.dataset.theme = normalized;
    }

    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        const isDark = normalized === 'dark';
        toggle.setAttribute('aria-pressed', String(isDark));
        toggle.setAttribute(
            'aria-label',
            isDark ? 'Switch to light mode' : 'Switch to dark mode'
        );
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const storedTheme = readStoredTheme();
    let hasExplicitPreference = storedTheme !== null;
    const prefersDarkQuery = window.matchMedia
        ? window.matchMedia('(prefers-color-scheme: dark)')
        : null;
    const initialTheme = storedTheme
        || (prefersDarkQuery && prefersDarkQuery.matches ? 'dark' : 'light');

    applyThemePreference(initialTheme);

    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const currentTheme =
                document.documentElement.dataset.theme === 'dark'
                    ? 'dark'
                    : 'light';
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyThemePreference(nextTheme);
            writeStoredTheme(nextTheme);
            hasExplicitPreference = true;
        });
    }

    const handleSystemThemeChange = (event) => {
        if (hasExplicitPreference) {
            return;
        }
        applyThemePreference(event.matches ? 'dark' : 'light');
    };

    if (prefersDarkQuery) {
        if (typeof prefersDarkQuery.addEventListener === 'function') {
            prefersDarkQuery.addEventListener('change', handleSystemThemeChange);
        } else if (typeof prefersDarkQuery.addListener === 'function') {
            prefersDarkQuery.addListener(handleSystemThemeChange);
        }
    }
});

// Format bytes to human readable format
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format date to local string
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape key closes modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display !== 'none') {
                modal.style.display = 'none';
            }
        });
    }
});

// Add smooth scrolling for all links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
