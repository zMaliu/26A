import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'output_excel'

# 读取边界数据
file_name = OUTPUT_DIR / 'output1.xlsx'
if not file_name.exists():
    raise FileNotFoundError(f"未找到边界文件：{file_name}，请先运行 q1_1.py")
df_input = pd.read_excel(file_name)
t_array = df_input.iloc[:, 0].values.astype(float)
T_air = df_input.iloc[:, 1].values.astype(float)
C_air = df_input.iloc[:, 2].values.astype(float)
if len(t_array) < 1801:
    raise ValueError("边界文件至少需要覆盖 0~1800 s")

# 物性参数
rho, Cp, k = 820.0, 2600.0, 0.36
h, hm = 25.0, 8e-7
alpha = k / (rho * Cp)
Nt, Nr = 1801, 21
dt, dr = 1.0, 0.001
r_grid = np.linspace(0, 2, Nr)

T_matrix, C_matrix = np.zeros((Nt, Nr)), np.zeros((Nt, Nr))
T_matrix[0, :] = 28.0
C_matrix[0, :] = 2.55

# 水分扩散系数
def D_of_C(C_val):
    C_val = np.clip(C_val, 1e-5, 10.0)
    return 7e-9 * np.exp(-0.89 / C_val)

# 界面扩散系数
def D_face(C_left, C_right):
    return D_of_C(0.5 * (C_left + C_right))

print("开始求解问题一...")

for n in range(0, Nt - 1):
    T_air_next, C_air_next = T_air[n+1], C_air[n+1]

    for i in range(1, Nr - 1):
        r_val = i * dr
        T_matrix[n+1, i] = T_matrix[n, i] + alpha * dt / (dr**2) * (
            (1 + dr/(2*r_val)) * T_matrix[n, i+1]
            - 2 * T_matrix[n, i]
            + (1 - dr/(2*r_val)) * T_matrix[n, i-1])

    T_matrix[n+1, 0] = T_matrix[n, 0] + 4 * alpha * dt / (dr**2) * (T_matrix[n, 1] - T_matrix[n, 0])

    # 表面温度
    i_s = Nr - 1
    V_factor = i_s - 0.25
    T_matrix[n+1, i_s] = T_matrix[n, i_s] + dt * (
        2 * (i_s - 0.5) * k * (T_matrix[n, i_s - 1] - T_matrix[n, i_s])
        / (rho * Cp * V_factor * dr**2)
        + 2 * i_s * h * (T_air_next - T_matrix[n, i_s])
        / (rho * Cp * V_factor * dr)
    )

    # 水分内部节点
    for i in range(1, Nr - 1):
        r_val = i * dr
        # 两侧界面系数
        D_L = D_face(C_matrix[n, i-1], C_matrix[n, i])
        D_R = D_face(C_matrix[n, i],   C_matrix[n, i+1])
        # 水分通量更新
        C_matrix[n+1, i] = C_matrix[n, i] + dt / (dr**2) * (
            (1 + dr/(2*r_val)) * D_R * (C_matrix[n, i+1] - C_matrix[n, i])
            + (1 - dr/(2*r_val)) * D_L * (C_matrix[n, i-1] - C_matrix[n, i]))

    # 水分中心节点
    D_01 = D_face(C_matrix[n, 0], C_matrix[n, 1])
    C_matrix[n+1, 0] = C_matrix[n, 0] + 4 * D_01 * dt / (dr**2) * (C_matrix[n, 1] - C_matrix[n, 0])

    # 水分表面节点
    i_s = Nr - 1
    D_sm = D_face(C_matrix[n, i_s-1], C_matrix[n, i_s])   # 表面界面系数
    V_factor = i_s - 0.25                                  # 表面控制体系数
    C_matrix[n+1, i_s] = C_matrix[n, i_s] + dt * (
        2 * (i_s - 0.5) * D_sm * (C_matrix[n, i_s-1] - C_matrix[n, i_s]) / (V_factor * dr**2)
        + 2 * i_s * hm * (C_air_next - C_matrix[n, i_s]) / (V_factor * dr)
    )

print("问题一求解完成")

# 整理完整结果
col_names = [f"{x:.1f}" for x in r_grid]
time_col = np.arange(0, 1801, 1)

df_q1_1 = pd.DataFrame(np.round(T_matrix, 4), columns=col_names)
df_q1_1.insert(0, '时间', time_col)

df_q1_2 = pd.DataFrame(np.round(C_matrix, 4), columns=col_names)
df_q1_2.insert(0, '时间', time_col)

# 提取指定时刻
target_times = [100, 300, 600, 900, 1200, 1500, 1800]
target_radii = ['0.0', '0.5', '1.0', '1.5', '2.0']

df_q1_3 = df_q1_1[df_q1_1['时间'].isin(target_times)][['时间'] + target_radii].reset_index(drop=True)
df_q1_4 = df_q1_2[df_q1_2['时间'].isin(target_times)][['时间'] + target_radii].reset_index(drop=True)

# 保存四个结果表
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
for name, frame in {
    'q1_1.xlsx': df_q1_1,
    'q1_2.xlsx': df_q1_2,
    'q1_3.xlsx': df_q1_3,
    'q1_4.xlsx': df_q1_4,
}.items():
    try:
        frame.to_excel(OUTPUT_DIR / name, index=False)
    except PermissionError:
        pending = OUTPUT_DIR / name.replace('.xlsx', '_pending.xlsx')
        frame.to_excel(pending, index=False)
        print(f'文件被占用，已写入临时结果：{pending}')

# 保存双工作表文件
result1_file = OUTPUT_DIR / 'result1.xlsx'
try:
    with pd.ExcelWriter(result1_file) as writer:
        df_q1_1.to_excel(writer, sheet_name='温度', index=False)
        df_q1_2.to_excel(writer, sheet_name='水分浓度', index=False)
    print(f'题目正式结果已保存：{result1_file}')
except PermissionError:
    pending = OUTPUT_DIR / 'result1_pending.xlsx'
    with pd.ExcelWriter(pending) as writer:
        df_q1_1.to_excel(writer, sheet_name='温度', index=False)
        df_q1_2.to_excel(writer, sheet_name='水分浓度', index=False)
    print(f'文件被占用，已写入临时结果：{pending}')

print("处理完成！已覆盖并生成 q1_1.xlsx, q1_2.xlsx, q1_3.xlsx, q1_4.xlsx")
print("结果图请运行 plot_condensed.py 统一生成。")
