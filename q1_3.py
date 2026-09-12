# 1. 时间步收敛  2. 空间步长收敛  3. 守恒检查
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'output_excel'
PIC_DIR = BASE_DIR / 'pic'

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei',
                                   'Arial Unicode MS', 'PingFang SC']
plt.rcParams['axes.unicode_minus'] = False


# 读取边界条件，返回 T_air(t), C_air(t)
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

# 求解 PDE，返回 t, r, T, C
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
    coef_p = 1.0 + dr / (2.0 * r_inner)   # r_{i+1/2}/r_i
    coef_m = 1.0 - dr / (2.0 * r_inner)   # r_{i-1/2}/r_i

    # 水分扩散系数
    def D_of_C(Cval):
        return 7e-9 * np.exp(-0.89 / np.clip(Cval, 1e-5, 10.0))

    stab_T = 4.0 * alpha * dt / dr**2
    if stab_T >= 1.0:
        print(f'  [!] dt={dt}, dr={dr} 时 4α·dt/dr² = {stab_T:.3f} >= 1，可能不稳定')

    for n in range(Nt - 1):
        T_air_next = float(T_air_func(t[n + 1]))
        C_air_next = float(C_air_func(t[n + 1]))

        # 温度：内部节点（不变）
        T[n + 1, 1:-1] = T[n, 1:-1] + alpha * dt / dr**2 * (
            coef_p * T[n, 2:] - 2.0 * T[n, 1:-1] + coef_m * T[n, :-2]
        )

        # 水分：内部节点（有限体积，D 用界面值）
        C_inner = C[n, 1:-1]
        C_left = C[n, :-2]
        C_right = C[n, 2:]
        D_L = D_of_C(0.5 * (C_left + C_inner))    # D_{i-1/2}
        D_R = D_of_C(0.5 * (C_inner + C_right))   # D_{i+1/2}
        C[n + 1, 1:-1] = C_inner + dt / dr**2 * (
            coef_p * D_R * (C_right - C_inner)
            + coef_m * D_L * (C_left - C_inner)
        )

        # 温度：中心节点（不变）
        T[n + 1, 0] = T[n, 0] + 4.0 * alpha * dt / dr**2 * (T[n, 1] - T[n, 0])

        # 水分：中心节点（D 用界面 D_{1/2}）
        D_01 = D_of_C(0.5 * (C[n, 0] + C[n, 1]))
        C[n + 1, 0] = C[n, 0] + 4.0 * D_01 * dt / dr**2 * (C[n, 1] - C[n, 0])

        # 温度：表面控制体
        i_s = Nr - 1
        V_factor = i_s - 0.25
        T[n + 1, -1] = T[n, -1] + dt * (
            2.0 * (i_s - 0.5) * k * (T[n, i_s - 1] - T[n, i_s])
            / (rho * Cp * V_factor * dr**2)
            + 2.0 * i_s * h * (T_air_next - T[n, i_s])
            / (rho * Cp * V_factor * dr)
        )

        # 水分：表面节点（有限体积，严格守恒）
        i_s = Nr - 1
        D_sm = D_of_C(0.5 * (C[n, i_s - 1] + C[n, i_s]))   # D_{N-3/2}
        V_factor = i_s - 0.25                                # 表面控制体体积 / (π dr²)
        C[n + 1, -1] = C[n, -1] + dt * (
            2.0 * (i_s - 0.5) * D_sm * (C[n, i_s - 1] - C[n, -1]) / (V_factor * dr**2)
            + 2.0 * i_s * hm * (C_air_next - C[n, -1]) / (V_factor * dr)
        )

    return t, r, T, C

# 验证1：时间步收敛
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

    # 共同时间点比较
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

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for dt in dt_list:
        t, r, T, C = results[dt]
        axes[0].plot(t, T[:, 0], label=f'dt={dt}s')
        axes[1].plot(t, C[:, -1], label=f'dt={dt}s')

    axes[0].set_xlabel('时间 t (s)')
    axes[0].set_ylabel('中心温度 T (°C)')
    axes[0].set_title('中心温度随时间变化（不同 dt）')
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].set_xlabel('时间 t (s)')
    axes[1].set_ylabel('表面水分 C')
    axes[1].set_title('表面水分随时间变化（不同 dt）')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    dt_err = np.array([0.5, 0.25])
    err_T = np.array([err_T_1_05, err_T_05_025])
    err_C = np.array([err_C_1_05, err_C_05_025])
    axes[2].loglog(dt_err, err_T, 'o-', label='温度误差')
    axes[2].loglog(dt_err, err_C, 's-', label='水分误差')
    axes[2].set_xlabel('dt (s)')
    axes[2].set_ylabel('最大绝对误差')
    axes[2].set_title('时间步收敛误差（log-log）')
    axes[2].legend()
    axes[2].grid(alpha=0.3, which='both')

    plt.tight_layout()
    plt.savefig(PIC_DIR / '验证_时间步收敛.png', dpi=300, bbox_inches='tight')
    plt.show()
    plt.close()


# 验证2：空间步长收敛
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

    # 共同半径点比较
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

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for dr in dr_list:
        t, r, T, C = results[dr]
        axes[0].plot(r * 100, T[-1, :], 'o-', label=f'dr={dr*1000:.2f}mm')
        axes[1].plot(r * 100, C[-1, :], 'o-', label=f'dr={dr*1000:.2f}mm')

    axes[0].set_xlabel('半径 r (cm)')
    axes[0].set_ylabel('最终温度 T (°C)')
    axes[0].set_title('最终温度沿半径分布（不同 dr）')
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].set_xlabel('半径 r (cm)')
    axes[1].set_ylabel('最终水分 C')
    axes[1].set_title('最终水分沿半径分布（不同 dr）')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    dr_err = np.array([0.0005, 0.00025])
    err_T = np.array([err_T_1_05, err_T_05_025])
    err_C = np.array([err_C_1_05, err_C_05_025])
    axes[2].loglog(dr_err, err_T, 'o-', label='温度误差')
    axes[2].loglog(dr_err, err_C, 's-', label='水分误差')
    axes[2].set_xlabel('dr (m)')
    axes[2].set_ylabel('最大绝对误差')
    axes[2].set_title('空间步长收敛误差（log-log）')
    axes[2].legend()
    axes[2].grid(alpha=0.3, which='both')

    plt.tight_layout()
    plt.savefig(PIC_DIR / '验证_空间步长收敛.png', dpi=300, bbox_inches='tight')
    plt.show()
    plt.close()


# 验证3：守恒检查
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

    # 总能量、总水分
    Q = np.sum(rho * Cp * T * V, axis=1)
    M = np.sum(C * V, axis=1)

    A_surf = 2.0 * np.pi * r_surf
    T_air_arr = np.array([float(T_func(tt)) for tt in t])
    C_air_arr = np.array([float(C_func(tt)) for tt in t])

    # 表面通量取 n+1 时刻环境值和 n 时刻表面值
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

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    axes[0].plot(t, Q_change, label='总能量变化')
    axes[0].plot(t, Q_flux_int, '--', label='边界热流积分')
    axes[0].set_xlabel('时间 t (s)')
    axes[0].set_ylabel('能量变化 (J/m)')
    axes[0].set_title('能量守恒检查')
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(t, M_change, label='总水分变化')
    axes[1].plot(t, M_flux_int, '--', label='边界质流积分')
    axes[1].set_xlabel('时间 t (s)')
    axes[1].set_ylabel('水分变化')
    axes[1].set_title('水分守恒检查')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    axes[2].plot(t, rel_err_Q, label='能量相对误差')
    axes[2].plot(t, rel_err_M, label='水分相对误差')
    axes[2].set_xlabel('时间 t (s)')
    axes[2].set_ylabel('相对误差')
    axes[2].set_title('守恒相对误差')
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(PIC_DIR / '验证_守恒检查.png', dpi=300, bbox_inches='tight')
    plt.show()
    plt.close()


if __name__ == '__main__':
    verify_time_step()
    verify_space_step()
    verify_conservation()
    print('\n全部验证完成，已生成 3 张图。')
