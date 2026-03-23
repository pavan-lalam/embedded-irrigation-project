"""
streamlit_app.py — Irrigation Dashboard (Enhanced v2)

LOCAL USE (with real Arduino):
  1. python server.py                     ← Terminal 1
  2. streamlit run streamlit_app.py       ← Terminal 2
  3. Set DEMO_MODE = False below

STREAMLIT CLOUD:
  Keep DEMO_MODE = True → animated demo data shown automatically
  Upload: streamlit_app.py + server.py + requirements.txt
"""

import streamlit as st
import requests
import time
import math
import random
from collections import deque
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ═══════════════════════════════════════════════════════
#  CONFIG  — only change things here
# ═══════════════════════════════════════════════════════
LOCAL_API   = "http://localhost:5000/data"
DEMO_MODE   = True       # ← False when running locally with server.py
HISTORY_LEN = 60         # data points kept in history charts
REFRESH_SEC = 2          # seconds between refreshes

TARGETS     = {"A": 70, "B": 60, "C": 50}
ZONE_COLOR  = {"A": "#2563eb", "B": "#16a34a", "C": "#f97316"}
ZONE_LIGHT  = {"A": "#eff6ff", "B": "#f0fdf4", "C": "#fff7ed"}
ZONE_BORDER = {"A": "#bfdbfe", "B": "#bbf7d0", "C": "#fed7aa"}

# ═══════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════
st.set_page_config(
    page_title="Irrigation Monitor",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],
section.main>div{background:#f0f4f8!important}
[data-testid="stHeader"]{background:#ffffff!important;
  border-bottom:1.5px solid #dde3ec!important}
#MainMenu,footer{visibility:hidden}
.block-container{padding:1.2rem 2.2rem 3rem;max-width:1380px}

.card{background:#ffffff;border:1px solid #dde3ec;border-radius:18px;
  padding:22px 24px;
  box-shadow:0 1px 3px rgba(15,23,42,.04),0 4px 16px rgba(15,23,42,.05)}

.sec{font-size:10.5px;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase;color:#94a3b8;margin:28px 0 12px 2px}

.kpi{font-size:40px;font-weight:900;letter-spacing:-2px;
  font-variant-numeric:tabular-nums;line-height:1}
.kpi-sm{font-size:30px;font-weight:800;letter-spacing:-1px;line-height:1}
.unit{font-size:17px;font-weight:400;color:#94a3b8;margin-left:1px}
.lbl{font-size:12px;color:#94a3b8;margin-top:4px;font-weight:500}

.bar-track{background:#f1f5f9;border-radius:999px;height:9px;
  overflow:hidden;margin:10px 0 6px}
.bar-fill{height:100%;border-radius:999px;transition:width .8s ease}

.bdg{padding:3px 12px;border-radius:999px;font-size:11px;
  font-weight:700;display:inline-block;letter-spacing:.03em}
.bdg-on  {background:#dcfce7;color:#15803d;border:1px solid #86efac}
.bdg-off {background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1}
.bdg-live{background:#dcfce7;color:#15803d;border:1px solid #86efac;
  padding:4px 14px;font-size:12px}
.bdg-demo{background:#dbeafe;color:#1d4ed8;border:1px solid #93c5fd;
  padding:4px 14px;font-size:12px}
.bdg-dead{background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;
  padding:4px 14px;font-size:12px}

.etbl{width:100%;border-collapse:collapse;font-size:13px}
.etbl th{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:#94a3b8;padding:0 10px 10px 0;
  border-bottom:1.5px solid #e2e8f0}
.etbl td{padding:12px 10px 12px 0;border-bottom:1px solid #f1f5f9;
  vertical-align:middle}
.etbl tr:last-child td{border:none}
.urgent{color:#dc2626;font-weight:800}
.normal{color:#f97316;font-weight:700}
.ok    {color:#16a34a;font-weight:600}
.mono  {font-family:'Courier New',monospace}

[data-testid="stPlotlyChart"]{border-radius:12px}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
#  SESSION STATE  — history deques
# ═══════════════════════════════════════════════════════
for key in ["hist_time","hist_mA","hist_mB","hist_mC","hist_temp","hist_hum"]:
    if key not in st.session_state:
        st.session_state[key] = deque(maxlen=HISTORY_LEN)

# ═══════════════════════════════════════════════════════
#  DEMO DATA
# ═══════════════════════════════════════════════════════
def get_demo_data():
    t  = time.time()
    mA = max(0, min(100, 58 + 14*math.sin(t/28)    + random.uniform(-.4,.4)))
    mB = max(0, min(100, 47 + 11*math.sin(t/22+1)  + random.uniform(-.4,.4)))
    mC = max(0, min(100, 36 +  9*math.sin(t/18+2)  + random.uniform(-.4,.4)))

    def dl(m, tgt):
        deficit = tgt - m
        return round(deficit / max(deficit * 0.1, 1.5), 2) if deficit > 0 else 9999

    dA, dB, dC = dl(mA,70), dl(mB,60), dl(mC,50)

    # EDF: activate valve of most urgent (smallest deadline) zone
    valid = [(d,z) for d,z in [(dA,"A"),(dB,"B"),(dC,"C")] if d < 9999]
    active = min(valid, key=lambda x:x[0])[1] if valid else None

    return dict(
        moistureA=round(mA,1), moistureB=round(mB,1), moistureC=round(mC,1),
        deadlineA=dA, deadlineB=dB, deadlineC=dC,
        valveA="ON" if active=="A" else "OFF",
        valveB="ON" if active=="B" else "OFF",
        valveC="ON" if active=="C" else "OFF",
        pump  ="ON" if active else "OFF",
        temp  =round(29 + 3*math.sin(t/60), 1),
        humidity=round(66 + 5*math.sin(t/45), 1),
        connected=False,
        lastUpdate=time.strftime("%H:%M:%S"),
        demo=True
    )

# ═══════════════════════════════════════════════════════
#  DATA FETCH  — real Arduino or demo fallback
# ═══════════════════════════════════════════════════════
def fetch_data():
    if not DEMO_MODE:
        try:
            r = requests.get(LOCAL_API, timeout=2)
            d = r.json()
            # ── Ensure all numeric fields are float (fixes "wrong values" bug) ──
            for k in ["moistureA","moistureB","moistureC",
                      "deadlineA","deadlineB","deadlineC","temp","humidity"]:
                try:    d[k] = float(d[k])
                except: d[k] = 0.0
            # ── Ensure valve/pump fields are strings ──
            for k in ["valveA","valveB","valveC","pump"]:
                d[k] = str(d.get(k,"OFF")).strip().upper()
            d["demo"] = False
            return d
        except Exception:
            pass          # fall through to demo
    return get_demo_data()

# ═══════════════════════════════════════════════════════
#  CHART HELPERS
# ═══════════════════════════════════════════════════════
def bar_hex(val, target):
    r = val / target if target else 0
    if r < .50: return "#ef4444"
    if r < .80: return "#f97316"
    return "#22c55e"

def fmt_dl(d):
    return "✓ Satisfied" if d >= 9999 else f"{d:.2f}"

def gauge(value, target, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix="%", font=dict(size=30, color=color, family="Arial Black")),
        gauge=dict(
            axis=dict(range=[0,100], tickwidth=1, tickcolor="#cbd5e1",
                      tickfont=dict(size=10, color="#94a3b8")),
            bar =dict(color=color, thickness=0.26),
            bgcolor="#f8fafc",
            borderwidth=0,
            steps=[
                dict(range=[0, target*.5],       color="#fee2e2"),
                dict(range=[target*.5, target*.85], color="#fef3c7"),
                dict(range=[target*.85, 100],    color="#dcfce7"),
            ],
            threshold=dict(
                line=dict(color="#475569", width=3),
                thickness=0.85, value=target
            )
        )
    ))
    fig.update_layout(margin=dict(l=16,r=16,t=24,b=8), height=185,
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor ="rgba(0,0,0,0)",
                      font=dict(family="Arial,sans-serif"))
    return fig

def moisture_history_chart():
    ss  = st.session_state
    ts  = list(ss["hist_time"])
    mAs = list(ss["hist_mA"])
    mBs = list(ss["hist_mB"])
    mCs = list(ss["hist_mC"])
    if len(ts) < 2:
        return None

    fig = go.Figure()

    # Target dashed lines
    for z, tgt, col in [("A",70,ZONE_COLOR["A"]),
                         ("B",60,ZONE_COLOR["B"]),
                         ("C",50,ZONE_COLOR["C"])]:
        fig.add_hline(y=tgt, line_dash="dot", line_color=col, line_width=1.3,
                      opacity=0.45,
                      annotation_text=f"Target {z} ({tgt}%)",
                      annotation_position="right",
                      annotation_font=dict(size=10, color=col))

    # Zone lines
    for ys, name, col in [(mAs,"Zone A",ZONE_COLOR["A"]),
                           (mBs,"Zone B",ZONE_COLOR["B"]),
                           (mCs,"Zone C",ZONE_COLOR["C"])]:
        r,g,b = tuple(int(col.lstrip("#")[i:i+2],16) for i in (0,2,4))
        fig.add_trace(go.Scatter(
            x=ts, y=ys, name=name,
            line=dict(color=col, width=2.8, shape="spline"),
            fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.07)",
            mode="lines",
            hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>"
        ))

    fig.update_layout(
        height=250,
        margin=dict(l=8, r=90, t=16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        font=dict(family="Arial,sans-serif", size=11, color="#64748b"),
        xaxis=dict(showgrid=False, tickfont=dict(size=10), linecolor="#e2e8f0"),
        yaxis=dict(gridcolor="#f1f5f9", range=[0,106],
                   ticksuffix="%", tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font=dict(size=11)),
        hovermode="x unified"
    )
    return fig

def env_history_chart():
    ss  = st.session_state
    ts  = list(ss["hist_time"])
    tmp = list(ss["hist_temp"])
    hum = list(ss["hist_hum"])
    if len(ts) < 2:
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=ts, y=tmp, name="Temp (°C)",
        line=dict(color="#ef4444", width=2.8, shape="spline"),
        mode="lines", hovertemplate="Temp: %{y:.1f}°C<extra></extra>"
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=ts, y=hum, name="Humidity (%)",
        line=dict(color="#3b82f6", width=2.8, shape="spline"),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        mode="lines", hovertemplate="Humidity: %{y:.1f}%<extra></extra>"
    ), secondary_y=True)

    fig.update_layout(
        height=230,
        margin=dict(l=8,r=10,t=16,b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        font=dict(family="Arial,sans-serif", size=11, color="#64748b"),
        xaxis=dict(showgrid=False, tickfont=dict(size=10), linecolor="#e2e8f0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font=dict(size=11)),
        hovermode="x unified"
    )
    fig.update_yaxes(gridcolor="#f1f5f9", tickfont=dict(size=10),
                     ticksuffix="°C", secondary_y=False)
    fig.update_yaxes(gridcolor="#f1f5f9", tickfont=dict(size=10),
                     ticksuffix="%", secondary_y=True, showgrid=False)
    return fig

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():

    # ── Header ──────────────────────────────────────
    h1, h2 = st.columns([5,1])
    with h1:
        st.markdown("""
        <div style='display:flex;align-items:center;gap:14px;padding:4px 0 2px'>
          <div style='background:linear-gradient(135deg,#1d4ed8,#2563eb);
                      width:46px;height:46px;border-radius:13px;
                      display:flex;align-items:center;justify-content:center;
                      font-size:24px;flex-shrink:0;
                      box-shadow:0 4px 12px rgba(37,99,235,.3)'>💧</div>
          <div>
            <div style='font-size:22px;font-weight:900;color:#0f172a;letter-spacing:-.5px'>
              Irrigation Control Monitor</div>
            <div style='font-size:12px;color:#94a3b8;margin-top:1px'>
              Arduino Due &nbsp;·&nbsp; EDF Scheduling &nbsp;·&nbsp; Real-Time Sensors</div>
          </div>
        </div>""", unsafe_allow_html=True)
    with h2:
        status_ph = st.empty()

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
    st.divider()

    # ── Build all placeholders ONCE ─────────────────
    st.markdown("<div class='sec'>🌱 Soil Moisture — Zone Cards</div>",
                unsafe_allow_html=True)
    zc1,zc2,zc3 = st.columns(3, gap="medium")
    zone_ph = [zc1.empty(), zc2.empty(), zc3.empty()]

    st.markdown("<div class='sec'>📊 Live Moisture Gauges</div>",
                unsafe_allow_html=True)
    gc1,gc2,gc3 = st.columns(3, gap="medium")
    gauge_ph = [gc1.empty(), gc2.empty(), gc3.empty()]

    st.markdown("<div class='sec'>📈 Moisture History — Zone A · B · C</div>",
                unsafe_allow_html=True)
    hist_ph = st.empty()

    st.markdown("<div class='sec'>🌡️ Environment &amp; Pump</div>",
                unsafe_allow_html=True)
    ec1,ec2,ec3,ec4 = st.columns(4, gap="medium")
    env_ph = [ec1.empty(), ec2.empty(), ec3.empty(), ec4.empty()]

    st.markdown("<div class='sec'>📉 Temperature &amp; Humidity History</div>",
                unsafe_allow_html=True)
    envhist_ph = st.empty()

    st.markdown("<div class='sec'>⏱️ EDF Deadline Scheduling Table</div>",
                unsafe_allow_html=True)
    table_ph = st.empty()

    # ══════════════════════════════════════════════
    #  LIVE REFRESH LOOP
    # ══════════════════════════════════════════════
    while True:
        d  = fetch_data()
        ts = d["lastUpdate"]

        # push to history
        st.session_state["hist_time"].append(ts)
        st.session_state["hist_mA"].append(d["moistureA"])
        st.session_state["hist_mB"].append(d["moistureB"])
        st.session_state["hist_mC"].append(d["moistureC"])
        st.session_state["hist_temp"].append(d["temp"])
        st.session_state["hist_hum"].append(d["humidity"])

        # ── Status ──
        if d.get("demo"):
            status_ph.markdown(
                "<div style='text-align:right;padding-top:10px'>"
                "<span class='bdg bdg-demo'>⚡ Demo Mode</span></div>",
                unsafe_allow_html=True)
        elif d.get("connected"):
            status_ph.markdown(
                f"<div style='text-align:right;padding-top:10px'>"
                f"<span class='bdg bdg-live'>● Live</span>"
                f"<div style='font-size:11px;color:#94a3b8;margin-top:3px'>{ts}</div></div>",
                unsafe_allow_html=True)
        else:
            status_ph.markdown(
                "<div style='text-align:right;padding-top:10px'>"
                "<span class='bdg bdg-dead'>✕ Disconnected</span></div>",
                unsafe_allow_html=True)

        # ── Zone cards ──
        zones = [
            ("A","🌱",d["moistureA"],d["deadlineA"],d["valveA"]),
            ("B","🌿",d["moistureB"],d["deadlineB"],d["valveB"]),
            ("C","🍀",d["moistureC"],d["deadlineC"],d["valveC"]),
        ]
        for i,(name,icon,moist,dead,valve) in enumerate(zones):
            tgt    = TARGETS[name]
            col    = ZONE_COLOR[name]
            lcol   = ZONE_LIGHT[name]
            bcol   = ZONE_BORDER[name]
            pct    = min(int(moist), 100)
            barcol = bar_hex(moist, tgt)
            deficit= max(0.0, tgt - moist)

            if moist >= tgt:         stat_txt,stat_col = "✅ Target met",      "#15803d"
            elif deficit < tgt*.2:   stat_txt,stat_col = "🟡 Nearly there",    "#b45309"
            else:                    stat_txt,stat_col = "🔴 Needs water",      "#b91c1c"

            vbdg = f"<span class='bdg {'bdg-on' if valve=='ON' else 'bdg-off'}'>{valve}</span>"

            zone_ph[i].markdown(f"""
            <div class='card' style='border-top:3px solid {col}'>
              <div style='display:flex;justify-content:space-between;
                          align-items:flex-start;margin-bottom:16px'>
                <div style='display:flex;align-items:center;gap:10px'>
                  <div style='background:{lcol};border:1px solid {bcol};
                              width:40px;height:40px;border-radius:11px;
                              display:flex;align-items:center;
                              justify-content:center;font-size:19px'>{icon}</div>
                  <div>
                    <div style='font-weight:900;font-size:16px;color:#0f172a'>Zone {name}</div>
                    <div style='font-size:11px;color:#94a3b8'>Target: {tgt}%</div>
                  </div>
                </div>
                {vbdg}
              </div>

              <div class='kpi' style='color:{col}'>{moist:.1f}<span class='unit'>%</span></div>
              <div class='lbl'>Soil Moisture</div>

              <div class='bar-track' style='margin-top:12px'>
                <div class='bar-fill' style='width:{pct}%;background:{barcol}'></div>
              </div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-top:4px'>
                <span style='color:{stat_col};font-weight:700'>{stat_txt}</span>
                <span style='color:#94a3b8'>Deficit&nbsp;
                  <b style='color:#475569'>{deficit:.1f}%</b></span>
              </div>

              <div style='margin-top:14px;padding-top:12px;
                          border-top:1px solid #f1f5f9;
                          display:flex;justify-content:space-between;
                          font-size:12px;color:#94a3b8'>
                <span>EDF deadline score</span>
                <span class='mono' style='font-weight:800;
                  color:{"#dc2626" if dead<5 else "#f97316" if dead<9999 else "#16a34a"}'>
                  {fmt_dl(dead)}</span>
              </div>
            </div>""", unsafe_allow_html=True)

        # ── Gauges ──
        for i,(name,_,moist,_,_) in enumerate(zones):
            with gauge_ph[i].container():
                fig = gauge(moist, TARGETS[name], ZONE_COLOR[name])
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar":False})
                st.markdown(
                    f"<div style='text-align:center;font-size:12px;font-weight:700;"
                    f"color:#475569;margin-top:-6px'>Zone {name} &nbsp;·&nbsp; "
                    f"Target {TARGETS[name]}%</div>",
                    unsafe_allow_html=True)

        # ── Moisture history ──
        fig_h = moisture_history_chart()
        if fig_h:
            with hist_ph.container():
                st.plotly_chart(fig_h, use_container_width=True,
                                config={"displayModeBar":False})
        else:
            hist_ph.info("Collecting history — needs 2+ readings…")

        # ── Env cards ──
        tcol = "#dc2626" if d["temp"]>35 else "#f97316" if d["temp"]>30 else "#0f172a"
        hcol = "#2563eb" if d["humidity"]>75 else "#0f172a"
        pon  = d["pump"] == "ON"

        env_ph[0].markdown(f"""
        <div class='card' style='border-top:3px solid #ef4444;text-align:center;padding:20px 14px'>
          <div style='font-size:30px;margin-bottom:8px'>🌡️</div>
          <div class='kpi-sm' style='color:{tcol}'>{d["temp"]:.1f}<span class='unit' style='font-size:14px'>°C</span></div>
          <div class='lbl' style='font-size:13px;font-weight:700'>Temperature</div>
        </div>""", unsafe_allow_html=True)

        env_ph[1].markdown(f"""
        <div class='card' style='border-top:3px solid #3b82f6;text-align:center;padding:20px 14px'>
          <div style='font-size:30px;margin-bottom:8px'>💦</div>
          <div class='kpi-sm' style='color:{hcol}'>{d["humidity"]:.1f}<span class='unit' style='font-size:14px'>%</span></div>
          <div class='lbl' style='font-size:13px;font-weight:700'>Humidity</div>
        </div>""", unsafe_allow_html=True)

        env_ph[2].markdown(f"""
        <div class='card' style='border-top:3px solid {"#2563eb" if pon else "#94a3b8"}'>
          <div style='display:flex;align-items:center;gap:16px'>
            <div style='background:{"#dbeafe" if pon else "#f1f5f9"};
                        width:56px;height:56px;border-radius:14px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:28px;flex-shrink:0'>⚙️</div>
            <div>
              <div style='font-weight:900;font-size:15px;color:#0f172a'>Main Pump</div>
              <div style='margin-top:5px'>
                <span class='bdg {"bdg-on" if pon else "bdg-off"}'>
                  {"● RUNNING" if pon else "○ STANDBY"}
                </span>
              </div>
              <div style='font-size:11px;color:#94a3b8;margin-top:5px'>
                {"Actively irrigating" if pon else "All zones satisfied"}
              </div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        env_ph[3].markdown(f"""
        <div class='card' style='border-top:3px solid #8b5cf6;text-align:center;padding:20px 14px'>
          <div style='font-size:30px;margin-bottom:8px'>⏱️</div>
          <div style='font-size:22px;font-weight:900;font-family:monospace;color:#0f172a'>{ts}</div>
          <div class='lbl' style='font-size:13px;font-weight:700'>Last Update</div>
        </div>""", unsafe_allow_html=True)

        # ── Env history ──
        fig_e = env_history_chart()
        if fig_e:
            with envhist_ph.container():
                st.plotly_chart(fig_e, use_container_width=True,
                                config={"displayModeBar":False})
        else:
            envhist_ph.info("Collecting environment history…")

        # ── EDF Table ──
        rows = sorted([
            ("A","🌱",d["moistureA"],TARGETS["A"],d["deadlineA"],d["valveA"]),
            ("B","🌿",d["moistureB"],TARGETS["B"],d["deadlineB"],d["valveB"]),
            ("C","🍀",d["moistureC"],TARGETS["C"],d["deadlineC"],d["valveC"]),
        ], key=lambda x: x[4])   # ascending deadline = highest priority first

        rows_html = ""
        for rank,(name,icon,moist,tgt,dead,valve) in enumerate(rows):
            col    = ZONE_COLOR[name]
            deficit= max(0.0, tgt - moist)
            if   dead >= 9999: pc,pl = "ok",     "✓ Satisfied"
            elif dead <  5:    pc,pl = "urgent",  "⚠ URGENT"
            else:              pc,pl = "normal",  "Normal"

            active_row = rank==0 and dead<9999
            row_style  = f"background:rgba({','.join(str(int(col.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.05)" if active_row else ""

            rank_span = f"<span style='background:{col};color:#fff;padding:2px 9px;border-radius:7px;font-size:11px;font-weight:800'>#{rank+1}</span>"
            irr_span  = "<span style='background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800;margin-left:6px'>IRRIGATING</span>" if valve=="ON" else ""

            defcol = "#dc2626" if deficit>tgt*.3 else "#f97316" if deficit>0 else "#16a34a"

            rows_html += f"""
            <tr style='{row_style}'>
              <td>{rank_span}&nbsp; <b>Zone {name}</b> {icon}</td>
              <td class='mono' style='color:{col};font-weight:800'>{moist:.1f}%</td>
              <td class='mono'>{tgt}%</td>
              <td class='mono' style='color:{defcol};font-weight:700'>{deficit:.1f}%</td>
              <td class='mono {pc}'>{fmt_dl(dead)}</td>
              <td><span class='{pc}'>{pl}</span>{irr_span}</td>
            </tr>"""

        table_ph.markdown(f"""
        <div class='card'>
          <div style='font-size:13px;font-weight:800;color:#0f172a;margin-bottom:14px'>
            Zones sorted by urgency &nbsp;—&nbsp; #1 is currently being irrigated
          </div>
          <table class='etbl'>
            <thead><tr>
              <th>Rank &amp; Zone</th>
              <th>Moisture</th><th>Target</th>
              <th>Deficit</th><th>Deadline Score</th><th>Status</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>""", unsafe_allow_html=True)

        time.sleep(REFRESH_SEC)
        st.rerun()


if __name__ == "__main__":
    main()
