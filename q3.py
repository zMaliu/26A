# 问题三干燥时间计算

from pathlib import Path

import numpy as np
import pandas as pd

from q2_3 import (
    BASE_DIR,
    DEFAULT_INITIAL_FILE,
    OUTPUT_DIR,
    INITIAL_TIME,
    _control_volumes,
    get_boundary_funcs,
    load_initial_profile,
    solve_pde,
)


MOISTURE_LIMIT = 0.15
MAX_ABSOLUTE_TIME = 259200.0  # 最长3天
DT = 60.0
DR = 0.001
R_MAX = 0.02


def get_full_boundary_funcs():
    # 拼接两段边界
    T_pre, C_pre = get_boundary_funcs(
        path=OUTPUT_DIR / "output1.xlsx", t_start=0.0
    )
    stable_file = OUTPUT_DIR / "output2.xlsx"
    if not stable_file.exists():
        raise FileNotFoundError(f"未找到恒温边界：{stable_file}，请先运行 q2_1.py")
    T_stable, C_stable = get_boundary_funcs(
        path=stable_file, t_start=INITIAL_TIME
    )

    def join(pre_func, stable_func):
        def func(query):
            q = np.asarray(query, dtype=float)
            scalar = q.ndim == 0
            q1 = np.atleast_1d(q)
            if np.any(q1 < -1e-9):
                raise ValueError("边界查询时间不能为负")
            out = np.empty_like(q1)
            pre_mask = q1 <= INITIAL_TIME
            if np.any(pre_mask):
                out[pre_mask] = np.asarray(pre_func(q1[pre_mask]), dtype=float)
            if np.any(~pre_mask):
                out[~pre_mask] = np.asarray(stable_func(q1[~pre_mask]), dtype=float)
            return float(out[0]) if scalar else out

        return func

    return join(T_pre, T_stable), join(C_pre, C_stable)


def get_simulation_end(max_absolute_time=MAX_ABSOLUTE_TIME, dt=DT):
    # 计算整步终点
    if max_absolute_time < 0 or dt <= 0:
        raise ValueError("时间参数必须为正")
    return float(np.floor(max_absolute_time / dt) * dt)


def solve_problem3(dt=DT, dr=DR, t_end=None):
    # 计算至阈值或终点
    if t_end is None:
        t_end = get_simulation_end(dt=dt)

    # 5500 s后切换恒温边界
    T_func, C_func = get_full_boundary_funcs()
    t, r, T, C = solve_pde(
        dt=dt,
        dr=dr,
        r_max=R_MAX,
        t_end=t_end,
        t_start=0.0,
        initial_file=None,
        initial_T=28.0,
        initial_C=2.55,
        T_air_func=T_func,
        C_air_func=C_func,
    )

    max_C = np.max(C, axis=1)
    hit = np.flatnonzero(max_C <= MOISTURE_LIMIT)
    if len(hit) == 0:
        return t, r, T, C, None, max_C

    j = int(hit[0])
    if j == 0:
        drying_time = 0.0
    else:
        # 线性插值结束时刻
        t0, t1 = t[j - 1], t[j]
        c0, c1 = max_C[j - 1], max_C[j]
        drying_time = float(
            t0 + (MOISTURE_LIMIT - c0) * (t1 - t0) / (c1 - c0)
        )
    return t, r, T, C, drying_time, max_C


def _select_rows(t, times):
    # 取最近时间行
    rows = []
    for target in times:
        if target < t[0] - 1e-9 or target > t[-1] + 1e-9:
            continue
        rows.append(int(np.argmin(np.abs(t - target))))
    return np.asarray(rows, dtype=int)


def verify_q2_checkpoint():
    # 核对5500 s剖面
    if not DEFAULT_INITIAL_FILE.exists():
        raise FileNotFoundError(f"未找到问题二初始文件：{DEFAULT_INITIAL_FILE}")
    T_func, C_func = get_boundary_funcs(
        path=OUTPUT_DIR / "output1.xlsx", t_start=0.0
    )
    _, r, T, C = solve_pde(
        1.0,
        DR,
        r_max=R_MAX,
        t_end=5500.0,
        t_start=0.0,
        initial_file=None,
        initial_T=28.0,
        initial_C=2.55,
        T_air_func=T_func,
        C_air_func=C_func,
    )
    _, T_ref, C_ref = load_initial_profile(
        DEFAULT_INITIAL_FILE, r_max=R_MAX, Nr=len(r)
    )
    err_T = float(np.max(np.abs(T[-1] - T_ref)))
    err_C = float(np.max(np.abs(C[-1] - C_ref)))
    print(f"5500 s 剖面校验：T={err_T:.3e}，C={err_C:.3e}")
    if err_T > 1e-4 or err_C > 1e-4:
        raise AssertionError("第三问与问题二的 5500 s 剖面不一致")
    return err_T, err_C


def save_problem3_results(
    output_file=OUTPUT_DIR / "result3.xlsx",
    summary_file=OUTPUT_DIR / "result3_summary.xlsx",
):
    # 保存完整表和摘要
    t_raw, r, T_raw, C_raw, drying_time, max_C_raw = solve_problem3()

    if drying_time is None:
        t, T, C, max_C = t_raw, T_raw, C_raw, max_C_raw
        end_time = float(t[-1])
        end_label = f"最大计算时长内未达到 {MOISTURE_LIMIT:g}"
    else:
        end_idx = int(np.flatnonzero(max_C_raw <= MOISTURE_LIMIT)[0])
        # 保留整步并追加结束行
        t = t_raw[:end_idx]
        T = T_raw[:end_idx]
        C = C_raw[:end_idx]
        max_C = max_C_raw[:end_idx]
        if end_idx == 0:
            frac = 0.0
        else:
            t_prev = t_raw[end_idx - 1]
            frac = (drying_time - t_prev) / (t_raw[end_idx] - t_prev)
        t = np.append(t, drying_time)
        T_end = T_raw[max(end_idx - 1, 0)] + frac * (
            T_raw[end_idx] - T_raw[max(end_idx - 1, 0)]
        )
        C_end = C_raw[max(end_idx - 1, 0)] + frac * (
            C_raw[end_idx] - C_raw[max(end_idx - 1, 0)]
        )
        T = np.vstack([T, T_end])
        C = np.vstack([C, C_end])
        max_C = np.append(max_C, np.max(C_end))
        end_time = drying_time
        end_label = f"烘干结束：{drying_time / 3600.0:.4f} h（自 0 s）"

    radii_cm = [f"{value * 100.0:.1f}" for value in r]
    time_s = np.round(t, 2)
    df_full = pd.DataFrame(np.round(C, 4), columns=radii_cm)
    df_full.insert(0, "时间", time_s)

    # 取6 h整数倍
    regular_hours = np.arange(
        6.0, np.floor(end_time / 21600.0) * 6.0 + 1e-12, 6.0
    )
    summary_idx = _select_rows(t, regular_hours * 3600.0)
    target_radii = ["0.0", "0.5", "1.0", "1.5", "2.0"]
    summary_rows = []
    for idx in summary_idx:
        row = {"时间/h": round(float(t[idx] / 3600.0), 4)}
        for radius in target_radii:
            radius_idx = int(round(float(radius) / (r[1] * 100.0)))
            row[radius] = round(float(C[idx, radius_idx]), 4)
        summary_rows.append(row)

    if drying_time is not None:
        end_idx = int(np.flatnonzero(max_C_raw <= MOISTURE_LIMIT)[0])
        if end_idx == 0:
            C_end = C_raw[0]
        else:
            t0, t1 = t_raw[end_idx - 1], t_raw[end_idx]
            frac = (drying_time - t0) / (t1 - t0)
            C_end = C_raw[end_idx - 1] + frac * (C_raw[end_idx] - C_raw[end_idx - 1])
        row = {"时间/h": round(float(drying_time / 3600.0), 4)}
        for radius in target_radii:
            radius_idx = int(round(float(radius) / (r[1] * 100.0)))
            row[radius] = float(round(C_end[radius_idx], 4))
        summary_rows.append(row)

    df_summary = pd.DataFrame(
        summary_rows, columns=["时间/h"] + target_radii
    )

    output_file = Path(output_file)
    summary_file = Path(summary_file)
    if not output_file.is_absolute():
        output_file = BASE_DIR / output_file
    if not summary_file.is_absolute():
        summary_file = BASE_DIR / summary_file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    df_full.to_excel(output_file, index=False)
    df_summary.to_excel(summary_file, index=False)

    print(f"问题三完整结果：{output_file}")
    print(f"问题三摘要结果：{summary_file}")
    print(end_label)
    return output_file, summary_file, t, r, T, C, drying_time, max_C


def verify_problem3():
    # 检查初值、阈值和范围
    print("\n问题三数值检验")
    verify_q2_checkpoint()
    _, _, t, r, T, C, drying_time, max_C = save_problem3_results()

    err_T = float(np.max(np.abs(T[0] - 28.0)))
    err_C = float(np.max(np.abs(C[0] - 2.55)))
    print(f"初值最大误差：T={err_T:.3e}，C={err_C:.3e}")

    if drying_time is None:
        print(f"最大计算时长内未达阈值，末端 max(C)={max_C[-1]:.6f}")
    else:
        cross = int(np.searchsorted(t, drying_time))
        before = max_C[max(cross - 1, 0)]
        after = max_C[min(cross, len(max_C) - 1)]
        print(f"烘干时间：{drying_time:.2f} s = {drying_time / 3600.0:.4f} h")
        print(f"阈值前 max(C)={before:.6f}")
        print(f"阈值后 max(C)={after:.6f}")
        if not (before > MOISTURE_LIMIT and after <= MOISTURE_LIMIT):
            raise AssertionError("阈值跨越判定错误")

    print(f"max(C) 是否单调不增：{bool(np.all(np.diff(max_C) <= 1e-10))}")
    print(f"温度范围：{T.min():.6f}～{T.max():.6f} °C")
    print(f"水分范围：{C.min():.6f}～{C.max():.6f} kg/kg")
    print("标准：初值误差 < 1e-10；max(C) 单调不增；阈值正确跨越；无 NaN 和负值。")

    if err_T > 1e-10 or err_C > 1e-10:
        raise AssertionError("问题三初值不一致")
    if not np.all(np.isfinite(T)) or not np.all(np.isfinite(C)):
        raise AssertionError("问题三出现 NaN 或无穷值")
    if np.any(C < -1e-12):
        raise AssertionError("问题三出现负水分浓度")
    if not np.all(np.diff(max_C) <= 1e-10):
        raise AssertionError("全域最大水分浓度不是单调不增")

    return drying_time


def verify_time_step(t_end=21600.0):
    # 检查时间步收敛
    print("\n问题三时间步收敛")
    dt_list = [60.0, 30.0, 15.0]
    results = {dt: solve_problem3(dt=dt, dr=DR, t_end=t_end) for dt in dt_list}
    common_t = np.arange(0.0, t_end + 1e-9, 3600.0)
    max_c = {}
    for dt, (t, _, _, C, _, _) in results.items():
        idx = np.rint(common_t / dt).astype(int)
        max_c[dt] = np.max(C[idx, :], axis=1)
    e1 = float(np.max(np.abs(max_c[60.0] - max_c[30.0])))
    e2 = float(np.max(np.abs(max_c[30.0] - max_c[15.0])))
    print(f"误差：60/30 s={e1:.6g}，30/15 s={e2:.6g}，收敛比={e2 / e1:.4f}")
    print("标准：第二次误差更小，收敛比接近 0.5")
    return e1, e2


def verify_space_step(t_end=21600.0):
    # 检查空间步收敛
    print("\n问题三空间步长收敛")
    dr_list = [0.001, 0.0005, 0.00025]
    results = {dr: solve_problem3(dt=DT, dr=dr, t_end=t_end) for dr in dr_list}
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    final = {}
    for dr, (_, r, _, C, _, _) in results.items():
        final[dr] = np.interp(common_r, r, C[-1, :])
    e1 = float(np.max(np.abs(final[0.001] - final[0.0005])))
    e2 = float(np.max(np.abs(final[0.0005] - final[0.00025])))
    print(f"误差：1/0.5 mm={e1:.6g}，0.5/0.25 mm={e2:.6g}，收敛比={e2 / e1:.4f}")
    print("标准：第二次误差更小，收敛比接近 0.25")
    return e1, e2


def verify_conservation(t_end=21600.0):
    # 检查水分守恒
    print("\n问题三水分守恒")
    T_func, C_func = get_full_boundary_funcs()
    t, r, _, C = solve_pde(
        DT,
        DR,
        r_max=R_MAX,
        t_end=t_end,
        t_start=0.0,
        initial_file=None,
        initial_T=28.0,
        initial_C=2.55,
        T_air_func=T_func,
        C_air_func=C_func,
    )
    V, r_surf = _control_volumes(DR, len(r))
    hm = 8e-7
    area = 2.0 * np.pi * r_surf
    M = np.sum(C * V, axis=1)
    c_air_next = np.asarray(C_func(t[1:]), dtype=float)
    flux = hm * area * (c_air_next - C[1:, -1])
    flux_integral = np.concatenate([[0.0], np.cumsum(flux * DT)])
    residual = abs((M[-1] - M[0]) - flux_integral[-1]) / max(
        abs(M[-1] - M[0]), 1e-12
    )
    print(f"最终相对残差：{residual:.4%}")
    print("标准：水分守恒残差小于 1%")
    if residual >= 0.01:
        raise AssertionError("问题三水分守恒未通过")
    return residual


def plot_problem3_results(t, r, C, drying_time):
    # 结果图统一由 plot_condensed.py 生成
    return None


if __name__ == "__main__":
    result = save_problem3_results()
    verify_problem3()
    verify_time_step()
    verify_space_step()
    verify_conservation()
