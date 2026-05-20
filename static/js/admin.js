// static/js/admin.js - SUPER SIMPLE VERSION

console.log("🚀 ADMIN.JS YUKLANDI");

// Dropdown funksiyasi
window.toggleProfileDropdown = function() {
    console.log("🎯 Dropdown funksiyasi chaqirildi");
    
    const dropdown = document.getElementById('profile-dropdown');
    
    // Agar dropdown bo'sh yashiringan bo'lsa, ko'rsatish
    if (!dropdown.style.display || dropdown.style.display === 'none') {
        dropdown.style.display = 'block';
        console.log("✅ Dropdown KO'RSATILDI");
    } else {
        dropdown.style.display = 'none';
        console.log("❌ Dropdown YASHIRILDI");
    }
};

// DOM yuklanganda
document.addEventListener('DOMContentLoaded', function() {
    console.log("🌐 DOM yuklandi");
    
    // Tugmaga event listener
    const btn = document.querySelector('.admin-profile-btn');
    if (btn) {
        btn.onclick = function(e) {
            e.stopPropagation();
            window.toggleProfileDropdown();
        };
    }
    
    // Tashqariga bosganda yopish
    document.addEventListener('click', function() {
        const dropdown = document.getElementById('profile-dropdown');
        if (dropdown && dropdown.style.display === 'block') {
            dropdown.style.display = 'none';
        }
    });
    
    // Dropdown ichiga bosganda tarqalmaslik
    const dropdown = document.getElementById('profile-dropdown');
    if (dropdown) {
        dropdown.onclick = function(e) {
            e.stopPropagation();
        };
    }
});

// admin.js fayliga qo'shing
function closeDropdown() {
    const dropdown = document.getElementById('profile-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
        dropdown.classList.remove('show');
    }
    return true;
}

// Global qilish
window.closeDropdown = closeDropdown;