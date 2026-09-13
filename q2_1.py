# 问题二边界识别
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = Path(__file__).resolve().parent
input_path = BASE_DIR / 'output_excel' / 'output1.xlsx'
output_path = BASE_DIR / 'output_excel' / 'output2.xlsx'
plot_path = BASE_DIR / 'pic' / '验证_稳定时间.png'

# 读取边界数据
try:
    df = pd.read_excel(input_path)
except FileNotFoundError:
    print(f"未找到文件: {input_path}")
    exit()

t = df.iloc[:, 0].to_numpy()
T = df.iloc[:, 1].to_numpy()
C = df.iloc[:, 2].to_numpy()

# 计算稳定值
tail_n = min(1000, len(T) // 10)
if tail_n < 10:
    tail_n = 10
T_stable = np.mean(T[-tail_n:])
C_stable = np.mean(C[-tail_n:])
print(f"计算得到稳定值：T = {T_stable:.4f}, C = {C_stable:.4f}")

# 设定5%误差带
tol_T = 0.05 * abs(T_stable)
tol_C = 0.05 * abs(C_stable)

# 判断是否稳定
cond_T = np.abs(T - T_stable) <= tol_T
cond_C = np.abs(C - C_stable) <= tol_C
cond_both = cond_T & cond_C

# 确定稳定起点
idx_start = 0
for i in range(len(cond_both) - 1, -1, -1):
    if not cond_both[i]:
        idx_start = i + 1
        break

# 统计稳定阶段
if idx_start < len(t):
    t_stable_point = t[idx_start]
    print(f"\n温度和水分从 t = {t_stable_point:.2f} 开始基本不变（同时满足5%误差带）。")
    
    T_stable_phase = T[idx_start:]
    C_stable_phase = C[idx_start:]
    
    print("\n--- 稳定阶段统计信息 ---")
    print(f"温度 T: 最大值={np.max(T_stable_phase):.4f}, 最小值={np.min(T_stable_phase):.4f}, 平均值={np.mean(T_stable_phase):.4f}")
    print(f"水分 C: 最大值={np.max(C_stable_phase):.4f}, 最小值={np.min(C_stable_phase):.4f}, 平均值={np.mean(C_stable_phase):.4f}")
    
    df_out = df.iloc[idx_start:].copy()
else:
    print("未找到稳定时间段，数据始终在变化。")
    df_out = df.copy()
    t_stable_point = None

output_path.parent.mkdir(parents=True, exist_ok=True)
plot_path.parent.mkdir(parents=True, exist_ok=True)
df_out.to_excel(output_path, index=False)
print(f"\n稳定阶段数据已保存至 '{output_path}'")

# 绘图
fig, ax1 = plt.subplots(figsize=(10, 6))

# 温度曲线（左轴）
color_T = 'tab:red'
ax1.set_xlabel('时间 t (s)')
ax1.set_ylabel('温度 T (°C)', color=color_T)
ax1.plot(t, T, color=color_T, label='温度')
ax1.tick_params(axis='y', labelcolor=color_T)
ax1.grid(alpha=0.3)

# 水分曲线（右轴）
ax2 = ax1.twinx()
color_C = 'tab:blue'
ax2.set_ylabel('水分浓度 C', color=color_C)
ax2.plot(t, C, color=color_C, label='水分浓度')
ax2.tick_params(axis='y', labelcolor=color_C)
ax2.set_ylim(0, 0.2)  # 右轴范围

# 绘制误差带
ax1.axhline(y=T_stable + tol_T, color='gray', linestyle=':', alpha=0.6)
ax1.axhline(y=T_stable - tol_T, color='gray', linestyle=':', alpha=0.6)
ax2.axhline(y=C_stable + tol_C, color='gray', linestyle=':', alpha=0.6)
ax2.axhline(y=C_stable - tol_C, color='gray', linestyle=':', alpha=0.6)

# 标注稳定起点
if t_stable_point is not None:
    ax1.axvline(x=t_stable_point, color='green', linestyle='--', linewidth=2)
    # 添加文字
    ax1.text(t_stable_point + (t[-1]-t[0])*0.02, np.max(T)*0.95, 
             f'同时稳定起点\nt={t_stable_point:.1f}s', 
             color='green', fontsize=12, verticalalignment='top')

# 合并图例
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='center right')

plt.tight_layout()
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
plt.show()
plt.close()
