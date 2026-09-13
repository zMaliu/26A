# 问题四变半径模型

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

from q3 import get_full_boundary_funcs


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input_excel"
OUTPUT_DIR = BASE_DIR / "output_excel"
RADIUS_FILE = INPUT_DIR / "附件2.xlsx"
if not RADIUS_FILE.exists():
    RADIUS_FILE = BASE_DIR / "附件" / "附件2.xlsx"

MOISTURE_LIMIT = 0.15
DT = 60.0
DX = 0.05
R0 = 0.02
MAX_TIME = 259200.0
R_MIN = 0.05
R_MAX = 10.0
T_MIN = -50.0
T_MAX = 250.0


def load_radius_data(path=RADIUS_FILE):
    # 读取半径数据
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"未找到半径文件：{path}")
    df = pd.read_excel(path)
    if df.shape[1] < 2:
        raise ValueError("附件2至少需要时间和半径两列")
    t = df.iloc[:, 0].to_numpy(dtype=float)
    radius_cm = df.iloc[:, 1].to_numpy(dtype=float)
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(radius_cm))):
        raise ValueError("附件2含有NaN或无穷值")
    if np.any(np.diff(t) <= 0) or np.any(radius_cm <= 0):
        raise ValueError("附件2时间须递增且半径须为正")
    if t[0] > 1e-12 or t[-1] < MAX_TIME - 1e-12:
        raise ValueError("附件2必须覆盖0~259200 s")
    if np.any(np.diff(radius_cm) > 1e-10):
        raise ValueError("附件2半径应单调不增")
    return t, radius_cm / 100.0


def interpolate_radius(dt=DT, t_end=MAX_TIME, path=RADIUS_FILE):
    # PCHIP插值
    t_raw, r_raw = load_radius_data(path)
    if dt <= 0 or t_end < 0:
        raise ValueError("时间参数必须为正")
    n = int(round(t_end / dt))
    t = np.arange(n + 1, dtype=float) * dt
    if t[-1] > t_raw[-1] + 1e-9:
        raise ValueError("插值终点超过附件2范围")
    pchip = PchipInterpolator(t_raw, r_raw)
    r = np.asarray(pchip(t), dtype=float)
    # 修正浮点误差
    r = np.minimum.accumulate(r)
    if np.any(r <= 0):
        raise ValueError("插值后出现非正半径")
    return t, r, t_raw, r_raw


def save_radius_interpolation():
    # 保存半径插值
    t, r, t_raw, r_raw = interpolate_radius()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"时间/s": t.astype(int), "半径/m": r, "半径/cm": r * 100.0}).to_excel(
        OUTPUT_DIR / "q4_radius_interp.xlsx", index=False
    )
    return t, r


# 附录4物性公式
def rho_of_C(C):
    return 760.0 + 90.0 * C


def cp_of_C(C):
    C_safe = np.maximum(C, 1e-8)
    return 1850.0 + 2150.0 * C_safe / (C_safe + 1.0)


def k_of_C(C):
    C_safe = np.maximum(C, 1e-8)
    return 0.12 + 0.20 * C_safe / (C_safe + 1.0)


def D_of_CT(C, T):
    C_safe = np.clip(C, 0.05, 10.0)
    T_K = np.clip(T + 273.15, 273.15, 373.15)
    D = 4.2e-4 * np.exp(-0.30 / C_safe) * np.exp(-3850.0 / T_K)
    return np.clip(D, 1e-14, 1e-3)


def solve_tridiag(a, b, c, d):
    # 追赶法
    n = len(b)
    if n == 0:
        return np.empty(0)
    cp = np.zeros(n)
    dp = np.zeros(n)
    if abs(b[0]) < 1e-14:
        raise ZeroDivisionError("三对角矩阵首行奇异")
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        den = b[i] - a[i] * cp[i - 1]
        if abs(den) < 1e-14:
            raise ZeroDivisionError(f"三对角矩阵第{i}行奇异")
        if i < n - 1:
            cp[i] = c[i] / den
        dp[i] = (d[i] - a[i] * dp[i - 1]) / den
    x = np.zeros(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def _assemble_scalar(old, coeff, storage, radius, dt, dx,
                     boundary_value, boundary_coeff):
    # 组装隐式方程
    nr = len(old)
    x = np.linspace(0.0, 1.0, nr)
    w = np.zeros(nr)
    w[0] = (dx / 2.0) ** 2
    w[1:-1] = 2.0 * x[1:-1] * dx
    w[-1] = 1.0 - (1.0 - dx / 2.0) ** 2
    a = np.zeros(nr)
    b = np.ones(nr)
    c = np.zeros(nr)
    d = old.copy()
    # 内部扩散通量
    face_x = (np.arange(nr - 1) + 0.5) * dx
    for f in range(nr - 1):
        xi_face = face_x[f]
        left, right = f, f + 1
        # 相邻控制体共用通量
        g_left = 2.0 * dt * xi_face * coeff[f] / (radius**2 * storage[left] * w[left] * dx)
        g_right = 2.0 * dt * xi_face * coeff[f] / (radius**2 * storage[right] * w[right] * dx)
        c[left] -= g_left
        b[left] += g_left
        a[right] -= g_right
        b[right] += g_right
    # 表面对流项
    g_conv = 2.0 * dt * boundary_coeff / (radius * storage[-1] * w[-1])
    b[-1] += g_conv
    d[-1] += g_conv * boundary_value
    return a, b, c, d


def solve_problem4(dt=DT, dx=DX, t_end=MAX_TIME, stop_at_threshold=True):
    # 求解变半径全过程
    if dt <= 0 or dx <= 0 or t_end < 0:
        raise ValueError("时间和空间步长必须为正")
    n_interval = int(round(1.0 / dx))
    if not np.isclose(n_interval * dx, 1.0, atol=1e-12, rtol=0.0):
        raise ValueError("dx 必须能整除无量纲区间 [0,1]")
    nr = n_interval + 1
    x = np.linspace(0.0, 1.0, nr)
    t, radius, _, _ = interpolate_radius(dt=dt, t_end=t_end)
    T_air_func, C_air_func = get_full_boundary_funcs()
    T = np.zeros((len(t), nr))
    C = np.zeros((len(t), nr))
    T[0, :] = 28.0
    C[0, :] = 2.55
    max_C = np.zeros(len(t))
    max_C[0] = np.max(C[0])
    hit = None

    for n in range(len(t) - 1):
        Rnext = radius[n + 1]
        T_air = float(T_air_func(t[n + 1]))
        C_air = float(C_air_func(t[n + 1]))
        C_mid = 0.5 * (C[n, :-1] + C[n, 1:])
        T_mid = 0.5 * (T[n, :-1] + T[n, 1:])
        k_face = k_of_C(C_mid)
        D_face = D_of_CT(C_mid, T_mid)
        H = rho_of_C(C[n]) * cp_of_C(C[n])

        aT, bT, cT, dT = _assemble_scalar(
            T[n], k_face, H, Rnext, dt, dx, T_air, 25.0,
        )
        # 温度存储量
        T[n + 1] = solve_tridiag(aT, bT, cT, dT)

        aC, bC, cC, dC = _assemble_scalar(
            C[n], D_face, np.ones(nr), Rnext, dt, dx, C_air, 8.0e-7,
        )
        C[n + 1] = solve_tridiag(aC, bC, cC, dC)
        T[n + 1] = np.clip(T[n + 1], T_MIN, T_MAX)
        C[n + 1] = np.clip(C[n + 1], 0.0, R_MAX)
        max_C[n + 1] = np.max(C[n + 1])
        if hit is None and max_C[n + 1] <= MOISTURE_LIMIT:
            hit = n + 1
            if stop_at_threshold:
                break

    n_used = len(t) if (hit is None or not stop_at_threshold) else hit + 1
    t = t[:n_used]
    radius = radius[:n_used]
    T = T[:n_used]
    C = C[:n_used]
    max_C = max_C[:n_used]
    drying_time = None
    if hit is not None:
        if hit == 0:
            drying_time = 0.0
        else:
            drying_time = float(
                t[hit - 1] + (MOISTURE_LIMIT - max_C[hit - 1])
                * (t[hit] - t[hit - 1]) / (max_C[hit] - max_C[hit - 1])
            )
    return t, radius, x, T, C, max_C, drying_time


def _append_interpolated_end(t, radius, T, C, max_C, drying_time):
    # 追加插值结束行
    if drying_time is None or drying_time >= t[-1] - 1e-12:
        return t, radius, T, C, max_C
    j = len(t) - 1
    t0, t1 = t[j - 1], t[j]
    f = (drying_time - t0) / (t1 - t0)
    t = np.append(t[:-1], drying_time)
    radius = np.append(radius[:-1], radius[j - 1] + f * (radius[j] - radius[j - 1]))
    T = np.vstack([T[:-1], T[j - 1] + f * (T[j] - T[j - 1])])
    C = np.vstack([C[:-1], C[j - 1] + f * (C[j] - C[j - 1])])
    max_C = np.append(max_C[:-1], np.max(C[-1]))
    return t, radius, T, C, max_C


def _physical_table(t, radius, x, C):
    # 输出物理半径网格
    target_cm = np.round(np.arange(0.0, 2.0 + 1e-12, 0.1), 1)
    rows = []
    for n, time in enumerate(t):
        row = {"时间/s": round(float(time), 2)}
        r_cm = radius[n] * 100.0
        r_nodes = x * radius[n] * 100.0
        for p in target_cm:
            key = f"{p:.1f}"
            row[key] = round(float(np.interp(p, r_nodes, C[n])), 4) if p <= r_cm + 1e-10 else None
        row["药材表面"] = round(float(C[n, -1]), 4)
        row["半径/cm"] = round(float(r_cm), 4)
        rows.append(row)
    return pd.DataFrame(rows, columns=["时间/s"] + [f"{p:.1f}" for p in target_cm] + ["药材表面", "半径/cm"])


def _summary_table(t, radius, x, C, drying_time):
    # 生成表6摘要
    regular = np.arange(6.0, np.floor(t[-1] / 21600.0) * 6.0 + 1e-12, 6.0) * 3600.0
    targets = list(regular)
    if drying_time is not None and (not targets or drying_time > targets[-1] + 1e-8):
        targets.append(drying_time)
    target_cm = [round(v, 1) for v in np.arange(0.0, 2.0 + 1e-12, 0.5)]
    rows = []
    for target in targets:
        idx = int(np.argmin(np.abs(t - target)))
        r_cm = radius[idx] * 100.0
        r_nodes = x * radius[idx] * 100.0
        row = {"时间/h": round(float(t[idx] / 3600.0), 4), "半径/cm": round(float(r_cm), 4)}
        for p in target_cm:
            row[f"{p:.1f}"] = round(float(np.interp(p, r_nodes, C[idx])), 4) if p <= r_cm + 1e-10 else None
        row["药材表面"] = round(float(C[idx, -1]), 4)
        rows.append(row)
    cols = ["时间/h"] + [f"{p:.1f}" for p in target_cm] + ["药材表面", "半径/cm"]
    return pd.DataFrame(rows, columns=cols)


def save_results():
    # 保存第四问结果
    t, radius, x, T, C, max_C, drying_time = solve_problem4()
    t, radius, T, C, max_C = _append_interpolated_end(t, radius, T, C, max_C, drying_time)
    full = _physical_table(t, radius, x, C)
    summary = _summary_table(t, radius, x, C, drying_time)
    normalized = pd.DataFrame(np.round(C, 4), columns=[f"xi={v:.2f}" for v in x])
    normalized.insert(0, "时间/s", np.round(t, 2))
    normalized["半径/cm"] = np.round(radius * 100.0, 4)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT_DIR / "result4.xlsx") as writer:
        full.to_excel(writer, sheet_name="水分浓度", index=False)
        summary.to_excel(writer, sheet_name="表6摘要", index=False)
        normalized.to_excel(writer, sheet_name="无量纲网格", index=False)
        pd.DataFrame({"时间/s": np.round(t, 2), "半径/cm": np.round(radius * 100.0, 6)}).to_excel(
            writer, sheet_name="半径插值", index=False
        )
    # 保存表6格式
    q4_1 = summary[["时间/h", "0.0", "0.5", "1.0", "1.5", "药材表面"]].copy()
    q4_1.to_excel(OUTPUT_DIR / "q4_1.xlsx", index=False)
    _plot_results(t, radius, x, C, max_C, drying_time)
    print(f"第四问结果已保存：{OUTPUT_DIR / 'result4.xlsx'}")
    print(f"表6结果已保存：{OUTPUT_DIR / 'q4_1.xlsx'}")
    if drying_time is None:
        print("最大计算时长内未达到水分阈值")
    else:
        print(f"第四问烘干时间：{drying_time:.4f} s = {drying_time / 3600.0:.5f} h")
    return t, radius, x, T, C, max_C, drying_time


def _plot_results(t, radius, x, C, max_C, drying_time):
    # 结果图统一由 plot_condensed.py 生成
    return None


def validate_q4():
    # 校验第四问
    result = solve_problem4(stop_at_threshold=False)
    t, radius, x, T, C, max_C, drying_time = result
    if not (np.all(np.isfinite(T)) and np.all(np.isfinite(C)) and np.all(C >= -1e-12)):
        raise AssertionError("第四问出现非有限值或负水分")
    if np.any(np.diff(radius) > 1e-12):
        raise AssertionError("第四问半径未保持单调不增")
    # 检查半径和水分浓度趋势
    stable_idx = np.searchsorted(t, 5500.0)
    if np.any(np.diff(max_C[stable_idx:]) > 1e-7):
        raise AssertionError("第四问恒温段全域最大水分浓度不单调")
    if drying_time is None:
        hit = np.flatnonzero(max_C <= MOISTURE_LIMIT)
        if len(hit):
            raise AssertionError("第四问阈值时间记录异常")
    # 检查材料坐标守恒
    dt = float(t[1] - t[0]) if len(t) > 1 else DT
    w = np.zeros(len(x))
    w[0] = (DX / 2.0) ** 2
    w[1:-1] = 2.0 * x[1:-1] * DX
    w[-1] = 1.0 - (1.0 - DX / 2.0) ** 2
    _, C_air = get_full_boundary_funcs()
    air = np.asarray(C_air(t[1:]), dtype=float)
    flux = 2.0 * dt * 8.0e-7 / radius[1:] * (air - C[1:, -1])
    mass_res = float(np.max(np.abs(np.sum((C[1:] - C[:-1]) * w, axis=1) - flux)))
    if mass_res > 1e-10:
        raise AssertionError(f"第四问水分守恒残差过大：{mass_res:.3e}")
    return {"time_end_s": float(t[-1]), "radius_start_cm": float(radius[0] * 100),
            "radius_end_cm": float(radius[-1] * 100), "C_min": float(C.min()),
            "C_max": float(C.max()), "drying_time_s": drying_time,
            "moisture_balance_abs": mass_res}


if __name__ == "__main__":
    save_radius_interpolation()
    save_results()
