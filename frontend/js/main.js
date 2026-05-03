// Check authentication
const token = localStorage.getItem('access_token');
if (!token && !window.location.pathname.includes('login.html')) {
    window.location.href = 'pages/login.html';
}

// Add token to all API calls
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const token = localStorage.getItem('access_token');
    if (token && args[1]) {
        args[1].headers = {
            ...args[1].headers,
            'Authorization': `Bearer ${token}`
        };
    }
    return originalFetch.apply(this, args);
};

// Logout function
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = 'pages/login.html';
}

// Add logout button to navbar
document.addEventListener('DOMContentLoaded', () => {
    const navMenu = document.querySelector('.nav-menu');
    if (navMenu) {
        const logoutLi = document.createElement('li');
        logoutLi.innerHTML = '<a href="#" onclick="logout()">🚪 Logout</a>';
        navMenu.appendChild(logoutLi);
    }
});
