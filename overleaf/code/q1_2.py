import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'output_excel'
PIC_DIR = BASE_DIR / 'pic'

# 读取输入数据：第一列时间，第二列环境温度T_air，第三列环境湿度C_air
file_name = OUTPUT_DIR / 'output1.xlsx'
if not file_name.exists():
    raise FileNotFoundError(f"未找到边界文件：{file_name}，请先运行 q1_1.py")
df_input = pd.read_excel(file_name)
t_array = df_input.iloc[:, 0].values.astype(float)
T_air = df_input.iloc[:, 1].values.astype(float)
C_air = df_input.iloc[:, 2].values.astype(float)
if len(t_array) < 1801:
    raise ValueError("边界文件至少需要覆盖 0~1800 s")

# 物理参数
rho, Cp, k = 820.0, 2600.0, 0.36
h, hm = 25.0, 8e-7
alpha = k / (rho * Cp)
Nt, Nr = 1801, 21
dt, dr = 1.0, 0.001
r_grid = np.linspace(0, 2, Nr)

T_matrix, C_matrix = np.zeros((Nt, Nr)), np.zeros((Nt, Nr))
T_matrix[0, :] = 28.0
C_matrix[0, :] = 2.55

# 水分扩散系数函数
def D_of_C(C_val):
    C_val = np.clip(C_val, 1e-5, 10.0)
    return 7e-9 * np.exp(-0.89 / C_val)

# 界面扩散系数：用左右节点 C 的算术平均求 D
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

    # 表面温度：控制体内导热与外部对流
    i_s = Nr - 1
    V_factor = i_s - 0.25
    T_matrix[n+1, i_s] = T_matrix[n, i_s] + dt * (
        2 * (i_s - 0.5) * k * (T_matrix[n, i_s - 1] - T_matrix[n, i_s])
        / (rho * Cp * V_factor * dr**2)
        + 2 * i_s * h * (T_air_next - T_matrix[n, i_s])
        / (rho * Cp * V_factor * dr)
    )

    # 内部节点 i = 1 ... Nr-2
    for i in range(1, Nr - 1):
        r_val = i * dr
        # 左界面 D_{i-1/2}，右界面 D_{i+1/2}
        D_L = D_face(C_matrix[n, i-1], C_matrix[n, i])
        D_R = D_face(C_matrix[n, i],   C_matrix[n, i+1])
        # 通量形式：dC/dt = [ (i+0.5)/i * D_R*(C_{i+1}-C_i) + (i-0.5)/i * D_L*(C_{i-1}-C_i) ] / dr²
        C_matrix[n+1, i] = C_matrix[n, i] + dt / (dr**2) * (
            (1 + dr/(2*r_val)) * D_R * (C_matrix[n, i+1] - C_matrix[n, i])
            + (1 - dr/(2*r_val)) * D_L * (C_matrix[n, i-1] - C_matrix[n, i]))

    # 中心节点 i = 0：D 用界面 D_{1/2}
    D_01 = D_face(C_matrix[n, 0], C_matrix[n, 1])
    C_matrix[n+1, 0] = C_matrix[n, 0] + 4 * D_01 * dt / (dr**2) * (C_matrix[n, 1] - C_matrix[n, 0])

    # 表面节点：有限体积
    i_s = Nr - 1
    D_sm = D_face(C_matrix[n, i_s-1], C_matrix[n, i_s])   # 界面 D_{N-3/2}
    V_factor = i_s - 0.25                                  # 表面控制体体积 / (π dr²)
    C_matrix[n+1, i_s] = C_matrix[n, i_s] + dt * (
        2 * (i_s - 0.5) * D_sm * (C_matrix[n, i_s-1] - C_matrix[n, i_s]) / (V_factor * dr**2)
        + 2 * i_s * hm * (C_air_next - C_matrix[n, i_s]) / (V_factor * dr)
    )

print("问题一求解完成")

# 构建完整输出DataFrame
col_names = [f"{x:.1f}" for x in r_grid]
time_col = np.arange(0, 1801, 1)

df_q1_1 = pd.DataFrame(np.round(T_matrix, 4), columns=col_names)
df_q1_1.insert(0, '时间', time_col)

df_q1_2 = pd.DataFrame(np.round(C_matrix, 4), columns=col_names)
df_q1_2.insert(0, '时间', time_col)

# 提取特定时间及半径切片数据
target_times = [100, 300, 600, 900, 1200, 1500, 1800]
target_radii = ['0.0', '0.5', '1.0', '1.5', '2.0']

df_q1_3 = df_q1_1[df_q1_1['时间'].isin(target_times)][['时间'] + target_radii].reset_index(drop=True)
df_q1_4 = df_q1_2[df_q1_2['时间'].isin(target_times)][['时间'] + target_radii].reset_index(drop=True)

# 覆盖并保存四个Excel文件
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

# 按题目格式保存双工作表文件
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

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'PingFang SC']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题

# 读取数据
df_T = pd.read_excel(OUTPUT_DIR / 'q1_1.xlsx')
df_C = pd.read_excel(OUTPUT_DIR / 'q1_2.xlsx')

time = df_T['时间'].values
radii = df_T.columns[1:].astype(float).values

# 空间分布图（水分浓度）
plt.figure(figsize=(10, 6))
target_radii = [0.0, 0.5, 1.0, 1.5, 2.0]
for r in target_radii:
    plt.plot(time, df_C[f'{r:.1f}'].values, label=f'r = {r} cm')
plt.xlabel('时间 t (s)', fontsize=12)
plt.ylabel('水分浓度 C (kg/kg)', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
PIC_DIR.mkdir(parents=True, exist_ok=True)
plt.savefig(PIC_DIR / '1_水分时间演化图.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close()

# 时间演化图（温度）
plt.figure(figsize=(10, 6))
target_radii = [0.0, 0.5, 1.0, 1.5, 2.0]
for r in target_radii:
    plt.plot(time, df_T[f'{r:.1f}'].values, label=f'r = {r} cm')
plt.xlabel('时间 t (s)', fontsize=12)
plt.ylabel('温度 T (°C)', fontsize=12)
# plt.title('不同半径位置药材温度随烘干时间的变化', fontsize=14)
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig(PIC_DIR / '2_温度时间演化图.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close()

# 二维热力图（温度与水分）
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# 温度热力图 温度随时间与空间的二维分布
sns.heatmap(df_T.iloc[:, 1:].T, cmap='YlOrRd', cbar_kws={'label': '温度 (°C)'}, ax=axes[0],
            yticklabels=np.round(radii, 1))
axes[0].set_xlabel('时间 t (s)')
axes[0].set_ylabel('半径 r (cm)')
axes[0].set_xticks(np.linspace(0, 1800, 7))
axes[0].set_xticklabels([int(x) for x in np.linspace(0, 1800, 7)])

# 水分热力图
sns.heatmap(df_C.iloc[:, 1:].T, cmap='Blues_r', cbar_kws={'label': '水分浓度 (kg/kg)'}, ax=axes[1],
            yticklabels=np.round(radii, 1))
axes[1].set_xlabel('时间 t (s)')
axes[1].set_ylabel('半径 r (cm)')
axes[1].set_xticks(np.linspace(0, 1800, 7))
axes[1].set_xticklabels([int(x) for x in np.linspace(0, 1800, 7)])

plt.tight_layout()
plt.savefig(PIC_DIR / '3_温度和水分热力图.png', dpi=300, bbox_inches='tight')
plt.show()
plt.close()

print("图表已生成并保存到当前文件夹！")
