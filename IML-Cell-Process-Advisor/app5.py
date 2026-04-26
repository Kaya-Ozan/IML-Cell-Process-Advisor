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
st.set_page_config(page_title="IML Cell Process Advisor", layout="wide")

MAX_INJECTION_PRESSURE_MPA = 190.0
PP_DENSITY_G_CM3 = 0.90


# =========================================================
# EXCEL AUTO-DETECT (KRİTİK ÇÖZÜM)
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
xlsx_files = list(BASE_DIR.glob("*.xlsx"))

if not xlsx_files:
    st.error("❌ Klasörde Excel dosyası yok.")
    st.write("Bulunan dosyalar:", [p.name for p in BASE_DIR.iterdir()])
    st.stop()

EXCEL_PATH = xlsx_files[0]


# =========================================================
# HELPERS
# =========================================================
def r1(x):
    return round(float(x), 1)


def clamp(x, low, high):
    return max(low, min(high, x))


def parse_robot_eyes(value):
    text = str(value).upper()

    if "N" in text:
        return None, None

    match = re.search(r"(\d+)\+(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None, None


# =========================================================
# LOAD EXCEL
# =========================================================
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)

    lib = pd.DataFrame({
        "no": df["NO"],
        "brand": df["MAKİNA ADI"],
        "model": df["MAKİNA MODEL"],
        "robot": df["ROBOT GÖZ SAYISI \n(IML + ÜRÜN TAHLİYE)"],
        "tonnage": df["MAKİNE TONAJ"],
        "type": df["MAKİNE TİPİ"],
        "screw": df["VİDA ÇAPI (mm)"],
    })

    parsed = lib["robot"].apply(parse_robot_eyes)

    lib["pick"] = parsed.apply(lambda x: x[0])
    lib["iml"] = parsed.apply(lambda x: x[1])

    lib["shot_cap"] = lib["tonnage"] * 1.5

    lib["display"] = lib.apply(
        lambda x: f"{x['no']} | {x['brand']} {x['model']} | {int(x['tonnage'])}T | Robot {x['robot']}",
        axis=1,
    )

    return lib


lib = load_data(EXCEL_PATH)


# =========================================================
# CALC ENGINE
# =========================================================
def calculate(machine, part_g, cavity, wall, mfi, iml):

    shot = part_g * cavity * 1.08
    shot_util = shot / machine["shot_cap"]

    melt = clamp(236 - 0.22 * (mfi - 20), 215, 240)
    mold = clamp(24 - wall * 3, 14, 32)

    fill = 0.25 if wall < 0.6 else 0.5 if wall < 1.5 else 1.2

    speed = 300 if wall < 0.6 else 180 if wall < 1.5 else 90

    z1 = r1(speed * 0.5)
    z2 = r1(speed)
    z3 = r1(speed * 0.7)

    pressure = clamp(80 + (20 / wall) - 0.3 * mfi, 50, 170)
    inj_set = clamp(pressure * 1.1, 40, 190)

    pack_pressure = r1(pressure * 0.6)
    pack_time = r1(1 + wall * 1.5)

    cooling = r1(wall**2 * 4)

    robot_cycle = 1.5 + cavity * 0.1 if machine["pick"] else 0

    polymer_cycle = fill + pack_time + cooling + 1

    final_cycle = max(polymer_cycle, robot_cycle)

    return {
        "machine": machine["display"],
        "shot": r1(shot),
        "shot_util": r1(shot_util),
        "z1": z1,
        "z2": z2,
        "z3": z3,
        "pressure": r1(inj_set),
        "pack_p": pack_pressure,
        "pack_t": pack_time,
        "cool": cooling,
        "cycle": r1(final_cycle),
    }


# =========================================================
# UI
# =========================================================
st.title("🏭 IML Cell Process Advisor")

with st.sidebar:

    mode = st.radio("Makine seçimi", ["Otomatik", "Manuel"])

    if mode == "Manuel":
        selected = st.selectbox("Makine", lib["display"])
        machine = lib[lib["display"] == selected].iloc[0]
    else:
        machine = lib.iloc[0]

    part = st.number_input("Parça ağırlığı", 0.1, 500.0, 10.0)
    cavity = st.number_input("Göz sayısı", 1, 64, 4)
    wall = st.number_input("Et kalınlığı", 0.3, 5.0, 0.6)
    mfi = st.number_input("MFI", 1.0, 150.0, 70.0)
    iml = st.checkbox("IML", True)

    run = st.button("Hesapla")


if run:

    r = calculate(machine, part, cavity, wall, mfi, iml)

    st.success("Çalıştı 🔥")

    st.write("Makine:", r["machine"])
    st.write("Shot:", r["shot"], "g")
    st.write("Shot Util:", r["shot_util"])

    st.write("Enjeksiyon Hızları (mm/s):")
    st.write("Z1:", r["z1"], "Z2:", r["z2"], "Z3:", r["z3"])

    st.write("Basınç:", r["pressure"], "MPa")
    st.write("Ütüleme:", r["pack_p"], "MPa /", r["pack_t"], "s")

    st.write("Soğutma:", r["cool"], "s")
    st.write("Çevrim:", r["cycle"], "s")
