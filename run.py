import webbrowser
import os
import sys
from threading import Timer
from app import app

def open_browser():
    """Открывает браузер после запуска сервера"""
    webbrowser.open('http://127.0.0.1:5000/')

def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == '__main__':
    # Создаем папку uploads, если её нет
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
        
    # Открываем браузер через 1.5 секунды после запуска
    Timer(1.5, open_browser).start()
    
    # Запускаем приложение
    app.run(debug=False) 