#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import speech_recognition as sr
import ollama
import json
import os
import threading
import pystray
import pyttsx3
import re
import time
import subprocess
import uuid
import webbrowser
import shutil
import requests
import pytz
from datetime import datetime
from pynput.keyboard import Key, Controller
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ddgs import DDGS

# ========== ВЕРСИЯ И ОБНОВЛЕНИЯ ==========
CURRENT_VERSION = "1.0.1"
UPDATE_URL = "https://raw.githubusercontent.com/sergio000x/echo-updates/main/version.txt"
DOWNLOAD_URL = "https://raw.githubusercontent.com/sergio000x/echo-updates/main/assistant.py"

def check_for_updates():
    """Проверяет наличие новой версии"""
    try:
        response = requests.get(UPDATE_URL, timeout=5)
        if response.status_code == 200:
            latest_version = response.text.strip()
            if latest_version > CURRENT_VERSION:
                print("\n" + "="*50)
                print("🔄 ДОСТУПНО ОБНОВЛЕНИЕ!")
                print("="*50)
                print(f"Текущая версия: {CURRENT_VERSION}")
                print(f"Новая версия: {latest_version}")
                print("="*50)
                print("При обновлении будут сохранены:")
                print("  ✅ Лицензия")
                print("  ✅ История чата")
                print("  ✅ Часовой пояс")
                
                answer = input("\nОбновить? (y/n): ").strip().lower()
                if answer == 'y':
                    new_code = requests.get(DOWNLOAD_URL, timeout=10)
                    if new_code.status_code == 200:
                        if os.path.exists("assistant.py"):
                            shutil.copy("assistant.py", "assistant_backup.py")
                            print("📦 Резервная копия сохранена")
                        
                        with open("assistant_new.py", "w", encoding="utf-8") as f:
                            f.write(new_code.text)
                        os.replace("assistant_new.py", "assistant.py")
                        print("✅ Обновление установлено! Перезапустите Эхо.")
                        input("Нажмите Enter для выхода...")
                        exit()
                    else:
                        print("❌ Ошибка загрузки")
                else:
                    print("Обновление отложено")
    except Exception as e:
        print(f"⚠️ Ошибка проверки обновлений: {e}")

# ========== НАСТРОЙКИ ==========
WAKE_WORD = "эхо"
MODEL_NAME = "deepseek-r1:14b"
HISTORY_FILE = "chat_history.json"
LICENSE_FILE = "license_accepted.txt"
CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_ID = "15hsAGY9O1-vat7fHuekP1yt2NsNxcWfsz4-TjgWrx80"
TIMEZONE_FILE = "timezone.txt"

# ========== ЧАСОВОЙ ПОЯС ==========
def get_timezone_offset():
    if os.path.exists(TIMEZONE_FILE):
        try:
            with open(TIMEZONE_FILE, 'r', encoding='utf-8') as f:
                return int(f.read().strip())
        except:
            pass
    return None

def save_timezone(offset: int):
    with open(TIMEZONE_FILE, 'w', encoding='utf-8') as f:
        f.write(str(offset))

def setup_timezone():
    if get_timezone_offset() is not None:
        return
    
    print("\n" + "="*50)
    print("🕐 НАСТРОЙКА ЧАСОВОГО ПОЯСА")
    print("="*50)
    print("Примеры: Москва → +3, Калининград → +2, Владивосток → +10\n")
    
    while True:
        try:
            offset = int(input("Ваше смещение от UTC: ").strip())
            if -12 <= offset <= 14:
                save_timezone(offset)
                print(f"✅ Часовой пояс сохранён: UTC{offset:+d}\n")
                break
            else:
                print("❌ Смещение от -12 до +14")
        except ValueError:
            print("❌ Введите целое число")

def get_current_time():
    offset = get_timezone_offset()
    if offset is None:
        return "Часовой пояс не настроен"
    utc_now = datetime.utcnow()
    local_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(pytz.FixedOffset(offset * 60))
    return local_now.strftime("Сейчас %H часов %M минут")

def get_current_date():
    offset = get_timezone_offset()
    if offset is None:
        return "Часовой пояс не настроен"
    utc_now = datetime.utcnow()
    local_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(pytz.FixedOffset(offset * 60))
    return local_now.strftime("Сегодня %d %B %Y года")

# ========== ПОИСК В ИНТЕРНЕТЕ ==========
def search_internet(query: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return f"Ничего не найдено по запросу '{query}'."
            response = f"Результаты поиска по запросу '{query}':\n\n"
            for i, r in enumerate(results, 1):
                title = r.get('title', 'Без заголовка')
                body = r.get('body', '')
                if len(body) > 300:
                    body = body[:300] + "..."
                response += f"{i}. {title}\n   {body}\n\n"
            return response
    except Exception as e:
        return f"Ошибка поиска: {e}"

# ========== ЛИЦЕНЗИРОВАНИЕ ==========
def get_hardware_id():
    mac = uuid.getnode()
    return ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))

def verify_key_online():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'HardwareID: (.+)', content)
                if match:
                    saved_hardware = match.group(1).strip()
                    if saved_hardware != get_hardware_id():
                        print("\n🔒 ЛИЦЕНЗИЯ НЕДЕЙСТВИТЕЛЬНА (другой компьютер)")
                        input("\nНажмите Enter для выхода...")
                        return False
                return True
        except:
            pass
        return True
    
    print("\n" + "="*50)
    print("🔐 АКТИВАЦИЯ ЭХО")
    print("="*50)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Файл {CREDENTIALS_FILE} не найден!")
        input("\nНажмите Enter для выхода...")
        return False
    
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        input("\nНажмите Enter для выхода...")
        return False
    
    for attempt in range(3):
        key = input("Введите ключ: ").strip()
        try:
            all_keys = sheet.get_all_records()
            found = False
            row_num = None
            for idx, row in enumerate(all_keys, start=2):
                if row.get("Key") == key and row.get("Used") == "FALSE":
                    found = True
                    row_num = idx
                    break
            
            if found:
                hardware_id = get_hardware_id()
                sheet.batch_update([
                    {'range': f'B{row_num}', 'values': [["TRUE"]]},
                    {'range': f'D{row_num}', 'values': [[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]},
                    {'range': f'E{row_num}', 'values': [[hardware_id]]}
                ])
                with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                    f.write(f"Активировано: {datetime.now()}\nКлюч: {key}\nHardwareID: {hardware_id}\n")
                print("\n✅ Активация успешна!\n")
                return True
            else:
                print("❌ Неверный или уже использованный ключ.")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        if attempt < 2:
            print(f"Осталось попыток: {2-attempt}\n")
    
    print("\n❌ Превышено количество попыток.")
    input("Нажмите Enter для выхода...")
    return False

# ========== ОЧИСТКА ТЕКСТА ==========
def clean_text(text):
    text = re.sub(r'[^\w\s\.,!?\-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[:;][()dD]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ========== ГОЛОС ==========
def speak(text):
    text = clean_text(text)
    print(f"🎤 Эхо: {text}")
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for voice in voices:
            if "irina" in voice.name.lower() or "pavel" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 160)
        engine.setProperty('volume', 0.9)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"Ошибка озвучки: {e}")

# ========== ИСТОРИЯ ==========
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [{"role": "system", "content": "Ты — Эхо, голосовой помощник. Говори на русском. Отвечай вежливо. Никогда не используй эмодзи. Пиши только чистый текст. Обращайся на 'вы'."}]

def save_history(messages):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

# ========== РАСПОЗНАВАНИЕ ==========
recognizer = sr.Recognizer()
microphone = sr.Microphone()

with microphone as source:
    print("🔧 Калибровка микрофона...")
    recognizer.adjust_for_ambient_noise(source, duration=2)
    recognizer.energy_threshold = 3000
    recognizer.dynamic_energy_threshold = True
    print("✅ Калибровка завершена")

def listen_for_wake_word():
    with microphone as source:
        print("🎤 Слушаю... (скажите 'Эхо')")
        while True:
            try:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                text = recognizer.recognize_google(audio, language="ru-RU").lower()
                if WAKE_WORD in text or "echo" in text:
                    speak("Да, слушаю. Чем могу помочь?")
                    return True
            except:
                pass

def listen_command():
    with microphone as source:
        print("🎤 Команда...")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            text = recognizer.recognize_google(audio, language="ru-RU")
            print(f"🗣️ Вы: {text}")
            return text.lower()
        except:
            speak("Не расслышал, повторите.")
            return None

def listen_for_multiple_commands():
    start_time = time.time()
    while time.time() - start_time < 20:
        print(f"🎤 Жду следующую команду... ({20 - int(time.time() - start_time)} сек)")
        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=5)
                text = recognizer.recognize_google(audio, language="ru-RU")
                print(f"🗣️ Вы: {text}")
                return text.lower()
        except:
            continue
    return None

# ========== УПРАВЛЕНИЕ СИСТЕМОЙ ==========
keyboard = Controller()

def find_and_run_app(app_name):
    start_menu_path = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")
    for root, dirs, files in os.walk(start_menu_path):
        for file in files:
            if file.endswith('.lnk') and app_name.lower() in file.lower().replace('.lnk', ''):
                try:
                    os.startfile(os.path.join(root, file))
                    return True
                except:
                    pass
    return False

def close_active_window():
    try:
        keyboard.press(Key.alt_l)
        keyboard.press(Key.f4)
        keyboard.release(Key.f4)
        keyboard.release(Key.alt_l)
        return True
    except:
        return False

def close_app_by_name(app_name):
    try:
        os.system(f"taskkill /f /im {app_name}.exe 2>nul")
        return True
    except:
        return False

def close_app_fuzzy(app_name):
    try:
        result = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if app_name.lower() in line.lower():
                proc_name = line.split('","')[0].strip('"')
                os.system(f"taskkill /f /im {proc_name} 2>nul")
                return proc_name
    except:
        pass
    return None

def execute_system_command(cmd):
    cmd = cmd.lower()
    
    # Время и дата
    if any(word in cmd for word in ["сколько времени", "который час", "текущее время"]):
        speak(get_current_time())
        return True
    if any(word in cmd for word in ["какая сегодня дата", "сегодняшняя дата", "какое сегодня число"]):
        speak(get_current_date())
        return True
    
    # Громкость
    if any(word in cmd for word in ["громче", "увеличь громкость"]):
        for _ in range(5):
            keyboard.press(Key.media_volume_up)
            keyboard.release(Key.media_volume_up)
        speak("Громкость увеличена")
        return True
    if any(word in cmd for word in ["тише", "уменьши громкость"]):
        for _ in range(5):
            keyboard.press(Key.media_volume_down)
            keyboard.release(Key.media_volume_down)
        speak("Громкость уменьшена")
        return True
    
    # Мультимедиа
    if any(word in cmd for word in ["следующий трек", "следующая песня"]):
        keyboard.press(Key.media_next)
        keyboard.release(Key.media_next)
        speak("Следующий трек")
        return True
    if any(word in cmd for word in ["пауза", "плей"]):
        keyboard.press(Key.media_play_pause)
        keyboard.release(Key.media_play_pause)
        speak("Пауза")
        return True
    
    # Запуск приложений
    if "запусти" in cmd or "открой" in cmd:
        words = cmd.split()
        for i, word in enumerate(words):
            if word in ["запусти", "открой"] and i+1 < len(words):
                app_to_run = ' '.join(words[i+1:])
                if find_and_run_app(app_to_run):
                    speak(f"Запускаю {app_to_run}")
                    return True
                else:
                    speak(f"Не нашёл {app_to_run}")
                    return True
    
    # Закрытие приложений
    if "закрой" in cmd:
        if any(word in cmd for word in ["это", "активное", "текущее", "окно"]):
            if close_active_window():
                speak("Активное окно закрыто")
                return True
        words = cmd.split()
        for i, word in enumerate(words):
            if word == "закрой" and i+1 < len(words):
                app_to_close = ' '.join(words[i+1:])
                if close_app_by_name(app_to_close):
                    speak(f"Закрываю {app_to_close}")
                    return True
                found = close_app_fuzzy(app_to_close)
                if found:
                    speak(f"Закрываю {found.replace('.exe', '')}")
                    return True
                else:
                    speak(f"Не нашёл запущенного {app_to_close}")
                    return True
    
    # Поиск в интернете
    if any(word in cmd for word in ["найди", "поищи", "найди в интернете", "загугли"]):
        search_query = cmd
        for word in ["найди", "поищи", "найди в интернете", "загугли", "эхо"]:
            search_query = search_query.replace(word, "")
        search_query = search_query.strip()
        if search_query:
            speak("Ищу в интернете...")
            results = search_internet(search_query)
            speak(results[:500])
            return True
        else:
            speak("Что именно найти?")
            return True
    
    return False

# ========== DEEPSEEK ==========
def ask_deepseek(question, messages):
    messages.append({"role": "user", "content": question})
    try:
        response = ollama.chat(model=MODEL_NAME, messages=messages)
        answer = response['message']['content']
        messages.append({"role": "assistant", "content": answer})
        if len(messages) > 30:
            messages[:] = [messages[0]] + messages[-29:]
        save_history(messages)
        return answer
    except Exception as e:
        return f"Ошибка: {e}"

# ========== ТРЕЙ ==========
def create_tray():
    try:
        icon_image = Image.open("icon.png")
    except:
        icon_image = Image.new('RGB', (64, 64), color='black')
    
    def on_quit():
        os._exit(0)
    
    menu = pystray.Menu(
        pystray.MenuItem("Эхо работает", lambda: None, default=True),
        pystray.MenuItem("Выйти", on_quit)
    )
    icon = pystray.Icon("echo", icon_image, "Эхо", menu)
    icon.run()

# ========== ГЛАВНЫЙ ЦИКЛ ==========
def main_loop():
    messages = load_history()
    print("🚀 Эхо запущен. Говорите 'Эхо'")
    while True:
        listen_for_wake_word()
        while True:
            command = listen_command()
            if not command:
                break
            
            if execute_system_command(command):
                continue
            
            speak("Обрабатываю...")
            answer = ask_deepseek(command, messages)
            speak(answer)
            
            print("\n⏳ Режим ожидания команд (20 секунд)...")
            next_command = listen_for_multiple_commands()
            if not next_command:
                print("🔇 Возврат в режим ожидания по слову 'Эхо'")
                break
            else:
                command = next_command
                if execute_system_command(command):
                    continue
                speak("Обрабатываю...")
                answer = ask_deepseek(command, messages)
                speak(answer)

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    setup_timezone()
    if not verify_key_online():
        exit()
    check_for_updates()
    assistant_thread = threading.Thread(target=main_loop, daemon=True)
    assistant_thread.start()
    create_tray()