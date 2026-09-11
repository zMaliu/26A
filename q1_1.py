import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

# 文件路径
input_file = '附件1.xlsx'  
output_file = 'output1.xlsx'

# 读取Excel（前三列：时间, 温度, 水分浓度）
df = pd.read_excel(input_file, header=0)
t_orig = df.iloc[:, 0].values.astype(float)
temp_orig = df.iloc[:, 1].values.astype(float)
moist_orig = df.iloc[:, 2].values.astype(float)

# 生成步长为1s的时间序列
t_new = np.arange(t_orig.min(), t_orig.max() + 0.1, 1.0)

# PCHIP插值（保形，防止过冲导致物理异常）
temp_new = PchipInterpolator(t_orig, temp_orig)(t_new)
moist_new = PchipInterpolator(t_orig, moist_orig)(t_new)

# 保存结果
pd.DataFrame({
    '时间': t_new, 
    '温度': temp_new, 
    '水分浓度': moist_new
}).to_excel(output_file, index=False)

print(f"完成，已保存至 {output_file}")

# 画温度图
plt.figure()
plt.plot(t_new, temp_new, label='插值数据 (1s)')
plt.plot(t_orig, temp_orig, 'o', label='原始数据 (60s)')
plt.xlabel('时间 (s)')
plt.ylabel('温度')
plt.legend()
plt.show()

# 画水分浓度图
plt.figure()
plt.plot(t_new, moist_new, label='插值数据 (1s)')
plt.plot(t_orig, moist_orig, 'o', label='原始数据 (60s)')
plt.xlabel('时间 (s)')
plt.ylabel('水分浓度')
plt.legend()
plt.show()