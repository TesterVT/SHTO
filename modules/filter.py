import re
from unidecode import unidecode
import json

class FilterModule:
    def __init__(self):
        with open("data/banned_words.json", "r", encoding="utf-8") as f:
            self.banned_data = json.load(f)

    def clean_message(self, message_content):
        # Приводим сообщение к нижнему регистру
        message_content = message_content.lower()
        
        # Проверка на наличие URL в сообщении
        if re.search(r'https?://|www\.|discord\.gg|t\.me|vk\.com', message_content):
            return True  # Если есть URL, сразу возвращаем True (считаем это запрещённым)

        # Удаляем все символы, которые не буквы или цифры (эмодзи, спецсимволы)
        message_content = re.sub(r'[^a-zа-яё0-9\s]', '', message_content)
        
        # Нормализуем текст, приводим в формат без акцентов
        message_content = unidecode(message_content)
        
        return message_content

    def check_message(self, message_content):
        # Очищаем сообщение
        cleaned_message = self.clean_message(message_content)
        
        # Если сообщение содержит запрещённые URL
        if cleaned_message is True:
            return True

        # Проверка на наличие запрещенных слов
        for banned_word in self.banned_data["twitch_banned_words"]:
            if banned_word.lower() in cleaned_message:
                return True
        return False
