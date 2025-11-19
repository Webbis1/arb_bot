import time
import sys

def temp_with_permanent_below(temp_text, perm_text, delay=3):
    # Временное сообщение в первой строке
    print(temp_text, end='', flush=True)
    time.sleep(delay)
    
    # Очищаем и переходим на новую строку для постоянного сообщения
    print('\r' + ' ' * len(temp_text))  # очистка + перевод строки
    print(perm_text)  # постоянное сообщение

# Использование
temp_with_permanent_below(
    "Загрузка завершена!", 
    "Программа готова к работе.",
    3
)