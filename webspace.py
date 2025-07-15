# pip install streamlit skyfield pandas pytz

import streamlit as st
from skyfield.api import EarthSatellite, load, wgs84
from datetime import timedelta
from pytz import timezone
import pandas as pd

SEOUL_LAT = 37.5665
SEOUL_LON = 126.9780

def format_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")  # No timezone offset

def round_val(val):
    try:
        return round(val, 3)
    except:
        return ""

def get_horizontal_velocity(sat):
    try:
        v = sat.velocity.km_per_s
        horiz_vel = (v[0]**2 + v[1]**2)**0.5
        return round_val(horiz_vel)
    except:
        return ""

def detect_pass_pairs(name, line1, line2, hours, radius_km):
    satellite = EarthSatellite(line1, line2, name)
    seoul = wgs84.latlon(SEOUL_LAT, SEOUL_LON, elevation_m=38)
    ts = load.timescale()
    now = ts.now()
    times = [ts.utc(now.utc_datetime() + timedelta(minutes=i)) for i in range(hours * 60)]
    kst = timezone('Asia/Seoul')

    entries = []
    exits = []
    inside = False

    for t in times:
        sat_at = satellite.at(t)
        seoul_pos = seoul.at(t)
        dist_km = (sat_at - seoul_pos).distance().km
        sub = sat_at.subpoint()
        lat = round_val(sub.latitude.degrees)
        lon = round_val(sub.longitude.degrees)
        alt = round_val(sub.elevation.km)
        vel = get_horizontal_velocity(sat_at)
        local_time = format_time(t.utc_datetime().astimezone(kst))

        if not inside and dist_km <= radius_km:
            inside = True
            entries.append({
                "Common Name": name,
                "Start Time (LCLG)": local_time,
                "Start Tgt CBF Lat (deg)": lat,
                "Start Tgt CBF Lon (deg)": lon,
                "Start Tgt CBF Alt (km)": alt,
                "Start LH HorizVel (km/sec)": vel,
                "Entry Time": t
            })
        elif inside and dist_km > radius_km:
            inside = False
            exits.append({
                "Common Name": name,
                "Stop Time (LCLG)": local_time,
                "Stop Tgt CBF Lat (deg)": lat,
                "Stop Tgt CBF Lon (deg)": lon,
                "Stop Tgt CBF Alt (km)": alt,
                "Stop LH HorizVel (km/sec)": vel,
                "Exit Time": t
            })

    results = []
    for ent, ext in zip(entries, exits):
        duration_sec = int((ext["Exit Time"].utc_datetime() - ent["Entry Time"].utc_datetime()).total_seconds())
        results.append({
            "Common Name": ent["Common Name"],
            "Start Time (LCLG)": ent["Start Time (LCLG)"],
            "Start Tgt CBF Lat (deg)": ent["Start Tgt CBF Lat (deg)"],
            "Start Tgt CBF Lon (deg)": ent["Start Tgt CBF Lon (deg)"],
            "Start Tgt CBF Alt (km)": ent["Start Tgt CBF Alt (km)"],
            "Start LH HorizVel (km/sec)": ent["Start LH HorizVel (km/sec)"],
            "Stop Time (LCLG)": ext["Stop Time (LCLG)"],
            "Stop Tgt CBF Lat (deg)": ext["Stop Tgt CBF Lat (deg)"],
            "Stop Tgt CBF Lon (deg)": ext["Stop Tgt CBF Lon (deg)"],
            "Stop Tgt CBF Alt (km)": ext["Stop Tgt CBF Alt (km)"],
            "Stop LH HorizVel (km/sec)": ext["Stop LH HorizVel (km/sec)"],
            "Duration (sec)": duration_sec
        })

    return results

# Streamlit UI
st.set_page_config(layout="centered", page_title="🛰️ WebSPACE CSV 분석기")
st.title("🛰️ WebSPACE | 통합 CSV 위성 분석기")
st.markdown("모든 위성 이벤트를 하나의 CSV로 분석하며, 좌표와 시간은 정제된 형식으로 저장됩니다.")

tle_text = st.text_area("📄 TLE 입력 (각 위성당 3줄)", height=300)
col1, col2 = st.columns(2)
radius_km = col1.slider("📍 서울 반경 (km)", min_value=100, max_value=2000, value=1000, step=100)
hours = col2.selectbox("⏱️ 분석 시간 범위 (시간)", options=[12, 24, 48, 72], index=2)

if st.button("🚀 분석 시작"):
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    if len(lines) % 3 != 0:
        st.error("❌ TLE 입력 오류: 위성당 3줄씩 입력되어야 합니다.")
    else:
        all_rows = []
        for i in range(0, len(lines), 3):
            name, l1, l2 = lines[i:i+3]
            rows = detect_pass_pairs(name, l1, l2, hours, radius_km)
            all_rows.extend(rows)

        df = pd.DataFrame(all_rows, columns=[
            "Common Name", "Start Time (LCLG)", "Start Tgt CBF Lat (deg)", "Start Tgt CBF Lon (deg)",
            "Start Tgt CBF Alt (km)", "Start LH HorizVel (km/sec)", "Stop Time (LCLG)",
            "Stop Tgt CBF Lat (deg)", "Stop Tgt CBF Lon (deg)", "Stop Tgt CBF Alt (km)",
            "Stop LH HorizVel (km/sec)", "Duration (sec)"
        ])

        st.success(f"✅ 분석 완료: 총 {len(df)}건의 통과 이벤트가 정리되었습니다")
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ 통합 CSV 다운로드", data=csv_data,
                           file_name="webspace_analysis.csv", mime="text/csv")
