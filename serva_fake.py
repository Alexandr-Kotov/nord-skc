import socket
import threading
import time
from datetime import datetime
import itertools

HOST = "0.0.0.0"
PORT = 6565
SEND_INTERVAL = 1.0  # секунды

# Реальные строки по мотивам твоих дампов
CSV_LINES = [
    "R2R2PF,J65,{ts},0.001,0.000,0.000,0.000,0.000,22.402,0.010,17.117,15.940,0.000,17.322,0.001,07\r\n",
    "R2R2PF,J65,{ts},0.003,0.000,0.000,0.000,0.000,22.725,0.010,17.117,15.940,0.000,17.322,0.001,07\r\n",
    "R2R2PF,J65,{ts},0.004,0.000,0.000,0.000,0.000,22.520,0.010,17.117,15.940,0.000,17.322,0.001,07\r\n",
    "R2R2PF,J65,{ts},0.001,0.000,0.000,0.000,0.000,22.800,0.010,17.117,15.940,0.000,17.322,0.001,07\r\n",
]

def log(msg):
    print(f"[SERVA FAKE] {msg}")

def handle_client(conn, addr):
    log(f"Client connected: {addr}")
    conn.settimeout(5.0)

    last_hello = 0
    csv_cycle = itertools.cycle(CSV_LINES)

    try:
        while True:
            # 1) читаем входящие данные (ждём $HELLO)
            try:
                data = conn.recv(1024)
                if not data:
                    log("Client disconnected")
                    break

                text = data.decode(errors="ignore").strip()
                if "$HELLO" in text:
                    last_hello = time.time()
                    log("Received $HELLO")

            except socket.timeout:
                pass

            # 2) если HELLO был недавно — шлём данные
            if time.time() - last_hello < 2.0:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = next(csv_cycle).format(ts=ts)
                conn.sendall(line.encode("ascii"))
                log(f"TX: {line.strip()}")
                time.sleep(SEND_INTERVAL)

    except Exception as e:
        log(f"Error: {e}")

    finally:
        conn.close()
        log("Connection closed")

def main():
    log(f"Listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)

        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
