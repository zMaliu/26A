"""问题二：恒温段求解、输出与检验。"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_excel"
PIC_DIR = BASE_DIR / "pic"
DEFAULT_INITIAL_FILE = OUTPUT_DIR / "output3.xlsx"
DEFAULT_BOUNDARY_FILE = OUTPUT_DIR / "output2.xlsx"
INITIAL_TIME = 5500.0
DEFAULT_SIMULATION_TIME = 10800.0  # 5500 s 后计算3小时


def _as_scalar_or_array(value):
    arr = np.asarray(value, dtype=float)
    return float(arr) if arr.ndim == 0 else arr


def get_boundary_funcs(path=DEFAULT_BOUNDARY_FILE, t_start=INITIAL_TIME):
    """读取边界，不向前外推。"""
    path = Path(path)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"Boundary file not found: {path}")

    df = pd.read_excel(path)
    if df.shape[1] < 3 or len(df) < 2:
        raise ValueError("Boundary file must contain at least 2 rows and 3 columns")
    t_data = df.iloc[:, 0].to_numpy(dtype=float)
    T_data = df.iloc[:, 1].to_numpy(dtype=float)
    C_data = df.iloc[:, 2].to_numpy(dtype=float)
    if not (np.all(np.isfinite(t_data)) and np.all(np.isfinite(T_data))
            and np.all(np.isfinite(C_data))):
        raise ValueError("Boundary data contains NaN or infinite values")
    if np.any(np.diff(t_data) <= 0):
        raise ValueError("Boundary time must be strictly increasing")
    if t_start < t_data[0] - 1e-9:
        raise ValueError(
            f"Simulation starts at {t_start:g} s, but boundary data starts at "
            f"{t_data[0]:g} s. Do not extrapolate backward."
        )

    tail_n = min(1000, len(t_data))
    T_tail = float(np.mean(T_data[-tail_n:]))
    C_tail = float(np.mean(C_data[-tail_n:]))

    def make_func(values, tail_value):
        def func(query):
            q = np.asarray(query, dtype=float)
            if np.any(q < t_data[0] - 1e-9):
                raise ValueError(
                    f"Boundary queried before available data: min={np.min(q):g} s, "
                    f"first={t_data[0]:g} s"
                )
            result = np.interp(q, t_data, values)
            result = np.where(q > t_data[-1], tail_value, result)
            return _as_scalar_or_array(result)

        return func

    T_func = make_func(T_data, T_tail)
    C_func = make_func(C_data, C_tail)
    print(
        f"Loaded boundary: {path.name}, range={t_data[0]:g}..{t_data[-1]:g} s, "
        f"tail=({T_tail:.4f} C, {C_tail:.6f})"
    )
    return T_func, C_func


def load_initial_profile(path=DEFAULT_INITIAL_FILE, r_max=0.02, Nr=21):
    """读取 5500 s 剖面并插值。"""
    path = Path(path)
    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        raise FileNotFoundError(f"Initial profile file not found: {path}")

    df = pd.read_excel(path)

    if df.shape[1] < 3:
        raise ValueError("output3.xlsx必须包含三列：r,T,C")

    radius_cm = df.iloc[:, 0].to_numpy(dtype=float)
    T0_data = df.iloc[:, 1].to_numpy(dtype=float)
    C0_data = df.iloc[:, 2].to_numpy(dtype=float)

    # 删除空行
    mask = np.isfinite(radius_cm) & np.isfinite(T0_data) & np.isfinite(C0_data)
    radius_cm = radius_cm[mask]
    T0_data = T0_data[mask]
    C0_data = C0_data[mask]

    if len(radius_cm) < 2 or np.any(np.diff(radius_cm) <= 0):
        raise ValueError("output3.xlsx半径必须严格递增")

    # 检查半径范围
    if radius_cm[0] > 1e-12:
        raise ValueError("output3.xlsx第一行半径必须为0cm")

    # 缺少 2.0 cm 时补节点
    if radius_cm[-1] < r_max * 100 - 1e-12:
        if abs(radius_cm[-1] - (r_max*100-0.1)) < 1e-8:
            radius_cm = np.append(radius_cm, r_max*100)
            T0_data = np.append(T0_data, T0_data[-1])
            C0_data = np.append(C0_data, C0_data[-1])
        else:
            raise ValueError(
                f"output3.xlsx半径范围不足: {radius_cm[0]}~{radius_cm[-1]} cm"
            )

    radius_m = radius_cm / 100.0

    r = np.linspace(0.0, r_max, Nr)

    T0 = np.interp(r, radius_m, T0_data)
    C0 = np.interp(r, radius_m, C0_data)

    print(
        f"Loaded initial profile: {path.name}"
    )
    print(
        f"radius: {radius_cm[0]:.1f}~{radius_cm[-1]:.1f} cm, "
        f"nodes={len(radius_cm)}"
    )
    print(
        f"T range={T0.min():.4f}~{T0.max():.4f} C, "
        f"C range={C0.min():.6f}~{C0.max():.6f} kg/kg"
    )

    return r, T0, C0


# 附录 3 物性公式
def rho_of_C(C_val):
    return 650.0 + 128.0 * C_val


def cp_of_C(C_val):
    return 1450.0 + 2736.0 * (C_val / (C_val + 1.0))


def k_of_C(C_val):
    return 0.21 + 0.38 * (C_val / (C_val + 1.0))


def D_of_CT(C_val, T_val):
    C_safe = np.clip(C_val, 0.05, 10.0)
    T_K = np.clip(T_val + 273.15, 273.15, 373.15)
    D = 2.4e-3 * np.exp(-0.45 / C_safe) * np.exp(-3850.0 / T_K)
    return np.clip(D, 1e-14, 1e-3)


def solve_tridiag(a, b, c, d):
    """追赶法求解三对角方程。"""
    n = len(b)
    cp = np.zeros(n)
    dp = np.zeros(n)
    if abs(b[0]) < 1e-14:
        raise ZeroDivisionError("Singular tridiagonal system at first row")
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        if abs(m) < 1e-14:
            raise ZeroDivisionError(f"Singular tridiagonal system at row {i}")
        if i < n - 1:
            cp[i] = c[i] / m
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.zeros(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def solve_pde(
    dt,
    dr,
    r_max=0.02,
    t_end=DEFAULT_SIMULATION_TIME,
    t_start=INITIAL_TIME,
    initial_file=DEFAULT_INITIAL_FILE,
    initial_T=None,
    initial_C=None,
    T_air_func=None,
    C_air_func=None,
):
    """求解恒温段，t 为经过时间，边界用绝对时间。"""
    if dt <= 0 or dr <= 0 or r_max <= 0 or t_end < 0:
        raise ValueError("dt, dr and r_max must be positive; t_end cannot be negative")
    if (T_air_func is None) != (C_air_func is None):
        raise ValueError("Provide both T_air_func and C_air_func, or neither")
    if T_air_func is None:
        T_air_func, C_air_func = get_boundary_funcs(t_start=t_start)

    Nr = int(round(r_max / dr)) + 1
    Nt = int(round(t_end / dt)) + 1
    r = np.linspace(0.0, r_max, Nr)
    t = np.linspace(0.0, t_end, Nt)
    if initial_T is None and initial_C is None:
        r0, T0, C0 = load_initial_profile(initial_file, r_max=r_max, Nr=Nr)
        if not np.allclose(r0, r):
            raise ValueError("Initial profile grid does not match solver grid")
    elif initial_T is None or initial_C is None:
        raise ValueError("initial_T 和 initial_C 必须同时提供")
    else:
        T0 = np.asarray(initial_T, dtype=float)
        C0 = np.asarray(initial_C, dtype=float)
        if T0.ndim == 0:
            T0 = np.full(Nr, float(T0))
        if C0.ndim == 0:
            C0 = np.full(Nr, float(C0))
        if T0.shape != (Nr,) or C0.shape != (Nr,):
            raise ValueError(f"初始数组长度必须为 {Nr}")
        if not (np.all(np.isfinite(T0)) and np.all(np.isfinite(C0))):
            raise ValueError("初始温度或水分含有 NaN/无穷值")

    T = np.zeros((Nt, Nr))
    C = np.zeros((Nt, Nr))
    T[0, :] = T0
    C[0, :] = C0

    h, hm = 25.0, 8e-7
    i_s = Nr - 1
    V_factor = i_s - 0.25
    r_inner = r[1:-1]
    coef_p = 1.0 + dr / (2.0 * r_inner)
    coef_m = 1.0 - dr / (2.0 * r_inner)

    for n in range(Nt - 1):
        T_air_next = float(T_air_func(t_start + t[n + 1]))
        C_air_next = float(C_air_func(t_start + t[n + 1]))

        C_mid_L = 0.5 * (C[n, :-2] + C[n, 1:-1])
        C_mid_R = 0.5 * (C[n, 1:-1] + C[n, 2:])
        T_mid_L = 0.5 * (T[n, :-2] + T[n, 1:-1])
        T_mid_R = 0.5 * (T[n, 1:-1] + T[n, 2:])
        k_L = k_of_C(C_mid_L)
        k_R = k_of_C(C_mid_R)
        D_L = D_of_CT(C_mid_L, T_mid_L)
        D_R = D_of_CT(C_mid_R, T_mid_R)
        rho_inner = rho_of_C(C[n, 1:-1])
        cp_inner = cp_of_C(C[n, 1:-1])
        alpha_T_inner = dt / (rho_inner * cp_inner * dr**2)

        a_T = np.zeros(Nr)
        b_T = np.zeros(Nr)
        c_T = np.zeros(Nr)
        d_T = np.zeros(Nr)
        for idx in range(Nr - 2):
            i = idx + 1
            ai = alpha_T_inner[idx]
            a_T[i] = -ai * coef_m[idx] * k_L[idx]
            b_T[i] = 1.0 + ai * (coef_p[idx] * k_R[idx] + coef_m[idx] * k_L[idx])
            c_T[i] = -ai * coef_p[idx] * k_R[idx]
            d_T[i] = T[n, i]

        k_01 = k_of_C(0.5 * (C[n, 0] + C[n, 1]))
        rho_0 = rho_of_C(C[n, 0])
        cp_0 = cp_of_C(C[n, 0])
        alpha_0 = dt / (rho_0 * cp_0 * dr**2)
        b_T[0] = 1.0 + 4.0 * alpha_0 * k_01
        c_T[0] = -4.0 * alpha_0 * k_01
        d_T[0] = T[n, 0]

        C_s_T = C[n, i_s]
        rho_s_T = rho_of_C(C_s_T)
        cp_s_T = cp_of_C(C_s_T)
        # 表面界面取两节点平均物性
        k_s_T = k_of_C(0.5 * (C[n, i_s - 1] + C[n, i_s]))
        beta_T = dt / (rho_s_T * cp_s_T * V_factor * dr**2)
        coef_s_T_diff = 2.0 * (i_s - 0.5) * k_s_T
        coef_s_T_conv = 2.0 * i_s * h * dr
        a_T[i_s] = -beta_T * coef_s_T_diff
        b_T[i_s] = 1.0 + beta_T * (coef_s_T_diff + coef_s_T_conv)
        d_T[i_s] = T[n, i_s] + beta_T * coef_s_T_conv * T_air_next
        T[n + 1, :] = solve_tridiag(a_T, b_T, c_T, d_T)

        alpha_C_inner = dt / dr**2
        a_C = np.zeros(Nr)
        b_C = np.zeros(Nr)
        c_C = np.zeros(Nr)
        d_C = np.zeros(Nr)
        for idx in range(Nr - 2):
            i = idx + 1
            a_C[i] = -alpha_C_inner * coef_m[idx] * D_L[idx]
            b_C[i] = 1.0 + alpha_C_inner * (coef_p[idx] * D_R[idx] + coef_m[idx] * D_L[idx])
            c_C[i] = -alpha_C_inner * coef_p[idx] * D_R[idx]
            d_C[i] = C[n, i]

        D_01 = D_of_CT(0.5 * (C[n, 0] + C[n, 1]), 0.5 * (T[n, 0] + T[n, 1]))
        b_C[0] = 1.0 + 4.0 * alpha_C_inner * D_01
        c_C[0] = -4.0 * alpha_C_inner * D_01
        d_C[0] = C[n, 0]

        # 共用表面界面扩散系数
        D_s_C = D_of_CT(
            0.5 * (C[n, i_s - 1] + C[n, i_s]),
            0.5 * (T[n, i_s - 1] + T[n, i_s]),
        )
        g1 = dt * 2.0 * (i_s - 0.5) * D_s_C / (V_factor * dr**2)
        g2 = dt * 2.0 * i_s * hm / (V_factor * dr)
        a_C[i_s] = -g1
        b_C[i_s] = 1.0 + g1 + g2
        d_C[i_s] = C[n, i_s] + g2 * C_air_next
        C[n + 1, :] = solve_tridiag(a_C, b_C, c_C, d_C)

        C[n + 1, :] = np.clip(C[n + 1, :], 0.0, 10.0)
        T[n + 1, :] = np.clip(T[n + 1, :], -50.0, 250.0)

    return t, r, T, C


def _solve_for_validation(dt, dr, t_end=1800.0):
    T_func, C_func = get_boundary_funcs(t_start=INITIAL_TIME)
    return solve_pde(
        dt, dr, t_end=t_end, t_start=INITIAL_TIME,
        initial_file=DEFAULT_INITIAL_FILE,
        T_air_func=T_func, C_air_func=C_func,
    )


def verify_initial_profile():
    """检查初值是否等于 output3.xlsx。"""
    _, T0, C0 = load_initial_profile(DEFAULT_INITIAL_FILE, r_max=0.02, Nr=21)
    t, r, T, C = _solve_for_validation(1.0, 0.001, t_end=0.0)
    err_T = float(np.max(np.abs(T[0] - T0)))
    err_C = float(np.max(np.abs(C[0] - C0)))
    print("\n初始剖面检查")
    print(f"  max |T[0]-T_output3| = {err_T:.3e} C")
    print(f"  max |C[0]-C_output3| = {err_C:.3e} kg/kg")
    print(f"  initial radius grid = {r[0] * 100:g}..{r[-1] * 100:g} cm")
    if err_T > 1e-10 or err_C > 1e-10:
        raise AssertionError("Initial row does not match output3.xlsx")
    return t, r, T, C


def verify_time_step(t_end=1800.0):
    print("\n时间步收敛")
    dt_list = [1.0, 0.5, 0.25]
    results = {dt: _solve_for_validation(dt, 0.001, t_end=t_end) for dt in dt_list}
    common_t = np.arange(0.0, t_end + 1e-9, 100.0)
    T_common, C_common = {}, {}
    for dt, result in results.items():
        _, _, T, C = result
        idx = np.rint(common_t / dt).astype(int)
        T_common[dt] = T[idx, :]
        C_common[dt] = C[idx, :]
    err_T_1_05 = np.max(np.abs(T_common[1.0] - T_common[0.5]))
    err_T_05_025 = np.max(np.abs(T_common[0.5] - T_common[0.25]))
    err_C_1_05 = np.max(np.abs(C_common[1.0] - C_common[0.5]))
    err_C_05_025 = np.max(np.abs(C_common[0.5] - C_common[0.25]))
    print(f"  T: dt 1.0 vs 0.5 = {err_T_1_05:.6g} C")
    print(f"  T: dt 0.5 vs 0.25 = {err_T_05_025:.6g} C")
    print(f"  C: dt 1.0 vs 0.5 = {err_C_1_05:.6g}")
    print(f"  C: dt 0.5 vs 0.25 = {err_C_05_025:.6g}")
    print(f"  温度收敛比 = {err_T_05_025 / err_T_1_05:.4f}")
    print(f"  水分收敛比 = {err_C_05_025 / err_C_1_05:.4f}")
    print("  标准：第二次误差更小，收敛比接近 0.5")
    ratio_T = err_T_05_025 / err_T_1_05
    ratio_C = err_C_05_025 / err_C_1_05
    if not (err_T_05_025 < err_T_1_05 and err_C_05_025 < err_C_1_05
            and 0.35 < ratio_T < 0.65 and 0.35 < ratio_C < 0.65
            and err_T_1_05 < 0.01 and err_C_1_05 < 0.01):
        raise AssertionError("问题二时间步收敛未通过")
    return results


def verify_space_step(t_end=1800.0):
    print("\n空间步收敛")
    dt = 1.0
    dr_list = [0.001, 0.0005, 0.00025]
    results = {dr: _solve_for_validation(dt, dr, t_end=t_end) for dr in dr_list}
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    T_final, C_final = {}, {}
    for dr, result in results.items():
        _, r, T, C = result
        T_final[dr] = np.interp(common_r, r, T[-1, :])
        C_final[dr] = np.interp(common_r, r, C[-1, :])
    err_T_1_05 = np.max(np.abs(T_final[0.001] - T_final[0.0005]))
    err_T_05_025 = np.max(np.abs(T_final[0.0005] - T_final[0.00025]))
    err_C_1_05 = np.max(np.abs(C_final[0.001] - C_final[0.0005]))
    err_C_05_025 = np.max(np.abs(C_final[0.0005] - C_final[0.00025]))
    print(f"  T: dr 1.0 vs 0.5 mm = {err_T_1_05:.6g} C")
    print(f"  T: dr 0.5 vs 0.25 mm = {err_T_05_025:.6g} C")
    print(f"  C: dr 1.0 vs 0.5 mm = {err_C_1_05:.6g}")
    print(f"  C: dr 0.5 vs 0.25 mm = {err_C_05_025:.6g}")
    print(f"  温度收敛比 = {err_T_05_025 / err_T_1_05:.4f}")
    print(f"  水分收敛比 = {err_C_05_025 / err_C_1_05:.4f}")
    print("  标准：第二次误差更小，收敛比接近 0.25")
    ratio_T = err_T_05_025 / err_T_1_05
    ratio_C = err_C_05_025 / err_C_1_05
    if not (err_T_05_025 < err_T_1_05 and err_C_05_025 < err_C_1_05
            and 0.15 < ratio_T < 0.35 and 0.15 < ratio_C < 0.35
            and err_T_1_05 < 0.01 and err_C_1_05 < 0.01):
        raise AssertionError("问题二空间步收敛未通过")
    return results


def _control_volumes(dr, Nr):
    V = np.zeros(Nr)
    V[0] = np.pi * (dr / 2.0) ** 2
    for i in range(1, Nr - 1):
        V[i] = 2.0 * np.pi * (i * dr) * dr
    r_surf = (Nr - 1) * dr
    V[-1] = np.pi * (r_surf**2 - (r_surf - dr / 2.0) ** 2)
    return V, r_surf


def verify_conservation(t_end=DEFAULT_SIMULATION_TIME):
    print("\n守恒检查")
    dt, dr = 1.0, 0.001
    T_func, C_func = get_boundary_funcs(t_start=INITIAL_TIME)
    t, r, T, C = solve_pde(
        dt, dr, t_end=t_end, t_start=INITIAL_TIME,
        initial_file=DEFAULT_INITIAL_FILE,
        T_air_func=T_func, C_air_func=C_func,
    )
    _, Nr = T.shape
    V, r_surf = _control_volumes(dr, Nr)
    h, hm = 25.0, 8e-7
    A_surf = 2.0 * np.pi * r_surf

    M = np.sum(C * V, axis=1)
    # 使用与表面方程相同的离散通量
    C_air_next = np.asarray(C_func(INITIAL_TIME + t[1:]), dtype=float)
    m_flux_step = hm * A_surf * (C_air_next - C[1:, -1])
    M_flux_int = np.concatenate([[0.0], np.cumsum(m_flux_step * dt)])
    M_change = M - M[0]
    moisture_rel_err = abs(M_change[-1] - M_flux_int[-1]) / max(abs(M_change[-1]), 1e-12)

    # 按离散方程计算蓄热量
    thermal_storage = np.sum(
        rho_of_C(C[:-1]) * cp_of_C(C[:-1]) * (T[1:] - T[:-1]) * V,
        axis=1,
    )
    T_air_next = np.asarray(T_func(INITIAL_TIME + t[1:]), dtype=float)
    q_flux_step = h * A_surf * (T_air_next - T[1:, -1])
    energy_residual = abs(np.sum(thermal_storage) - np.sum(q_flux_step * dt))
    energy_scale = max(abs(np.sum(thermal_storage)), 1e-12)
    energy_rel_err = energy_residual / energy_scale

    print(f"  最终水分守恒残差 = {moisture_rel_err:.4%}")
    print(f"  最终热量诊断残差 = {energy_rel_err:.4%}")
    print("  标准：水分和热量残差均小于 1%")
    if moisture_rel_err >= 0.01 or energy_rel_err >= 0.01:
        raise AssertionError("问题二守恒检验未通过")
    return moisture_rel_err, energy_rel_err


def verify_physical_bounds(t_end=DEFAULT_SIMULATION_TIME):
    print("\n物理范围检查")
    t, r, T, C = _solve_for_validation(1.0, 0.001, t_end=t_end)
    finite = bool(np.all(np.isfinite(T)) and np.all(np.isfinite(C)))
    clipped_T = bool(np.any((T <= -50.0) | (T >= 250.0)))
    clipped_C = bool(np.any((C <= 0.0) | (C >= 10.0)))
    print(f"  数组有限：{finite}")
    print(f"  T 范围：{T.min():.6f}..{T.max():.6f} C；触及截断：{clipped_T}")
    print(f"  C 范围：{C.min():.6f}..{C.max():.6f} kg/kg；触及截断：{clipped_C}")
    print("  标准：有限值、C>=0，且计算未触及截断")
    if not finite:
        raise AssertionError("NaN or infinite value detected")
    if np.any(C < -1e-12) or clipped_T or clipped_C:
        raise AssertionError("问题二物理范围检验未通过")
    return t, r, T, C


def save_problem2_results(
    dt=1.0,
    dr=0.001,
    t_end=DEFAULT_SIMULATION_TIME,
):
    """保存问题二四个结果表，时间从 0 开始。"""
    T_func, C_func = get_boundary_funcs(t_start=INITIAL_TIME)
    t, r, T, C = solve_pde(
        dt, dr, t_end=t_end, t_start=INITIAL_TIME,
        initial_file=DEFAULT_INITIAL_FILE,
        T_air_func=T_func, C_air_func=C_func,
    )
    radii_cm = [f"{value * 100.0:.1f}" for value in r]
    time_s = np.rint(t).astype(int)
    df_T = pd.DataFrame(np.round(T, 4), columns=radii_cm)
    df_C = pd.DataFrame(np.round(C, 4), columns=radii_cm)
    df_T.insert(0, "时间", time_s)
    df_C.insert(0, "时间", time_s)

    target_hours = np.arange(0.5, 3.0 + 1e-12, 0.5)
    target_seconds = np.rint(target_hours * 3600.0).astype(int)
    target_radii = ["0.0", "0.5", "1.0", "1.5", "2.0"]
    # 按目标秒数取样，避免浮点时间比较误差
    sample_idx = [int(np.argmin(np.abs(time_s - value))) for value in target_seconds]
    df_T_sample = df_T.iloc[sample_idx][["时间"] + target_radii].copy()
    df_C_sample = df_C.iloc[sample_idx][["时间"] + target_radii].copy()
    # 摘要表改用小时
    df_T_sample["时间"] = df_T_sample["时间"] / 3600.0
    df_C_sample["时间"] = df_C_sample["时间"] / 3600.0

    if not np.allclose(df_T_sample["时间"].to_numpy(), target_hours):
        raise AssertionError("温度摘要表时间点错误")
    if not np.allclose(df_C_sample["时间"].to_numpy(), target_hours):
        raise AssertionError("水分摘要表时间点错误")

    outputs = {
        "q2_1.xlsx": df_T,
        "q2_2.xlsx": df_C,
        "q2_3.xlsx": df_T_sample,
        "q2_4.xlsx": df_C_sample,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        target = OUTPUT_DIR / name
        try:
            frame.to_excel(target, index=False)
            print(f"已保存：{target}")
        except PermissionError:
            pending = OUTPUT_DIR / name.replace(".xlsx", "_pending.xlsx")
            frame.to_excel(pending, index=False)
            print(f"文件被占用，已写入临时结果：{pending}")

    # 按题目格式保存双工作表文件
    result2_file = OUTPUT_DIR / "result2.xlsx"
    try:
        with pd.ExcelWriter(result2_file) as writer:
            df_T.to_excel(writer, sheet_name="温度", index=False)
            df_C.to_excel(writer, sheet_name="水分浓度", index=False)
        print(f"题目正式结果已保存：{result2_file}")
    except PermissionError:
        pending = OUTPUT_DIR / "result2_pending.xlsx"
        with pd.ExcelWriter(pending) as writer:
            df_T.to_excel(writer, sheet_name="温度", index=False)
            df_C.to_excel(writer, sheet_name="水分浓度", index=False)
        print(f"文件被占用，已写入临时结果：{pending}")

    print(f"完整表时间：0～{int(round(t_end))} s，共 {len(t)} 行")
    print("摘要表时间：0.5、1.0、1.5、2.0、2.5、3.0 h")
    print(f"径向范围：0～{r[-1] * 100:g} cm，共 {len(r)} 个节点")
    return outputs, t, r, T, C


def plot_problem2_results(t, r, T, C):
    """绘制问题二温度、水分和热力图。"""
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    time_h = t / 3600.0
    target_r = [0.0, 0.5, 1.0, 1.5, 2.0]
    target_idx = [int(np.argmin(np.abs(r * 100.0 - value))) for value in target_r]

    plt.figure(figsize=(10, 6))
    for radius, idx in zip(target_r, target_idx):
        plt.plot(time_h, C[:, idx], label=f"r={radius:g} cm")
    plt.xlabel("时间 t (h)")
    plt.ylabel("水分浓度 C (kg/kg)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PIC_DIR / "q2_水分时间演化图.png", dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    for radius, idx in zip(target_r, target_idx):
        plt.plot(time_h, T[:, idx], label=f"r={radius:g} cm")
    plt.xlabel("时间 t (h)")
    plt.ylabel("温度 T (°C)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PIC_DIR / "q2_温度时间演化图.png", dpi=300)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    extent = [time_h[0], time_h[-1], r[0] * 100.0, r[-1] * 100.0]
    im0 = axes[0].imshow(T.T, origin="lower", aspect="auto", extent=extent, cmap="YlOrRd")
    axes[0].set_xlabel("时间 t (h)")
    axes[0].set_ylabel("半径 r (cm)")
    axes[0].set_title("温度时空分布")
    fig.colorbar(im0, ax=axes[0], label="温度 (°C)")
    im1 = axes[1].imshow(C.T, origin="lower", aspect="auto", extent=extent, cmap="Blues_r")
    axes[1].set_xlabel("时间 t (h)")
    axes[1].set_ylabel("半径 r (cm)")
    axes[1].set_title("水分时空分布")
    fig.colorbar(im1, ax=axes[1], label="水分浓度 (kg/kg)")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "q2_温度和水分热力图.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    _, t_result, r_result, T_result, C_result = save_problem2_results()
    plot_problem2_results(t_result, r_result, T_result, C_result)
    verify_initial_profile()
    verify_time_step()
    verify_space_step()
    verify_conservation()
    verify_physical_bounds()
    print("\n问题二全部数值检验完成。")
