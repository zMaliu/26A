# 生成精简结果图和三维图

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_excel"
PIC_DIR = BASE_DIR / "pic"

plt.rcParams.update(
    {
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "mathtext.fontset": "stix",
        "axes.linewidth": 1.0,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.size": 4,
        "ytick.major.size": 4,
    }
)

COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7"]


def _table(path, sheet=0):
    # 读取时间和空间矩阵
    df = pd.read_excel(path, sheet_name=sheet)
    time = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(float)
    values = df.iloc[:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    labels = [str(c) for c in df.columns[1:]]
    return time, labels, values


def _axis(ax):
    # 统一坐标轴
    ax.grid(True, color="#B8C2CC", alpha=0.35, linewidth=0.75)
    ax.set_axisbelow(True)
    ax.minorticks_on()


def _save(fig, name):
    # 保存图片
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    path = PIC_DIR / name
    fig.savefig(path, dpi=400, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"已保存：{path}")


def _surface(ax, time, space, values, cmap, xlabel, ylabel, zlabel, title,
             time_unit=1.0, elev=28, azim=-125):
    # 绘制三维表面
    step = max(1, int(np.ceil(len(time) / 360)))
    t = time[::step] / time_unit
    z = values[::step]
    y = np.asarray(space, dtype=float)
    xx, yy = np.meshgrid(t, y, indexing="xy")
    zz = z.T
    surface = ax.plot_surface(
        xx, yy, zz, cmap=cmap, linewidth=0, antialiased=True,
        rcount=min(180, zz.shape[0]), ccount=min(360, zz.shape[1]),
        alpha=0.96, shade=True,
    )
    ax.set_xlabel(xlabel, labelpad=8)
    ax.set_ylabel(ylabel, labelpad=8)
    ax.set_zlabel(zlabel, labelpad=8)
    ax.set_title(title, pad=14, fontsize=12, fontweight="bold")
    ax.view_init(elev=elev, azim=azim)
    ax.grid(True, alpha=0.25)
    return surface


def q1_summary():
    # 问题一二维综合图
    t, labels_t, temp = _table(OUTPUT_DIR / "q1_1.xlsx")
    tc, labels_c, moist = _table(OUTPUT_DIR / "q1_2.xlsx")
    radii = np.asarray([float(v) for v in labels_t])
    if not np.allclose(t, tc) or labels_t != labels_c:
        raise ValueError("问题一温度和水分网格不一致")
    targets = [100.0, 600.0, 1200.0, 1800.0]
    rows = [int(np.argmin(np.abs(t - v))) for v in targets]

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), sharex=True)
    for color, label, row in zip(COLORS, [f"t={v:.0f} s" for v in targets], rows):
        axes[0].plot(radii, temp[row], color=color, linewidth=2.2, label=label)
        axes[1].plot(radii, moist[row], color=color, linewidth=2.2, label=label)
    axes[0].set_ylabel(r"温度 $T$ / $^{\circ}$C")
    axes[1].set_ylabel(r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    for ax, tag in zip(axes, ["(a) 温度", "(b) 水分浓度"]):
        ax.set_title(tag, fontsize=12, pad=8)
        ax.set_xlabel(r"半径 $r$ / cm")
        ax.set_xlim(0, 2)
        ax.set_xticks(np.arange(0, 2.01, 0.5))
        ax.legend(frameon=False, fontsize=9, ncol=2)
        _axis(ax)
    fig.suptitle("问题一径向温度和水分浓度分布", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.16, top=0.83, wspace=0.24)
    _save(fig, "q1_综合图.png")

    fig = plt.figure(figsize=(12.0, 5.5))
    ax1 = fig.add_subplot(121, projection="3d")
    ax2 = fig.add_subplot(122, projection="3d")
    surf1 = _surface(ax1, t, radii, temp, "YlOrRd", r"时间 $t$ / h", r"半径 $r$ / cm",
                     r"温度 $T$ / $^{\circ}$C", "(a) 温度三维场", time_unit=3600.0)
    surf2 = _surface(ax2, t, radii, moist, "Blues_r", r"时间 $t$ / h", r"半径 $r$ / cm",
                     r"水分浓度 $C$ / (kg·kg$^{-1}$)", "(b) 水分浓度三维场", time_unit=3600.0)
    fig.colorbar(surf1, ax=ax1, shrink=0.62, pad=0.08, label=r"温度 $T$ / $^{\circ}$C")
    fig.colorbar(surf2, ax=ax2, shrink=0.62, pad=0.08,
                 label=r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    fig.suptitle("问题一温度和水分浓度三维时空分布", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.86, wspace=0.02)
    _save(fig, "q1_三维图.png")


def q2_summary():
    # 问题二二维综合图
    t, labels_t, temp = _table(OUTPUT_DIR / "result2.xlsx", 0)
    tc, labels_c, moist = _table(OUTPUT_DIR / "result2.xlsx", 1)
    radii = np.asarray([float(v) for v in labels_t])
    if not np.allclose(t, tc) or labels_t != labels_c:
        raise ValueError("问题二温度和水分网格不一致")
    time_h = t / 3600.0

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.9), sharey=True)
    for ax, data, cmap, title, cbar_label in [
        (axes[0], temp, "YlOrRd", "(a) 温度场", r"温度 $T$ / $^{\circ}$C"),
        (axes[1], moist, "Blues_r", "(b) 水分浓度场", r"水分浓度 $C$ / (kg·kg$^{-1}$)"),
    ]:
        mesh = ax.pcolormesh(time_h, radii, data.T, shading="auto", cmap=cmap,
                              rasterized=True)
        ax.set_title(title, fontsize=12, pad=8)
        ax.set_xlabel(r"时间 $t$ / h")
        ax.set_xlim(0, 3)
        ax.set_xticks(np.arange(0, 3.01, 0.5))
        ax.set_ylim(0, 2)
        ax.set_yticks(np.arange(0, 2.01, 0.5))
        _axis(ax)
        cbar = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(cbar_label)
    axes[0].set_ylabel(r"半径 $r$ / cm")
    fig.suptitle("问题二恒温阶段温度和水分浓度时空分布", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.16, top=0.83, wspace=0.28)
    _save(fig, "q2_综合图.png")

    fig = plt.figure(figsize=(12.0, 5.5))
    ax1 = fig.add_subplot(121, projection="3d")
    ax2 = fig.add_subplot(122, projection="3d")
    surf1 = _surface(ax1, t, radii, temp, "YlOrRd", r"时间 $t$ / h", r"半径 $r$ / cm",
                     r"温度 $T$ / $^{\circ}$C", "(a) 温度三维场", time_unit=3600.0)
    surf2 = _surface(ax2, t, radii, moist, "Blues_r", r"时间 $t$ / h", r"半径 $r$ / cm",
                     r"水分浓度 $C$ / (kg·kg$^{-1}$)", "(b) 水分浓度三维场", time_unit=3600.0)
    fig.colorbar(surf1, ax=ax1, shrink=0.62, pad=0.08, label=r"温度 $T$ / $^{\circ}$C")
    fig.colorbar(surf2, ax=ax2, shrink=0.62, pad=0.08,
                 label=r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    fig.suptitle("问题二恒温阶段三维时空分布", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.04, top=0.86, wspace=0.02)
    _save(fig, "q2_三维图.png")


def q3_summary():
    # 问题三二维综合图
    t, labels, moist = _table(OUTPUT_DIR / "result3.xlsx")
    radii = np.asarray([float(v) for v in labels])
    time_h = t / 3600.0
    target_r = [0.0, 0.5, 1.0, 1.5, 2.0]
    idx = [int(np.argmin(np.abs(radii - v))) for v in target_r]
    max_c = np.max(moist, axis=1)
    hit = np.flatnonzero(max_c <= 0.15)
    # 优先使用摘要表中的插值结束时刻
    summary_path = OUTPUT_DIR / "result3_summary.xlsx"
    if summary_path.exists():
        summary = pd.read_excel(summary_path)
        end_h = float(pd.to_numeric(summary.iloc[-1, 0], errors="coerce"))
        if not np.isfinite(end_h):
            raise ValueError("result3_summary.xlsx结束时刻无效")
    else:
        end_h = float(time_h[hit[0]]) if len(hit) else float(time_h[-1])

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    for color, radius, j in zip(COLORS, target_r, idx):
        axes[0].plot(time_h, moist[:, j], color=color, linewidth=2.0, label=f"r={radius:g} cm")
    axes[0].axhline(0.15, color="#555555", linestyle="--", linewidth=1.2, label="C=0.15")
    axes[0].set_xlabel(r"时间 $t$ / h")
    axes[0].set_ylabel(r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    axes[0].set_xlim(0, end_h)
    axes[0].legend(frameon=False, fontsize=9, ncol=2)
    axes[0].set_title("(a) 各半径水分浓度")
    _axis(axes[0])
    axes[1].plot(time_h, max_c, color="#0072B2", linewidth=2.3, label=r"$C_{\max}(t)$")
    axes[1].axhline(0.15, color="#555555", linestyle="--", linewidth=1.2, label="干燥标准")
    axes[1].axvline(end_h, color="#D55E00", linestyle=":", linewidth=1.5, label=f"结束 {end_h:.2f} h")
    axes[1].set_xlabel(r"时间 $t$ / h")
    axes[1].set_ylabel(r"全域最大水分浓度 $C_{\max}$")
    axes[1].set_xlim(0, end_h)
    axes[1].set_ylim(0, max(0.2, float(max_c.max()) * 1.06))
    axes[1].legend(frameon=False, fontsize=9)
    axes[1].set_title("(b) 干燥阈值判定")
    _axis(axes[1])
    fig.suptitle("问题三干燥过程与阈值判定", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.16, top=0.83, wspace=0.25)
    _save(fig, "q3_综合图.png")

    fig = plt.figure(figsize=(9.5, 6.0))
    ax = fig.add_subplot(111, projection="3d")
    surf = _surface(ax, t, radii, moist, "Blues_r", r"时间 $t$ / h", r"半径 $r$ / cm",
                    r"水分浓度 $C$ / (kg·kg$^{-1}$)", "问题三水分浓度三维时空分布", time_unit=3600.0,
                    elev=30, azim=-122)
    fig.colorbar(surf, ax=ax, shrink=0.65, pad=0.10,
                 label=r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    ax.set_zlim(0, max(0.2, float(moist.max()) * 1.03))
    _save(fig, "q3_三维图.png")


def q4_summary():
    # 问题四二维综合图
    t, labels, moist = _table(OUTPUT_DIR / "result4.xlsx", 2)
    radius = moist[:, -1]
    field = moist[:, :-1]
    xi = np.linspace(0, 1, field.shape[1])
    time_h = t / 3600.0
    max_c = np.max(field, axis=1)
    end_h = float(time_h[-1])

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.8))
    axes[0].plot(time_h, radius, color="#0072B2", linewidth=2.3)
    axes[0].fill_between(time_h, radius, radius[0], color="#0072B2", alpha=0.10)
    axes[0].set_xlabel(r"时间 $t$ / h")
    axes[0].set_ylabel(r"药材半径 $R$ / cm")
    axes[0].set_xlim(0, end_h)
    axes[0].set_ylim(float(radius.min()) * 0.98, float(radius.max()) * 1.02)
    axes[0].set_title("(a) 半径收缩")
    _axis(axes[0])
    axes[1].plot(time_h, max_c, color="#D55E00", linewidth=2.3, label=r"$C_{\max}(t)$")
    axes[1].plot(time_h, field[:, 0], color="#0072B2", linewidth=1.8, label="中心")
    axes[1].plot(time_h, field[:, -1], color="#009E73", linewidth=1.8, label="表面")
    axes[1].axhline(0.15, color="#555555", linestyle="--", linewidth=1.2, label="干燥标准")
    axes[1].axvline(end_h, color="#D55E00", linestyle=":", linewidth=1.5, label=f"结束 {end_h:.2f} h")
    axes[1].set_xlabel(r"时间 $t$ / h")
    axes[1].set_ylabel(r"水分浓度 / (kg·kg$^{-1}$)")
    axes[1].set_xlim(0, end_h)
    axes[1].set_ylim(0, max(0.2, float(max_c.max()) * 1.06))
    axes[1].set_title("(b) 水分浓度与阈值")
    axes[1].legend(frameon=False, fontsize=9)
    _axis(axes[1])
    fig.suptitle("问题四变半径烘干过程", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.16, top=0.83, wspace=0.25)
    _save(fig, "q4_综合图.png")

    # 变半径物理坐标三维图
    fig = plt.figure(figsize=(9.5, 6.0))
    ax = fig.add_subplot(111, projection="3d")
    step = max(1, int(np.ceil(len(t) / 360)))
    ts = time_h[::step]
    rs = radius[::step]
    cs = field[::step]
    xx, xi_grid = np.meshgrid(ts, xi, indexing="xy")
    yy = xi_grid * rs[np.newaxis, :]
    zz = cs.T
    surf = ax.plot_surface(xx, yy, zz, cmap="Blues_r", linewidth=0, antialiased=True,
                           rcount=min(180, zz.shape[0]), ccount=min(360, zz.shape[1]), alpha=0.96)
    ax.set_xlabel(r"时间 $t$ / h", labelpad=8)
    ax.set_ylabel(r"物理半径 $r$ / cm", labelpad=8)
    ax.set_zlabel(r"水分浓度 $C$ / (kg·kg$^{-1}$)", labelpad=8)
    ax.set_title("问题四变半径水分浓度三维分布", pad=14, fontsize=12, fontweight="bold")
    ax.view_init(elev=30, azim=-122)
    ax.grid(True, alpha=0.25)
    ax.set_zlim(0, max(0.2, float(field.max()) * 1.03))
    fig.colorbar(surf, ax=ax, shrink=0.65, pad=0.10,
                 label=r"水分浓度 $C$ / (kg·kg$^{-1}$)")
    _save(fig, "q4_三维图.png")


def main():
    # 生成全部精简图
    q1_summary()
    q2_summary()
    q3_summary()
    q4_summary()


if __name__ == "__main__":
    main()
