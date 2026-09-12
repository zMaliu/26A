"""三问结果的独立重算、收敛、守恒和物理范围交叉验证。"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from q1_3 import get_boundary_funcs as get_q1_boundary
from q1_3 import solve_pde as solve_q1
from q2_3 import (
    DEFAULT_INITIAL_FILE,
    INITIAL_TIME,
    OUTPUT_DIR,
    get_boundary_funcs as get_q2_boundary,
    load_initial_profile,
    solve_pde as solve_q2,
)
from q3 import MOISTURE_LIMIT, solve_problem3


BASE_DIR = Path(__file__).resolve().parent
PIC_DIR = BASE_DIR / "pic"
REPORT_FILE = OUTPUT_DIR / "validation_report.json"
R_MAX = 0.02

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def control_volumes(dr: float, nr: int):
    """返回单位长度控制体体积和表面积。"""
    v = np.zeros(nr)
    v[0] = np.pi * (dr / 2.0) ** 2
    for i in range(1, nr - 1):
        v[i] = 2.0 * np.pi * (i * dr) * dr
    r_surface = (nr - 1) * dr
    v[-1] = np.pi * (r_surface**2 - (r_surface - dr / 2.0) ** 2)
    return v, 2.0 * np.pi * r_surface


def read_sheet(path: Path, sheet_index: int = 0) -> pd.DataFrame:
    book = pd.ExcelFile(path)
    return pd.read_excel(path, sheet_name=book.sheet_names[sheet_index])


def add_check(report: dict, name: str, passed: bool, value=None, criterion: str = ""):
    item = {"passed": bool(passed), "criterion": criterion}
    if value is not None:
        item["value"] = value
    report["checks"][name] = item
    if not passed:
        raise AssertionError(f"验证未通过：{name}; value={value}; criterion={criterion}")


def validate_file_structure(report: dict):
    """检查结果文件的工作表、网格、时间和有限值。"""
    expected = {
        "result1.xlsx": (2, 1801, 0.0, 1800.0, 1.0),
        "result2.xlsx": (2, 10801, 0.0, 10800.0, 1.0),
    }
    for name, (n_sheet, n_rows, t0, t1, step) in expected.items():
        path = OUTPUT_DIR / name
        book = pd.ExcelFile(path)
        ok_sheets = len(book.sheet_names) == n_sheet
        add_check(report, f"{name}_工作表", ok_sheets, book.sheet_names, f"工作表数={n_sheet}")
        for j in range(n_sheet):
            df = pd.read_excel(path, sheet_name=book.sheet_names[j])
            times = df.iloc[:, 0].to_numpy(dtype=float)
            values = df.iloc[:, 1:].to_numpy(dtype=float)
            radii = list(df.columns[1:])
            ok = (
                df.shape == (n_rows, 22)
                and np.isclose(times[0], t0)
                and np.isclose(times[-1], t1)
                and np.allclose(np.diff(times), step)
                and radii == [f"{i / 10:.1f}" for i in range(21)]
                and np.all(np.isfinite(values))
                and np.allclose(values, np.round(values, 4))
            )
            add_check(
                report,
                f"{name}_表{j + 1}_结构",
                ok,
                {"shape": list(df.shape), "time": [float(times[0]), float(times[-1])]},
                "22列；时间连续；半径0.0~2.0 cm；四位小数；无NaN",
            )

    path = OUTPUT_DIR / "result3.xlsx"
    df = read_sheet(path)
    times = df.iloc[:, 0].to_numpy(dtype=float)
    values = df.iloc[:, 1:].to_numpy(dtype=float)
    ok = (
        df.shape == (3512, 22)
        and np.isclose(times[0], 0.0)
        and np.isclose(times[-1], 210634.74, atol=0.02)
        and np.all(np.diff(times[:-1]) == 60.0)
        and np.all(np.isfinite(values))
        and np.allclose(values, np.round(values, 4))
    )
    add_check(
        report,
        "result3_结构",
        ok,
        {"shape": list(df.shape), "first_time_s": float(times[0]), "last_time_s": float(times[-1])},
        "0~烘干结束；60 s网格并追加插值结束行；无NaN；四位小数",
    )

    summary = read_sheet(OUTPUT_DIR / "result3_summary.xlsx")
    summary_t = summary.iloc[:, 0].to_numpy(dtype=float)
    ok = (
        summary.shape == (10, 6)
        and np.allclose(summary_t[:-1], np.arange(6.0, 55.0, 6.0))
        and np.isclose(summary_t[-1], 210634.74 / 3600.0, atol=1e-4)
        and np.all(np.isfinite(summary.iloc[:, 1:].to_numpy(dtype=float)))
    )
    add_check(report, "result3_摘要结构", ok, summary_t.tolist(), "每6 h及结束时刻")

    profile = read_sheet(OUTPUT_DIR / "output3.xlsx")
    ok = profile.shape == (21, 3) and np.all(np.isfinite(profile.iloc[:, 1:].to_numpy(dtype=float)));
    add_check(report, "output3_结构", ok, list(profile.shape), "21个径向节点，温度和水分均有限")


def q1_recompute_and_balance(report: dict):
    """独立重算问题一，并检查全局能量和水分守恒。"""
    t_func, c_func = get_q1_boundary()
    t, r, temp, moist = solve_q1(1.0, 0.001, t_end=1800.0, T_air_func=t_func, C_air_func=c_func)
    book = pd.ExcelFile(OUTPUT_DIR / "result1.xlsx")
    stored_t = read_sheet(OUTPUT_DIR / "result1.xlsx", 0).iloc[:, 1:].to_numpy(dtype=float)
    stored_c = read_sheet(OUTPUT_DIR / "result1.xlsx", 1).iloc[:, 1:].to_numpy(dtype=float)
    err_t = float(np.max(np.abs(np.round(temp, 4) - stored_t)))
    err_c = float(np.max(np.abs(np.round(moist, 4) - stored_c)))
    add_check(report, "问题一_独立重算", err_t <= 1e-12 and err_c <= 1e-12,
              {"T_max_abs": err_t, "C_max_abs": err_c}, "重算结果与Excel四位小数结果一致")

    v, area = control_volumes(0.001, len(r))
    rho, cp, h, hm = 820.0, 2600.0, 25.0, 8e-7
    air_t = np.asarray(t_func(t), dtype=float)
    air_c = np.asarray(c_func(t), dtype=float)
    q_step = h * area * (air_t[1:] - temp[:-1, -1])
    m_step = hm * area * (air_c[1:] - moist[:-1, -1])
    storage_q = np.sum(rho * cp * (temp[1:] - temp[:-1]) * v, axis=1)
    storage_m = np.sum((moist[1:] - moist[:-1]) * v, axis=1)
    q_res = abs(np.sum(storage_q) - np.sum(q_step)) / max(abs(np.sum(storage_q)), 1e-12)
    m_res = abs(np.sum(storage_m) - np.sum(m_step)) / max(abs(np.sum(storage_m)), 1e-12)
    add_check(report, "问题一_守恒", q_res < 0.01 and m_res < 0.01,
              {"energy_relative": q_res, "moisture_relative": m_res}, "两项相对残差<1%")
    return {"t": t, "r": r, "T": temp, "C": moist, "q_res": q_res, "m_res": m_res}


def q2_recompute_and_balance(report: dict):
    """独立重算问题二，并检查5500 s断点、守恒和物理范围。"""
    t_func, c_func = get_q2_boundary(t_start=INITIAL_TIME)
    t, r, temp, moist = solve_q2(
        1.0, 0.001, t_end=10800.0, t_start=INITIAL_TIME,
        initial_file=DEFAULT_INITIAL_FILE, T_air_func=t_func, C_air_func=c_func,
    )
    stored_t = read_sheet(OUTPUT_DIR / "result2.xlsx", 0).iloc[:, 1:].to_numpy(dtype=float)
    stored_c = read_sheet(OUTPUT_DIR / "result2.xlsx", 1).iloc[:, 1:].to_numpy(dtype=float)
    err_t = float(np.max(np.abs(np.round(temp, 4) - stored_t)))
    err_c = float(np.max(np.abs(np.round(moist, 4) - stored_c)))
    add_check(report, "问题二_独立重算", err_t <= 1e-12 and err_c <= 1e-12,
              {"T_max_abs": err_t, "C_max_abs": err_c}, "重算结果与Excel四位小数结果一致")

    _, t0, c0 = load_initial_profile(DEFAULT_INITIAL_FILE, r_max=R_MAX, Nr=len(r))
    add_check(report, "问题二_初始剖面", np.max(abs(temp[0] - t0)) <= 1e-12 and np.max(abs(moist[0] - c0)) <= 1e-12,
              {"T_max_abs": float(np.max(abs(temp[0] - t0))), "C_max_abs": float(np.max(abs(moist[0] - c0)))},
              "t=0行等于output3.xlsx")

    v, area = control_volumes(0.001, len(r))
    h, hm = 25.0, 8e-7
    air_t = np.asarray(t_func(INITIAL_TIME + t), dtype=float)
    air_c = np.asarray(c_func(INITIAL_TIME + t), dtype=float)
    rho = 650.0 + 128.0 * moist[:-1]
    cp = 1450.0 + 2736.0 * (moist[:-1] / (moist[:-1] + 1.0))
    q_step = h * area * (air_t[1:] - temp[1:, -1])
    m_step = hm * area * (air_c[1:] - moist[1:, -1])
    storage_q = np.sum(rho * cp * (temp[1:] - temp[:-1]) * v, axis=1)
    storage_m = np.sum((moist[1:] - moist[:-1]) * v, axis=1)
    q_res = abs(np.sum(storage_q) - np.sum(q_step)) / max(abs(np.sum(storage_q)), 1e-12)
    m_res = abs(np.sum(storage_m) - np.sum(m_step)) / max(abs(np.sum(storage_m)), 1e-12)
    finite = bool(np.all(np.isfinite(temp)) and np.all(np.isfinite(moist)))
    physical = finite and bool(np.all(moist >= -1e-12)) and bool(np.all(temp > -50.0)) and bool(np.all(temp < 250.0))
    add_check(report, "问题二_守恒", q_res < 0.01 and m_res < 0.01,
              {"energy_relative": q_res, "moisture_relative": m_res}, "两项相对残差<1%")
    add_check(report, "问题二_物理范围", physical,
              {"T_min": float(temp.min()), "T_max": float(temp.max()), "C_min": float(moist.min()), "C_max": float(moist.max())},
              "有限值、C>=0且未触及截断")
    return {"t": t, "r": r, "T": temp, "C": moist, "q_res": q_res, "m_res": m_res}


def convergence_q1(report: dict):
    tf, cf = get_q1_boundary()
    dt_list = [1.0, 0.5, 0.25]
    sol = {dt: solve_q1(dt, 0.001, t_end=1800.0, T_air_func=tf, C_air_func=cf) for dt in dt_list}
    common_t = np.arange(0.0, 1800.0 + 1e-9, 100.0)
    vals = {dt: (x[2][np.rint(common_t / dt).astype(int)], x[3][np.rint(common_t / dt).astype(int)]) for dt, x in sol.items()}
    e_t = [float(np.max(abs(vals[1.0][0] - vals[0.5][0]))), float(np.max(abs(vals[0.5][0] - vals[0.25][0])))]
    e_c = [float(np.max(abs(vals[1.0][1] - vals[0.5][1]))), float(np.max(abs(vals[0.5][1] - vals[0.25][1])))]
    sf = {"dt": [0.5, 0.25], "T_error": e_t, "C_error": e_c, "T_ratio": e_t[1] / e_t[0], "C_ratio": e_c[1] / e_c[0]}
    add_check(report, "问题一_时间收敛", 0.35 < sf["T_ratio"] < 0.65 and 0.35 < sf["C_ratio"] < 0.65 and e_t[1] < e_t[0] and e_c[1] < e_c[0], sf, "误差递减，收敛比接近0.5")

    dr_list = [0.001, 0.0005, 0.00025]
    sol = {dr: solve_q1(0.05, dr, t_end=1800.0, T_air_func=tf, C_air_func=cf) for dr in dr_list}
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    final = {dr: (np.interp(common_r, x[1], x[2][-1]), np.interp(common_r, x[1], x[3][-1])) for dr, x in sol.items()}
    e_t = [float(np.max(abs(final[0.001][0] - final[0.0005][0]))), float(np.max(abs(final[0.0005][0] - final[0.00025][0])))]
    e_c = [float(np.max(abs(final[0.001][1] - final[0.0005][1]))), float(np.max(abs(final[0.0005][1] - final[0.00025][1])))]
    sf2 = {"dr": [0.0005, 0.00025], "T_error": e_t, "C_error": e_c, "T_ratio": e_t[1] / e_t[0], "C_ratio": e_c[1] / e_c[0]}
    add_check(report, "问题一_空间收敛", 0.15 < sf2["T_ratio"] < 0.35 and 0.15 < sf2["C_ratio"] < 0.35 and e_t[1] < e_t[0] and e_c[1] < e_c[0], sf2, "误差递减，收敛比接近0.25")
    return {"time": sf, "space": sf2}


def convergence_q2(report: dict):
    tf, cf = get_q2_boundary(t_start=INITIAL_TIME)
    dt_list = [1.0, 0.5, 0.25]
    sol = {dt: solve_q2(dt, 0.001, t_end=1800.0, t_start=INITIAL_TIME, initial_file=DEFAULT_INITIAL_FILE, T_air_func=tf, C_air_func=cf) for dt in dt_list}
    common_t = np.arange(0.0, 1800.0 + 1e-9, 100.0)
    vals = {dt: (x[2][np.rint(common_t / dt).astype(int)], x[3][np.rint(common_t / dt).astype(int)]) for dt, x in sol.items()}
    e_t = [float(np.max(abs(vals[1.0][0] - vals[0.5][0]))), float(np.max(abs(vals[0.5][0] - vals[0.25][0])))]
    e_c = [float(np.max(abs(vals[1.0][1] - vals[0.5][1]))), float(np.max(abs(vals[0.5][1] - vals[0.25][1])))]
    sf = {"dt": [0.5, 0.25], "T_error": e_t, "C_error": e_c, "T_ratio": e_t[1] / e_t[0], "C_ratio": e_c[1] / e_c[0]}
    add_check(report, "问题二_时间收敛", 0.35 < sf["T_ratio"] < 0.65 and 0.35 < sf["C_ratio"] < 0.65 and e_t[1] < e_t[0] and e_c[1] < e_c[0], sf, "误差递减，收敛比接近0.5")

    dr_list = [0.001, 0.0005, 0.00025]
    sol = {dr: solve_q2(1.0, dr, t_end=1800.0, t_start=INITIAL_TIME, initial_file=DEFAULT_INITIAL_FILE, T_air_func=tf, C_air_func=cf) for dr in dr_list}
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    final = {dr: (np.interp(common_r, x[1], x[2][-1]), np.interp(common_r, x[1], x[3][-1])) for dr, x in sol.items()}
    e_t = [float(np.max(abs(final[0.001][0] - final[0.0005][0]))), float(np.max(abs(final[0.0005][0] - final[0.00025][0])))]
    e_c = [float(np.max(abs(final[0.001][1] - final[0.0005][1]))), float(np.max(abs(final[0.0005][1] - final[0.00025][1])))]
    sf2 = {"dr": [0.0005, 0.00025], "T_error": e_t, "C_error": e_c, "T_ratio": e_t[1] / e_t[0], "C_ratio": e_c[1] / e_c[0]}
    add_check(report, "问题二_空间收敛", 0.15 < sf2["T_ratio"] < 0.35 and 0.15 < sf2["C_ratio"] < 0.35 and e_t[1] < e_t[0] and e_c[1] < e_c[0], sf2, "误差递减，收敛比接近0.25")
    return {"time": sf, "space": sf2}


def convergence_q3(report: dict):
    dt_list = [60.0, 30.0, 15.0]
    sol = {dt: solve_problem3(dt=dt, dr=0.001, t_end=21600.0) for dt in dt_list}
    common_t = np.arange(0.0, 21600.0 + 1e-9, 3600.0)
    maxc = {dt: np.max(x[3][np.rint(common_t / dt).astype(int)], axis=1) for dt, x in sol.items()}
    e_t = [float(np.max(abs(maxc[60.0] - maxc[30.0]))), float(np.max(abs(maxc[30.0] - maxc[15.0])))]
    sf = {"dt": [30.0, 15.0], "maxC_error": e_t, "ratio": e_t[1] / e_t[0]}
    add_check(report, "问题三_时间收敛", 0.35 < sf["ratio"] < 0.65 and e_t[1] < e_t[0], sf, "误差递减，收敛比接近0.5")

    dr_list = [0.001, 0.0005, 0.00025]
    sol = {dr: solve_problem3(dt=60.0, dr=dr, t_end=21600.0) for dr in dr_list}
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    final = {dr: np.interp(common_r, x[1], x[3][-1]) for dr, x in sol.items()}
    e_s = [float(np.max(abs(final[0.001] - final[0.0005]))), float(np.max(abs(final[0.0005] - final[0.00025])))]
    sf2 = {"dr": [0.0005, 0.00025], "maxC_error": e_s, "ratio": e_s[1] / e_s[0]}
    add_check(report, "问题三_空间收敛", 0.15 < sf2["ratio"] < 0.35 and e_s[1] < e_s[0], sf2, "误差递减，收敛比接近0.25")
    return {"time": sf, "space": sf2}


def q3_full(report: dict):
    """复核问题三全过程、阈值和最终表。"""
    t, r, temp, moist, drying_time, max_c = solve_problem3()
    stored = read_sheet(OUTPUT_DIR / "result3.xlsx").iloc[:, 1:].to_numpy(dtype=float)
    err = float(np.max(np.abs(np.round(moist[: stored.shape[0] - 1], 4) - stored[:-1])))
    add_check(report, "问题三_独立重算", err <= 1e-12, err, "60 s网格重算与Excel一致")
    j = int(np.flatnonzero(max_c <= MOISTURE_LIMIT)[0])
    before, after = float(max_c[j - 1]), float(max_c[j])
    frac = (drying_time - t[j - 1]) / (t[j] - t[j - 1])
    c_end = moist[j - 1] + frac * (moist[j] - moist[j - 1])
    monotonic = bool(np.all(np.diff(max_c) <= 1e-10))
    physical = bool(np.all(np.isfinite(moist)) and np.all(moist >= -1e-12))
    add_check(report, "问题三_阈值", before > MOISTURE_LIMIT and after <= MOISTURE_LIMIT and abs(np.max(c_end) - MOISTURE_LIMIT) < 1e-10,
              {"drying_time_s": drying_time, "drying_time_h": drying_time / 3600.0, "before": before, "after": after, "interpolated_max": float(np.max(c_end))},
              "首次跨越0.15并线性插值")
    add_check(report, "问题三_单调与范围", monotonic and physical,
              {"monotonic": monotonic, "T_min": float(temp.min()), "T_max": float(temp.max()), "C_min": float(moist.min()), "C_max": float(moist.max())},
              "max(C)单调不增；有限值；C>=0")

    v, area = control_volumes(0.001, len(r))
    hm = 8e-7
    t_func, c_func = __import__("q3").get_full_boundary_funcs()
    c_air = np.asarray(c_func(t[1:]), dtype=float)
    flux = hm * area * (c_air - moist[1:, -1])
    storage = np.sum((moist[1:] - moist[:-1]) * v, axis=1)
    m_res = abs(np.sum(storage) - np.sum(flux * 60.0)) / max(abs(np.sum(storage)), 1e-12)
    add_check(report, "问题三_守恒", m_res < 0.01, m_res, "水分守恒相对残差<1%")
    return {"t": t, "r": r, "T": temp, "C": moist, "maxC": max_c, "drying_time": drying_time, "m_res": m_res}


def plot_convergence(report: dict):
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    colors = {"T": "tab:red", "C": "tab:blue", "maxC": "tab:green"}
    labels = [("问题一", report["convergence"]["q1"]), ("问题二", report["convergence"]["q2"]), ("问题三", report["convergence"]["q3"])]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for ax, (title, data) in zip(axes, labels):
        s = data["time"]
        x = s["dt"]
        for key in ["T_error", "C_error", "maxC_error"]:
            if key in s:
                ax.loglog(x, s[key], "o-", color=colors["T" if key == "T_error" else "C" if key == "C_error" else "maxC"], label=key.replace("_error", ""))
        ax.set_title(f"{title} 时间步")
        ax.set_xlabel("时间步长 Δt (s)")
        ax.set_ylabel("最大绝对误差")
        ax.grid(alpha=0.3, which="both")
        ax.legend()
    fig.suptitle("三问时间步收敛交叉验证")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "验证_时间步收敛_三问.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for ax, (title, data) in zip(axes, labels):
        s = data["space"]
        x = s["dr"]
        for key in ["T_error", "C_error", "maxC_error"]:
            if key in s:
                ax.loglog(x, s[key], "o-", color=colors["T" if key == "T_error" else "C" if key == "C_error" else "maxC"], label=key.replace("_error", ""))
        ax.set_title(f"{title} 空间步")
        ax.set_xlabel("空间步长 Δr (m)")
        ax.set_ylabel("最大绝对误差")
        ax.grid(alpha=0.3, which="both")
        ax.legend()
    fig.suptitle("三问空间步收敛交叉验证")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "验证_空间步收敛_三问.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_balance(q1: dict, q2: dict, q3: dict):
    """绘制储量变化与边界通量积分的对照图。"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    # 问题一能量和水分
    v1, area1 = control_volumes(0.001, len(q1["r"]))
    tf1, cf1 = get_q1_boundary()
    at1, ac1 = np.asarray(tf1(q1["t"])), np.asarray(cf1(q1["t"]))
    dq1 = np.cumsum(25.0 * area1 * (at1[1:] - q1["T"][:-1, -1]))
    dm1 = np.cumsum(8e-7 * area1 * (ac1[1:] - q1["C"][:-1, -1]))
    q_storage1 = np.cumsum(np.sum(820.0 * 2600.0 * np.diff(q1["T"], axis=0) * v1, axis=1))
    m_storage1 = np.cumsum(np.sum(np.diff(q1["C"], axis=0) * v1, axis=1))
    axes[0, 0].plot(q1["t"][1:], q_storage1, label="储能变化")
    axes[0, 0].plot(q1["t"][1:], dq1, "--", label="边界热流积分")
    axes[0, 0].set_title(f"问题一能量守恒（残差 {q1['q_res']:.2e}）")
    axes[0, 1].plot(q1["t"][1:], m_storage1, label="水分变化")
    axes[0, 1].plot(q1["t"][1:], dm1, "--", label="边界质流积分")
    axes[0, 1].set_title(f"问题一水分守恒（残差 {q1['m_res']:.2e}）")

    # 问题二、三水分
    v2, area2 = control_volumes(0.001, len(q2["r"]))
    tf2, cf2 = get_q2_boundary(t_start=INITIAL_TIME)
    ac2 = np.asarray(cf2(INITIAL_TIME + q2["t"]))
    dm2 = np.cumsum(8e-7 * area2 * (ac2[1:] - q2["C"][1:, -1]))
    ms2 = np.cumsum(np.sum(np.diff(q2["C"], axis=0) * v2, axis=1))
    axes[1, 0].plot(q2["t"][1:] / 3600.0, ms2, label="水分变化")
    axes[1, 0].plot(q2["t"][1:] / 3600.0, dm2, "--", label="边界质流积分")
    axes[1, 0].set_title(f"问题二水分守恒（残差 {q2['m_res']:.2e}）")

    v3, area3 = control_volumes(0.001, len(q3["r"]))
    from q3 import get_full_boundary_funcs

    _, cf3 = get_full_boundary_funcs()
    ac3 = np.asarray(cf3(q3["t"]))
    dm3 = np.cumsum(8e-7 * area3 * (ac3[1:] - q3["C"][1:, -1]) * 60.0)
    ms3 = np.cumsum(np.sum(np.diff(q3["C"], axis=0) * v3, axis=1))
    axes[1, 1].plot(q3["t"][1:] / 3600.0, ms3, label="水分变化")
    axes[1, 1].plot(q3["t"][1:] / 3600.0, dm3, "--", label="边界质流积分")
    axes[1, 1].set_title(f"问题三水分守恒（残差 {q3['m_res']:.2e}）")

    for ax in axes.flat:
        ax.set_xlabel("时间 (s)" if ax in axes[0, :] else "时间 (h)")
        ax.set_ylabel("单位长度储量变化")
        ax.grid(alpha=0.3)
        ax.legend()
    fig.suptitle("守恒定律交叉验证：储量变化与边界通量积分")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "验证_守恒对照_三问.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_cross_check(report: dict):
    names = ["Q1重算T", "Q1重算C", "Q2重算T", "Q2重算C", "5500s断点T", "5500s断点C"]
    vals = [
        report["checks"]["问题一_独立重算"]["value"]["T_max_abs"],
        report["checks"]["问题一_独立重算"]["value"]["C_max_abs"],
        report["checks"]["问题二_独立重算"]["value"]["T_max_abs"],
        report["checks"]["问题二_独立重算"]["value"]["C_max_abs"],
        report["checkpoint"]["T_max_abs"], report["checkpoint"]["C_max_abs"],
    ]
    vals_plot = np.maximum(vals, 1e-16)
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(names, vals_plot, color=["tab:red", "tab:blue"] * 3)
    ax.set_yscale("log")
    ax.set_ylabel("最大绝对差异（对数坐标）")
    ax.set_title("独立重算与5500 s断点交叉校验")
    ax.grid(axis="y", alpha=0.3, which="both")
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2e}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(PIC_DIR / "验证_独立重算交叉校验.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    report = {"checks": {}, "convergence": {}}
    validate_file_structure(report)
    q1 = q1_recompute_and_balance(report)
    q2 = q2_recompute_and_balance(report)
    q3 = q3_full(report)

    # 5500 s 断点：用问题三全过程重算值与 output3.xlsx 比较
    t_func, c_func = get_q2_boundary(path=OUTPUT_DIR / "output1.xlsx", t_start=0.0)
    _, r_chk, t_chk, c_chk = solve_q2(
        1.0, 0.001, t_end=5500.0, t_start=0.0, initial_file=None,
        initial_T=28.0, initial_C=2.55, T_air_func=t_func, C_air_func=c_func,
    )
    _, t_ref, c_ref = load_initial_profile(DEFAULT_INITIAL_FILE, r_max=R_MAX, Nr=len(r_chk))
    checkpoint = {"T_max_abs": float(np.max(abs(t_chk[-1] - t_ref))), "C_max_abs": float(np.max(abs(c_chk[-1] - c_ref)))}
    add_check(report, "问题二_5500s断点", checkpoint["T_max_abs"] <= 1e-4 and checkpoint["C_max_abs"] <= 1e-4, checkpoint, "全过程重算与output3最大差异<=1e-4")
    report["checkpoint"] = checkpoint

    report["convergence"]["q1"] = convergence_q1(report)
    report["convergence"]["q2"] = convergence_q2(report)
    report["convergence"]["q3"] = convergence_q3(report)
    plot_convergence(report)
    plot_balance(q1, q2, q3)
    plot_cross_check(report)

    report["summary"] = {
        "all_passed": True,
        "q3_drying_time_s": q3["drying_time"],
        "q3_drying_time_h": q3["drying_time"] / 3600.0,
        "figure_files": [
            "验证_时间步收敛_三问.png",
            "验证_空间步收敛_三问.png",
            "验证_守恒对照_三问.png",
            "验证_独立重算交叉校验.png",
        ],
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"全部交叉验证通过，报告已保存：{REPORT_FILE}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
