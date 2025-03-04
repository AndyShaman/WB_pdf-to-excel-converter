from flask import Flask, render_template, request, send_file, flash, redirect, url_for, after_this_request
import os
from werkzeug.utils import secure_filename
from pdf_to_excel import extract_data_from_page
import fitz
import pandas as pd
import time
from datetime import datetime, timedelta
import threading

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Конфигурация загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'PDF'}
MAX_FILE_AGE = 86400  # Максимальный возраст файла в секундах (24 часа)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Ограничение размера файла 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].upper() in ALLOWED_EXTENSIONS

def clean_up_files(pdf_path=None, excel_path=None):
    """Удаляет временные файлы"""
    files_to_remove = []
    if pdf_path:
        files_to_remove.append(pdf_path)
    if excel_path:
        files_to_remove.append(excel_path)
    
    for file_path in files_to_remove:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

def wait_until_midnight():
    """Ожидает до следующего запуска в 00:00 UTC"""
    now = datetime.utcnow()
    next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    time_to_wait = (next_run - now).total_seconds()
    time.sleep(time_to_wait)

def clean_old_files():
    """Периодически удаляет старые файлы из папки uploads"""
    while True:
        try:
            # Ждем до 00:00 UTC
            wait_until_midnight()
            
            # Очищаем старые файлы
            current_time = time.time()
            for filename in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > MAX_FILE_AGE:
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
        except Exception:
            pass

# Запускаем поток для периодической очистки файлов
cleanup_thread = threading.Thread(target=clean_old_files, daemon=True)
cleanup_thread.start()

def format_numbers(df):
    """Форматирует числовые колонки в DataFrame"""
    # Заменяем запятые на точки в числовых значениях
    df['Количество'] = df['Количество'].str.replace(',', '.').astype(float)
    df['Сумма выкупа, BYN, (вкл. НДС)'] = df['Сумма выкупа, BYN, (вкл. НДС)'].str.replace(',', '.').astype(float)
    return df

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Проверяем, был ли файл в запросе
        if 'file' not in request.files:
            flash('Файл не выбран')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Если пользователь не выбрал файл
        if file.filename == '':
            flash('Файл не выбран')
            return redirect(request.url)
        
        if not file or not allowed_file(file.filename):
            flash('Разрешены только PDF файлы')
            return redirect(request.url)
        
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_filename = f"processed_{filename.rsplit('.', 1)[0]}.xlsx"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            # Сохраняем PDF
            file.save(filepath)
            
            try:
                # Открываем PDF файл
                pdf_document = fitz.open(filepath)
                
                # Собираем данные со всех страниц
                all_rows = []
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    rows = extract_data_from_page(page)
                    all_rows.extend(rows)
                
                # Закрываем PDF файл
                pdf_document.close()
                
                if not all_rows:
                    raise ValueError("Не удалось извлечь данные из PDF файла")
                
                # Создаем DataFrame
                df = pd.DataFrame(all_rows)
                
                # Удаляем дубликаты
                df = df.drop_duplicates(subset=['Артикул', 'Количество', 'Сумма выкупа, BYN, (вкл. НДС)'], keep='first')
                
                # Сортируем DataFrame по номеру строки
                df = df.sort_values(by=['Номер строки'])
                
                # Удаляем столбец с номером строки
                df = df.drop('Номер строки', axis=1)
                
                # Форматируем числовые колонки
                df = format_numbers(df)
                
                # Создаем writer для Excel с движком openpyxl
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                    # Получаем рабочий лист
                    worksheet = writer.sheets['Sheet1']
                    
                    # Устанавливаем формат для числовых колонок
                    for row in range(2, len(df) + 2):  # +2 потому что Excel начинается с 1 и у нас есть заголовок
                        # Форматируем колонку "Количество"
                        cell = worksheet.cell(row=row, column=2)
                        cell.number_format = '0'
                        
                        # Форматируем колонку "Сумма выкупа"
                        cell = worksheet.cell(row=row, column=3)
                        cell.number_format = '0.00'
                
                # Удаляем исходный PDF файл
                clean_up_files(pdf_path=filepath)
                
                @after_this_request
                def remove_excel(response):
                    clean_up_files(excel_path=output_path)
                    return response
                
                return send_file(
                    output_path,
                    as_attachment=True,
                    download_name=output_filename,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
            except Exception as e:
                # Очищаем все временные файлы в случае ошибки
                clean_up_files(pdf_path=filepath, excel_path=output_path)
                error_message = str(e)
                if "Не удалось извлечь данные" in error_message:
                    flash('Не удалось извлечь данные из PDF файла. Убедитесь, что файл содержит корректные данные.')
                else:
                    flash(f'Ошибка при обработке файла: {error_message}')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'Ошибка при загрузке файла: {str(e)}')
            return redirect(request.url)
    
    return render_template('upload.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 