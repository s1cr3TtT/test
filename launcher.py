import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
log_file = Path(__file__).resolve().parent / "launcher_error.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

target_exe = "client.exe"
base_dir = Path(__file__).resolve().parent
exe_path = base_dir / target_exe

def launch_client():
    # If not found in current directory, check PATH or current working dir
    resolved_path = exe_path if exe_path.exists() else Path(target_exe)

    try:
        # Launching client.exe detached / non-blocking
        process = subprocess.Popen(
            [str(resolved_path)],
            cwd=str(base_dir),
            shell=False
        )
        print("всё успешно открыто!")
        return 0
    except FileNotFoundError as fnf_err:
        err_msg = f"Файл '{target_exe}' не найден по пути {resolved_path}. Причина: {fnf_err}"
        print(f"[ОШИБКА] {err_msg}")
        logging.error(err_msg)
        return 1
    except PermissionError as perm_err:
        err_msg = f"Отказано в доступе при попытке запустить '{target_exe}'. Причина: {perm_err}"
        print(f"[ОШИБКА] {err_msg}")
        logging.error(err_msg)
        return 2
    except Exception as ex:
        err_msg = f"Не удалось открыть '{target_exe}'. Причина: {type(ex).__name__} - {ex}"
        print(f"[ОШИБКА] {err_msg}")
        logging.exception(err_msg)
        return 3

if __name__ == "__main__":
    sys.exit(launch_client())
