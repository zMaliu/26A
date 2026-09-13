# 时间步、空间步和守恒检验
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'output_excel'


# 读取边界函数
def get_boundary_funcs():
    path = OUTPUT_DIR / 'output1.xlsx'
    df = pd.read_excel(path)
    t_orig = df.iloc[:, 0].values.astype(float)
    T_orig = df.iloc[:, 1].values.astype(float)
    C_orig = df.iloc[:, 2].values.astype(float)
    if np.any(np.diff(t_orig) <= 0):
        raise ValueError('output1.xlsx 时间必须严格递增')
    T_func = PchipInterpolator(t_orig, T_orig, extrapolate=False)
    C_func = PchipInterpolator(t_orig, C_orig, extrapolate=False)
    print(f'已读取 {path} 作为边界条件')
    return T_func, C_func

# 求解温度和水分
def solve_pde(dt, dr, r_max=0.02, t_end=1800.0,
              T_air_func=None, C_air_func=None):
    if T_air_func is None or C_air_func is None:
        T_air_func, C_air_func = get_boundary_funcs()

    rho, Cp, k = 820.0, 2600.0, 0.36
    h, hm = 25.0, 8e-7
    alpha = k / (rho * Cp)

    Nr = int(round(r_max / dr)) + 1
    Nt = int(round(t_end / dt)) + 1

    r = np.linspace(0, r_max, Nr)
    t = np.linspace(0, t_end, Nt)

    T = np.zeros((Nt, Nr))
    C = np.zeros((Nt, Nr))
    T[0, :] = 28.0
    C[0, :] = 2.55

    r_inner = r[1:-1]
    coef_p = 1.0 + dr / (2.0 * r_inner)   # 外侧几何系数
    coef_m = 1.0 - dr / (2.0 * r_inner)   # 内侧几何系数

    # 水分扩散系数
    def D_of_C(Cval):
        return 7e-9 * np.exp(-0.89 / np.clip(Cval, 1e-5, 10.0))

    stab_T = 4.0 * alpha * dt / dr**2
    if stab_T >= 1.0:
        print(f'  [!] dt={dt}, dr={dr} 时 4*alpha*dt/dr^2 = {stab_T:.3f} >= 1，可能不稳定')

    for n in range(Nt - 1):
        T_air_next = float(T_air_func(t[n + 1]))
        C_air_next = float(C_air_func(t[n + 1]))

        # 温度内部节点
        T[n + 1, 1:-1] = T[n, 1:-1] + alpha * dt / dr**2 * (
            coef_p * T[n, 2:] - 2.0 * T[n, 1:-1] + coef_m * T[n, :-2]
        )

        # 水分内部节点
        C_inner = C[n, 1:-1]
        C_left = C[n, :-2]
        C_right = C[n, 2:]
        D_L = D_of_C(0.5 * (C_left + C_inner))    # 左界面系数
        D_R = D_of_C(0.5 * (C_inner + C_right))   # 右界面系数
        C[n + 1, 1:-1] = C_inner + dt / dr**2 * (
            coef_p * D_R * (C_right - C_inner)
            + coef_m * D_L * (C_left - C_inner)
        )

        # 温度中心节点
        T[n + 1, 0] = T[n, 0] + 4.0 * alpha * dt / dr**2 * (T[n, 1] - T[n, 0])

        # 水分中心节点
        D_01 = D_of_C(0.5 * (C[n, 0] + C[n, 1]))
        C[n + 1, 0] = C[n, 0] + 4.0 * D_01 * dt / dr**2 * (C[n, 1] - C[n, 0])

        # 温度表面节点
        i_s = Nr - 1
        V_factor = i_s - 0.25
        T[n + 1, -1] = T[n, -1] + dt * (
            2.0 * (i_s - 0.5) * k * (T[n, i_s - 1] - T[n, i_s])
            / (rho * Cp * V_factor * dr**2)
            + 2.0 * i_s * h * (T_air_next - T[n, i_s])
            / (rho * Cp * V_factor * dr)
        )

        # 水分表面节点
        i_s = Nr - 1
        D_sm = D_of_C(0.5 * (C[n, i_s - 1] + C[n, i_s]))   # 表面界面系数
        V_factor = i_s - 0.25                                # 表面控制体系数
        C[n + 1, -1] = C[n, -1] + dt * (
            2.0 * (i_s - 0.5) * D_sm * (C[n, i_s - 1] - C[n, -1]) / (V_factor * dr**2)
            + 2.0 * i_s * hm * (C_air_next - C[n, -1]) / (V_factor * dr)
        )

    return t, r, T, C

# 时间步收敛
def verify_time_step():
    print('\n时间步收敛验证')

    T_func, C_func = get_boundary_funcs()
    dr = 0.001
    dt_list = [1.0, 0.5, 0.25]
    results = {}

    for dt in dt_list:
        print(f'  求解 dt = {dt} s ...')
        t, r, T, C = solve_pde(dt, dr, T_air_func=T_func, C_air_func=C_func)
        results[dt] = (t, r, T, C)

    # 比较共同时间点
    common_t = np.arange(0, 1801, 100)
    T_common, C_common = {}, {}
    for dt in dt_list:
        t, r, T, C = results[dt]
        idx = np.round(common_t / dt).astype(int)
        T_common[dt] = T[idx, :]
        C_common[dt] = C[idx, :]

    err_T_1_05 = np.max(np.abs(T_common[1.0] - T_common[0.5]))
    err_T_05_025 = np.max(np.abs(T_common[0.5] - T_common[0.25]))
    err_C_1_05 = np.max(np.abs(C_common[1.0] - C_common[0.5]))
    err_C_05_025 = np.max(np.abs(C_common[0.5] - C_common[0.25]))

    print('\n误差结果：')
    print(f'  温度 dt=1.0 vs 0.5   : {err_T_1_05:.6f} °C')
    print(f'  温度 dt=0.5 vs 0.25  : {err_T_05_025:.6f} °C')
    print(f'  水分 dt=1.0 vs 0.5   : {err_C_1_05:.6f}')
    print(f'  水分 dt=0.5 vs 0.25  : {err_C_05_025:.6f}')
    print('\n判断标准：')
    print('  1) 第二次误差应小于第一次')
    print('  2) 收敛比应接近 0.5（一阶）')
    print(f'     温度收敛比 = {err_T_05_025/err_T_1_05:.3f}')
    print(f'     水分收敛比 = {err_C_05_025/err_C_1_05:.3f}')
    print('  3) 温度误差 < 0.1°C，水分误差 < 0.01')
    ratio_T = err_T_05_025 / err_T_1_05
    ratio_C = err_C_05_025 / err_C_1_05
    if not (err_T_05_025 < err_T_1_05 and err_C_05_025 < err_C_1_05
            and 0.35 < ratio_T < 0.65 and 0.35 < ratio_C < 0.65
            and err_T_1_05 < 0.1 and err_C_1_05 < 0.01):
        raise AssertionError('问题一时间步收敛未通过')

# 空间步收敛
def verify_space_step():
    print('\n空间步长收敛验证')

    T_func, C_func = get_boundary_funcs()
    dt = 0.05
    dr_list = [0.001, 0.0005, 0.00025]
    results = {}

    for dr in dr_list:
        print(f'  求解 dr = {dr} m ...')
        t, r, T, C = solve_pde(dt, dr, T_air_func=T_func, C_air_func=C_func)
        results[dr] = (t, r, T, C)

    # 比较共同半径点
    common_r = np.array([0.0, 0.005, 0.01, 0.015, 0.02])
    T_final, C_final = {}, {}
    for dr in dr_list:
        t, r, T, C = results[dr]
        T_final[dr] = np.interp(common_r, r, T[-1, :])
        C_final[dr] = np.interp(common_r, r, C[-1, :])

    err_T_1_05 = np.max(np.abs(T_final[0.001] - T_final[0.0005]))
    err_T_05_025 = np.max(np.abs(T_final[0.0005] - T_final[0.00025]))
    err_C_1_05 = np.max(np.abs(C_final[0.001] - C_final[0.0005]))
    err_C_05_025 = np.max(np.abs(C_final[0.0005] - C_final[0.00025]))

    print('\n误差结果：')
    print(f'  温度 dr=1mm vs 0.5mm    : {err_T_1_05:.6f} °C')
    print(f'  温度 dr=0.5mm vs 0.25mm : {err_T_05_025:.6f} °C')
    print(f'  水分 dr=1mm vs 0.5mm    : {err_C_1_05:.6f}')
    print(f'  水分 dr=0.5mm vs 0.25mm : {err_C_05_025:.6f}')
    print('\n判断标准：')
    print('  1) 第二次误差应小于第一次')
    print('  2) 收敛比应接近 0.25（二阶）')
    print(f'     温度收敛比 = {err_T_05_025/err_T_1_05:.3f}')
    print(f'     水分收敛比 = {err_C_05_025/err_C_1_05:.3f}')
    print('  3) 温度差异 < 0.05°C，水分差异 < 0.005')
    ratio_T = err_T_05_025 / err_T_1_05
    ratio_C = err_C_05_025 / err_C_1_05
    if not (err_T_05_025 < err_T_1_05 and err_C_05_025 < err_C_1_05
            and 0.15 < ratio_T < 0.35 and 0.15 < ratio_C < 0.35
            and err_T_1_05 < 0.05 and err_C_1_05 < 0.005):
        raise AssertionError('问题一空间步收敛未通过')

# 守恒检验
def verify_conservation():
    print('\n守恒检查')

    T_func, C_func = get_boundary_funcs()
    dt = 1.0
    dr = 0.001
    r_max = 0.02
    t_end = 1800.0

    t, r, T, C = solve_pde(dt, dr, r_max, t_end, T_func, C_func)
    Nt, Nr = T.shape

    rho, Cp = 820.0, 2600.0
    h, hm = 25.0, 8e-7

    # 控制体体积
    V = np.zeros(Nr)
    V[0] = np.pi * (dr / 2.0)**2
    for i in range(1, Nr - 1):
        V[i] = 2.0 * np.pi * (i * dr) * dr
    r_surf = (Nr - 1) * dr
    V[-1] = np.pi * (r_surf**2 - (r_surf - dr / 2.0)**2)

    # 总能量和总水分
    Q = np.sum(rho * Cp * T * V, axis=1)
    M = np.sum(C * V, axis=1)

    A_surf = 2.0 * np.pi * r_surf
    T_air_arr = np.array([float(T_func(tt)) for tt in t])
    C_air_arr = np.array([float(C_func(tt)) for tt in t])

    # 计算表面通量
    q_step = h * A_surf * (T_air_arr[1:] - T[:-1, -1])
    m_step = hm * A_surf * (C_air_arr[1:] - C[:-1, -1])
    Q_flux_int = np.concatenate([[0.0], np.cumsum(q_step * dt)])
    M_flux_int = np.concatenate([[0.0], np.cumsum(m_step * dt)])

    Q_change = Q - Q[0]
    M_change = M - M[0]

    eps = 1e-12
    rel_err_Q = np.abs(Q_change - Q_flux_int) / np.maximum(np.abs(Q_change), eps)
    rel_err_M = np.abs(M_change - M_flux_int) / np.maximum(np.abs(M_change), eps)

    print('\n误差结果：')
    print(f'  最终能量守恒相对误差 : {rel_err_Q[-1]:.4%}')
    print(f'  最终水分守恒相对误差 : {rel_err_M[-1]:.4%}')
    print('\n判断标准：')
    print('  1) 两条累积曲线应基本重合')
    print('  2) 相对误差应 < 1%~5%')
    print('  3) 若误差快速累积，检查边界离散或体积权重')
    if rel_err_Q[-1] >= 0.01 or rel_err_M[-1] >= 0.01:
        raise AssertionError('问题一守恒检验未通过')

if __name__ == '__main__':
    verify_time_step()
    verify_space_step()
    verify_conservation()
    print('\n全部验证完成。结果图请运行 plot_condensed.py，验证图请运行 validate_all.py。')
