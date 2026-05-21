
from __future__ import annotations

import math, re
from pathlib import Path
from typing import Optional
import pandas as pd
import streamlit as st

st.set_page_config(page_title="IML Moldflow-Lite Pro", layout="wide", initial_sidebar_state="expanded")

MATERIAL_LIBRARY = {
    "Borealis BJ368MO": dict(supplier="Borealis", polymer_type="PP Heterophasic Copolymer", mfi=70.0, density=0.905, thermal_diffusivity=0.115, eta0_ref=1850.0, power_index=0.26, tau_star=95000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=210, melt_max=245, mold_min=15, mold_max=40, shrinkage_min=1.1, shrinkage_max=1.8, warpage_multiplier=0.92, orientation_sensitivity=0.90, pack_sensitivity=0.95, cooling_sensitivity=0.95, flash_sensitivity=0.95, short_shot_sensitivity=0.90, sink_sensitivity=0.95, note="BJ368MO. Kapak ve gövde uygulamalarında stabil davranış varsayıldı."),
    "Borealis RJ768MO": dict(supplier="Borealis / Borouge", polymer_type="Random Copolymer PP", mfi=70.0, density=0.905, thermal_diffusivity=0.115, eta0_ref=1750.0, power_index=0.24, tau_star=90000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=210, melt_max=240, mold_min=15, mold_max=35, shrinkage_min=1.0, shrinkage_max=1.7, warpage_multiplier=0.88, orientation_sensitivity=0.88, pack_sensitivity=0.92, cooling_sensitivity=0.92, flash_sensitivity=1.05, short_shot_sensitivity=0.85, sink_sensitivity=0.90, note="RJ768MO. Yüksek akışlı random copolymer; dolum kolay, warpage hassasiyeti düşük/orta varsayıldı."),
    "Borealis RH668MO": dict(supplier="Borealis", polymer_type="Random Copolymer PP", mfi=40.0, density=0.905, thermal_diffusivity=0.113, eta0_ref=2300.0, power_index=0.25, tau_star=100000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=215, melt_max=245, mold_min=18, mold_max=40, shrinkage_min=1.0, shrinkage_max=1.7, warpage_multiplier=0.95, orientation_sensitivity=0.95, pack_sensitivity=0.95, cooling_sensitivity=0.95, flash_sensitivity=0.90, short_shot_sensitivity=1.10, sink_sensitivity=0.95, note="RH668MO. MFR daha düşük kabul edildi; eksik dolum hassasiyeti BJ/RJ768MO'ya göre daha yüksek varsayıldı."),
    "LyondellBasell Moplen EP2641": dict(supplier="LyondellBasell", polymer_type="Impact / Heterophasic Copolymer PP", mfi=70.0, density=0.900, thermal_diffusivity=0.100, eta0_ref=2250.0, power_index=0.30, tau_star=115000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=215, melt_max=250, mold_min=20, mold_max=45, shrinkage_min=1.4, shrinkage_max=2.2, warpage_multiplier=1.28, orientation_sensitivity=1.25, pack_sensitivity=1.15, cooling_sensitivity=1.10, flash_sensitivity=0.95, short_shot_sensitivity=1.10, sink_sensitivity=1.15, note="EP2641. Kapak uygulamalarında warpage hassasiyeti yüksek kabul edildi."),
    "LyondellBasell Moplen HP401R": dict(supplier="LyondellBasell", polymer_type="Homo PP", mfi=25.0, density=0.900, thermal_diffusivity=0.115, eta0_ref=2800.0, power_index=0.25, tau_star=105000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=220, melt_max=250, mold_min=20, mold_max=45, shrinkage_min=1.3, shrinkage_max=2.0, warpage_multiplier=1.08, orientation_sensitivity=1.05, pack_sensitivity=1.05, cooling_sensitivity=1.00, flash_sensitivity=0.85, short_shot_sensitivity=1.25, sink_sensitivity=1.05, note="HP401R. Daha düşük MFI nedeniyle dolum hassasiyeti yüksek kabul edildi."),
    "SK Chemical Yuplene B393G": dict(supplier="SK Chemical", polymer_type="Impact Copolymer PP", mfi=30.0, density=0.900, thermal_diffusivity=0.105, eta0_ref=2700.0, power_index=0.29, tau_star=110000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=220, melt_max=255, mold_min=20, mold_max=45, shrinkage_min=1.3, shrinkage_max=2.1, warpage_multiplier=1.15, orientation_sensitivity=1.15, pack_sensitivity=1.10, cooling_sensitivity=1.08, flash_sensitivity=0.90, short_shot_sensitivity=1.25, sink_sensitivity=1.10, note="Yuplene B393G. Impact copolymer davranışı; dolum ve warpage hassasiyeti orta-yüksek varsayıldı."),
    "Lotte Chemical Ranpelen J-590K": dict(supplier="Lotte Chemical", polymer_type="Nucleated Random Copolymer PP", mfi=44.0, density=0.900, thermal_diffusivity=0.112, eta0_ref=2200.0, power_index=0.25, tau_star=98000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=215, melt_max=245, mold_min=18, mold_max=40, shrinkage_min=1.0, shrinkage_max=1.7, warpage_multiplier=0.95, orientation_sensitivity=0.95, pack_sensitivity=0.95, cooling_sensitivity=0.92, flash_sensitivity=0.92, short_shot_sensitivity=1.08, sink_sensitivity=0.95, note="Ranpelen J-590K. Nucleated random copolymer; dengeli ancak MFI 70 sınıfına göre dolum daha hassas kabul edildi."),
    "SK Chemical HSPP BH3500": dict(supplier="SK Chemical", polymer_type="High Impact Copolymer PP", mfi=35.0, density=0.905, thermal_diffusivity=0.100, eta0_ref=3000.0, power_index=0.30, tau_star=120000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=220, melt_max=260, mold_min=20, mold_max=50, shrinkage_min=1.3, shrinkage_max=2.2, warpage_multiplier=1.22, orientation_sensitivity=1.20, pack_sensitivity=1.15, cooling_sensitivity=1.12, flash_sensitivity=0.85, short_shot_sensitivity=1.35, sink_sensitivity=1.20, note="HSPP BH3500. Yüksek darbe sınıfı; dolum, sink ve warpage hassasiyeti yüksek varsayıldı."),
    "Hyundai G-144": dict(supplier="Hyundai", polymer_type="PP", mfi=25.0, density=0.900, thermal_diffusivity=0.110, eta0_ref=2800.0, power_index=0.26, tau_star=105000.0, wlf_c1=8.86, wlf_c2=101.6, melt_min=220, melt_max=250, mold_min=20, mold_max=45, shrinkage_min=1.2, shrinkage_max=2.0, warpage_multiplier=1.08, orientation_sensitivity=1.05, pack_sensitivity=1.05, cooling_sensitivity=1.05, flash_sensitivity=0.85, short_shot_sensitivity=1.25, sink_sensitivity=1.05, note="Hyundai G-144. Fabrika verisine göre kullanılan grade; teknik değerler başlangıç presetidir."),
}

PRODUCT_TYPES_TR = ["Margarin/Labne Gövde", "Margarin/Labne Kapak", "Tereyağ Gövde", "Tava Gövde", "Tava Kapak", "Tatlı Kase", "Yoğurt Gövde", "Yoğurt Kapak", "Oje Kapak", "Sprey Kapak", "Çubuk", "Zeytin Kase", "Zeytin Kapak", "Bebeto Gövde", "Bebeto Kapak"]
PRODUCT_TYPE_MAP = {
    "Margarin/Labne Gövde": "Container", "Margarin/Labne Kapak": "Lid", "Tereyağ Gövde": "Container",
    "Tava Gövde": "Container", "Tava Kapak": "Lid", "Tatlı Kase": "Cup", "Yoğurt Gövde": "Container",
    "Yoğurt Kapak": "Lid", "Oje Kapak": "Lid", "Sprey Kapak": "Lid", "Çubuk": "Container",
    "Zeytin Kase": "Cup", "Zeytin Kapak": "Lid", "Bebeto Gövde": "Container", "Bebeto Kapak": "Lid",
}

BASE_DIR = Path(__file__).resolve().parent
XLSX_FILES = list(BASE_DIR.glob("*.xlsx"))
if not XLSX_FILES:
    st.error("Excel dosyası bulunamadı. Uygulama klasörüne Excel dosyalarını koy.")
    st.stop()

def r(x: float, digits: int = 2) -> float:
    return round(float(x), digits)

def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))

def norm_text(value) -> str:
    text = str(value).strip().upper()
    for old, new in {"İ": "I", "İ": "I", "Ğ": "G", "Ü": "U", "Ş": "S", "Ö": "O", "Ç": "C"}.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text)

def parse_robot_eyes(value) -> tuple[Optional[int], Optional[int]]:
    match = re.search(r"(\d+)\s*\+\s*(\d+)", str(value).strip().upper())
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)

def product_factor(product: str, key: str) -> float:
    return {
        "Cup": {"speed": 1.10, "area": 1.00, "mold_bias": -3},
        "Lid": {"speed": 1.15, "area": 1.12, "mold_bias": -2},
        "Container": {"speed": 1.00, "area": 1.05, "mold_bias": 0},
    }[product][key]

def detect_product_type(product_name: str) -> str:
    n = norm_text(product_name)
    if "SPREY" in n: return "Sprey Kapak"
    if "OJE" in n or "FLORMAR KAPAK" in n: return "Oje Kapak"
    if "BEBETO" in n and "KAPAK" in n: return "Bebeto Kapak"
    if "BEBETO" in n: return "Bebeto Gövde"
    if "CUBUK" in n or "KASIK" in n: return "Çubuk"
    if "ZEYTIN" in n or "M.BIRLIK" in n: return "Zeytin Kapak" if "KAPAK" in n else "Zeytin Kase"
    if "TATLI" in n or "KASE" in n: return "Tatlı Kase"
    if "TAVA" in n: return "Tava Kapak" if "KAPAK" in n else "Tava Gövde"
    if "TEREYAG" in n: return "Tereyağ Gövde"
    if "YOGURT" in n or "KOVA" in n: return "Yoğurt Kapak" if "KAPAK" in n else "Yoğurt Gövde"
    if "KAPAK" in n: return "Margarin/Labne Kapak"
    if "LABNE" in n or "MARGARIN" in n or "KERRY" in n or "SUTAS" in n or "PINAR" in n: return "Margarin/Labne Gövde"
    return "Margarin/Labne Gövde"

def estimate_wall_from_product(product_type_tr: str, part_weight_g: float) -> float:
    base = {
        "Margarin/Labne Kapak": 0.65, "Tava Kapak": 0.70, "Yoğurt Kapak": 0.65,
        "Oje Kapak": 0.90, "Sprey Kapak": 1.10, "Zeytin Kapak": 0.70, "Bebeto Kapak": 0.70,
        "Margarin/Labne Gövde": 0.75, "Tereyağ Gövde": 0.80, "Tava Gövde": 0.90,
        "Tatlı Kase": 0.70, "Yoğurt Gövde": 0.95, "Çubuk": 0.80, "Zeytin Kase": 0.80, "Bebeto Gövde": 0.75,
    }.get(product_type_tr, 0.75)
    corr = -0.08 if part_weight_g <= 8 else 0.00 if part_weight_g <= 15 else 0.10 if part_weight_g <= 30 else 0.20 if part_weight_g <= 60 else 0.30
    return clamp(base + corr, 0.35, 2.20)

def normalize_material_name(raw) -> str:
    n = norm_text(raw)
    if "BJ368" in n: return "Borealis BJ368MO"
    if "RJ768" in n: return "Borealis RJ768MO"
    if "RH668" in n: return "Borealis RH668MO"
    if "EP2641" in n: return "LyondellBasell Moplen EP2641"
    if "HP401" in n: return "LyondellBasell Moplen HP401R"
    if "B393" in n: return "SK Chemical Yuplene B393G"
    if "J-590" in n or "J590" in n: return "Lotte Chemical Ranpelen J-590K"
    if "BH3500" in n: return "SK Chemical HSPP BH3500"
    if "HYUNDAI" in n or "G-144" in n or "G144" in n: return "Hyundai G-144"
    return "Borealis BJ368MO"

def find_excel_with_columns(required_keywords: list[str]) -> Optional[Path]:
    for path in XLSX_FILES:
        try:
            df = pd.read_excel(path, header=None, nrows=8)
            flat = " ".join(norm_text(x) for x in df.astype(str).values.flatten())
            if all(k in flat for k in required_keywords):
                return path
        except Exception:
            continue
    return None

MACHINE_EXCEL = find_excel_with_columns(["MAKINA ADI", "MAKINA MODEL", "MAKINE TONAJ", "VIDA CAPI"])
PRODUCT_EXCEL = find_excel_with_columns(["KALIP ADI", "URUN KODU", "KAVITE SAYISI", "URUN GRAMAJ"])
if MACHINE_EXCEL is None:
    st.error("Makine listesi Excel'i bulunamadı.")
    st.stop()

@st.cache_data
def load_machine_library(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    lib = pd.DataFrame({
        "machine_no": df["NO"], "brand": df["MAKİNA ADI"], "model": df["MAKİNA MODEL"],
        "robot_raw": df["ROBOT GÖZ SAYISI \n(IML + ÜRÜN TAHLİYE)"], "tonnage": df["MAKİNE TONAJ"],
        "machine_type": df["MAKİNE TİPİ"], "screw_mm": df["VİDA ÇAPI (mm)"],
    }).dropna(subset=["machine_no", "brand", "model", "tonnage", "screw_mm"])
    lib["machine_no"] = lib["machine_no"].astype(int)
    lib["tonnage"] = lib["tonnage"].astype(float)
    lib["screw_mm"] = lib["screw_mm"].astype(float)
    parsed = lib["robot_raw"].apply(parse_robot_eyes)
    lib["robot_pick_eyes"] = parsed.apply(lambda x: x[0])
    lib["robot_iml_eyes"] = parsed.apply(lambda x: x[1])
    lib["shot_capacity_g"] = lib["tonnage"] * 1.6
    lib["display"] = lib.apply(lambda x: f"{x['machine_no']} - {x['brand']} {x['model']} - {int(x['tonnage'])} Ton - {x['machine_type']} - Robot {x['robot_raw']}", axis=1)
    return lib

@st.cache_data
def load_product_rules(path: Optional[Path]) -> pd.DataFrame:
    if path is None: return pd.DataFrame()
    raw = pd.read_excel(path, header=None)
    header_row = None
    for i in range(min(10, len(raw))):
        row_text = " ".join(norm_text(x) for x in raw.iloc[i].tolist())
        if "MAKINE NO" in row_text and "KALIP ADI" in row_text:
            header_row = i
            break
    if header_row is None: return pd.DataFrame()
    df = pd.read_excel(path, header=header_row).dropna(how="all")
    col_map = {}
    for c in df.columns:
        nc = norm_text(c)
        if "MAKINE NO" in nc: col_map[c] = "machine_no"
        elif "KALIP ADI" in nc: col_map[c] = "product_name"
        elif "URUN KODU" in nc: col_map[c] = "product_code"
        elif "KAVITE" in nc: col_map[c] = "cavity"
        elif "URUN GRAMAJ" in nc or "GRAMAJ" in nc: col_map[c] = "part_weight_g"
        elif "HAMMADDE" in nc: col_map[c] = "material_raw"
        elif "IML" in nc: col_map[c] = "iml_raw"
    df = df.rename(columns=col_map)
    for n in ["machine_no", "product_name", "product_code", "cavity", "part_weight_g", "material_raw", "iml_raw"]:
        if n not in df.columns: df[n] = None
    for n in ["machine_no", "product_name", "cavity", "part_weight_g", "material_raw", "iml_raw"]:
        df[n] = df[n].ffill()
    df = df.dropna(subset=["machine_no", "product_name", "product_code"])
    df["machine_no"] = df["machine_no"].astype(int)
    df["cavity"] = df["cavity"].astype(int)
    df["part_weight_g"] = df["part_weight_g"].astype(float)
    df["iml"] = df["iml_raw"].apply(lambda x: True if "VAR" in norm_text(x) or "TRUE" in norm_text(x) else False)
    df["material_name_default"] = df["material_raw"].apply(normalize_material_name)
    df["product_type_tr"] = df["product_name"].apply(detect_product_type)
    df["product_internal"] = df["product_type_tr"].map(PRODUCT_TYPE_MAP)
    df["wall_estimated_mm"] = df.apply(lambda x: estimate_wall_from_product(x["product_type_tr"], x["part_weight_g"]), axis=1)
    df["display"] = df.apply(lambda x: f"{x['product_name']} - Kod: {x['product_code']}", axis=1)
    return df

machine_library = load_machine_library(MACHINE_EXCEL)
product_rules = load_product_rules(PRODUCT_EXCEL)

def get_material(material_name: str, override_mfi: bool, user_mfi: float) -> dict:
    mat = MATERIAL_LIBRARY[material_name].copy()
    if override_mfi:
        mat["mfi"] = user_mfi
        mat["note"] += " User MFI override applied."
    return mat

def estimate_melt_temp_c(material: dict) -> float:
    return clamp((material["melt_min"] + material["melt_max"]) / 2, material["melt_min"], material["melt_max"])

def estimate_mold_temp_c(product: str, wall_mm: float, iml: bool, material: dict) -> float:
    base = (material["mold_min"] + material["mold_max"]) / 2 + product_factor(product, "mold_bias")
    base += -3 if wall_mm < 0.7 else 3 if wall_mm > 2.0 else 0
    base += 2 if iml else 0
    return clamp(base, material["mold_min"], material["mold_max"])

def eta_zero_cross_wlf(melt_temp_c: float, material: dict) -> float:
    eta0_mfi = material["eta0_ref"] * (1.0 / max(material["mfi"], 1.0) ** 0.8)
    t_ref = (material["melt_min"] + material["melt_max"]) / 2
    d_t = melt_temp_c - t_ref
    a_t = 10 ** (-material["wlf_c1"] * d_t / (material["wlf_c2"] + d_t + 1e-6))
    return eta0_mfi * a_t

def eta_cross(eta0: float, shear_rate: float, material: dict) -> float:
    term = eta0 * shear_rate / material["tau_star"]
    return eta0 / (1 + term ** (1 - material["power_index"]))

def total_shot_g(part_weight_g: float, cavity: int) -> float:
    return part_weight_g * cavity * 1.08

def projected_area_cm2(product: str, part_weight_g: float, cavity: int, wall_mm: float, material: dict) -> float:
    wall_cm = max(wall_mm / 10.0, 0.03)
    volume_cm3 = part_weight_g / material["density"]
    return (volume_cm3 / wall_cm) * product_factor(product, "area") * cavity

def clamp_load_ratio(product: str, part_weight_g: float, cavity: int, wall_mm: float, material: dict, tonnage: float) -> float:
    area_cm2 = projected_area_cm2(product, part_weight_g, cavity, wall_mm, material)
    cavity_pressure_bar = 230 + (140 / max(wall_mm, 0.45)) - 0.8 * material["mfi"]
    if product in {"Cup", "Lid"}: cavity_pressure_bar += 20
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: cavity_pressure_bar += 15
    cavity_pressure_bar = clamp(cavity_pressure_bar, 180, 440)
    return (area_cm2 * cavity_pressure_bar * 1.15 / 1000) / tonnage

def choose_best_machine(lib: pd.DataFrame, product: str, part_weight_g: float, cavity: int, wall_mm: float, material: dict, iml: bool) -> pd.Series:
    shot = total_shot_g(part_weight_g, cavity)
    candidates = []
    for _, machine in lib.iterrows():
        shot_util = shot / machine["shot_capacity_g"]
        clamp_load = clamp_load_ratio(product, part_weight_g, cavity, wall_mm, material, machine["tonnage"])
        robot_ok = True
        if pd.notna(machine["robot_pick_eyes"]): robot_ok = cavity <= machine["robot_pick_eyes"]
        if iml:
            robot_ok = robot_ok and (pd.notna(machine["robot_iml_eyes"]) and cavity <= machine["robot_iml_eyes"])
        shot_ok = 0.08 <= shot_util <= 0.60
        clamp_ok = clamp_load <= 0.65
        feasible = shot_ok and clamp_ok and robot_ok
        score = 100 - abs(shot_util - 0.25) * 120 - max(0, clamp_load - 0.35) * 80
        if not robot_ok: score -= 40
        if not shot_ok: score -= 30
        if not clamp_ok: score -= 30
        candidates.append({"index": machine.name, "tonnage": machine["tonnage"], "score": score, "feasible": feasible})
    feasible_candidates = [c for c in candidates if c["feasible"]]
    selected = sorted(feasible_candidates, key=lambda c: (c["tonnage"], -c["score"]))[0] if feasible_candidates else sorted(candidates, key=lambda c: (-c["score"], c["tonnage"]))[0]
    return lib.loc[selected["index"]]

def fill_time_s(wall_mm: float, product: str, material: dict) -> float:
    if wall_mm <= 0.45: base = 0.24
    elif wall_mm <= 0.70: base = 0.34
    elif wall_mm <= 1.20: base = 0.52
    elif wall_mm <= 2.00: base = 0.85
    else: base = 1.25
    mfi_factor = 1 - clamp((material["mfi"] - 40) * 0.002, -0.08, 0.08)
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: base *= 1.05
    if "Random" in material["polymer_type"]: base *= 0.97
    return base / product_factor(product, "speed") * mfi_factor

def risk_label(score: float) -> str:
    return "Düşük" if score < 0.25 else "Orta" if score < 0.55 else "Yüksek"

def moldflow_lite_calculate(machine, material, material_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml):
    shot_g = total_shot_g(part_weight_g, cavity)
    shot_util = shot_g / machine["shot_capacity_g"]
    volume_cm3 = shot_g / material["density"]
    melt_c = estimate_melt_temp_c(material)
    mold_c = estimate_mold_temp_c(product, wall_mm, iml, material)
    fill_s = fill_time_s(wall_mm, product, material)
    flow_rate_cm3_s = volume_cm3 / max(fill_s, 0.01)
    shear_rate = (6.0 * flow_rate_cm3_s) / (max(wall_mm, 0.3) ** 3 * max(cavity, 1))
    eta0 = eta_zero_cross_wlf(melt_c, material)
    viscosity = eta_cross(eta0, shear_rate, material)

    flow_length_factor = 1.0 + 0.10 * cavity
    if product in {"Cup", "Lid"}: flow_length_factor *= 1.10
    if iml: flow_length_factor *= 1.05
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: flow_length_factor *= 1.08

    pressure_demand_mpa = clamp(viscosity * shear_rate * wall_mm * flow_length_factor / 1e6, 40, 175)
    injection_pressure_set_mpa = clamp(pressure_demand_mpa * 1.10, 40, 190)

    main_speed = (flow_rate_cm3_s / (max(wall_mm, 0.3) * max(cavity, 1))) * 10.0 * product_factor(product, "speed")
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: main_speed *= 0.95
    if "Random" in material["polymer_type"]: main_speed *= 1.03
    if "HİDROLİK" in str(machine["machine_type"]).upper() or "HIDROLIK" in str(machine["machine_type"]).upper(): main_speed *= 0.96

    speed_z2 = clamp(main_speed, 60, 350)
    speed_z1 = clamp(speed_z2 * 0.55, 30, 220)
    speed_z3 = clamp(speed_z2 * 0.70, 40, 260)

    vp_time_s = fill_s * 0.90
    vp_position_pct = clamp(96 - 2.5 * wall_mm, 86, 96)
    alpha = material["thermal_diffusivity"]
    gate_freeze_s = (wall_mm ** 2) / (math.pi ** 2 * alpha) * math.log(8)
    if "Random" in material["polymer_type"]: gate_freeze_s *= 0.95
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: gate_freeze_s *= 1.08
    pack_time_s = clamp(gate_freeze_s * 1.20, 0.8, 6.0)

    pack_ratio = 0.58 if wall_mm <= 0.7 else 0.62 if wall_mm <= 1.5 else 0.68
    if product == "Lid": pack_ratio -= 0.03
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: pack_ratio += 0.03
    pack_pressure_mpa = pressure_demand_mpa * pack_ratio
    pack_speed_mm_s = clamp(speed_z2 * 0.15, 10, 60)

    eject_c = 95 if wall_mm <= 1.2 else 105 if wall_mm <= 2.5 else 115
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: eject_c += 5
    numerator = max(melt_c - mold_c, 1)
    denominator = max(eject_c - mold_c, 1)
    arg = max((8 / (math.pi ** 2)) * (numerator / denominator), 1.05)
    cooling_s = (wall_mm ** 2) / (math.pi ** 2 * alpha) * math.log(arg)
    cooling_factor = 2.8
    if product == "Lid": cooling_factor *= 0.92
    if iml: cooling_factor *= 1.05
    if "Random" in material["polymer_type"]: cooling_factor *= 0.95
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: cooling_factor *= 1.08
    cooling_s = clamp(cooling_s * cooling_factor, 2.0, 40.0)

    rpm = 78 - 0.35 * (machine["screw_mm"] - 45)
    if material["mfi"] > 70: rpm += 4
    elif material["mfi"] < 30: rpm -= 6
    if shot_util < 0.12: rpm -= 5
    elif shot_util > 0.45: rpm += 4
    if "SERVO" in str(machine["machine_type"]).upper(): rpm += 2
    rpm = clamp(rpm, 35, 95)

    back_pressure_mpa = 0.4 if material["mfi"] >= 70 else 0.6 if material["mfi"] >= 40 else 0.8
    if "Impact" in material["polymer_type"] or "Heterophasic" in material["polymer_type"]: back_pressure_mpa += 0.1
    plast_rate = machine["screw_mm"] * rpm * 0.045
    recovery_s = clamp(shot_g / max(plast_rate, 1), 0.8, 8.0)

    robot_pick, robot_iml = machine["robot_pick_eyes"], machine["robot_iml_eyes"]
    robot_ok = True
    if pd.notna(robot_pick): robot_ok = cavity <= robot_pick
    if iml: robot_ok = robot_ok and (pd.notna(robot_iml) and cavity <= robot_iml)
    robot_cycle_s = 1.20 + cavity * 0.07 + (cavity * 0.09 if iml else 0) + (0.15 if robot_ok else 0.70)
    polymer_cycle_s = max(fill_s + pack_time_s + cooling_s + 1.0, recovery_s + cooling_s + 0.8)
    final_cycle_s = max(polymer_cycle_s, robot_cycle_s)
    bottleneck = "Polimer veya soğutma sınırlı" if final_cycle_s > robot_cycle_s + 0.3 else "Robot veya IML sınırlı" if final_cycle_s > polymer_cycle_s + 0.3 else "Dengeli hücre"

    clamp_load = clamp_load_ratio(product, part_weight_g, cavity, wall_mm, material, machine["tonnage"])
    delta_t = melt_c - mold_c
    pack_ratio_actual = pack_pressure_mpa / max(pressure_demand_mpa, 1e-6)
    shrinkage_mid = (material["shrinkage_min"] + material["shrinkage_max"]) / 2
    orientation_risk = clamp((shear_rate - 8000) / 18000, 0, 1)
    pack_risk = clamp((0.62 - pack_ratio_actual) / 0.25, 0, 1)
    cooling_gradient_risk = clamp((delta_t - 175) / 90, 0, 1)
    pressure_margin_risk = clamp((injection_pressure_set_mpa - 150) / 40, 0, 1)

    warpage_score = 0.0
    warpage_score += clamp((delta_t - 170) / 90, 0, 1) * 0.20
    warpage_score += clamp((wall_mm - 0.8) / 2.5, 0, 1) * 0.17
    warpage_score += clamp((22 - mold_c) / 12, 0, 1) * 0.12
    warpage_score += clamp((0.58 - pack_ratio_actual) / 0.20, 0, 1) * 0.12
    warpage_score += clamp((shrinkage_mid - 1.2) / 0.8, 0, 1) * 0.17
    warpage_score += orientation_risk * 0.14 * material.get("orientation_sensitivity", 1.0)
    warpage_score += pack_risk * 0.10 * material.get("pack_sensitivity", 1.0)
    warpage_score += cooling_gradient_risk * 0.08 * material.get("cooling_sensitivity", 1.0)
    if iml: warpage_score *= 1.12
    warpage_score *= material.get("warpage_multiplier", 1.0)
    warpage_score = clamp(warpage_score, 0, 1)

    flash_score = 0.0
    flash_score += clamp((material["mfi"] - 55) / 60, 0, 1) * 0.25
    flash_score += clamp((injection_pressure_set_mpa - 130) / 60, 0, 1) * 0.20
    flash_score += clamp((pack_pressure_mpa - 70) / 80, 0, 1) * 0.20
    flash_score += clamp((speed_z2 - 220) / 130, 0, 1) * 0.15
    flash_score += clamp((clamp_load - 0.45) / 0.35, 0, 1) * 0.20
    flash_score *= material.get("flash_sensitivity", 1.0)
    flash_score = clamp(flash_score, 0, 1)

    short_shot_score = 0.0
    short_shot_score += clamp((viscosity - 120) / 300, 0, 1) * 0.25
    short_shot_score += clamp((0.75 - wall_mm) / 0.45, 0, 1) * 0.20
    short_shot_score += pressure_margin_risk * 0.25
    short_shot_score += clamp((120 - speed_z2) / 80, 0, 1) * 0.15
    short_shot_score += clamp((material["mfi"] - 40) / -35, 0, 1) * 0.15
    short_shot_score *= material.get("short_shot_sensitivity", 1.0)
    short_shot_score = clamp(short_shot_score, 0, 1)

    sink_score = 0.0
    sink_score += clamp((wall_mm - 1.0) / 1.5, 0, 1) * 0.30
    sink_score += pack_risk * 0.30
    sink_score += clamp((pack_time_s - gate_freeze_s) / -2.0, 0, 1) * 0.20
    sink_score += clamp((shrinkage_mid - 1.3) / 0.8, 0, 1) * 0.20
    sink_score *= material.get("sink_sensitivity", 1.0)
    sink_score = clamp(sink_score, 0, 1)

    notes = []
    if shot_util < 0.08: notes.append("Makine shot kapasitesi bu ürün için büyük kalıyor.")
    if shot_util > 0.55: notes.append("Shot utilization yüksek. Cushion ve dozaj stabilitesi izlenmeli.")
    if injection_pressure_set_mpa > 175: notes.append("Enjeksiyon basıncı 190 MPa limite yakın.")
    if not robot_ok: notes.append("Robot göz sayısı kalıp göz sayısı veya IML için uyumsuz.")
    if cooling_s > 25: notes.append("Soğutma süresi çevrim darboğazı olabilir.")
    if risk_label(warpage_score) == "Yüksek": notes.append("Warpage riski yüksek: kalıp sıcaklığı, ütüleme ve soğutma dengesi kontrol edilmeli.")
    if risk_label(flash_score) == "Yüksek": notes.append("Çapak riski yüksek: V/P geçişi, ütüleme basıncı ve kalıp kapanma yüzeyi kontrol edilmeli.")
    if risk_label(short_shot_score) == "Yüksek": notes.append("Eksik dolum riski yüksek: melt sıcaklığı, Zone 2 hız ve basınç limiti kontrol edilmeli.")
    if risk_label(sink_score) == "Yüksek": notes.append("Sink/çökme riski yüksek: ütüleme süresi, pack pressure ve soğutma süresi kontrol edilmeli.")

    return locals() | {
        "machine": machine["display"], "machine_no": machine["machine_no"], "tonnage": machine["tonnage"],
        "machine_type": machine["machine_type"], "robot_raw": machine["robot_raw"], "screw_mm": machine["screw_mm"],
        "shot_capacity_g": machine["shot_capacity_g"], "product_name": product_name, "product_type_tr": product_type_tr,
        "material_name": material_name, "material_supplier": material["supplier"], "material_type": material["polymer_type"],
        "material_mfi": material["mfi"], "material_density": material["density"], "material_note": material["note"],
        "zone1_c": melt_c - 30, "zone2_c": melt_c - 20, "zone3_c": melt_c - 10,
        "zone4_c": melt_c - 5, "nozzle_c": melt_c,
        "warpage_risk": risk_label(warpage_score), "flash_risk": risk_label(flash_score),
        "short_shot_risk": risk_label(short_shot_score), "sink_risk": risk_label(sink_score), "notes": notes,
    }



# =========================================================
# RECOMMENDATION ENGINE - MACHINE + MATERIAL ADVISOR
# =========================================================
def process_quality_score(result: dict) -> float:
    """Lower score is better. Combines cycle, pressure and risk indicators."""
    risk_sum = (
        result.get("warpage_score", 0) * 1.40
        + result.get("flash_score", 0) * 1.10
        + result.get("short_shot_score", 0) * 1.20
        + result.get("sink_score", 0) * 0.90
    )
    cycle_penalty = clamp((result.get("final_cycle_s", 0) - 3.0) / 20.0, 0, 1) * 0.60
    pressure_penalty = clamp((result.get("injection_pressure_set_mpa", 0) - 145.0) / 45.0, 0, 1) * 0.50
    return risk_sum + cycle_penalty + pressure_penalty


def material_group(material_name: str) -> str:
    """Malzeme alternatifi sadece aynı uygulama ailesi içinde aranır.
    Bu sayede natural/opaque bir grade için şeffaf/random grade önerilmez.
    """
    n = norm_text(material_name)
    if any(k in n for k in ["RJ768", "RH668", "J-590", "J590"]):
        return "transparent_random"
    if any(k in n for k in ["BJ368", "EP2641"]):
        return "opaque_heterophasic_thinwall"
    if any(k in n for k in ["BH3500", "B393", "HP401", "G-144", "G144"]):
        return "impact_or_lower_flow"
    return "general_pp"


def product_material_group(product_type_tr: str, dedicated_material_name: str | None, selected_material_name: str) -> str:
    """Saha ürünü varsa dedike hammaddenin ailesini esas alır.
    Manuel üründe seçilen hammaddenin ailesini esas alır.
    """
    if dedicated_material_name:
        return material_group(dedicated_material_name)
    return material_group(selected_material_name)


def material_is_compatible(candidate_name: str, target_group: str) -> bool:
    return material_group(candidate_name) == target_group


def recommend_machine_alternative(product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml, material, material_name, current_machine_no: int):
    """Seçilen/dedike makineden farklı ve anlamlı avantaj sağlayan makineyi arar.
    Aynı makineyi alternatif diye döndürmez.
    """
    current_machine = machine_library[machine_library["machine_no"] == int(current_machine_no)].iloc[0]
    current_result = moldflow_lite_calculate(current_machine, material, material_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml)
    current_score = process_quality_score(current_result)

    candidates = []
    for _, machine in machine_library.iterrows():
        if int(machine["machine_no"]) == int(current_machine_no):
            continue

        shot = total_shot_g(part_weight_g, cavity)
        shot_util = shot / machine["shot_capacity_g"]
        clamp_load = clamp_load_ratio(product, part_weight_g, cavity, wall_mm, material, machine["tonnage"])

        robot_ok = True
        if pd.notna(machine["robot_pick_eyes"]):
            robot_ok = cavity <= machine["robot_pick_eyes"]
        if iml:
            if pd.notna(machine["robot_iml_eyes"]):
                robot_ok = robot_ok and cavity <= machine["robot_iml_eyes"]
            else:
                robot_ok = False

        if not (0.08 <= shot_util <= 0.60 and clamp_load <= 0.65 and robot_ok):
            continue

        res = moldflow_lite_calculate(machine, material, material_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml)
        score = process_quality_score(res)
        candidates.append({"machine": machine, "result": res, "score": score})

    if not candidates:
        return None, current_result

    best = sorted(candidates, key=lambda x: x["score"])[0]

    # Küçük farkları alternatif olarak göstermiyoruz. Böylece tablo tutarsız görünmez.
    if current_score - best["score"] < 0.08:
        return None, current_result

    return best, current_result


def recommend_best_material_for_machine(machine, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml, selected_material_name, dedicated_material_name=None):
    target_group = product_material_group(product_type_tr, dedicated_material_name, selected_material_name)
    candidates = []

    for mat_name in MATERIAL_LIBRARY.keys():
        if not material_is_compatible(mat_name, target_group):
            continue

        mat = get_material(mat_name, False, MATERIAL_LIBRARY[mat_name]["mfi"])
        res = moldflow_lite_calculate(machine, mat, mat_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml)
        candidates.append({"material_name": mat_name, "result": res, "score": process_quality_score(res)})

    if not candidates:
        mat = get_material(selected_material_name, False, MATERIAL_LIBRARY[selected_material_name]["mfi"])
        res = moldflow_lite_calculate(machine, mat, selected_material_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml)
        return {"material_name": selected_material_name, "result": res, "score": process_quality_score(res)}, []

    ordered = sorted(candidates, key=lambda x: x["score"])
    current = next((c for c in ordered if c["material_name"] == selected_material_name), ordered[0])
    best = ordered[0]

    # Seçili hammaddeye göre anlamlı fark yoksa alternatif gösterme.
    if selected_material_name == best["material_name"] or current["score"] - best["score"] < 0.08:
        return current, ordered

    return best, ordered


def recommendation_feedback(current_result, alternative_result, current_label: str, alternative_label: str) -> str:
    current_score = process_quality_score(current_result)
    alternative_score = process_quality_score(alternative_result)
    improvement = current_score - alternative_score
    if improvement > 0.20:
        return f"{alternative_label} ile daha iyi sonuç alınabilir. Risk/çevrim skoru {r(current_score, 2)} → {r(alternative_score, 2)} seviyesine düşüyor."
    if improvement > 0.08:
        return f"{alternative_label} küçük bir avantaj sağlayabilir. Risk/çevrim skoru {r(current_score, 2)} → {r(alternative_score, 2)}. İlk denemede karşılaştırmalı çalıştırma önerilir."
    return f"{current_label} mevcut koşullarda yeterli görünüyor. {alternative_label} belirgin avantaj göstermiyor."

st.title("IML Moldflow-Lite Pro")
st.caption("Dedike makine + yeni ürün için otomatik makine önerisi + hammadde bazlı proses reçetesi")

with st.sidebar:
    st.header("Girdi Parametreleri")
    source_mode = st.radio("Ürün seçimi", ["Saha listesinden seç", "Manuel giriş"])
    selected_rule = None
    dedicated_machine_no = None
    dedicated_material_name = None

    if source_mode == "Saha listesinden seç" and not product_rules.empty:
        selected_display = st.selectbox("Ürün / Kalıp", product_rules["display"].tolist())
        selected_rule = product_rules[product_rules["display"] == selected_display].iloc[0]
        product_name = selected_rule["product_name"]
        product_type_tr = selected_rule["product_type_tr"]
        product = selected_rule["product_internal"]
        part_weight_g = float(selected_rule["part_weight_g"])
        cavity = int(selected_rule["cavity"])
        iml = bool(selected_rule["iml"])
        dedicated_machine_no = int(selected_rule["machine_no"])
        default_material = selected_rule["material_name_default"]
        dedicated_material_name = default_material
        auto_wall_mm = float(selected_rule["wall_estimated_mm"])
        st.info(f"Dedike saha makinesi: {dedicated_machine_no}")
        st.write(f"Ürün tipi: {product_type_tr}")
        st.write(f"Gramaj: {part_weight_g} g")
        st.write(f"Kavite: {cavity}")
        st.write(f"IML: {'Var' if iml else 'Yok'}")
        st.write(f"Tahmini et kalınlığı: {r(auto_wall_mm, 2)} mm")
    else:
        product_name = "Manuel ürün"
        product_type_tr = st.selectbox("Ürün tipi", PRODUCT_TYPES_TR)
        product = PRODUCT_TYPE_MAP[product_type_tr]
        part_weight_g = st.number_input("Parça ağırlığı (g)", min_value=0.1, max_value=500.0, value=10.0, step=0.1)
        cavity = st.number_input("Kalıp göz sayısı", min_value=1, max_value=64, value=4, step=1)
        iml = st.checkbox("IML kullanılıyor", value=True)
        default_material = "Borealis BJ368MO"
        dedicated_material_name = None
        auto_wall_mm = estimate_wall_from_product(product_type_tr, part_weight_g)

    material_default_index = list(MATERIAL_LIBRARY.keys()).index(default_material) if default_material in MATERIAL_LIBRARY else 0
    material_name = st.selectbox("Hammadde", list(MATERIAL_LIBRARY.keys()), index=material_default_index)

    if dedicated_material_name is not None:
        st.write(f"Sahadaki dedike hammadde: {dedicated_material_name}")
        if material_name != dedicated_material_name:
            st.warning("Seçilen hammadde sahadaki dedike hammaddeden farklı. Sistem reçeteyi ve riskleri seçilen hammaddeye göre yeniden hesaplayacak.")

    wall_mode = st.radio("Et kalınlığı", ["Otomatik tahmin", "Manuel gir"])
    if wall_mode == "Manuel gir":
        wall_mm = st.number_input("Et kalınlığı (mm)", min_value=0.30, max_value=5.00, value=float(auto_wall_mm), step=0.05)
    else:
        wall_mm = auto_wall_mm
        st.write(f"Kullanılan tahmini et kalınlığı: {r(wall_mm, 2)} mm")

    override_mfi = st.checkbox("MFI değerini manuel değiştir", value=False)
    user_mfi = st.number_input("Manuel MFI", min_value=1.0, max_value=150.0, value=MATERIAL_LIBRARY[material_name]["mfi"], step=1.0) if override_mfi else MATERIAL_LIBRARY[material_name]["mfi"]
    material = get_material(material_name, override_mfi, user_mfi)
    calculate_button = st.button("Hesapla", type="primary", use_container_width=True)

if not calculate_button:
    st.info("Parametreleri girip Hesapla butonuna bas.")
    st.stop()

if dedicated_machine_no is not None:
    match = machine_library[machine_library["machine_no"] == dedicated_machine_no]
    if not match.empty:
        selected_machine = match.iloc[0]
        machine_source_note = f"Bu ürün sahada {dedicated_machine_no} no'lu makineye dedike olduğu için reçete bu makineye göre üretildi."
    else:
        selected_machine = choose_best_machine(machine_library, product, part_weight_g, cavity, wall_mm, material, iml)
        machine_source_note = "Dedike makine makine kütüphanesinde bulunamadı; otomatik uygun makine önerildi."
else:
    selected_machine = choose_best_machine(machine_library, product, part_weight_g, cavity, wall_mm, material, iml)
    machine_source_note = "Bu ürün saha listesinde olmadığı için mevcut makine parkuruna göre otomatik uygun makine önerildi."

result = moldflow_lite_calculate(selected_machine, material, material_name, product, product_type_tr, product_name, part_weight_g, cavity, wall_mm, iml)

baseline_result = None
if dedicated_material_name is not None and material_name != dedicated_material_name and dedicated_material_name in MATERIAL_LIBRARY:
    baseline_material = get_material(dedicated_material_name, False, MATERIAL_LIBRARY[dedicated_material_name]["mfi"])
    baseline_result = moldflow_lite_calculate(
        selected_machine,
        baseline_material,
        dedicated_material_name,
        product,
        product_type_tr,
        product_name,
        part_weight_g,
        cavity,
        wall_mm,
        iml,
    )

st.success("Reçete oluşturuldu.")
st.info(machine_source_note)
if baseline_result is not None:
    st.warning("Hammadde değişikliği algılandı: aşağıdaki reçete seçilen hammaddeye göre üretilmiştir. Karşılaştırma tablosu, sahadaki dedike hammaddeye göre farkı gösterir.")

# Makine ve hammadde önerileri: aynı seçimi alternatif diye göstermeden, uyumlu malzeme ailesi içinde karar destek üretir.
machine_alt_candidate, current_machine_check_result = recommend_machine_alternative(
    product,
    product_type_tr,
    product_name,
    part_weight_g,
    cavity,
    wall_mm,
    iml,
    material,
    material_name,
    int(result["machine_no"]),
)

best_material_candidate, all_material_candidates = recommend_best_material_for_machine(
    selected_machine,
    product,
    product_type_tr,
    product_name,
    part_weight_g,
    cavity,
    wall_mm,
    iml,
    material_name,
    dedicated_material_name,
)
best_material_result = best_material_candidate["result"]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Önerilen Makine", f"{int(result['machine_no'])} / {int(result['tonnage'])} Ton")
k2.metric("Final Çevrim", f"{r(result['final_cycle_s'], 1)} s")
k3.metric("Enjeksiyon Basıncı", f"{r(result['injection_pressure_set_mpa'], 1)} MPa")
k4.metric("Zone 2 Hız", f"{r(result['speed_z2'], 1)} mm/s")
k5.metric("Warpage", result["warpage_risk"])

st.subheader("Karar Destek Feedback")
feedback_items = []

if machine_alt_candidate is not None:
    feedback_items.append(recommendation_feedback(
        result,
        machine_alt_candidate["result"],
        f"{int(result['machine_no'])} no'lu makine",
        f"{int(machine_alt_candidate['result']['machine_no'])} no'lu makine"
    ))
else:
    feedback_items.append(
        f"Makine seçimi tutarlı görünüyor: {int(result['machine_no'])} no'lu makine için anlamlı bir makine alternatifi bulunmadı."
    )

if best_material_candidate["material_name"] != material_name:
    feedback_items.append(recommendation_feedback(
        result,
        best_material_result,
        material_name,
        best_material_candidate["material_name"]
    ))
else:
    target_group = product_material_group(product_type_tr, dedicated_material_name, material_name)
    feedback_items.append(
        f"Hammadde seçimi tutarlı görünüyor: {material_name} aynı uygulama ailesi içinde en dengeli seçeneklerden biri. Alternatif araması '{target_group}' ailesiyle sınırlandı."
    )

if dedicated_material_name is not None and material_name != dedicated_material_name and baseline_result is not None:
    feedback_items.append(recommendation_feedback(
        result,
        baseline_result,
        material_name,
        f"sahadaki dedike hammadde {dedicated_material_name}"
    ))

for item in feedback_items:
    st.info(item)

rec_rows = [{
    "Öneri Alanı": "Mevcut reçete",
    "Makine": f"{int(result['machine_no'])} / {int(result['tonnage'])} Ton",
    "Hammadde": result["material_name"],
    "Çevrim": f"{r(result['final_cycle_s'], 2)} s",
    "Basınç": f"{r(result['injection_pressure_set_mpa'], 1)} MPa",
    "Warpage": f"{result['warpage_risk']} ({r(result['warpage_score'], 2)})",
    "Çapak": f"{result['flash_risk']} ({r(result['flash_score'], 2)})",
    "Eksik Dolum": f"{result['short_shot_risk']} ({r(result['short_shot_score'], 2)})",
    "Skor": f"{r(process_quality_score(result), 2)}",
}]

if machine_alt_candidate is not None:
    mres = machine_alt_candidate["result"]
    rec_rows.append({
        "Öneri Alanı": "Makine alternatifi",
        "Makine": f"{int(mres['machine_no'])} / {int(mres['tonnage'])} Ton",
        "Hammadde": mres["material_name"],
        "Çevrim": f"{r(mres['final_cycle_s'], 2)} s",
        "Basınç": f"{r(mres['injection_pressure_set_mpa'], 1)} MPa",
        "Warpage": f"{mres['warpage_risk']} ({r(mres['warpage_score'], 2)})",
        "Çapak": f"{mres['flash_risk']} ({r(mres['flash_score'], 2)})",
        "Eksik Dolum": f"{mres['short_shot_risk']} ({r(mres['short_shot_score'], 2)})",
        "Skor": f"{r(process_quality_score(mres), 2)}",
    })

if best_material_candidate["material_name"] != material_name:
    bres = best_material_result
    rec_rows.append({
        "Öneri Alanı": "Hammadde alternatifi",
        "Makine": f"{int(bres['machine_no'])} / {int(bres['tonnage'])} Ton",
        "Hammadde": bres["material_name"],
        "Çevrim": f"{r(bres['final_cycle_s'], 2)} s",
        "Basınç": f"{r(bres['injection_pressure_set_mpa'], 1)} MPa",
        "Warpage": f"{bres['warpage_risk']} ({r(bres['warpage_score'], 2)})",
        "Çapak": f"{bres['flash_risk']} ({r(bres['flash_score'], 2)})",
        "Eksik Dolum": f"{bres['short_shot_risk']} ({r(bres['short_shot_score'], 2)})",
        "Skor": f"{r(process_quality_score(bres), 2)}",
    })

rec_df = pd.DataFrame(rec_rows)
st.dataframe(rec_df, use_container_width=True, hide_index=True)

if baseline_result is not None:
    st.subheader("Hammadde Değişimi Karşılaştırması")
    comparison_df = pd.DataFrame({
        "Parametre": [
            "Hammadde",
            "Melt sıcaklığı",
            "Kalıp sıcaklığı",
            "Zone 2 hız",
            "Enjeksiyon basıncı",
            "Ütüleme basıncı",
            "Ütüleme süresi",
            "Soğutma süresi",
            "Final çevrim",
            "Warpage riski",
            "Çapak riski",
            "Eksik dolum riski",
            "Sink / çökme riski",
        ],
        "Dedike hammadde": [
            baseline_result["material_name"],
            f"{r(baseline_result['melt_c'], 1)} °C",
            f"{r(baseline_result['mold_c'], 1)} °C",
            f"{r(baseline_result['speed_z2'], 1)} mm/s",
            f"{r(baseline_result['injection_pressure_set_mpa'], 1)} MPa",
            f"{r(baseline_result['pack_pressure_mpa'], 1)} MPa",
            f"{r(baseline_result['pack_time_s'], 2)} s",
            f"{r(baseline_result['cooling_s'], 2)} s",
            f"{r(baseline_result['final_cycle_s'], 2)} s",
            f"{baseline_result['warpage_risk']} ({r(baseline_result['warpage_score'], 2)})",
            f"{baseline_result['flash_risk']} ({r(baseline_result['flash_score'], 2)})",
            f"{baseline_result['short_shot_risk']} ({r(baseline_result['short_shot_score'], 2)})",
            f"{baseline_result['sink_risk']} ({r(baseline_result['sink_score'], 2)})",
        ],
        "Seçilen hammadde": [
            result["material_name"],
            f"{r(result['melt_c'], 1)} °C",
            f"{r(result['mold_c'], 1)} °C",
            f"{r(result['speed_z2'], 1)} mm/s",
            f"{r(result['injection_pressure_set_mpa'], 1)} MPa",
            f"{r(result['pack_pressure_mpa'], 1)} MPa",
            f"{r(result['pack_time_s'], 2)} s",
            f"{r(result['cooling_s'], 2)} s",
            f"{r(result['final_cycle_s'], 2)} s",
            f"{result['warpage_risk']} ({r(result['warpage_score'], 2)})",
            f"{result['flash_risk']} ({r(result['flash_score'], 2)})",
            f"{result['short_shot_risk']} ({r(result['short_shot_score'], 2)})",
            f"{result['sink_risk']} ({r(result['sink_score'], 2)})",
        ],
    })
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    delta_notes = []
    if result["warpage_score"] > baseline_result["warpage_score"] + 0.10:
        delta_notes.append("Seçilen hammadde ile çarpılma riski belirgin artıyor. Ütüleme ve soğutma dengesine özellikle dikkat edilmeli.")
    if result["flash_score"] > baseline_result["flash_score"] + 0.10:
        delta_notes.append("Seçilen hammadde ile çapak riski artıyor. V/P geçişi ve ütüleme basıncı daha hassas ayarlanmalı.")
    if result["short_shot_score"] > baseline_result["short_shot_score"] + 0.10:
        delta_notes.append("Seçilen hammadde ile eksik dolum riski artıyor. Melt sıcaklığı, ana dolum hızı ve basınç limiti kontrol edilmeli.")
    if result["final_cycle_s"] > baseline_result["final_cycle_s"] + 1.0:
        delta_notes.append("Seçilen hammadde ile çevrim süresi uzama eğiliminde. Soğutma ve gate freeze etkisi kontrol edilmeli.")
    if not delta_notes:
        delta_notes.append("Seçilen hammadde dedike reçeteye yakın görünüyor; yine de ilk denemede ürün ölçüsü, çapak ve çarpılma kontrol edilmeli.")
    for note in delta_notes:
        st.info(note)

st.markdown("---")
col1, col2 = st.columns([1.15, 1])

with col1:
    st.subheader("Proses Reçetesi")
    process_df = pd.DataFrame({
        "Parametre": [
            "Ürün", "Ürün tipi", "Tahmini et kalınlığı", "Önerilen/Dedike makine", "Makine tipi", "Robot yapısı", "Vida çapı",
            "Hammadde", "Hammadde tipi", "Malzeme MFI", "Yoğunluk", "Shot kapasitesi", "Shot weight", "Shot utilization",
            "Fill time", "Flow rate", "Shear rate", "Eta zero", "Viskozite", "Proses basınç ihtiyacı",
            "Enjeksiyon basınç seti", "V/P zamanı", "V/P pozisyonu", "Gate freeze tahmini", "Ütüleme hızı",
            "Ütüleme basıncı", "Ütüleme süresi", "Soğutma süresi", "Screw RPM", "Back pressure", "Screw recovery",
        ],
        "Değer": [
            result["product_name"], result["product_type_tr"], f"{r(wall_mm, 2)} mm", result["machine"], result["machine_type"],
            result["robot_raw"], f"{r(result['screw_mm'], 0)} mm", result["material_name"], result["material_type"],
            f"{r(result['material_mfi'], 1)}", f"{r(result['material_density'], 3)} g/cm³", f"{r(result['shot_capacity_g'], 1)} g",
            f"{r(result['shot_g'], 1)} g", f"{r(result['shot_util'], 3)}", f"{r(result['fill_s'], 2)} s",
            f"{r(result['flow_rate_cm3_s'], 2)} cm³/s", f"{r(result['shear_rate'], 1)} 1/s", f"{r(result['eta0'], 1)} Pa.s",
            f"{r(result['viscosity'], 1)} Pa.s", f"{r(result['pressure_demand_mpa'], 1)} MPa",
            f"{r(result['injection_pressure_set_mpa'], 1)} MPa", f"{r(result['vp_time_s'], 2)} s",
            f"{r(result['vp_position_pct'], 1)} %", f"{r(result['gate_freeze_s'], 2)} s",
            f"{r(result['pack_speed_mm_s'], 1)} mm/s", f"{r(result['pack_pressure_mpa'], 1)} MPa",
            f"{r(result['pack_time_s'], 2)} s", f"{r(result['cooling_s'], 2)} s", f"{r(result['rpm'], 0)}",
            f"{r(result['back_pressure_mpa'], 2)} MPa", f"{r(result['recovery_s'], 2)} s",
        ],
    })
    st.dataframe(process_df, use_container_width=True, hide_index=True)

with col2:
    st.subheader("Sıcaklık Profili - 5 Zon")
    temp_df = pd.DataFrame({
        "Bölge": ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Nozzle", "Kalıp"],
        "Sıcaklık": [
            f"{r(result['zone1_c'], 1)} °C", f"{r(result['zone2_c'], 1)} °C", f"{r(result['zone3_c'], 1)} °C",
            f"{r(result['zone4_c'], 1)} °C", f"{r(result['nozzle_c'], 1)} °C", f"{r(result['mold_c'], 1)} °C",
        ],
    })
    st.dataframe(temp_df, use_container_width=True, hide_index=True)

    st.subheader("Enjeksiyon Hız Profili - 3 Zon")
    speed_df = pd.DataFrame({
        "Zon": ["Zone 1 - Başlangıç", "Zone 2 - Ana dolum", "Zone 3 - V/P öncesi"],
        "Hız": [f"{r(result['speed_z1'], 1)} mm/s", f"{r(result['speed_z2'], 1)} mm/s", f"{r(result['speed_z3'], 1)} mm/s"],
    })
    st.dataframe(speed_df, use_container_width=True, hide_index=True)

st.markdown("---")
risk_col, cell_col = st.columns(2)

with risk_col:
    st.subheader("Proses Risk Analizi")
    risk_df = pd.DataFrame({
        "Risk": ["Warpage / Çarpılma", "Çapak", "Eksik dolum", "Sink / Çökme", "Oryantasyon riski", "Ütüleme riski", "Soğuma gradyan riski"],
        "Seviye": [result["warpage_risk"], result["flash_risk"], result["short_shot_risk"], result["sink_risk"], f"{r(result['orientation_risk'], 2)}", f"{r(result['pack_risk'], 2)}", f"{r(result['cooling_gradient_risk'], 2)}"],
        "Skor": [f"{r(result['warpage_score'], 2)}", f"{r(result['flash_score'], 2)}", f"{r(result['short_shot_score'], 2)}", f"{r(result['sink_score'], 2)}", "", "", ""],
    })
    st.dataframe(risk_df, use_container_width=True, hide_index=True)

with cell_col:
    st.subheader("Robot ve Hücre Analizi")
    cell_df = pd.DataFrame({
        "Parametre": ["Robot çevrimi", "Polimer çevrimi", "Final çevrim", "Darboğaz"],
        "Değer": [f"{r(result['robot_cycle_s'], 2)} s", f"{r(result['polymer_cycle_s'], 2)} s", f"{r(result['final_cycle_s'], 2)} s", result["bottleneck"]],
    })
    st.dataframe(cell_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("Mühendislik Notları")
st.write(result["material_note"])
if result["notes"]:
    for note in result["notes"]:
        st.warning(note)
else:
    st.success("Başlangıç reçetesi uygun görünüyor.")

st.caption("Bu sistem Moldflow yerine geçmez; ancak dedike makine bilgisi, otomatik makine önerisi, hammadde fingerprint'i, reoloji, shear, basınç, soğuma, gate freeze ve proses risk tahminini birlikte kullanan başlangıç proses penceresi üretir.")


