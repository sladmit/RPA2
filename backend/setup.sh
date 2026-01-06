#!/bin/bash

# ============================================
# 🚀 Russian Photo Awards - Quick Setup
# ============================================

echo "================================================"
echo "🎯 RPA Voting System - Quick Setup"
echo "================================================"
echo ""

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# Крок 1: Перевірка Python
# ============================================
echo -e "${BLUE}📦 Крок 1: Перевірка Python...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 не знайдено!${NC}"
    echo "   Встановіть Python 3: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"
echo ""

# ============================================
# Крок 2: Перевірка pip
# ============================================
echo -e "${BLUE}📦 Крок 2: Перевірка pip...${NC}"

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip не знайдено!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ pip встановлено${NC}"
echo ""

# ============================================
# Крок 3: Встановлення залежностей
# ============================================
echo -e "${BLUE}📦 Крок 3: Встановлення залежностей...${NC}"

pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Залежності встановлено${NC}"
else
    echo -e "${RED}❌ Помилка встановлення залежностей${NC}"
    exit 1
fi
echo ""

# ============================================
# Крок 4: Перевірка Redis
# ============================================
echo -e "${BLUE}📦 Крок 4: Перевірка Redis...${NC}"

if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis запущений${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis встановлений але не запущений${NC}"
        echo "   Запустіть Redis:"
        echo "   - macOS: brew services start redis"
        echo "   - Linux: sudo systemctl start redis"
        echo "   - Docker: docker run -d -p 6379:6379 redis:alpine"
    fi
else
    echo -e "${YELLOW}⚠️  Redis не встановлений${NC}"
    echo ""
    echo "   Оберіть спосіб встановлення:"
    echo ""
    echo "   1) Docker (рекомендовано):"
    echo "      docker run -d --name redis -p 6379:6379 redis:alpine"
    echo ""
    echo "   2) macOS:"
    echo "      brew install redis"
    echo "      brew services start redis"
    echo ""
    echo "   3) Ubuntu/Debian:"
    echo "      sudo apt install redis-server"
    echo "      sudo systemctl start redis"
    echo ""
fi
echo ""

# ============================================
# Крок 5: Створення .env файлу
# ============================================
echo -e "${BLUE}📦 Крок 5: Налаштування .env...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env файл не знайдено${NC}"
    echo ""
    read -p "Створити .env файл? (y/n): " create_env
    
    if [ "$create_env" = "y" ]; then
        echo ""
        echo "Введіть Telegram API credentials:"
        echo "(Отримати можна на: https://my.telegram.org/auth)"
        echo ""
        
        read -p "TELEGRAM_API_ID: " api_id
        read -p "TELEGRAM_API_HASH: " api_hash
        
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        
        cat > .env << EOF
TELEGRAM_API_ID=$api_id
TELEGRAM_API_HASH=$api_hash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
SECRET_KEY=$SECRET_KEY
PROXY_ENABLED=false
EOF
        
        echo -e "${GREEN}✅ .env файл створено${NC}"
    else
        echo -e "${YELLOW}⚠️  Створіть .env файл вручну${NC}"
    fi
else
    echo -e "${GREEN}✅ .env файл існує${NC}"
fi
echo ""

# ============================================
# Крок 6: Структура файлів
# ============================================
echo -e "${BLUE}📦 Крок 6: Перевірка структури...${NC}"

if [ -f "app.py" ] || [ -f "app_voting.py" ]; then
    echo -e "${GREEN}✅ Flask додаток знайдено${NC}"
else
    echo -e "${RED}❌ Flask додаток не знайдено (app.py або app_voting.py)${NC}"
fi

if [ -f "voting.js" ]; then
    echo -e "${GREEN}✅ voting.js знайдено${NC}"
else
    echo -e "${YELLOW}⚠️  voting.js не знайдено${NC}"
fi
echo ""

# ============================================
# Підсумок
# ============================================
echo "================================================"
echo -e "${GREEN}✨ Setup завершено!${NC}"
echo "================================================"
echo ""
echo "📝 Наступні кроки:"
echo ""
echo "1. Запустіть Redis (якщо не запущений):"
echo "   docker run -d -p 6379:6379 redis:alpine"
echo ""
echo "2. Запустіть Flask backend:"
echo "   python3 app.py"
echo "   або: python3 app_voting.py"
echo ""
echo "3. Backend запуститься на:"
echo "   http://localhost:5000"
echo ""
echo "4. Додайте voting.js у ваші HTML файли:"
echo "   <script src=\"path/to/voting.js\"></script>"
echo ""
echo "================================================"
