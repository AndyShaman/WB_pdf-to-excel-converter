import fitz
import pandas as pd
import os

def convert_pdf_to_excel(pdf_path, excel_path):
    try:
        print("Извлечение данных из PDF...")
        
        # Открываем PDF файл
        doc = fitz.open(pdf_path)
        
        # Получаем первую страницу
        page = doc[0]
        
        # Получаем текст страницы с информацией о структуре
        text_dict = page.get_text("dict")
        
        print("\nАнализ структуры документа...")
        print("Блоков на странице:", len(text_dict["blocks"]))
        
        # Собираем все текстовые блоки с их координатами
        text_blocks = []
        for block in text_dict["blocks"]:
            if block.get("type") == 0:  # текстовый блок
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            bbox = span["bbox"]  # [x0, y0, x1, y1]
                            height = bbox[3] - bbox[1]
                            # Увеличиваем максимальную высоту блока
                            if height < 20:  # Игнорируем только очень высокие блоки
                                text_blocks.append({
                                    'text': text,
                                    'x': bbox[0],
                                    'y': bbox[1],
                                    'width': bbox[2] - bbox[0],
                                    'height': height
                                })
        
        print(f"Найдено текстовых блоков: {len(text_blocks)}")
        
        # Выводим все блоки для анализа
        print("\nВсе текстовые блоки:")
        for block in sorted(text_blocks, key=lambda x: (x['y'], x['x'])):
            print(f"Текст: {block['text']}, X: {block['x']:.2f}, Y: {block['y']:.2f}")
        
        # Сортируем блоки по Y-координате для определения строк
        text_blocks.sort(key=lambda x: x['y'])
        
        # Примерные X-координаты колонок с увеличенными диапазонами
        column_ranges = {
            "Артикул": (55, 150),  # Сужаем диапазон для артикула, чтобы не захватывать номера строк
            "Количество": (350, 380),
            "Сумма выкупа, BYN, (вкл. НДС)": (430, 460)
        }
        
        # Находим все номера строк
        row_data = []
        header_found = False
        
        # Находим все возможные Y-координаты строк
        y_coordinates = set()
        for block in text_blocks:
            if block['x'] < 50 and block['text'].replace('.', '').isdigit():
                y_coordinates.add(block['y'])
        
        print(f"\nНайдено возможных Y-координат строк: {len(y_coordinates)}")
        print("Y-координаты:", sorted(y_coordinates))
        
        # Обрабатываем каждую Y-координату
        for y_coord in sorted(y_coordinates):
            # Собираем все блоки, которые находятся рядом с этой Y-координатой
            row_blocks = []
            for block in text_blocks:
                if abs(block['y'] - y_coord) < 8:  # Увеличиваем диапазон поиска
                    row_blocks.append(block)
            
            # Извлекаем данные из блоков
            row_info = {
                "Артикул": None,
                "Количество": None,
                "Сумма выкупа, BYN, (вкл. НДС)": None
            }
            
            # Сначала ищем артикул
            for block in sorted(row_blocks, key=lambda x: x['x']):
                if 55 <= block['x'] <= 150 and not block['text'].replace('.', '').isdigit():
                    row_info["Артикул"] = block['text']
                    break
            
            # Затем ищем остальные данные
            for block in row_blocks:
                # Определяем, к какой колонке относится текст
                for header in ["Количество", "Сумма выкупа, BYN, (вкл. НДС)"]:
                    x_min, x_max = column_ranges[header]
                    if x_min <= block['x'] <= x_max:
                        try:
                            # Проверяем, что это число
                            clean_text = block['text'].replace(" ", "").replace(",", ".")
                            float(clean_text)
                            row_info[header] = block['text']
                        except ValueError:
                            continue
            
            # Если нашли хотя бы артикул, добавляем строку
            if row_info["Артикул"]:
                print(f"\nНайдена строка на Y={y_coord:.2f}:")
                print("  Блоки в строке:", [(b['text'], b['x'], b['y']) for b in row_blocks])
                print("  Извлеченные данные:", row_info)
                row_data.append(row_info)
        
        print(f"\nИзвлечено строк с данными: {len(row_data)}")
        
        # Создаем DataFrame
        df = pd.DataFrame(row_data)
        
        # Удаляем пустые строки и строки, где все значения None
        df = df.replace("", pd.NA).dropna(how='all').fillna("")
        
        # Удаляем дубликаты, учитывая все колонки
        df = df.drop_duplicates(subset=['Артикул', 'Количество', 'Сумма выкупа, BYN, (вкл. НДС)'], keep='first')
        
        # Сортируем DataFrame по номеру строки (если есть) или по артикулу
        df = df.sort_values(by=['Артикул'])
        
        print(f"После очистки осталось строк: {len(df)}")
        
        if len(df) > 0:
            print("\nПример данных:")
            print(df.head())
            print("\nВсе данные:")
            print(df)
        
        # Сохраняем в Excel
        print("\nСохранение данных в Excel...")
        if not df.empty:
            output_file = "output.xlsx"
            try:
                # Пробуем сохранить файл
                df.to_excel(output_file, index=False)
                print(f"Файл успешно сохранен: {output_file}")
            except PermissionError:
                # Если файл открыт, пробуем сохранить с другим именем
                import os
                base, ext = os.path.splitext(output_file)
                i = 1
                while True:
                    try:
                        new_file = f"{base}_{i}{ext}"
                        df.to_excel(new_file, index=False)
                        print(f"Файл сохранен как: {new_file}")
                        break
                    except PermissionError:
                        i += 1
                        if i > 10:  # Максимум 10 попыток
                            print("Не удалось сохранить файл. Пожалуйста, закройте Excel и попробуйте снова.")
                            break
        return True
    
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        return False

def extract_data_from_page(page):
    print(f"\nОбработка страницы {page.number + 1}...")
    
    # Получаем все текстовые блоки на странице
    text_blocks = []
    words = page.get_text("words")  # Получаем слова вместо блоков
    
    for word in words:
        text = word[4].strip()
        if text:
            x = word[0]  # X-координата
            y = word[1]  # Y-координата
            text_blocks.append((text, x, y))
    
    print(f"Найдено текстовых блоков: {len(text_blocks)}")
    
    # Находим все возможные Y-координаты для строк
    y_coords = sorted(list(set(block[2] for block in text_blocks)))
    
    # Группируем блоки по Y-координатам с учетом допуска
    y_tolerance = 2  # Уменьшаем допуск с 4 до 2
    rows = []
    processed_y = set()
    row_number = 0  # Добавляем счетчик строк
    
    for y in y_coords:
        if any(abs(py - y) <= y_tolerance for py in processed_y):
            continue
            
        # Находим все блоки рядом с текущей Y-координатой
        row_blocks = []
        for block in text_blocks:
            if abs(block[2] - y) <= y_tolerance:
                row_blocks.append(block)
                processed_y.add(block[2])
        
        if row_blocks:
            print(f"\nНайдена строка на Y={y:.2f}:")
            print(f"  Блоки в строке: {row_blocks}")
            
            # Проверяем наличие артикула в строке
            article = None
            quantity = None
            amount = None
            
            for block in row_blocks:
                text, x, _ = block
                
                # Поиск артикула (X: 55-150)
                if 55 <= x <= 150 and not text.isdigit():
                    article = text
                
                # Поиск количества (X: 359-365)
                if 359 <= x <= 365 and text.replace('.', '').isdigit():
                    quantity = text
                
                # Поиск суммы (X: 434-450)
                if 434 <= x <= 450 and ',' in text:
                    amount = text
            
            if article and quantity and amount:
                row_number += 1  # Увеличиваем счетчик только для валидных строк
                row_data = {
                    'Номер строки': row_number + (page.number * 100),  # Добавляем смещение для каждой страницы
                    'Артикул': article,
                    'Количество': quantity,
                    'Сумма выкупа, BYN, (вкл. НДС)': amount
                }
                print(f"  Извлеченные данные: {row_data}")
                rows.append(row_data)
            else:
                print(f"  Пропущена строка - не найдены все необходимые данные:")
                print(f"    Артикул: {article}")
                print(f"    Количество: {quantity}")
                print(f"    Сумма: {amount}")
    
    return rows

if __name__ == "__main__":
    # Путь к входному PDF файлу
    pdf_path = "Уведомление о выкупе №297750693 от 2025-02-10.pdf"
    
    print("Извлечение данных из PDF...")
    
    # Открываем PDF файл
    pdf_document = fitz.open(pdf_path)
    print(f"\nКоличество страниц в документе: {len(pdf_document)}")
    
    # Собираем данные со всех страниц
    all_rows = []
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        rows = extract_data_from_page(page)
        all_rows.extend(rows)
    
    # Создаем DataFrame
    df = pd.DataFrame(all_rows)
    
    # Удаляем дубликаты, учитывая все колонки кроме номера строки
    df = df.drop_duplicates(subset=['Артикул', 'Количество', 'Сумма выкупа, BYN, (вкл. НДС)'], keep='first')
    
    # Сортируем DataFrame по номеру строки
    df = df.sort_values(by=['Номер строки'])
    
    # Удаляем столбец с номером строки перед сохранением
    df = df.drop('Номер строки', axis=1)
    
    print(f"\nВсего извлечено строк: {len(df)}")
    
    if not df.empty:
        print("\nПример данных:")
        print(df.head().to_string())
        
        print("\nВсе данные:")
        print(df.to_string())
    else:
        print("\nНе удалось извлечь данные из документа.")
    
    # Сохраняем результаты в Excel
    if not df.empty:
        output_file = "output.xlsx"
        print(f"\nСохранение данных в Excel...")
        try:
            # Пробуем сохранить файл
            df.to_excel(output_file, index=False)
            print(f"Файл успешно сохранен: {output_file}")
        except PermissionError:
            # Если файл открыт, пробуем сохранить с другим именем
            import os
            base, ext = os.path.splitext(output_file)
            i = 1
            while True:
                try:
                    new_file = f"{base}_{i}{ext}"
                    df.to_excel(new_file, index=False)
                    print(f"Файл сохранен как: {new_file}")
                    break
                except PermissionError:
                    i += 1
                    if i > 10:  # Максимум 10 попыток
                        print("Не удалось сохранить файл. Пожалуйста, закройте Excel и попробуйте снова.")
                        break
    
    # Закрываем PDF файл
    pdf_document.close() 