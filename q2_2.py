"""生成问题二的 5500 s 初始剖面。"""

from pathlib import Path

import numpy as np
import pandas as pd

from q2_3 import OUTPUT_DIR, get_boundary_funcs, solve_pde


BASE_DIR = Path(__file__).resolve().parent
INITIAL_TIME = 0.0
TARGET_TIME = 5500.0
DT = 1.0
DR = 0.001
NR = 21
R_MAX = 0.02


def main():
    """用附录 3 变物性模型计算 5500 s 状态。"""
    boundary_file = OUTPUT_DIR / "output1.xlsx"
    if not boundary_file.exists():
        raise FileNotFoundError(f"未找到边界文件：{boundary_file}，请先运行 q1_1.py")

    T_func, C_func = get_boundary_funcs(path=boundary_file, t_start=INITIAL_TIME)
    t, r, T, C = solve_pde(
        dt=DT,
        dr=DR,
        r_max=R_MAX,
        t_end=TARGET_TIME,
        t_start=INITIAL_TIME,
        initial_file=None,
        initial_T=28.0,
        initial_C=2.55,
        T_air_func=T_func,
        C_air_func=C_func,
    )

    result = pd.DataFrame({
        "半径 r (cm)": r * 100.0,
        "温度 T (°C)": np.round(T[-1], 4),
        "水分浓度 C (kg/kg)": np.round(C[-1], 4),
    })
    out_file = OUTPUT_DIR / "output3.xlsx"
    result.to_excel(out_file, index=False)
    print(f"5500 s 初始剖面已保存：{out_file}")
    print(result.to_string(index=False))
    return out_file, t, r, T, C


if __name__ == "__main__":
    main()
