from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="IML Cell Process Advisor",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

EXCEL_PATH = "parametre_ayarlama(1).xlsx"
MAX_INJECTION_PRESSURE_MPA = 190.0
PP_DENSITY_G_CM3 = 0.90

PRODUCT_FACTORS = {
    "Cup": {"speed": 1.10, "area": 1.00, "mold_bias": -3},
    "Lid": {"speed": 1.15, "area": 1.12, "mold_bias": -2},
    "Tray": {"speed": 0.95, "area": 1.20, "mold_bias": 0},
    "Container": {"speed": 1.00, "area": 1.05, "mold_bias": 0},
}


# =========================================================
# BASIC HELPERS
# =========================================================
def r1(x: float) -> float:
    return round(float(x), 1)


def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def parse_robot_eyes(value) -> tuple[Optional[int], Optional[int]]:
    text = str(value).strip().upper()

    if text in {"N/A", "NA", "NONE", "YOK", "-", "", "NAN"}:
        return None, None

    match = re.search(r"(\d+)\s*\+\s*(\d+)", text)

    if not match:
        return None, None

    return int(match.group(1)), int(match.group(2))


def estimate_shot_capacity_g(tonnage: float, screw_mm: float) -> float:
    base = 0.165 * tonnage + 0.095 * screw_mm**2
    return r1(clamp(base, 120, 1200))


# =========================================================
# EXCEL LOADING
# =========================================================
def load_machine_library(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)

    required_columns = [
        "NO",
        "MAKİNA ADI",
        "MAKİNA MODEL",
        "ROBOT GÖZ SAYISI \n(IML + ÜRÜN TAHLİYE)",
        "MAKİNE TONAJ",
        "MAKİNE TİPİ",
        "VİDA ÇAPI (mm)",
    ]

    missing = [c for c in required_columns if c not in df.columns]

    if missing:
        st.error("Excel kolon isimleri beklenen formatta değil.")
        st.write("Eksik kolonlar:", missing)
        st.write("Excel'de bulunan kolonlar:", list(df.columns))
        st.stop()

    lib = pd.DataFrame(
        {
            "machine_no": df["NO"],
            "brand": df["MAKİNA ADI"],
            "model": df["MAKİNA MODEL"],
            "robot_raw": df["ROBOT GÖZ SAYISI \n(IML + ÜRÜN TAHLİYE)"],
            "tonnage": df["MAKİNE TONAJ"],
            "machine_type": df["MAKİNE TİPİ"],
            "screw_mm": df["VİDA ÇAPI (mm)"],
        }
    )

    lib = lib.dropna(subset=["machine_no", "brand", "model", "tonnage", "screw_mm"])

    lib["machine_no"] = lib["machine_no"].astype(int)
    lib["tonnage"] = lib["tonnage"].astype(float)
    lib["screw_mm"] = lib["screw_mm"].astype(float)

    parsed = lib["robot_raw"].apply(parse_robot_eyes)
    lib["robot_pick_eyes"] = parsed.apply(lambda x: x[0])
    lib["robot_iml_eyes"] = parsed.apply(lambda x: x[1])

    lib["shot_capacity_g"] = lib.apply(
        lambda x: estimate_shot_capacity_g(x["tonnage"], x["screw_mm"]),
        axis=1,
    )

    lib["max_pressure_mpa"] = MAX_INJECTION_PRESSURE_MPA

    lib["display"] = lib.apply(
        lambda x: (
            f"{x['machine_no']} | {x['brand']} {x['model']} | "
            f"{int(x['tonnage'])}T | {x['machine_type']} | Robot {x['robot_raw']}"
        ),
        axis=1,
    )

    return lib


# =========================================================
# ENGINE FUNCTIONS
# =========================================================
def total_shot_g(part_g: float, cavity: int) -> float:
    return part_g * cavity * 1.08


def projected_area_cm2(product: str, part_g: float, cavity: int, wall_mm: float) -> float:
    wall_cm = max(wall_mm / 10, 0.03)
    volume = part_g / PP_DENSITY_G_CM3
    return (volume / wall_cm) * PRODUCT_FACTORS[product]["area"] * cavity


def clamp_load_ratio(
    product: str,
    part_g: float,
    cavity: int,
    wall_mm: float,
    mfi: float,
    tonnage: float,
) -> float:
    area = projected_area_cm2(product, part_g, cavity, wall_mm)

    cavity_pressure_bar = 230 + (140 / max(wall_mm, 0.45)) - 0.8 * mfi

    if product in {"Cup", "Lid"}:
        cavity_pressure_bar += 20

    cavity_pressure_bar = clamp(cavity_pressure_bar, 180, 420)

    clamp_req_t = area * cavity_pressure_bar * 1.15 / 1000

    return clamp_req_t / tonnage


def melt_temp_c(mfi: float) -> float:
    return r1(clamp(236 - 0.22 * (mfi - 20), 215, 240))


def mold_temp_c(product: str, wall_mm: float, iml: bool) -> float:
    base = 24 - 6 * min(wall_mm, 2.0) / 2
    temp = base + PRODUCT_FACTORS[product]["mold_bias"]

    if iml:
        temp += 2

    return r1(clamp(temp, 14, 32))


def feed_throat_temp_c(mfi: float) -> float:
    if mfi >= 70:
        return 25
    if mfi >= 40:
        return 28
    return 30


def fill_time_s(wall_mm: float, product: str, mfi: float) -> float:
    if wall_mm <= 0.45:
        base = 0.22
    elif wall_mm <= 0.70:
        base = 0.32
    elif wall_mm <= 1.20:
        base = 0.48
    elif wall_mm <= 2.00:
        base = 0.75
    elif wall_mm <= 3.00:
        base = 1.10
    else:
        base = 1.45

    mfi_factor = 1 - clamp((mfi - 40) * 0.002, -0.08, 0.08)

    return r1(base / PRODUCT_FACTORS[product]["speed"] * mfi_factor)


def injection_speed_zones(
    wall_mm: float,
    product: str,
    mfi: float,
    machine_type: str,
) -> tuple[float, float, float]:
    if wall_mm <= 0.45:
        main = 320
    elif wall_mm <= 0.70:
        main = 250
    elif wall_mm <= 1.20:
        main = 180
    elif wall_mm <= 2.00:
        main = 130
    elif wall_mm <= 3.00:
        main = 95
    else:
        main = 75

    main *= PRODUCT_FACTORS[product]["speed"]

    if mfi >= 70:
        main *= 0.95
    elif mfi < 25:
        main *= 1.05

    mt = str(machine_type).upper()

    if "HİDROLİK" in mt or "HIDROLIK" in mt:
        main *= 0.96

    z2 = clamp(main, 55, 340)
    z1 = clamp(z2 * 0.55, 30, 220)
    z3 = clamp(z2 * 0.70, 40, 250)

    return r1(z1), r1(z2), r1(z3)


def pressure_demand_mpa(
    wall_mm: float,
    mfi: float,
    cavity: int,
    product: str,
    iml: bool,
) -> float:
    pressure = 78 + (22 / max(wall_mm, 0.45)) - 0.30 * mfi + cavity * 1.5

    if product in {"Cup", "Lid"}:
        pressure += 6

    if iml:
        pressure += 3

    return r1(clamp(pressure, 45, 175))


def vp_values(fill_s: float, wall_mm: float, product: str) -> tuple[float, float]:
    pos = 96 - 2.5 * wall_mm

    if product == "Lid":
        pos += 1

    return r1(fill_s * 0.90), r1(clamp(pos, 86, 96))


def pack_values(
    pressure_mpa: float,
    inj_z2: float,
    wall_mm: float,
    product: str,
) -> tuple[float, float, float]:
    if wall_mm <= 0.7:
        ratio = 0.58
    elif wall_mm <= 1.5:
        ratio = 0.62
    else:
        ratio = 0.68

    if product == "Lid":
        ratio -= 0.03

    pack_pressure = pressure_mpa * ratio
    pack_speed = clamp(inj_z2 * 0.15, 10, 55)

    if wall_mm <= 0.6:
        pack_time = 0.8
    elif wall_mm <= 1.0:
        pack_time = 1.2
    elif wall_mm <= 1.5:
        pack_time = 1.8
    elif wall_mm <= 2.0:
        pack_time = 2.4
    elif wall_mm <= 3.0:
        pack_time = 3.2
    else:
        pack_time = 4.0

    return r1(pack_speed), r1(pack_pressure), r1(pack_time)


def cooling_time_s(
    wall_mm: float,
    melt_c: float,
    mold_c: float,
    product: str,
    iml: bool,
) -> float:
    alpha = 0.11
    eject_c = 95 if wall_mm <= 1.2 else 105 if wall_mm <= 2.5 else 115

    numerator = max(melt_c - mold_c, 1)
    denominator = max(eject_c - mold_c, 1)

    arg = max((8 / math.pi**2) * (numerator / denominator), 1.05)

    base = ((wall_mm**2) / (math.pi**2 * alpha)) * math.log(arg)

    factor = 2.8

    if product == "Lid":
        factor *= 0.92
    elif product == "Tray":
        factor *= 1.05

    if iml:
        factor *= 1.05

    return r1(clamp(base * factor, 2.0, 40.0))


def screw_rpm(mfi: float, screw_mm: float, shot_util: float, machine_type: str) -> float:
    rpm = 78 - 0.35 * (screw_mm - 45)

    if mfi < 30:
        rpm -= 6
    elif mfi > 70:
        rpm += 4

    if shot_util < 0.12:
        rpm -= 5
    elif shot_util > 0.45:
        rpm += 4

    if "SERVO" in str(machine_type).upper():
        rpm += 2

    return r1(clamp(rpm, 35, 95))


def back_pressure_mpa(mfi: float) -> float:
    if mfi >= 70:
        return 0.4
    if mfi >= 40:
        return 0.6
    return 0.8


def screw_recovery_s(total_shot: float, screw_mm: float, rpm: float) -> float:
    plast_rate = screw_mm * rpm * 0.045
    return r1(clamp(total_shot / max(plast_rate, 1), 0.8, 8.0))


def robot_cycle_s(
    cavity: int,
    pick_eyes: Optional[int],
    iml_eyes: Optional[int],
    iml: bool,
) -> tuple[float, str]:
    if pick_eyes is None:
        return 0.0, "Robot bilgisi yok"

    if iml and iml_eyes is None:
        return 0.0, "IML robot bilgisi yok"

    compatible = cavity <= pick_eyes and (not iml or cavity <= iml_eyes)

    base = 1.15
    cavity_add = cavity * 0.07
    iml_add = cavity * 0.09 if iml else 0
    penalty = 0.15 if compatible else 0.70

    cycle = base + cavity_add + iml_add + penalty

    status = "Robot/kalıp uyumlu" if compatible else "Robot göz sayısı kalıp göz sayısı için uyumsuz"

    return r1(cycle), status


def choose_best_machine(
    lib: pd.DataFrame,
    product: str,
    part_g: float,
    cavity: int,
    wall_mm: float,
    mfi: float,
    iml: bool,
) -> pd.Series:
    rows = []
    shot = total_shot_g(part_g, cavity)

    for _, m in lib.iterrows():
        shot_util = shot / m["shot_capacity_g"]
        c_load = clamp_load_ratio(product, part_g, cavity, wall_mm, mfi, m["tonnage"])

        robot_pick = m["robot_pick_eyes"]
        robot_iml = m["robot_iml_eyes"]

        robot_ok = True

        if pd.notna(robot_pick):
            robot_ok = cavity <= robot_pick

        if iml and pd.notna(robot_iml):
            robot_ok = robot_ok and cavity <= robot_iml

        if iml and pd.isna(robot_iml):
            robot_ok = False

        shot_ok = 0.08 <= shot_util <= 0.55
        clamp_ok = c_load <= 0.60

        feasible = shot_ok and clamp_ok and robot_ok

        score = 100
        score -= abs(shot_util - 0.25) * 120
        score -= max(0, c_load - 0.35) * 80
        score -= 35 if not robot_ok else 0
        score -= 25 if not shot_ok else 0
        score -= 20 if not clamp_ok else 0

        rows.append((feasible, score, m["tonnage"], m.name))

    feasible_rows = [r for r in rows if r[0]]

    if feasible_rows:
        chosen = sorted(feasible_rows, key=lambda x: (x[2], -x[1]))[0]
    else:
        chosen = sorted(rows, key=lambda x: (-x[1], x[2]))[0]

    return lib.loc[chosen[3]]


def build_recipe(
    machine: pd.Series,
    product: str,
    part_g: float,
    cavity: int,
    wall_mm: float,
    mfi: float,
    iml: bool,
) -> dict:
    shot = total_shot_g(part_g, cavity)
    shot_util = shot / machine["shot_capacity_g"]

    melt = melt_temp_c(mfi)
    mold = mold_temp_c(product, wall_mm, iml)
    hopper = feed_throat_temp_c(mfi)

    fill = fill_time_s(wall_mm, product, mfi)
    z1, z2, z3 = injection_speed_zones(wall_mm, product, mfi, machine["machine_type"])

    demand = pressure_demand_mpa(wall_mm, mfi, cavity, product, iml)
    inj_set = r1(clamp(demand * 1.08, 35, MAX_INJECTION_PRESSURE_MPA))

    vp_time, vp_pos = vp_values(fill, wall_mm, product)
    pack_speed, pack_press, pack_time = pack_values(demand, z2, wall_mm, product)
    cooling = cooling_time_s(wall_mm, melt, mold, product, iml)

    rpm = screw_rpm(mfi, machine["screw_mm"], shot_util, machine["machine_type"])
    bp = back_pressure_mpa(mfi)
    recovery = screw_recovery_s(shot, machine["screw_mm"], rpm)

    robot_cycle, robot_status = robot_cycle_s(
        cavity,
        machine["robot_pick_eyes"] if pd.notna(machine["robot_pick_eyes"]) else None,
        machine["robot_iml_eyes"] if pd.notna(machine["robot_iml_eyes"]) else None,
        iml,
    )

    polymer_cycle = r1(max(fill + pack_time + cooling + 1.2, recovery + cooling + 0.8))
    final_cycle = r1(max(polymer_cycle, robot_cycle))

    if final_cycle == polymer_cycle and final_cycle > robot_cycle + 0.3:
        bottleneck = "Polimer / soğutma sınırlı"
    elif final_cycle == robot_cycle and final_cycle > polymer_cycle + 0.3:
        bottleneck = "Robot / IML sınırlı"
    else:
        bottleneck = "Dengeli hücre"

    notes = []

    if shot_util < 0.08:
        notes.append("Makine shot kapasitesi bu ürün için büyük kalıyor.")

    if shot_util > 0.55:
        notes.append("Shot utilization yüksek; cushion ve dozaj stabilitesi izlenmeli.")

    if inj_set > 175:
        notes.append("Enjeksiyon basıncı 190 MPa limite yakın.")

    if "uyumsuz" in robot_status.lower():
        notes.append(robot_status)

    if cooling > 25:
        notes.append("Soğutma çevrim darboğazı olabilir.")

    return {
        "machine_no": int(machine["machine_no"]),
        "machine_name": f"{machine['brand']} {machine['model']}",
        "tonnage": int(machine["tonnage"]),
        "machine_type": machine["machine_type"],
        "screw_mm": r1(machine["screw_mm"]),
        "robot": machine["robot_raw"],
        "shot_capacity_g": r1(machine["shot_capacity_g"]),
        "shot_g": r1(shot),
        "shot_util": r1(shot_util),
        "hopper": hopper,
        "zone1": r1(melt - 28),
        "zone2": r1(melt - 18),
        "zone3": r1(melt - 10),
        "zone4": r1(melt - 4),
        "nozzle": melt,
        "mold": mold,
        "fill": fill,
        "inj_z1": z1,
        "inj_z2": z2,
        "inj_z3": z3,
        "pressure_demand": demand,
        "inj_pressure_set": inj_set,
        "vp_time": vp_time,
        "vp_pos": vp_pos,
        "pack_speed": pack_speed,
        "pack_pressure": pack_press,
        "pack_time": pack_time,
        "cooling": cooling,
        "rpm": rpm,
        "bp": bp,
        "recovery": recovery,
        "robot_cycle": robot_cycle,
        "robot_status": robot_status,
        "polymer_cycle": polymer_cycle,
        "final_cycle": final_cycle,
        "bottleneck": bottleneck,
        "notes": notes,
    }


# =========================================================
# UI
# =========================================================
st.title("🏭 IML Cell Process Advisor")
st.caption("Makine + Robot + IML + PP proses reçetesi")

if not Path(EXCEL_PATH).exists():
    st.error(f"Excel dosyası bulunamadı: {EXCEL_PATH}")
    st.info("Excel dosyasını app5.py ile aynı klasöre koy.")
    st.stop()

lib = load_machine_library(EXCEL_PATH)

with st.sidebar:
    st.header("Girdi Parametreleri")

    mode = st.radio(
        "Makine seçimi",
        ["Otomatik öner", "Listeden seç"],
        horizontal=True,
    )

    selected_machine_display = None

    if mode == "Listeden seç":
        selected_machine_display = st.selectbox(
            "Makine seç",
            lib["display"].tolist(),
        )

    product = st.selectbox(
        "Ürün tipi",
        ["Cup", "Lid", "Tray", "Container"],
    )

    iml = st.checkbox("IML kullanılıyor", value=True)

    part_g = st.number_input(
        "Parça ağırlığı (g)",
        min_value=0.1,
        max_value=500.0,
        value=1.0,
        step=0.1,
    )

    cavity = st.number_input(
        "Kalıp göz sayısı",
        min_value=1,
        max_value=64,
        value=1,
        step=1,
    )

    wall_mm = st.number_input(
        "Ortalama et kalınlığı (mm)",
        min_value=0.30,
        max_value=5.00,
        value=0.50,
        step=0.05,
    )

    mfi = st.number_input(
        "PP MFI",
        min_value=1.0,
        max_value=150.0,
        value=70.0,
        step=1.0,
    )

    run = st.button(
        "Reçete Oluştur",
        type="primary",
        use_container_width=True,
    )

if not run:
    st.info("Sol panelden değerleri girip **Reçete Oluştur** butonuna bas.")
    st.stop()

if mode == "Otomatik öner":
    machine = choose_best_machine(lib, product, part_g, cavity, wall_mm, mfi, iml)
else:
    machine = lib[lib["display"] == selected_machine_display].iloc[0]

recipe = build_recipe(machine, product, part_g, cavity, wall_mm, mfi, iml)

st.success("Reçete oluşturuldu.")

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Makine", f"{recipe['machine_no']} / {recipe['tonnage']}T")
k2.metric("Shot", f"{recipe['shot_g']} g")
k3.metric("Zone 2 Hız", f"{recipe['inj_z2']} mm/s")
k4.metric("Enj. Basıncı", f"{recipe['inj_pressure_set']} MPa")
k5.metric("Final Çevrim", f"{recipe['final_cycle']} s")

st.markdown("---")

c1, c2 = st.columns([1.2, 1])

with c1:
    st.subheader("⚙️ Proses Reçetesi")

    process_df = pd.DataFrame(
        {
            "Parametre": [
                "Makine",
                "Makine tipi",
                "Vida çapı",
                "Robot yapısı",
                "Shot kapasitesi",
                "Shot weight",
                "Shot utilization",
                "Enjeksiyon hızı Zone 1",
                "Enjeksiyon hızı Zone 2",
                "Enjeksiyon hızı Zone 3",
                "Proses basınç ihtiyacı",
                "Enjeksiyon basınç seti",
                "Fill time",
                "V/P zamanı",
                "V/P switch pozisyonu",
                "Ütüleme hızı",
                "Ütüleme basıncı",
                "Ütüleme süresi",
                "Soğutma süresi",
                "Screw recovery",
                "Screw RPM",
                "Back pressure",
            ],
            "Değer": [
                f"{recipe['machine_no']} - {recipe['machine_name']}",
                recipe["machine_type"],
                f"{recipe['screw_mm']} mm",
                recipe["robot"],
                f"{recipe['shot_capacity_g']} g",
                f"{recipe['shot_g']} g",
                recipe["shot_util"],
                f"{recipe['inj_z1']} mm/s",
                f"{recipe['inj_z2']} mm/s",
                f"{recipe['inj_z3']} mm/s",
                f"{recipe['pressure_demand']} MPa",
                f"{recipe['inj_pressure_set']} MPa",
                f"{recipe['fill']} s",
                f"{recipe['vp_time']} s",
                f"{recipe['vp_pos']} %",
                f"{recipe['pack_speed']} mm/s",
                f"{recipe['pack_pressure']} MPa",
                f"{recipe['pack_time']} s",
                f"{recipe['cooling']} s",
                f"{recipe['recovery']} s",
                recipe["rpm"],
                f"{recipe['bp']} MPa",
            ],
        }
    )

    st.dataframe(process_df, use_container_width=True, hide_index=True)

with c2:
    st.subheader("🌡️ Sıcaklık Profili")

    temp_df = pd.DataFrame(
        {
            "Bölge": [
                "Feed throat / hopper",
                "Zone 1",
                "Zone 2",
                "Zone 3",
                "Zone 4",
                "Nozzle",
                "Mold",
            ],
            "Sıcaklık": [
                f"{recipe['hopper']} °C",
                f"{recipe['zone1']} °C",
                f"{recipe['zone2']} °C",
                f"{recipe['zone3']} °C",
                f"{recipe['zone4']} °C",
                f"{recipe['nozzle']} °C",
                f"{recipe['mold']} °C",
            ],
        }
    )

    st.dataframe(temp_df, use_container_width=True, hide_index=True)

st.markdown("---")

r1_col, r2_col = st.columns([1, 1])

with r1_col:
    st.subheader("🤖 Robot / IML Hücre Analizi")

    robot_df = pd.DataFrame(
        {
            "Parametre": [
                "Robot durumu",
                "Robot çevrimi",
                "Polimer çevrimi",
                "Final çevrim",
                "Darboğaz",
            ],
            "Değer": [
                recipe["robot_status"],
                f"{recipe['robot_cycle']} s",
                f"{recipe['polymer_cycle']} s",
                f"{recipe['final_cycle']} s",
                recipe["bottleneck"],
            ],
        }
    )

    st.dataframe(robot_df, use_container_width=True, hide_index=True)

with r2_col:
    st.subheader("🧠 Mühendislik Notları")

    if recipe["notes"]:
        for note in recipe["notes"]:
            st.warning(note)
    else:
        st.success("Başlangıç reçetesi olarak uygun görünüyor.")

st.markdown("---")

st.subheader("📋 Makine Kütüphanesi")

st.dataframe(
    lib[
        [
            "machine_no",
            "brand",
            "model",
            "robot_raw",
            "tonnage",
            "machine_type",
            "screw_mm",
            "shot_capacity_g",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)