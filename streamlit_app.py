"""
streamlit_app.py — Irrigation Dashboard (Streamlit version)

LOCAL USE (with real Arduino):
  1. Run server.py first:     python server.py
  2. Run this app:            streamlit run streamlit_app.py

STREAMLIT CLOUD (demo mode):
  - No Arduino needed — shows simulated live data automatically
  - Just deploy this file + requirements.txt to Streamlit Cloud
"""

import streamlit as st
import requests
import time
import math
import random

# ── PAGE CONFIG ────────────────────────────────
st.set_page_config(
    page_title="Irrigation Monitor",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── CONFIG ──────────────────────────────────────
LOCAL_API   = "http://localhost:5000/data"
DEMO_MODE   = True   # Set False if running locally with server.py

# ── CUSTOM CSS ─────────────────────────────────
st.markdown("""
<style>
  /* White background */
  .stApp { background-color: #ffffff; }
  [data-testid="stAppViewContainer"] { background: #ffffff; }
  [data-testid="stHeader"] { background: #ffffff; border-bottom: 1px solid #e8eaee; }

  /* Hide default Streamlit elements */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e8eaee;
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }

  /* Zone card */
  .zone-card {
    background: #ffffff;
    border: 1px solid #e8eaee;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 12px;
  }

  /* Status badges */
  .badge-on  { background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0;
               padding:3px 12px; border-radius:999px; font-weight:700;
               font-size:12px; display:inline-block; }
  .badge-off { background:#f7f8fa; color:#6b7280; border:1px solid #e8eaee;
               padding:3px 12px; border-radius:999px; font-weight:600;
               font-size:12px; display:inline-block; }
  .badge-live { background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0;
                padding:4px 14px; border-radius:999px; font-weight:700;
                font-size:13px; display:inline-block; }
  .badge-demo { background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;
                padding:4px 14px; border-radius:999px; font-weight:700;
                font-size:13px; display:inline-block; }
  .badge-off2 { background:#fef2f2; color:#dc2626; border:1px solid #fecaca;
                padding:4px 14px; border-radius:999px; font-weight:700;
                font-size:13px; display:inline-block; }

  /* Progress bar colours */
  .stProgress > div > div > div > div { border-radius: 999px; }

  /* Section heading */
  .sec-title {
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: #6b7280; margin: 24px 0 12px;
  }

  /* Table */
  .edf-table { width:100%; border-collapse:collapse; font-size:13px; }
  .edf-table th { text-align:left; font-size:11px; font-weight:600;
                  color:#6b7280; text-transform:uppercase;
                  letter-spacing:.06em; padding:0 0 10px;
                  border-bottom:1px solid #e8eaee; }
  .edf-table td { padding:11px 0; border-bottom:1px solid #f1f3f5; }
  .edf-table tr:last-child td { border-bottom:none; }
  .pri-high   { color:#dc2626; font-weight:700; }
  .pri-medium { color:#ea580c; font-weight:600; }
  .pri-low    { color:#16a34a; font-weight:500; }
  .mono       { font-family: monospace; }
</style>
""", unsafe_allow_html=True)


# ── DEMO DATA GENERATOR ─────────────────────────
def get_demo_data():
    """Generate realistic fluctuating demo data when no Arduino is connected."""
    t = time.time()
    mA = 55 + 12 * math.sin(t / 30)  + random.uniform(-1, 1)
    mB = 45 + 10 * math.sin(t / 25 + 1) + random.uniform(-1, 1)
    mC = 35 + 8  * math.sin(t / 20 + 2) + random.uniform(-1, 1)
    mA, mB, mC = max(0, min(100, mA)), max(0, min(100, mB)), max(0, min(100, mC))

    def deadline(m, target):
        deficit = target - m
        return round(deficit / 2.0, 2) if deficit > 0 else 9999

    dA, dB, dC = deadline(mA, 70), deadline(mB, 60), deadline(mC, 50)

    # EDF: open valve for zone with smallest deadline
    active = None
    candidates = [(dA, "A"), (dB, "B"), (dC, "C")]
    valid = [(d, z) for d, z in candidates if d < 9999]
    if valid:
        active = min(valid, key=lambda x: x[0])[1]

    return {
        "moistureA": round(mA, 1), "moistureB": round(mB, 1), "moistureC": round(mC, 1),
        "deadlineA": dA, "deadlineB": dB, "deadlineC": dC,
        "valveA": "ON" if active == "A" else "OFF",
        "valveB": "ON" if active == "B" else "OFF",
        "valveC": "ON" if active == "C" else "OFF",
        "pump":   "ON" if active else "OFF",
        "temp":   round(28 + 3 * math.sin(t / 60), 1),
        "humidity": round(65 + 5 * math.sin(t / 45), 1),
        "connected": False,
        "lastUpdate": time.strftime("%H:%M:%S"),
        "demo": True
    }


def fetch_data():
    """Try real Arduino API first; fall back to demo data."""
    if not DEMO_MODE:
        try:
            r = requests.get(LOCAL_API, timeout=1.5)
            d = r.json()
            d["demo"] = False
            return d
        except:
            pass
    return get_demo_data()


# ── HELPERS ─────────────────────────────────────
def bar_color(val, target):
    ratio = val / target if target else 0
    if ratio < 0.5:  return "#dc2626"
    if ratio < 0.85: return "#ea580c"
    return "#16a34a"

def fmt_deadline(d):
    return "✓ Met" if d >= 9999 else f"{d:.2f}"

def priority_class(d):
    if d >= 9999: return "pri-low"
    if d < 5:     return "pri-high"
    return "pri-medium"

def priority_label(d):
    if d >= 9999: return "Satisfied"
    if d < 5:     return "URGENT"
    return "Normal"

def moisture_bar(val, target, key):
    color = bar_color(val, target)
    pct = min(int(val), 100)
    st.markdown(f"""
    <div style="background:#f7f8fa;border-radius:999px;height:8px;overflow:hidden;margin:4px 0 8px">
      <div style="width:{pct}%;height:100%;background:{color};border-radius:999px;
                  transition:width 0.8s ease"></div>
    </div>""", unsafe_allow_html=True)


# ── MAIN APP ─────────────────────────────────────
def main():
    # Header
    col_logo, col_status = st.columns([3, 1])
    with col_logo:
        st.markdown("## 💧 Irrigation Monitor")
        st.caption("Arduino Due · EDF Real-Time Control System")
    with col_status:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        status_placeholder = st.empty()

    st.markdown("<hr style='border:none;border-top:1px solid #e8eaee;margin:8px 0 4px'>",
                unsafe_allow_html=True)

    # Placeholders
    st.markdown("<div class='sec-title'>Soil Moisture · Zones</div>", unsafe_allow_html=True)
    zone_row   = st.columns(3)
    zone_ph    = [c.empty() for c in zone_row]

    st.markdown("<div class='sec-title'>Environment &amp; Pump</div>", unsafe_allow_html=True)
    env_row    = st.columns(4)
    env_ph     = [c.empty() for c in env_row]

    st.markdown("<div class='sec-title'>EDF Scheduling · Deadline Priority</div>",
                unsafe_allow_html=True)
    table_ph   = st.empty()

    # Auto-refresh loop
    while True:
        d = fetch_data()

        # ── Status badge
        if d.get("demo"):
            status_placeholder.markdown(
                "<div style='text-align:right'><span class='badge-demo'>⚡ Demo mode</span></div>",
                unsafe_allow_html=True)
        elif d.get("connected"):
            status_placeholder.markdown(
                f"<div style='text-align:right'><span class='badge-live'>● Live</span>"
                f"<br><small style='color:#6b7280;font-size:11px'>Updated {d['lastUpdate']}</small></div>",
                unsafe_allow_html=True)
        else:
            status_placeholder.markdown(
                "<div style='text-align:right'><span class='badge-off2'>✕ Disconnected</span></div>",
                unsafe_allow_html=True)

        # ── Zone cards
        zones = [
            ("A", "🌱", d["moistureA"], d["deadlineA"], d["valveA"], 70),
            ("B", "🌿", d["moistureB"], d["deadlineB"], d["valveB"], 60),
            ("C", "🍀", d["moistureC"], d["deadlineC"], d["valveC"], 50),
        ]
        for i, (name, icon, moist, dead, valve, target) in enumerate(zones):
            valve_badge = f"<span class='{'badge-on' if valve=='ON' else 'badge-off'}'>{valve}</span>"
            pct = min(int(moist), 100)
            color = bar_color(moist, target)
            zone_ph[i].markdown(f"""
            <div class="zone-card">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                <div style="display:flex;align-items:center;gap:10px">
                  <span style="font-size:20px">{icon}</span>
                  <div>
                    <div style="font-weight:700;font-size:15px">Zone {name}</div>
                    <div style="font-size:11px;color:#6b7280">Target {target}%</div>
                  </div>
                </div>
                {valve_badge}
              </div>
              <div style="font-size:34px;font-weight:700;font-family:monospace;letter-spacing:-1px;color:{color}">{moist:.1f}%</div>
              <div style="font-size:12px;color:#6b7280;margin-bottom:10px">Soil Moisture</div>
              <div style="background:#f7f8fa;border-radius:999px;height:8px;overflow:hidden">
                <div style="width:{pct}%;height:100%;background:{color};border-radius:999px"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:12px;color:#6b7280;margin-top:8px">
                <span>Deadline: <span style="font-family:monospace">{fmt_deadline(dead)}</span></span>
                <span>Target: {target}%</span>
              </div>
            </div>""", unsafe_allow_html=True)

        # ── Env cards
        temp_color = "#dc2626" if d["temp"] > 35 else "#ea580c" if d["temp"] > 30 else "#1a1d23"
        hum_color  = "#2563eb" if d["humidity"] > 80 else "#1a1d23"

        env_ph[0].markdown(f"""
        <div class="zone-card" style="padding:18px">
          <div style="font-size:26px;margin-bottom:6px">🌡️</div>
          <div style="font-size:28px;font-weight:700;font-family:monospace;color:{temp_color}">{d['temp']:.1f}</div>
          <div style="font-size:12px;color:#6b7280">Temperature (°C)</div>
        </div>""", unsafe_allow_html=True)

        env_ph[1].markdown(f"""
        <div class="zone-card" style="padding:18px">
          <div style="font-size:26px;margin-bottom:6px">💨</div>
          <div style="font-size:28px;font-weight:700;font-family:monospace;color:{hum_color}">{d['humidity']:.1f}</div>
          <div style="font-size:12px;color:#6b7280">Humidity (%)</div>
        </div>""", unsafe_allow_html=True)

        pump_on = d["pump"] == "ON"
        env_ph[2].markdown(f"""
        <div class="zone-card" style="padding:18px;grid-column:span 2">
          <div style="display:flex;align-items:center;gap:16px">
            <div style="width:52px;height:52px;border-radius:14px;
                        background:{'#eff6ff' if pump_on else '#f7f8fa'};
                        display:flex;align-items:center;justify-content:center;font-size:26px">💧</div>
            <div>
              <div style="font-weight:700;font-size:15px">Main Pump</div>
              <div style="font-size:13px;font-weight:600;color:{'#2563eb' if pump_on else '#6b7280'};margin-top:2px">
                {'ON — Running' if pump_on else 'OFF — Standby'}
              </div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        env_ph[3].markdown(f"""
        <div class="zone-card" style="padding:18px">
          <div style="font-size:26px;margin-bottom:6px">⏱️</div>
          <div style="font-size:18px;font-weight:700;font-family:monospace">{d['lastUpdate']}</div>
          <div style="font-size:12px;color:#6b7280">Last update</div>
        </div>""", unsafe_allow_html=True)

        # ── EDF Table
        rows = sorted([
            ("A 🌱", d["moistureA"], 70, d["deadlineA"]),
            ("B 🌿", d["moistureB"], 60, d["deadlineB"]),
            ("C 🍀", d["moistureC"], 50, d["deadlineC"]),
        ], key=lambda x: x[3])

        rows_html = ""
        for i, (zone, moist, target, dead) in enumerate(rows):
            pc = priority_class(dead)
            pl = priority_label(dead)
            prefix = "▶ " if i == 0 and dead < 9999 else ""
            deficit = max(0, target - moist)
            rows_html += f"""
            <tr>
              <td><strong>Zone {zone}</strong></td>
              <td class="mono">{moist:.1f}%</td>
              <td class="mono">{target}%</td>
              <td class="mono">{deficit:.1f}%</td>
              <td class="mono {pc}">{fmt_deadline(dead)}</td>
              <td class="{pc}">{prefix}{pl}</td>
            </tr>"""

        table_ph.markdown(f"""
        <div class="zone-card">
          <table class="edf-table">
            <thead><tr>
              <th>Zone</th><th>Moisture</th><th>Target</th>
              <th>Deficit</th><th>Deadline score</th><th>Priority</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>""", unsafe_allow_html=True)

        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
