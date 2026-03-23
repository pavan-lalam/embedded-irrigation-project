"""
server.py — Arduino Serial Bridge + Web API
Reads from Arduino Due over USB Serial and serves data via Flask.

Run locally:  python server.py
Then open:    dashboard.html  in your browser
"""

import serial
import threading
import time
import re
from flask import Flask, jsonify
from flask_cors import CORS

# ── CONFIG ─────────────────────────────────────
SERIAL_PORT = "COM11"      # Windows: COM3, COM4 ...
                          # Mac/Linux: /dev/ttyACM0
BAUD_RATE   = 9600
# ───────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

data = {
    "moistureA": 0, "moistureB": 0, "moistureC": 0,
    "deadlineA": 9999, "deadlineB": 9999, "deadlineC": 9999,
    "valveA": "OFF", "valveB": "OFF", "valveC": "OFF",
    "pump": "OFF",
    "temp": 0, "humidity": 0,
    "connected": False,
    "lastUpdate": ""
}
lock = threading.Lock()


def parse_line(line):
    line = line.strip()
    patterns = {
        "moistureA": r"Moisture A:\s*([\d.]+)",
        "moistureB": r"Moisture B:\s*([\d.]+)",
        "moistureC": r"Moisture C:\s*([\d.]+)",
        "deadlineA": r"Deadline A:\s*([\d.]+)",
        "deadlineB": r"Deadline B:\s*([\d.]+)",
        "deadlineC": r"Deadline C:\s*([\d.]+)",
        "valveA":    r"Valve A:\s*(ON|OFF)",
        "valveB":    r"Valve B:\s*(ON|OFF)",
        "valveC":    r"Valve C:\s*(ON|OFF)",
        "pump":      r"Pump:\s*(ON|OFF)",
    }
    m = re.search(r"Temp:\s*([\d.]+)\s*C\s*Humidity:\s*([\d.]+)", line)
    if m:
        with lock:
            data["temp"]     = float(m.group(1))
            data["humidity"] = float(m.group(2))
        return
    for key, pat in patterns.items():
        m = re.search(pat, line)
        if m:
            with lock:
                try:    data[key] = float(m.group(1))
                except: data[key] = m.group(1)
            return


def serial_reader():
    while True:
        try:
            print(f"[server] Connecting to {SERIAL_PORT}...")
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
            print("[server] Connected to Arduino!")
            with lock:
                data["connected"] = True
            while True:
                raw = ser.readline()
                line = raw.decode("utf-8", errors="ignore")
                if line.strip():
                    parse_line(line)
                    with lock:
                        data["lastUpdate"] = time.strftime("%H:%M:%S")
        except Exception as e:
            print(f"[server] Serial error: {e} — retrying in 3s...")
            with lock:
                data["connected"] = False
            time.sleep(3)


@app.route("/data")
def get_data():
    with lock:
        return jsonify(dict(data))


if __name__ == "__main__":
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    print("[server] API running at http://localhost:5000/data")
    app.run(host="0.0.0.0", port=5000, debug=False)
