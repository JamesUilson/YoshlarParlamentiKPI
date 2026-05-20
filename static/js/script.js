// static/js/script.js
document.addEventListener('DOMContentLoaded', function() {
    // ====================
    // TUNGI REJIM BOSHQARUVI
    // ====================
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = themeToggle.querySelector('i');
    
    // Mavjud mavzuni tekshirish
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
    } else {
        document.body.classList.remove('dark-mode');
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
    }
    
    // Mavzuni o'zgartirish
    themeToggle.addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');
        
        if (document.body.classList.contains('dark-mode')) {
            localStorage.setItem('theme', 'dark');
            themeIcon.classList.remove('fa-moon');
            themeIcon.classList.add('fa-sun');
        } else {
            localStorage.setItem('theme', 'light');
            themeIcon.classList.remove('fa-sun');
            themeIcon.classList.add('fa-moon');
        }
    });
    
    // ====================
    // FORMA VALIDATSIYASI
    // ====================
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let valid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    valid = false;
                    field.style.borderColor = '#dc2626';
                    
                    // Xabar yaratish
                    const errorMsg = document.createElement('div');
                    errorMsg.style.color = '#dc2626';
                    errorMsg.style.fontSize = '0.85rem';
                    errorMsg.style.marginTop = '0.25rem';
                    errorMsg.textContent = 'Bu maydon toʻldirilishi shart';
                    
                    if (!field.nextElementSibling || !field.nextElementSibling.classList.contains('error-msg')) {
                        field.insertAdjacentElement('afterend', errorMsg);
                        errorMsg.classList.add('error-msg');
                    }
                } else {
                    field.style.borderColor = '';
                    const errorMsg = field.nextElementSibling;
                    if (errorMsg && errorMsg.classList.contains('error-msg')) {
                        errorMsg.remove();
                    }
                }
            });
            
            if (!valid) {
                e.preventDefault();
                alert('Iltimos, barcha majburiy maydonlarni toʻldiring!');
            }
        });
    });
    
    // ====================
    // MOBILE MENU BOSHQARUVI
    // ====================
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            const navLinks = document.querySelector('.nav-links');
            navLinks.classList.toggle('active');
        });
    }
    
    // ====================
    // REYTING BOSHQARUVI
    // ====================
    const ratingStars = document.querySelectorAll('.rating-stars .star');
    ratingStars.forEach(star => {
        star.addEventListener('click', function() {
            const value = this.getAttribute('data-value');
            const starsContainer = this.parentElement;
            const input = document.getElementById(starsContainer.id.replace('Stars', 'Input'));
            
            // Yulduzchalarni yangilash
            const stars = starsContainer.querySelectorAll('.star');
            stars.forEach((s, index) => {
                if (index < value) {
                    s.classList.add('active');
                } else {
                    s.classList.remove('active');
                }
            });
            
            // Input qiymatini yangilash
            if (input) {
                input.value = value;
            }
        });
    });
    
    // ====================
    // COUNTER BOSHQARUVI
    // ====================
    const counterButtons = document.querySelectorAll('.counter-btn');
    counterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const action = this.textContent.trim();
            const counterValue = this.parentElement.querySelector('.counter-value');
            let value = parseInt(counterValue.value);
            
            if (action === '+' && value < parseInt(counterValue.max || 100)) {
                counterValue.value = value + 1;
            } else if (action === '-' && value > parseInt(counterValue.min || 0)) {
                counterValue.value = value - 1;
            }
            
            // Input hodisasi
            const event = new Event('change');
            counterValue.dispatchEvent(event);
        });
    });
    
    // ====================
    // FILE UPLOAD BOSHQARUVI
    // ====================
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileName = this.files[0] ? this.files[0].name : 'Fayl tanlanmadi';
            const label = this.nextElementSibling;
            
            if (label && label.classList.contains('file-name')) {
                label.textContent = fileName;
            }
        });
    });
    
    // ====================
    // TAB BOSHQARUVI
    // ====================
    const tabButtons = document.querySelectorAll('.tab, .nav-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab') || 
                           this.getAttribute('onclick').match(/switchTab\('([^']+)'\)/)[1];
            
            // Barcha tab va kontentlarni yashirish
            document.querySelectorAll('.tab, .nav-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Faqat tanlangan tab va kontentni ko'rsatish
            this.classList.add('active');
            const tabContent = document.getElementById(`${tabName}-tab`);
            if (tabContent) {
                tabContent.classList.add('active');
            }
        });
    });
    
    // ====================
    // REAL TIME SAAT
    // ====================
    function updateClock() {
        const now = new Date();
        const clockElements = document.querySelectorAll('.current-time');
        
        if (clockElements.length > 0) {
            const timeString = now.toLocaleTimeString('uz-UZ');
            clockElements.forEach(element => {
                element.textContent = timeString;
            });
        }
    }
    
    // Har sekund yangilash
    setInterval(updateClock, 1000);
    updateClock(); // Boshlang'ich qiymat
    
    // ====================
    // NOTIFICATION BOSHQARUVI
    // ====================
    const notificationButtons = document.querySelectorAll('.notification-btn');
    notificationButtons.forEach(button => {
        button.addEventListener('click', function() {
            const notification = this.nextElementSibling;
            if (notification && notification.classList.contains('notification-dropdown')) {
                notification.classList.toggle('active');
            }
        });
    });
    
    // Notification yopish
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.notification-btn')) {
            document.querySelectorAll('.notification-dropdown').forEach(dropdown => {
                dropdown.classList.remove('active');
            });
        }
    });
    
    // ====================
    // AUTO LOGOUT TIMER
    // ====================
    let idleTime = 0;
    
    function resetIdleTime() {
        idleTime = 0;
    }
    
    function checkIdleTime() {
        idleTime++;
        
        // 30 daqiqa (1800 soniya) dan keyin ogohlantirish
        if (idleTime === 1740) { // 29 daqiqa
            if (confirm('Sessiya 1 daqiqadan soʻng tugaydi. Davom ettirishni istaysizmi?')) {
                resetIdleTime();
            }
        }
        
        // 30 daqiqadan keyin avtomatik logout
        if (idleTime > 1800) {
            window.location.href = '/logout';
        }
    }

    // Faollikni kuzatish
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    events.forEach(event => {
        document.addEventListener(event, resetIdleTime);
    });
    
    // Har sekund tekshirish
    setInterval(checkIdleTime, 1000);
    
    // ====================
    // PRINT FUNCTION
    // ====================
    window.printPage = function() {
        window.print();
    };
    
    // ====================
    // COPY TO CLIPBOARD
    // ====================
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            alert('Nusxalandi: ' + text);
        }, function(err) {
            console.error('Nusxalashda xatolik: ', err);
        });
    };
    
    // ====================
    // AJAX LOADING INDICATOR
    // ====================
    document.addEventListener('ajaxStart', function() {
        document.getElementById('loadingIndicator').style.display = 'block';
    });
    
    document.addEventListener('ajaxStop', function() {
        document.getElementById('loadingIndicator').style.display = 'none';
    });
    
    // ====================
    // SMOOTH SCROLL
    // ====================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // ====================
    // FORM AUTO-SAVE (DRAFT)
    // ====================
    const autoSaveForms = document.querySelectorAll('form[data-autosave]');
    autoSaveForms.forEach(form => {
        let saveTimeout;
        
        form.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            
            saveTimeout = setTimeout(function() {
                const formData = new FormData(form);
                
                // AJAX orqali saqlash
                fetch('/save_draft', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Qoralamaga saqlandi');
                    }
                })
                .catch(error => {
                    console.error('Xatolik:', error);
                });
            }, 3000); // 3 soniyadan keyin
        });
    });
});

// ====================
// GLOBAL FUNCTIONS
// ====================

// Show loading
function showLoading() {
    const loader = document.createElement('div');
    loader.id = 'globalLoader';
    loader.innerHTML = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999;">
            <div style="background: white; padding: 2rem; border-radius: 8px; display: flex; flex-direction: column; align-items: center; gap: 1rem;">
                <div class="spinner" style="width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <p>Yuklanmoqda...</p>
            </div>
        </div>
    `;
    document.body.appendChild(loader);
}

// Hide loading
function hideLoading() {
    const loader = document.getElementById('globalLoader');
    if (loader) {
        loader.remove();
    }
}

// Format date
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('uz-UZ', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Format number
function formatNumber(num) {
    return new Intl.NumberFormat('uz-UZ').format(num);
}

// Show toast message
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div style="padding: 1rem; background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'}; color: white; border-radius: 4px; margin-bottom: 0.5rem;">
            ${message}
        </div>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Confirm dialog
function confirmDialog(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

function importDatabase() {
    // Fayl tanlash uchun input yaratish
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.sql';
    
    fileInput.onchange = async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        if (!confirm(`${file.name} faylini yuklashni tasdiqlaysizmi?\nEslatma: Hozirgi baza avtomatik backup qilinadi.`)) {
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/admin/import_database', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                alert(`Muvaffaqiyatli!\n\n${result.message}\nBackup fayli: ${result.backup_file}`);
                // Sahifani yangilash
                location.reload();
            } else {
                alert('Xatolik: ' + result.error);
            }
        } catch (error) {
            alert('Server bilan aloqa xatosi: ' + error);
        }
    };
    
    fileInput.click();
}