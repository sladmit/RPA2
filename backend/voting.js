/**
 * Russian Photo Awards - Voting System
 * Адаптовано для статичного HTML сайту
 */

// 🔧 НАЛАШТУВАННЯ: Змініть URL на ваш backend
const API_BASE_URL = 'http://localhost:5000';  // Локально
// const API_BASE_URL = 'https://vote.russianphotoawards.com';  // Production

/**
 * Функція для Alpine.js компонента голосування
 * @param {string} workId - UUID роботи
 * @param {number} initialLikes - Початкова кількість лайків
 */
function likeData(workId, initialLikes) {
    return {
        workId: workId,
        likes: initialLikes,
        isVoting: false,
        
        /**
         * Обробка кліку на кнопку лайку
         */
        async like() {
            // Запобігання подвійному кліку
            if (this.isVoting) return;
            
            // Перевірка чи вже голосував (локально)
            const hasVoted = localStorage.getItem(`voted_${this.workId}`);
            
            if (hasVoted) {
                this.showMessage('Вы уже проголосовали за эту работу!', 'error');
                return;
            }
            
            // Перевірка Telegram сесії
            const telegramSession = localStorage.getItem('telegram_session');
            
            if (!telegramSession) {
                // Редірект на сторінку авторизації
                const currentUrl = window.location.href;
                window.location.href = `${API_BASE_URL}/vote?work=${this.workId}&return=${encodeURIComponent(currentUrl)}`;
                return;
            }
            
            this.isVoting = true;
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/vote`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        work_id: this.workId,
                        session: telegramSession
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Оновлюємо лічильник
                    this.likes = data.votes;
                    
                    // Зберігаємо що проголосували
                    localStorage.setItem(`voted_${this.workId}`, 'true');
                    
                    // Показуємо повідомлення
                    this.showMessage('Спасибо за ваш голос!', 'success');
                    
                    // Анімація сердечка
                    this.animateHeart();
                } else {
                    this.handleVoteError(data.error);
                }
            } catch (error) {
                console.error('Vote error:', error);
                this.showMessage('Ошибка соединения с сервером', 'error');
            } finally {
                this.isVoting = false;
            }
        },
        
        /**
         * Обробка помилок голосування
         */
        handleVoteError(error) {
            if (error === 'Already voted') {
                this.showMessage('Вы уже проголосовали за эту работу!', 'error');
                localStorage.setItem(`voted_${this.workId}`, 'true');
            } else if (error === 'Invalid session') {
                // Сесія недійсна - видаляємо і редіректимо
                localStorage.removeItem('telegram_session');
                const currentUrl = window.location.href;
                window.location.href = `${API_BASE_URL}/vote?work=${this.workId}&return=${encodeURIComponent(currentUrl)}`;
            } else {
                this.showMessage(error || 'Ошибка голосования', 'error');
            }
        },
        
        /**
         * Анімація сердечка після голосування
         */
        animateHeart() {
            const heartButton = this.$el.querySelector('a');
            if (heartButton) {
                heartButton.classList.add('scale-125');
                setTimeout(() => {
                    heartButton.classList.remove('scale-125');
                }, 300);
            }
        },
        
        /**
         * Показ toast повідомлення
         */
        showMessage(text, type) {
            const toast = document.createElement('div');
            const bgColor = type === 'success' ? '#10b981' : '#ef4444';
            const icon = type === 'success' 
                ? '<svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
                : '<svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
            
            toast.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: ${bgColor};
                color: white;
                padding: 16px 24px;
                border-radius: 8px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.2);
                z-index: 9999;
                display: flex;
                align-items: center;
                font-family: 'Avenir Next Cyr', sans-serif;
                font-size: 14px;
                font-weight: 500;
                opacity: 0;
                transition: opacity 0.3s ease;
            `;
            
            toast.innerHTML = `${icon}<span>${text}</span>`;
            
            document.body.appendChild(toast);
            
            // Fade in
            setTimeout(() => {
                toast.style.opacity = '1';
            }, 10);
            
            // Fade out and remove
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    }
}

/**
 * Функція для оновлення кількості голосів (можна викликати періодично)
 */
async function updateVotesCount(workId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/get-votes/${workId}`);
        const data = await response.json();
        return data.votes;
    } catch (error) {
        console.error('Error fetching votes:', error);
        return null;
    }
}

/**
 * Функція для перевірки чи користувач вже голосував (серверна перевірка)
 */
async function checkIfVoted(workId) {
    const telegramSession = localStorage.getItem('telegram_session');
    if (!telegramSession) return false;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/check-vote`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                work_id: workId,
                session: telegramSession
            })
        });
        
        const data = await response.json();
        return data.has_voted;
    } catch (error) {
        console.error('Error checking vote:', error);
        return false;
    }
}

// Ініціалізація при завантаженні сторінки
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 RPA Voting System initialized');
    console.log('📡 API Base URL:', API_BASE_URL);
    
    // Перевірка чи є Telegram сесія
    const hasSession = localStorage.getItem('telegram_session');
    if (hasSession) {
        console.log('✅ Telegram session found');
    } else {
        console.log('❌ No Telegram session');
    }
});
