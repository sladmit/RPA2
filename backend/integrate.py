#!/usr/bin/env python3
"""
🎯 Russian Photo Awards - Auto Integration Script
Автоматично додає voting.js у всі HTML файли
"""

import os
import glob
import sys
from pathlib import Path

# ============================================
# НАЛАШТУВАННЯ
# ============================================

# Шлях до вашого сайту (відносно цього скрипту)
SITE_PATH = "../downloaded_site/html"

# Рядок для вставки
VOTING_JS_LINE = '    <script src="../../resources/js/voting.js"></script>'

# Шаблон після якого вставляти
SEARCH_PATTERN = '<script type="module" src="https://russianphotoawards.com/build/assets/app-BNnG8_5N.js"></script>'

# Кольори для виводу
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

# ============================================
# ФУНКЦІЇ
# ============================================

def print_header():
    """Виведення заголовку"""
    print("=" * 60)
    print("🎯 RPA Voting System - Auto Integration")
    print("=" * 60)
    print()

def check_site_path():
    """Перевірка чи існує шлях до сайту"""
    if not os.path.exists(SITE_PATH):
        print(f"{Colors.RED}❌ Помилка: Папка {SITE_PATH} не знайдена!{Colors.END}")
        print()
        print("Змініть SITE_PATH в скрипті на правильний шлях до вашого сайту.")
        print("Наприклад:")
        print('  SITE_PATH = "D:/RPA/downloaded_site/html"')
        print('  SITE_PATH = "/Users/username/sites/rpa/html"')
        sys.exit(1)
    
    print(f"{Colors.GREEN}✅ Знайдено папку сайту: {SITE_PATH}{Colors.END}")
    print()

def process_file(filepath, relative_path="../../resources/js/voting.js"):
    """
    Обробка одного файлу
    
    Args:
        filepath: Шлях до файлу
        relative_path: Відносний шлях до voting.js
    
    Returns:
        str: Статус обробки ('success', 'skip', 'error')
    """
    try:
        # Читання файлу
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Перевірка чи вже є voting.js
        if 'voting.js' in content:
            return 'skip'
        
        # Перевірка чи є шаблон для вставки
        if SEARCH_PATTERN not in content:
            return 'error_no_pattern'
        
        # Створення рядка для вставки з правильним шляхом
        insert_line = f'    <script src="{relative_path}"></script>'
        
        # Вставка рядка
        content = content.replace(
            SEARCH_PATTERN,
            SEARCH_PATTERN + '\n' + insert_line
        )
        
        # Backup оригінального файлу
        backup_path = filepath + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            with open(filepath, 'r', encoding='utf-8') as orig:
                f.write(orig.read())
        
        # Збереження зміненого файлу
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return 'success'
        
    except Exception as e:
        print(f"{Colors.RED}❌ Помилка обробки {filepath}: {e}{Colors.END}")
        return 'error'

def get_relative_path(filepath):
    """
    Визначає правильний відносний шлях до voting.js
    
    Args:
        filepath: Шлях до HTML файлу
    
    Returns:
        str: Відносний шлях до voting.js
    """
    # Розраховуємо глибину вкладення
    relative = os.path.relpath(filepath, SITE_PATH)
    depth = len(Path(relative).parts) - 1
    
    # Будуємо шлях з потрібною кількістю ../
    prefix = '../' * (depth + 1)
    return f"{prefix}resources/js/voting.js"

def process_directory(directory, description):
    """
    Обробка всіх HTML файлів в директорії
    
    Args:
        directory: Шлях до директорії
        description: Опис директорії
    
    Returns:
        tuple: (total, success, skip, error)
    """
    print(f"{Colors.BLUE}📂 Обробка: {description}{Colors.END}")
    
    pattern = os.path.join(SITE_PATH, directory, "*.html")
    files = glob.glob(pattern)
    
    if not files:
        print(f"   {Colors.YELLOW}⚠️  Файли не знайдені{Colors.END}")
        print()
        return (0, 0, 0, 0)
    
    total = len(files)
    success = 0
    skip = 0
    error = 0
    
    for filepath in files:
        filename = os.path.basename(filepath)
        relative_path = get_relative_path(filepath)
        status = process_file(filepath, relative_path)
        
        if status == 'success':
            print(f"   {Colors.GREEN}✅{Colors.END} {filename}")
            success += 1
        elif status == 'skip':
            print(f"   {Colors.YELLOW}⏭️{Colors.END}  {filename} (вже має voting.js)")
            skip += 1
        elif status == 'error_no_pattern':
            print(f"   {Colors.RED}❌{Colors.END} {filename} (не знайдено шаблон)")
            error += 1
        else:
            error += 1
    
    print()
    return (total, success, skip, error)

def copy_voting_js():
    """Копіювання voting.js у папку resources"""
    print(f"{Colors.BLUE}📦 Копіювання voting.js...{Colors.END}")
    
    source = "voting.js"
    dest_dir = os.path.join(SITE_PATH, "../resources/js")
    dest_file = os.path.join(dest_dir, "voting.js")
    
    # Створення папки якщо не існує
    os.makedirs(dest_dir, exist_ok=True)
    
    if not os.path.exists(source):
        print(f"   {Colors.YELLOW}⚠️  voting.js не знайдено в поточній папці{Colors.END}")
        print(f"   Скопіюйте voting.js вручну в: {dest_dir}")
        print()
        return False
    
    # Копіювання
    with open(source, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(dest_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"   {Colors.GREEN}✅ voting.js скопійовано в {dest_dir}{Colors.END}")
    print()
    return True

def print_summary(stats):
    """Виведення підсумків"""
    total_files = stats['total']
    total_success = stats['success']
    total_skip = stats['skip']
    total_error = stats['error']
    
    print("=" * 60)
    print("📊 ПІДСУМКИ:")
    print("=" * 60)
    print(f"📁 Всього файлів:      {total_files}")
    print(f"{Colors.GREEN}✅ Змінено:            {total_success}{Colors.END}")
    print(f"{Colors.YELLOW}⏭️  Пропущено:         {total_skip}{Colors.END}")
    print(f"{Colors.RED}❌ Помилки:            {total_error}{Colors.END}")
    print("=" * 60)
    print()
    
    if total_success > 0:
        print(f"{Colors.GREEN}✨ Інтеграція завершена успішно!{Colors.END}")
        print()
        print("📝 Backup файли збережено з розширенням .backup")
        print("💡 Якщо все працює - можна видалити backup:")
        print(f"   find {SITE_PATH} -name '*.backup' -delete")
        print()
    else:
        print(f"{Colors.YELLOW}⚠️  Жодного файлу не було змінено.{Colors.END}")
        print()

# ============================================
# ГОЛОВНА ФУНКЦІЯ
# ============================================

def main():
    """Головна функція"""
    print_header()
    
    # Перевірка шляху
    check_site_path()
    
    # Копіювання voting.js
    copy_voting_js()
    
    # Обробка файлів
    stats = {
        'total': 0,
        'success': 0,
        'skip': 0,
        'error': 0
    }
    
    # Обробка works/
    if os.path.exists(os.path.join(SITE_PATH, "works")):
        total, success, skip, error = process_directory("works", "Категорії (works/)")
        stats['total'] += total
        stats['success'] += success
        stats['skip'] += skip
        stats['error'] += error
    
    # Обробка work/
    if os.path.exists(os.path.join(SITE_PATH, "work")):
        total, success, skip, error = process_directory("work", "Окремі роботи (work/)")
        stats['total'] += total
        stats['success'] += success
        stats['skip'] += skip
        stats['error'] += error
    
    # Обробка кореневих файлів
    root_files = glob.glob(os.path.join(SITE_PATH, "*.html"))
    if root_files:
        print(f"{Colors.BLUE}📂 Обробка: Кореневі файли{Colors.END}")
        for filepath in root_files:
            filename = os.path.basename(filepath)
            if filename != 'vote.html':  # Пропускаємо vote.html
                status = process_file(filepath, "resources/js/voting.js")
                stats['total'] += 1
                
                if status == 'success':
                    print(f"   {Colors.GREEN}✅{Colors.END} {filename}")
                    stats['success'] += 1
                elif status == 'skip':
                    print(f"   {Colors.YELLOW}⏭️{Colors.END}  {filename} (вже має voting.js)")
                    stats['skip'] += 1
                else:
                    print(f"   {Colors.RED}❌{Colors.END} {filename}")
                    stats['error'] += 1
        print()
    
    # Підсумки
    print_summary(stats)
    
    # Наступні кроки
    print("🚀 Наступні кроки:")
    print()
    print("1. Запустіть Redis:")
    print("   docker run -d -p 6379:6379 redis:alpine")
    print()
    print("2. Запустіть Flask backend:")
    print("   python3 app.py")
    print()
    print("3. Відкрийте сайт та перевірте:")
    print(f"   file://{os.path.abspath(SITE_PATH)}/works/female-portrait.html")
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
