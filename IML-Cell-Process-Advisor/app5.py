from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(
    page_title="IML Moldflow-Lite Pro",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CONSTANTS
# =========================================================
PP_DENSITY_G_CM3 = 0.90
MAX_INJECTION_PRESSURE_MPA = 190.0
THERMAL_DIFFUSIVITY_MM2_S = 0.12

ETA0_REF_PA_S = 2000.0
T_REF_C = 230.0
C1 = 8.86
C2 = 101.6
TAU_STAR_PA = 100000.0
POWER_INDEX = 0.25

PRODUCT_FACTORS = {
    "Cup": {"speed": 1.10, "area": 1.00, "mold_bias": -3},
    "Lid": {"speed": 1.15, "area": 1.12, "mold_bias": -2},
    "Tray": {"speed": 0.95, "area": 1.20, "mold_bias": 0},
    "Container": {"speed": 1.00, "area": 1.05, "mold_bias": 0},
}


# =========================================================
# EXCEL AUTO-DETECT
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
XLSX_FILES = list(BASE_DIR.glob("*.xlsx"))

if not XLSX_FILES:
    st.error("Excel dosyası bulunamadı. Uygulama klasörüne makine listesini içeren .xlsx dosyasını koy.")
    st.write("Klasörde görülen dosyalar:", [p.name for p in BASE_DIR.iterdir()])
    st.stop()

EXCEL_PATH = XLSX_FILES[0]


# =========================================================
# HELPERS
# =========================================================
def r(x: float, digits: int = 2) -> float:
    return round(float(x), digits)


def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def parse_robot_eyes(value) -> tuple[Optional[int], Optional[int]]:
    text = str(value).strip().upper()
    match = re.search(r"(\d+)\s*\+\s*(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


# =========================================================
# LOAD MACHINE LIBRARY
# =========================================================
@st.cache_data
def load_machine_library(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)

    lib = pd.DataFrame({
        "machine_no": df["NO"],
        "brand": df["MAKİNA ADI"],
        "model": df["MAKİNA MODEL"],
        "robot_raw": df["ROBOT GÖZ SAYISI \n(IML + ÜRÜN TAHLİYE)"],
        "tonnage": df["MAKİNE TONAJ"],
        "machine_type": df["MAKİNE TİPİ"],
        "screw_mm": df["VİDA ÇAPI (mm)"],
    })

    lib = lib.dropna(subset=["machine_no", "brand", "model", "tonnage", "screw_mm"])

    lib["machine_no"] = lib["machine_no"].astype(int)
    lib["tonnage"] = lib["tonnage"].astype(float)
    lib["screw_mm"] = lib["screw_mm"].astype(float)

    parsed = lib["robot_raw"].apply(parse_robot_eyes)
    lib["robot_pick_eyes"] = parsed.apply(lambda x: x[0])
    lib["robot_iml_eyes"] = parsed.apply(lambda x: x[1])

    lib["shot_capacity_g"] = lib["tonnage"] * 1.6

    lib["display"] = lib.apply(
        lambda x: (
            f"{x['machine_no']} - {x['brand']} {x['model']} - "
            f"{int(x['tonnage'])} Ton - {x['machine_type']} - Robot {x['robot_raw']}"
        ),
        axis=1,
    )

    return lib


machine_library = load_machine_library(EXCEL_PATH)


# =========================================================
# MOLDFLOW-LITE ENGINE
# =========================================================
def estimate_melt_temp_c(mfi: float) -> float:
    return clamp(236 - 0.22 * (mfi - 20), 215, 240)


def estimate_mold_temp_c(product: str, wall_mm: float, iml: bool) -> float:
    base = 24 - 3.0 * wall_mm
    base += PRODUCT_FACTORS[product]["mold_bias"]
    if iml:
        base += 2
    return clamp(base, 14, 32)


def eta_zero_cross_wlf(melt_temp_c: float, mfi: float) -> float:
    eta0_mfi = ETA0_REF_PA_S * (1.0 / max(mfi, 1.0) ** 0.8)
    d_t = melt_temp_c - T_REF_C
    log_a_t = -C1 * d_t / (C2 + d_t + 1e-6)
    a_t = 10 ** log_a_t
    return eta0_mfi * a_t


def eta_cross(eta0: float, shear_rate: float) -> float:
    term = eta0 * shear_rate / TAU_STAR_PA
    return eta0 / (1 + term ** (1 - POWER_INDEX))


def total_shot_g(part_weight_g: float, cavity: int) -> float:
    return part_weight_g * cavity * 1.08


def projected_area_cm2(product: str, part_weight_g: float, cavity: int, wall_mm: float) -> float:
    wall_cm = max(wall_mm / 10.0, 0.03)
    volume_cm3 = part_weight_g / PP_DENSITY_G_CM3
    area_per_cavity = (volume_cm3 / wall_cm) * PRODUCT_FACTORS[product]["area"]
    return area_per_cavity * cavity


def clamp_load_ratio(product: str, part_weight_g: float, cavity: int, wall_mm: float, mfi: float, tonnage: float) -> float:
    area_cm2 = projected_area_cm2(product, part_weight_g, cavity, wall_mm)

    cavity_pressure_bar = 230 + (140 / max(wall_mm, 0.45)) - 0.8 * mfi
    if product in {"Cup", "Lid"}:
        cavity_pressure_bar += 20

    cavity_pressure_bar = clamp(cavity_pressure_bar, 180, 420)
    clamp_requirement_ton = area_cm2 * cavity_pressure_bar * 1.15 / 1000

    return clamp_requirement_ton / tonnage


def choose_best_machine(
    lib: pd.DataFrame,
    product: str,
    part_weight_g: float,
    cavity: int,
    wall_mm: float,
    mfi: float,
    iml: bool,
) -> pd.Series:
    shot = total_shot_g(part_weight_g, cavity)
    candidates = []

    for _, machine in lib.iterrows():
        shot_util = shot / machine["shot_capacity_g"]
        clamp_load = clamp_load_ratio(product, part_weight_g, cavity, wall_mm, mfi, machine["tonnage"])

        robot_ok = True
        if pd.notna(machine["robot_pick_eyes"]):
            robot_ok = cavity <= machine["robot_pick_eyes"]
        if iml:
            if pd.notna(machine["robot_iml_eyes"]):
                robot_ok = robot_ok and cavity <= machine["robot_iml_eyes"]
            else:
                robot_ok = False

        shot_ok = 0.08 <= shot_util <= 0.60
        clamp_ok = clamp_load <= 0.65
        feasible = shot_ok and clamp_ok and robot_ok

        score = 100
        score -= abs(shot_util - 0.25) * 120
        score -= max(0, clamp_load - 0.35) * 80
        if not robot_ok:
            score -= 40
        if not shot_ok:
            score -= 30
        if not clamp_ok:
            score -= 30

        candidates.append({
            "index": machine.name,
            "tonnage": machine["tonnage"],
            "score": score,
            "feasible": feasible,
        })

    feasible_candidates = [c for c in candidates if c["feasible"]]

    if feasible_candidates:
        selected = sorted(feasible_candidates, key=lambda c: (c["tonnage"], -c["score"]))[0]
    else:
        selected = sorted(candidates, key=lambda c: (-c["score"], c["tonnage"]))[0]

    return lib.loc[selected["index"]]


def fill_time_s(wall_mm: float, product: str, mfi: float) -> float:
    if wall_mm <= 0.45:
        base = 0.24
    elif wall_mm <= 0.70:
        base = 0.34
    elif wall_mm <= 1.20:
        base = 0.52
    elif wall_mm <= 2.00:
        base = 0.85
    else:
        base = 1.25

    mfi_factor = 1 - clamp((mfi - 40) * 0.002, -0.08, 0.08)
    return base / PRODUCT_FACTORS[product]["speed"] * mfi_factor


def moldflow_lite_calculate(
    machine: pd.Series,
    product: str,
    part_weight_g: float,
    cavity: int,
    wall_mm: float,
    mfi: float,
    iml: bool,
) -> dict:
    shot_g = total_shot_g(part_weight_g, cavity)
    shot_util = shot_g / machine["shot_capacity_g"]
    volume_cm3 = shot_g / PP_DENSITY_G_CM3

    melt_c = estimate_melt_temp_c(mfi)
    mold_c = estimate_mold_temp_c(product, wall_mm, iml)

    fill_s = fill_time_s(wall_mm, product, mfi)
    flow_rate_cm3_s = volume_cm3 / max(fill_s, 0.01)

    shear_rate = (6.0 * flow_rate_cm3_s) / (max(wall_mm, 0.3) ** 3 * max(cavity, 1))

    eta0 = eta_zero_cross_wlf(melt_c, mfi)
    viscosity = eta_cross(eta0, shear_rate)

    flow_length_factor = 1.0 + 0.10 * cavity
    if product in {"Cup", "Lid"}:
        flow_length_factor *= 1.10
    if iml:
        flow_length_factor *= 1.05

    pressure_demand_mpa = viscosity * shear_rate * wall_mm * flow_length_factor / 1e6
    pressure_demand_mpa = clamp(pressure_demand_mpa, 40, 175)

    injection_pressure_set_mpa = clamp(pressure_demand_mpa * 1.10, 40, MAX_INJECTION_PRESSURE_MPA)

    main_speed = (flow_rate_cm3_s / (max(wall_mm, 0.3) * max(cavity, 1))) * 10.0
    main_speed *= PRODUCT_FACTORS[product]["speed"]

    if "HİDROLİK" in str(machine["machine_type"]).upper() or "HIDROLIK" in str(machine["machine_type"]).upper():
        main_speed *= 0.96

    speed_z2 = clamp(main_speed, 60, 350)
    speed_z1 = clamp(speed_z2 * 0.55, 30, 220)
    speed_z3 = clamp(speed_z2 * 0.70, 40, 260)

    vp_time_s = fill_s * 0.90
    vp_position_pct = clamp(96 - 2.5 * wall_mm, 86, 96)

    gate_freeze_s = (wall_mm ** 2) / (math.pi ** 2 * THERMAL_DIFFUSIVITY_MM2_S) * math.log(8)
    pack_time_s = clamp(gate_freeze_s * 1.20, 0.8, 6.0)

    if wall_mm <= 0.7:
        pack_ratio = 0.58
    elif wall_mm <= 1.5:
        pack_ratio = 0.62
    else:
        pack_ratio = 0.68

    if product == "Lid":
        pack_ratio -= 0.03

    pack_pressure_mpa = pressure_demand_mpa * pack_ratio
    pack_speed_mm_s = clamp(speed_z2 * 0.15, 10, 60)

    eject_c = 95 if wall_mm <= 1.2 else 105 if wall_mm <= 2.5 else 115
    numerator = max(melt_c - mold_c, 1)
    denominator = max(eject_c - mold_c, 1)
    arg = max((8 / (math.pi ** 2)) * (numerator / denominator), 1.05)

    cooling_s = (wall_mm ** 2) / (math.pi ** 2 * THERMAL_DIFFUSIVITY_MM2_S) * math.log(arg)

    cooling_factor = 2.8
    if product == "Lid":
        cooling_factor *= 0.92
    elif product == "Tray":
        cooling_factor *= 1.05
    if iml:
        cooling_factor *= 1.05

    cooling_s = clamp(cooling_s * cooling_factor, 2.0, 40.0)

    rpm = 78 - 0.35 * (machine["screw_mm"] - 45)
    if mfi > 70:
        rpm += 4
    elif mfi < 30:
        rpm -= 6
    if shot_util < 0.12:
        rpm -= 5
    elif shot_util > 0.45:
        rpm += 4
    if "SERVO" in str(machine["machine_type"]).upper():
        rpm += 2
    rpm = clamp(rpm, 35, 95)

    back_pressure_mpa = 0.4 if mfi >= 70 else 0.6 if mfi >= 40 else 0.8
    plast_rate = machine["screw_mm"] * rpm * 0.045
    recovery_s = clamp(shot_g / max(plast_rate, 1), 0.8, 8.0)

    robot_pick = machine["robot_pick_eyes"]
    robot_iml = machine["robot_iml_eyes"]

    robot_ok = True
    if pd.notna(robot_pick):
        robot_ok = cavity <= robot_pick
    if iml:
        if pd.notna(robot_iml):
            robot_ok = robot_ok and cavity <= robot_iml
        else:
            robot_ok = False

    robot_cycle_s = 1.20 + cavity * 0.07 + (cavity * 0.09 if iml else 0) + (0.15 if robot_ok else 0.70)

    polymer_cycle_s = max(fill_s + pack_time_s + cooling_s + 1.0, recovery_s + cooling_s + 0.8)
    final_cycle_s = max(polymer_cycle_s, robot_cycle_s)

    if final_cycle_s > robot_cycle_s + 0.3:
        bottleneck = "Polimer veya soğutma sınırlı"
    elif final_cycle_s > polymer_cycle_s + 0.3:
        bottleneck = "Robot veya IML sınırlı"
    else:
        bottleneck = "Dengeli hücre"

    delta_t = melt_c - mold_c
    pack_ratio_actual = pack_pressure_mpa / max(pressure_demand_mpa, 1e-6)

    warpage_score = 0.0
    warpage_score += clamp((delta_t - 170) / 90, 0, 1) * 0.30
    warpage_score += clamp((wall_mm - 0.8) / 2.5, 0, 1) * 0.25
    warpage_score += clamp((22 - mold_c) / 12, 0, 1) * 0.15
    warpage_score += clamp((0.58 - pack_ratio_actual) / 0.20, 0, 1) * 0.15

    if iml:
        warpage_score *= 1.12

    warpage_score = clamp(warpage_score, 0, 1)

    if warpage_score < 0.25:
        warpage_risk = "Düşük"
    elif warpage_score < 0.55:
        warpage_risk = "Orta"
    else:
        warpage_risk = "Yüksek"

    notes = []
    if shot_util < 0.08:
        notes.append("Makine shot kapasitesi bu ürün için büyük kalıyor.")
    if shot_util > 0.55:
        notes.append("Shot utilization yüksek. Cushion ve dozaj stabilitesi izlenmeli.")
    if injection_pressure_set_mpa > 175:
        notes.append("Enjeksiyon basıncı 190 MPa limite yakın.")
    if not robot_ok:
        notes.append("Robot göz sayısı kalıp göz sayısı veya IML için uyumsuz.")
    if cooling_s > 25:
        notes.append("Soğutma süresi çevrim darboğazı olabilir.")
    if warpage_risk == "Yüksek":
        notes.append("Warpage riski yüksek. Kalıp sıcaklığı, ütüleme ve soğutma dengesi kontrol edilmeli.")

    return {
        "machine": machine["display"],
        "machine_no": machine["machine_no"],
        "brand": machine["brand"],
        "model": machine["model"],
        "tonnage": machine["tonnage"],
        "machine_type": machine["machine_type"],
        "robot_raw": machine["robot_raw"],
        "screw_mm": machine["screw_mm"],
        "shot_capacity_g": machine["shot_capacity_g"],

        "shot_g": shot_g,
        "shot_util": shot_util,

        "melt_c": melt_c,
        "zone1_c": melt_c - 30,
        "zone2_c": melt_c - 20,
        "zone3_c": melt_c - 10,
        "zone4_c": melt_c - 5,
        "nozzle_c": melt_c,
        "mold_c": mold_c,

        "fill_s": fill_s,
        "flow_rate_cm3_s": flow_rate_cm3_s,
        "shear_rate": shear_rate,
        "eta0_pa_s": eta0,
        "viscosity_pa_s": viscosity,
        "pressure_demand_mpa": pressure_demand_mpa,
        "injection_pressure_set_mpa": injection_pressure_set_mpa,

        "speed_z1": speed_z1,
        "speed_z2": speed_z2,
        "speed_z3": speed_z3,

        "vp_time_s": vp_time_s,
        "vp_position_pct": vp_position_pct,

        "gate_freeze_s": gate_freeze_s,
        "pack_speed_mm_s": pack_speed_mm_s,
        "pack_pressure_mpa": pack_pressure_mpa,
        "pack_time_s": pack_time_s,

        "cooling_s": cooling_s,
        "rpm": rpm,
        "back_pressure_mpa": back_pressure_mpa,
        "recovery_s": recovery_s,

        "robot_cycle_s": robot_cycle_s,
        "polymer_cycle_s": polymer_cycle_s,
        "final_cycle_s": final_cycle_s,
        "bottleneck": bottleneck,
        "warpage_risk": warpage_risk,
        "warpage_score": warpage_score,
        "notes": notes,
    }


# =========================================================
# UI
# =========================================================
st.title("IML Moldflow-Lite Pro")
st.caption("Makine önerisi, reoloji, shear-rate basınç modeli, V/P, gate freeze, soğuma, warpage ve robot çevrim analizi")

with st.sidebar:
    st.header("Girdi Parametreleri")

    mode = st.radio("Makine seçimi", ["Otomatik öner", "Manuel seçim"])

    product = st.selectbox("Ürün tipi", ["Cup", "Lid", "Tray", "Container"])
    iml = st.checkbox("IML kullanılıyor", value=True)

    part_weight_g = st.number_input("Parça ağırlığı (g)", min_value=0.1, max_value=500.0, value=10.0, step=0.1)
    cavity = st.number_input("Kalıp göz sayısı", min_value=1, max_value=64, value=4, step=1)
    wall_mm = st.number_input("Et kalınlığı (mm)", min_value=0.30, max_value=5.00, value=0.60, step=0.05)
    mfi = st.number_input("PP MFI", min_value=1.0, max_value=150.0, value=70.0, step=1.0)

    selected_display = None
    if mode == "Manuel seçim":
        selected_display = st.selectbox("Makine", machine_library["display"].tolist())

    calculate_button = st.button("Hesapla", type="primary", use_container_width=True)

if not calculate_button:
    st.info("Parametreleri girip Hesapla butonuna bas.")
    st.stop()

if mode == "Otomatik öner":
    selected_machine = choose_best_machine(machine_library, product, part_weight_g, cavity, wall_mm, mfi, iml)
else:
    selected_machine = machine_library[machine_library["display"] == selected_display].iloc[0]

result = moldflow_lite_calculate(selected_machine, product, part_weight_g, cavity, wall_mm, mfi, iml)

st.success("Reçete oluşturuldu.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Önerilen Makine", f"{int(result['machine_no'])} / {int(result['tonnage'])} Ton")
k2.metric("Final Çevrim", f"{r(result['final_cycle_s'], 1)} s")
k3.metric("Enjeksiyon Basıncı", f"{r(result['injection_pressure_set_mpa'], 1)} MPa")
k4.metric("Zone 2 Hız", f"{r(result['speed_z2'], 1)} mm/s")
k5.metric("Warpage Riski", result["warpage_risk"])

st.markdown("---")

col1, col2 = st.columns([1.15, 1])

with col1:
    st.subheader("Proses Reçetesi")

    process_df = pd.DataFrame({
        "Parametre": [
            "Makine",
            "Makine tipi",
            "Robot yapısı",
            "Vida çapı",
            "Shot kapasitesi",
            "Shot weight",
            "Shot utilization",
            "Fill time",
            "Shear rate",
            "Eta zero",
            "Viskozite",
            "Proses basınç ihtiyacı",
            "Enjeksiyon basınç seti",
            "V/P zamanı",
            "V/P pozisyonu",
            "Gate freeze tahmini",
            "Ütüleme hızı",
            "Ütüleme basıncı",
            "Ütüleme süresi",
            "Soğutma süresi",
            "Screw RPM",
            "Back pressure",
            "Screw recovery",
            "Warpage skoru",
        ],
        "Değer": [
            result["machine"],
            result["machine_type"],
            result["robot_raw"],
            f"{r(result['screw_mm'], 0)} mm",
            f"{r(result['shot_capacity_g'], 1)} g",
            f"{r(result['shot_g'], 1)} g",
            f"{r(result['shot_util'], 3)}",
            f"{r(result['fill_s'], 2)} s",
            f"{r(result['shear_rate'], 1)} 1/s",
            f"{r(result['eta0_pa_s'], 1)} Pa.s",
            f"{r(result['viscosity_pa_s'], 1)} Pa.s",
            f"{r(result['pressure_demand_mpa'], 1)} MPa",
            f"{r(result['injection_pressure_set_mpa'], 1)} MPa",
            f"{r(result['vp_time_s'], 2)} s",
            f"{r(result['vp_position_pct'], 1)} %",
            f"{r(result['gate_freeze_s'], 2)} s",
            f"{r(result['pack_speed_mm_s'], 1)} mm/s",
            f"{r(result['pack_pressure_mpa'], 1)} MPa",
            f"{r(result['pack_time_s'], 2)} s",
            f"{r(result['cooling_s'], 2)} s",
            f"{r(result['rpm'], 0)}",
            f"{r(result['back_pressure_mpa'], 2)} MPa",
            f"{r(result['recovery_s'], 2)} s",
            f"{r(result['warpage_score'], 2)}",
        ],
    })
    st.dataframe(process_df, use_container_width=True, hide_index=True)

with col2:
    st.subheader("Sıcaklık Profili - 5 Zon")

    temp_df = pd.DataFrame({
        "Bölge": ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Nozzle", "Kalıp"],
        "Sıcaklık": [
            f"{r(result['zone1_c'], 1)} °C",
            f"{r(result['zone2_c'], 1)} °C",
            f"{r(result['zone3_c'], 1)} °C",
            f"{r(result['zone4_c'], 1)} °C",
            f"{r(result['nozzle_c'], 1)} °C",
            f"{r(result['mold_c'], 1)} °C",
        ],
    })
    st.dataframe(temp_df, use_container_width=True, hide_index=True)

    st.subheader("Enjeksiyon Hız Profili - 3 Zon")
    speed_df = pd.DataFrame({
        "Zon": ["Zone 1 - Başlangıç", "Zone 2 - Ana dolum", "Zone 3 - V/P öncesi"],
        "Hız": [
            f"{r(result['speed_z1'], 1)} mm/s",
            f"{r(result['speed_z2'], 1)} mm/s",
            f"{r(result['speed_z3'], 1)} mm/s",
        ],
    })
    st.dataframe(speed_df, use_container_width=True, hide_index=True)

st.markdown("---")

col3, col4 = st.columns(2)

with col3:
    st.subheader("Robot ve Hücre Analizi")
    cell_df = pd.DataFrame({
        "Parametre": [
            "Robot çevrimi",
            "Polimer çevrimi",
            "Final çevrim",
            "Darboğaz",
        ],
        "Değer": [
            f"{r(result['robot_cycle_s'], 2)} s",
            f"{r(result['polymer_cycle_s'], 2)} s",
            f"{r(result['final_cycle_s'], 2)} s",
            result["bottleneck"],
        ],
    })
    st.dataframe(cell_df, use_container_width=True, hide_index=True)

with col4:
    st.subheader("Mühendislik Notları")
    if result["notes"]:
        for note in result["notes"]:
            st.warning(note)
    else:
        st.success("Başlangıç reçetesi uygun görünüyor.")

st.markdown("---")
st.caption("Bu sistem Moldflow yerine geçmez; ancak reoloji, shear, basınç, soğuma, gate freeze, IML robot çevrimi ve makine kütüphanesini birlikte kullanan başlangıç proses penceresi üretir.")
