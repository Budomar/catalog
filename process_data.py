import pandas as pd
import json
import re
import os
from datetime import datetime
import requests

def main():
    try:
        print("Загрузка данных из Google Sheets...")
        
        # Прямые ссылки на CSV экспорт Google Sheets
        price_url = "https://docs.google.com/spreadsheets/d/19PRNpA6F_HMI6iHSCg2iJF52PnN203ckY1WnqY_t5fc/export?format=csv"
        stock_url = "https://docs.google.com/spreadsheets/d/1o0e3-E20mQsWToYVQpCHZgLcbizCafLRpoPdxr8Rqfw/export?format=csv"
        
        # Загружаем данные
        print("Загружаем прайс...")
        price_df = pd.read_csv(price_url)
        print("Колонки в прайсе:", price_df.columns.tolist())
        
        print("Загружаем остатки...")
        stock_df = pd.read_csv(stock_url)
        print("Колонки в остатках:", stock_df.columns.tolist())
        
        print("Обработка данных...")
        
        # Автоматически находим нужные колонки
        def find_column(df, possible_names):
            for col in df.columns:
                col_lower = str(col).lower()
                if any(name.lower() in col_lower for name in possible_names):
                    return col
            return None
        
        # Находим колонки в прайсе
        article_col_price = find_column(price_df, ['артикул', 'article', 'код', 'articul', 'sku'])
        name_col = find_column(price_df, ['товар', 'наименование', 'модель', 'name', 'product', 'название'])
        price_col = find_column(price_df, ['розничная', 'цена', 'price', 'retail', 'стоимость', 'руб'])
        
        print(f"Найдены колонки в прайсе: Артикул='{article_col_price}', Название='{name_col}', Цена='{price_col}'")
        
        # Находим колонки в остатках
        article_col_stock = find_column(stock_df, ['артикул', 'article', 'код', 'articul', 'sku'])
        stock_col = find_column(stock_df, ['в наличии', 'остаток', 'количество', 'quantity', 'stock', 'наличие', 'кол-во'])
        
        print(f"Найдены колонки в остатках: Артикул='{article_col_stock}', Наличие='{stock_col}'")
        
        if not all([article_col_price, name_col, price_col, article_col_stock, stock_col]):
            raise ValueError("Не найдены все необходимые колонки в таблицах")
        
        # Создаем чистые датафреймы
        price_clean = price_df[[article_col_price, name_col, price_col]].copy()
        price_clean.columns = ['Артикул', 'Модель', 'Цена']
        
        stock_clean = stock_df[[article_col_stock, stock_col]].copy()
        stock_clean.columns = ['Артикул', 'В_наличии']
        
        # Очистка данных
        price_clean = price_clean.dropna(subset=['Артикул'])
        price_clean['Артикул'] = price_clean['Артикул'].astype(str).str.strip()
        
        stock_clean = stock_clean.dropna(subset=['Артикул'])
        stock_clean['Артикул'] = stock_clean['Артикул'].astype(str).str.strip()
        
        # Обработка цены
        def parse_price(price):
            try:
                if pd.isna(price):
                    return 0.0
                price_str = str(price).replace(' ', '').replace(',', '.')
                price_str = re.sub(r'[^\d\.]', '', price_str)
                return float(price_str)
            except:
                return 0.0
        
        price_clean['Цена'] = price_clean['Цена'].apply(parse_price)
        
        # Обработка количества
        def parse_quantity(qty):
            try:
                if pd.isna(qty):
                    return 0
                qty_str = str(qty).replace(' ', '').replace(',', '.')
                qty_val = float(qty_str)
                return max(0, int(qty_val))
            except:
                return 0
        
        stock_clean['В_наличии'] = stock_clean['В_наличии'].apply(parse_quantity)
        
        # Объединяем данные
        merged_df = pd.merge(price_clean, stock_clean, on='Артикул', how='left')
        merged_df['В_наличии'] = merged_df['В_наличии'].fillna(0).astype(int)
        
        # Функция для определения типа товара
        def detect_product_type(model_name):
            """Определяет тип товара по названию"""
            model = str(model_name).upper()
            
            if 'КОТЕЛ' in model:
                return 'boiler'
            elif 'БОЙЛЕР' in model:
                return 'water_heater'
            elif 'ДЫМОХОД' in model or 'АДАПТЕР' in model:
                return 'chimney'
            elif 'КОМПЛЕКТ' in model or 'ДАТЧИК' in model:
                return 'accessory'
            else:
                return 'other'
        
        # Функция для извлечения информации в зависимости от типа товара
        def extract_info(model):
            model_str = str(model).upper()
            product_type = detect_product_type(model_str)
            
            # Для котлов
            if product_type == 'boiler':
                # Правила сопоставления моделей и мощностей
                power_patterns = [
                    (r'(T2|M6|M30|B20|B30|C30|C11|Q3)[^\d]*(\d+)', 2),  # METEOR T2 45 H
                    (r'(\d+)\s*(C|H|С|Х|кВт|KW)', 1),  # 24 C, 28 H
                    (r'ГАЗ\s*6000\s*(\d+)', 1),  # LaggarTT ГАЗ 6000 24 С
                    (r'MK\s*(\d+)', 1),  # MK 250, MK 350
                    (r'LL1GBQ(\d+)', 1),  # Devotion LL1GBQ30
                    (r'LN1GBQ(\d+)', 1),  # Devotion LN1GBQ60
                    (r'L1PB(\d+)', 1)  # Devotion L1PB20
                ]
                
                power = "Не указана"
                for pattern, group in power_patterns:
                    match = re.search(pattern, model_str)
                    if match:
                        power = match.group(group)
                        break
                
                # Если не нашли по шаблонам, ищем любое подходящее число
                if power == "Не указана":
                    numbers = re.findall(r'\b(\d{2,3})\b', model_str)
                    if numbers:
                        power = numbers[0]
                
                # Определяем контуры (особое исключение для LN1GBQ60 - одноконтурный)
                if 'LN1GBQ60' in model_str:
                    contours = "Одноконтурный"
                elif any(x in model_str for x in [' C', 'С ', 'C)', '-C', ' C ', ' С ']):
                    contours = "Двухконтурный"
                elif any(x in model_str for x in [' H', 'Н ', 'H)', '-H', ' H ', ' Н ']):
                    contours = "Одноконтурный"
                else:
                    contours = "Двухконтурный" if 'НАСТЕННЫЙ' in model_str else "Одноконтурный"
                
                # Wi-Fi
                wifi = "Да" if any(x in model_str for x in ['WI-FI', 'WIFI', 'ВАЙ-ФАЙ', 'WI FI']) else "Нет"
                
                return power, contours, wifi, product_type
            
            # Для бойлеров - извлекаем объем
            elif product_type == 'water_heater':
                volume_match = re.search(r'G\s*(\d+)', model_str)
                volume = volume_match.group(1) if volume_match else "Не указан"
                return volume, "", "", product_type
            
            # Для дымоходов - извлекаем диаметр и тип
            elif product_type == 'chimney':
                # Диаметр
                diameter_match = re.search(r'DN(\d+/\d+)', model_str)
                diameter = diameter_match.group(1) if diameter_match else "Не указан"
                
                # Тип (PP - конденсационный, иначе обычный)
                chimney_type = "конденсационный" if 'PP' in model_str else "обычный"
                
                return diameter, chimney_type, "", product_type
            
            # Для комплектующих - без дополнительных характеристик
            elif product_type == 'accessory':
                return "", "", "", product_type
            
            # Для других товаров
            else:
                return "", "", "", product_type
        
        # Функция для определения фото по модели и типу
        def get_image_for_model(model_name, product_type):
            """Определяет какое фото использовать для модели"""
            model = str(model_name).upper()
            
            # Для каждого типа товара своя логика
            if product_type == 'boiler':
                # Правила сопоставления моделей с фото
                if 'METEOR T2' in model:
                    return 'images/meteor-t2.jpg'
                elif 'METEOR C30' in model:
                    return 'images/meteor-c30.jpg'
                elif 'METEOR B30' in model:
                    return 'images/meteor-b30.jpg'
                elif 'METEOR B20' in model:
                    return 'images/meteor-b20.jpg'
                elif 'METEOR C11' in model:
                    return 'images/meteor-c11.jpg'
                elif 'METEOR Q3' in model:
                    return 'images/meteor-q3.jpg'
                elif 'METEOR M30' in model:
                    return 'images/meteor-m30.jpg'
                elif 'METEOR M6' in model:
                    return 'images/meteor-m6.jpg'
                elif 'LAGGARTT' in model or 'ГАЗ 6000' in model:
                    return 'images/laggartt.jpg'
                elif 'DEVOTION' in model:
                    return 'images/devotion.jpg'
                elif 'MK' in model:
                    return 'images/mk.jpg'
                else:
                    return 'images/default.jpg'
            
            elif product_type == 'water_heater':
                return 'images/water_heater.jpg'
            
            elif product_type == 'chimney':
                if 'АДАПТЕР' in model:
                    return 'images/adapter.jpg'
                elif 'PP' in model:
                    return 'images/chimney-condensing.jpg'
                else:
                    return 'images/chimney-regular.jpg'
            
            elif product_type == 'accessory':
                if 'ДАТЧИК' in model:
                    return 'images/sensor.jpg'
                elif 'КОМПЛЕКТ' in model:
                    return 'images/gas-kit.jpg'
                else:
                    return 'images/accessory.jpg'
            
            else:
                return 'images/default.jpg'
        
        # Применяем функции к каждой модели
        merged_df[['Мощность', 'Контуры', 'WiFi', 'Тип']] = merged_df['Модель'].apply(
            lambda x: pd.Series(extract_info(x))
        )
        
        # Добавляем фото с учетом типа товара
        merged_df['Фото'] = merged_df.apply(
            lambda row: get_image_for_model(row['Модель'], row['Тип']), axis=1
        )
        
        # Добавляем статус
        merged_df['Статус'] = merged_df['В_наличии'].apply(lambda x: 'В наличии' if x > 0 else 'Нет в наличии')
        
        # Добавляем поля для рекомендаций
        def get_product_category(model):
            model_str = str(model).lower()
            if 'meteor' in model_str:
                return 'meteor'
            elif 'laggartt' in model_str or 'газ' in model_str:
                return 'laggartt'
            elif 'devotion' in model_str:
                return 'devotion'
            elif 'mk' in model_str:
                return 'mk'
            else:
                return 'other'
        
        def get_power_level(power):
            try:
                power_val = int(power)
                if power_val <= 20:
                    return 'low'
                elif power_val <= 30:
                    return 'medium'
                else:
                    return 'high'
            except:
                return 'unknown'
        
        merged_df['Категория'] = merged_df['Модель'].apply(get_product_category)
        merged_df['Уровень_мощности'] = merged_df['Мощность'].apply(get_power_level)
        
        # Конвертируем в JSON
        result = merged_df.to_dict('records')
        
        # Сохраняем
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Готово! Обработано {len(result)} товаров")
        print(f"📊 В наличии: {sum(1 for x in result if x['В_наличии'] > 0)} товаров")
        
        # Покажем пример данных
        print("\nПример данных (первые 5 товаров):")
        for i, item in enumerate(result[:5]):
            print(f"{i+1}. {item['Артикул']} - {item['Модель'][:30]}...")
            print(f"   Тип: {item['Тип']}, Цена: {item['Цена']} руб., Наличие: {item['В_наличии']} шт.")
            if item['Тип'] == 'boiler':
                print(f"   Контуры: {item['Контуры']}, Мощность: {item['Мощность']} кВт, Wi-Fi: {item['WiFi']}")
            elif item['Тип'] == 'water_heater':
                print(f"   Объем: {item['Мощность']} л")
            elif item['Тип'] == 'chimney':
                print(f"   Диаметр: DN{item['Мощность']}, Тип: {item['Контуры']}")
            print(f"   Фото: {item['Фото']}")
        
        # Отправляем уведомления об обновлении данных
        print("📧 Отправка уведомлений об обновлении данных...")
        
        # Подсчитываем статистику для уведомлений
        new_products = len([p for p in result if p['В_наличии'] > 0])
        restocked_products = len([p for p in result if p['В_наличии'] > 5])
        
        print(f"✅ Новых товаров: {new_products}")
        print(f"📦 Пополненных позиций: {restocked_products}")
        
        # Сохраняем статистику для уведомлений
        update_data = {
            'timestamp': datetime.now().isoformat(),
            'total_products': len(result),
            'available_products': sum(1 for p in result if p['В_наличии'] > 0),
            'new_products': new_products,
            'restocked_products': restocked_products
        }
        
        with open('update_stats.json', 'w', encoding='utf-8') as f:
            json.dump(update_data, f, ensure_ascii=False, indent=2)
        
        # Отправляем push-уведомление (в демо-режиме просто логируем)
        try:
            print("🚀 Отправка push-уведомления о новом обновлении...")
            
            # Формируем сообщение для уведомления
            notification_message = f"Каталог обновлен! {new_products} новых товаров, {restocked_products} пополнений"
            
            print(f"📢 Уведомление отправлено: {notification_message}")
            
        except Exception as e:
            print(f"⚠️ Ошибка отправки уведомления: {e}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Создаем пустой файл чтобы сайт не сломался
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()