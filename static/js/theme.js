// Theme toggle funksiyasi
function toggleTheme() {
    const darkStyle = document.getElementById('dark-style');
    const themeToggle = document.getElementById('themeToggle');
    const icon = themeToggle ? themeToggle.querySelector('i') : null;
    
    // Dark mode ni yoqish/o'chirish
    const isDark = document.body.classList.toggle('dark-mode');
    
    // dark.css ni yoqish/o'chirish
    if (darkStyle) {
        darkStyle.disabled = !isDark;
    }
    
    // Iconni o'zgartirish
    if (icon) {
        if (isDark) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
            localStorage.setItem('theme', 'dark');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
            localStorage.setItem('theme', 'light');
        }
    }
}

// Sahifa yuklanganda theme ni o'rnatish
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    const darkStyle = document.getElementById('dark-style');
    const themeToggle = document.getElementById('themeToggle');
    const icon = themeToggle ? themeToggle.querySelector('i') : null;
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (darkStyle) {
            darkStyle.disabled = false;
        }
        if (icon) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        }
    }
}

// DOM yuklanganda theme ni yuklash va event listener qo'shish
document.addEventListener('DOMContentLoaded', function() {
    // Theme ni yuklash
    loadTheme();
    
    // Theme toggle tugmasiga event listener qo'shish
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Agar CSS o'zgaruvchilarini dark mode uchun yangilash kerak bo'lsa
    if (document.body.classList.contains('dark-mode')) {
        updateCSSVariablesForDarkMode();
    }
});

// Dark mode uchun CSS o'zgaruvchilarini yangilash (agar kerak bo'lsa)
function updateCSSVariablesForDarkMode() {
    const root = document.documentElement;
    
    // Dark mode uchun yangi o'zgaruvchilar
    root.style.setProperty('--light-color', '#374151');
    root.style.setProperty('--text-color', '#e5e7eb');
    root.style.setProperty('--text-light', '#9ca3af');
    
    // Yana kerakli o'zgaruvchilarni qo'shing
}