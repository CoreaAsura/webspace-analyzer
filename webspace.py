# pip install streamlit skyfield pandas pytz geopy

import streamlit as st
from skyfield.api import EarthSatellite, load, wgs84
from datetime import timedelta
from pytz import timezone
import pandas as pd
from geopy.geocoders import Nominatim

def format_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def round_val(val):
    try:
        return round(val, 3)
    except:
        return ""

def get_horizontal_velocity(sat):
    try:
        v = sat.velocity.km_per_s
        return round_val((v[0]**2 + v[1]**2)**0.5)
    except:
        return ""

def geocode_address(address):
    geolocator = Nominatim(user_agent="webspace_locator")
    location = geolocator.geocode(address)
    if location:
        return round_val(location.latitude), round_val(location.longitude)
    else:
        return None, None

def detect_pass_pairs(name, line1, line2, hours, radius_km, user_lat, user_lon):
    satellite = EarthSatellite(line1, line2, name)
    observer = wgs84.latlon(user_lat, user_lon, elevation_m=38)
    ts = load.timescale()
    now = ts.now()
    times = [ts.utc(now.utc_datetime() + timedelta(minutes=i)) for i in range(hours * 60)]
    kst = timezone('Asia/Seoul')

    entries, exits, inside = [], [], False

    for t in times:
        try:
            sat_at = satellite.at(t)
            obs_pos = observer.at(t)
            dist_km = (sat_at - obs_pos).distance().km
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
        except:
            continue

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

# 🌐 Streamlit UI
st.set_page_config(layout="centered", page_title="WebSPACE for GREENSTAR")
st.title("WebSPACE for GREENSTAR")
st.markdown("기준 위치를 주소로 입력하면, 해당 위치 주변을 기준으로 위성 통과 이벤트를 분석합니다.")

address = st.text_input("📮 기준 주소 입력 (예: 서울 / 청주시 서원구 성화동)", value="서울")
lat, lon = geocode_address(address)

if lat is None or lon is None:
    st.error("❌ 주소를 찾을 수 없습니다. 정확한 지명을 입력해주세요.")
    st.stop()
else:
    st.success(f"✅ 기준 위치 좌표: 위도 {lat}, 경도 {lon}")

tle_text = st.text_area("궤도정보 / 각 3줄씩 입력 (위성명 + TLE)", height=300)
col1, col2 = st.columns(2)
radius_km = col1.slider("📍 기준 반경 (km)", 100, 4000, 1000, step=100)
hours = col2.selectbox("⏱️ 분석 시간 범위 (시간)", [12, 24, 48, 72, 96, 120, 144, 168], index=2)

if st.button("🚀 분석 시작"):
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    if len(lines) % 3 != 0:
        st.error("❌ TLE 입력 오류: 위성당 3줄씩 구성되어야 합니다.")
    else:
        all_rows = []
        for i in range(0, len(lines), 3):
            name, l1, l2 = lines[i:i+3]
            rows = detect_pass_pairs(name, l1, l2, hours, radius_km, lat, lon)
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
