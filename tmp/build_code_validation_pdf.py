from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(r"E:\xwechat_files\wxid_7mpmo8qdgm6m22_2d7f\msg\file\2026-09\model.pdf")
TMP = BASE / "tmp"
SUPP = TMP / "code_validation_supplement.pdf"
OUT = BASE / "output" / "pdf" / "model_with_validation.pdf"

pdfmetrics.registerFont(TTFont("SimSun", r"C:\Windows\Fonts\simsun.ttc"))
pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))

sample = getSampleStyleSheet()
body = ParagraphStyle(
    "body", parent=sample["BodyText"], fontName="SimSun", fontSize=9.4,
    leading=15.5, alignment=TA_LEFT, spaceAfter=5,
)
small = ParagraphStyle(
    "small", parent=body, fontSize=8.2, leading=12,
)
section = ParagraphStyle(
    "section", parent=sample["Heading1"], fontName="SimHei", fontSize=15,
    leading=22, alignment=TA_LEFT, spaceBefore=0, spaceAfter=12,
)
subsection = ParagraphStyle(
    "subsection", parent=sample["Heading2"], fontName="SimHei", fontSize=11.5,
    leading=17, alignment=TA_LEFT, spaceBefore=7, spaceAfter=5,
)
formula = ParagraphStyle(
    "formula", parent=body, fontName="Times-Roman", fontSize=10.3,
    leading=17, alignment=TA_CENTER, spaceBefore=3, spaceAfter=7,
)
title = ParagraphStyle(
    "title", parent=sample["Title"], fontName="SimHei", fontSize=16,
    leading=24, alignment=TA_CENTER, spaceAfter=12,
)


def P(text, style=body):
    return Paragraph(text, style)


def cell(text):
    return Paragraph(text, small)


def page_header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFont("SimSun", 8)
    canvas.setFillColor(colors.black)
    canvas.drawString(2.0 * cm, height - 1.05 * cm, "7  四问结果的检验与正确性说明")
    canvas.drawRightString(width - 2.0 * cm, height - 1.05 * cm, str(doc.page + 12))
    canvas.line(2.0 * cm, height - 1.18 * cm, width - 2.0 * cm, height - 1.18 * cm)
    canvas.drawCentredString(width / 2, 1.0 * cm, str(doc.page + 12))
    canvas.restoreState()


def table(data, widths):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "SimSun"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def make_supplement():
    TMP.mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "pdf").mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(SUPP), pagesize=A4, leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=1.55 * cm, bottomMargin=1.55 * cm,
        title="四问结果的检验与正确性说明",
    )
    s = []
    s += [
        Spacer(1, 0.35 * cm),
        P("7  四问结果的检验与正确性说明", title),
        P("本节接续前文的统一建模框架和四问求解过程。检验不是重新提出一套模型，而是逐项核对代码 validate_all.py 实际执行的结果，判断输出文件、离散方程和最终结论是否与前文模型一致。所有数值均来自当前项目重新运行后的 validation_report.json。", body),
        P("7.1  检验程序与判据", subsection),
        P("执行 python q4.py 生成问题四结果，再执行 python validate_all.py。验证程序首先检查 Excel 文件结构，然后重新运行各问题求解器，将重算值与已保存数据逐元素比较，最后检查守恒、收敛和物理范围。若任一检查失败，程序立即报错；本次报告的 summary.all_passed=true。", body),
        table([
            [cell("检验类别"), cell("代码实际检查"), cell("通过标准")],
            [cell("文件结构"), cell("工作表、行列、时间、半径列、四位小数和有限值"), cell("满足题目模板要求")],
            [cell("独立重算"), cell("重新运行求解器并比较 Excel 数据"), cell("最大误差不超过设定阈值")],
            [cell("守恒关系"), cell("能量、水分或材料坐标积分恒等式"), cell("相对残差小于 1%，或绝对残差小于 1e-10")],
            [cell("网格收敛"), cell("时间步和空间步逐级加密"), cell("误差下降，收敛比接近理论值")],
            [cell("物理判据"), cell("半径、温度、水分和阈值跨越"), cell("范围合理且首次满足阈值")],
        ], [2.8 * cm, 8.7 * cm, 5.1 * cm]),
        PageBreak(),
    ]

    s += [
        P("7.2  问题一结果检验", section),
        P("问题一采用常物性、固定半径模型，程序输出 result1.xlsx。代码对温度表和水分表分别检查 1801 行、22 列，时间从 0 s 连续到 1800 s，径向列为 0.0--2.0 cm 且间隔 0.1 cm。两张表均无 NaN、无无穷值，并按四位小数保存。", body),
        P("独立重算检验。用 q1_3.py 重新调用问题一求解器，再与 result1.xlsx 比较，温度最大绝对误差为 0，水分最大绝对误差为 0。因此可以排除时间索引、径向索引和写表错位。", body),
        P("守恒检验。对单位长度圆柱控制体，内部界面通量求和后相互抵消，储量变化应等于表面对流通量积分：", body),
        P("Q^n-Q^0 = sum_m h A_s (T_air^(m+1)-T_s^m) dt,    M^n-M^0 = sum_m h_m A_s (C_air^(m+1)-C_s^m) dt.", formula),
        P("代码得到能量相对残差 2.9336e-14，水分相对残差 1.0201e-14，均远小于 1%。这说明问题一的中心控制体、表面半控制体、边界通量符号和内部界面通量是一致的。", body),
        P("收敛检验。时间步由 1 s 加密到 0.5 s、0.25 s，温度收敛比为 0.4997，水分收敛比为 0.4987，符合一阶时间离散；空间步由 0.001 m 加密到 0.0005 m、0.00025 m，温度收敛比为 0.2524，水分收敛比为 0.2467，符合二阶空间离散。", body),
        table([
            [cell("问题一检查"), cell("实际结果"), cell("判定")],
            [cell("文件结构"), cell("1801 x 22；0--1800 s；两工作表"), cell("通过")],
            [cell("独立重算"), cell("T 误差=0；C 误差=0"), cell("通过")],
            [cell("能量守恒"), cell("2.9336e-14"), cell("小于 1%")],
            [cell("水分守恒"), cell("1.0201e-14"), cell("小于 1%")],
            [cell("时间/空间收敛"), cell("0.4997/0.4987；0.2524/0.2467"), cell("接近 0.5/0.25")],
        ], [4.0 * cm, 8.6 * cm, 4.0 * cm]),
        PageBreak(),
    ]

    s += [
        P("7.3  问题二结果检验", section),
        P("问题二的时间原点是绝对时间 5500 s。程序输出 result2.xlsx，包含温度和水分两个工作表，每张表有 10801 行、22 列，记录的是恒温阶段经过时间 0--10800 s。", body),
        P("初值检验。代码读取 output3.xlsx 的 5500 s 温度和水分径向剖面，比较 result2.xlsx 第一行，温度最大误差为 0，水分最大误差为 0。因此问题二确实使用了 5500 s 剖面，而没有错误地重新使用均匀初值。", body),
        P("断点检验。代码把问题二模型从原始初态推进到绝对时间 5500 s，再与 output3.xlsx 比较，温度最大差异为 4.4195e-5 °C，水分最大差异为 4.8757e-5 kg/kg，均小于 1e-4。该结果同时检验了问题一到问题二的阶段衔接。", body),
        P("守恒检验。问题二使用系数滞后的后向 Euler 半隐式控制体格式，能量和水分的全时段相对残差分别为 1.1742e-14 和 6.1149e-14，均小于 1%。", body),
        P("物理范围检验。温度范围为 46.0518--50.0415 °C，水分范围为 0.728149--2.3745 kg/kg；所有值有限，水分没有负值，且没有触及程序的截断边界。", body),
        P("收敛检验。时间收敛比为温度 0.5011、水分 0.5001；空间收敛比为温度 0.2508、水分 0.2499，分别符合一阶时间精度和二阶空间精度。", body),
        table([
            [cell("问题二检查"), cell("实际结果"), cell("判定")],
            [cell("文件结构"), cell("10801 x 22；0--10800 s；两工作表"), cell("通过")],
            [cell("5500 s 初值"), cell("T 误差=0；C 误差=0"), cell("通过")],
            [cell("5500 s 断点"), cell("T=4.4195e-5；C=4.8757e-5"), cell("小于 1e-4")],
            [cell("守恒"), cell("能量 1.1742e-14；水分 6.1149e-14"), cell("小于 1%")],
            [cell("时间/空间收敛"), cell("0.5011/0.5001；0.2508/0.2499"), cell("接近 0.5/0.25")],
        ], [4.0 * cm, 8.6 * cm, 4.0 * cm]),
        PageBreak(),
    ]

    s += [
        P("7.4  问题三结果检验", section),
        P("问题三从 t=0 的原始初态开始，使用问题二的附录3变物性模型和 5500 s 阶段边界切换。程序以全域最大水分浓度 C_max(t)=max_i C_i(t) 作为烘干结束判据。", body),
        P("输出结构检验。result3.xlsx 从 0 s 开始按 60 s 保存，并在末尾追加线性插值结束行，共 3512 行、22 列；result3_summary.xlsx 包含每 6 h 数据和结束时刻。", body),
        P("独立重算检验。重新运行问题三求解器，与 result3.xlsx 的 60 s 网格比较，最大误差为 0。该结果说明问题三的时间保存、结束行追加和径向索引均正确。", body),
        P("阈值检验。首次跨越阈值的相邻点为 C_max(210600 s)=0.1500097682 和 C_max(210660 s)=0.1499928973。线性插值得到：", body),
        P("t_d = 210634.7398 s = 58.50965 h,    C_max(t_d)=0.15.", formula),
        P("阈值前一点大于 0.15，阈值后一点小于 0.15；同时 max(C) 单调不增，水分始终非负，温度范围为 28.0--50.0392 °C，水分范围为 0.0517481--2.55 kg/kg。", body),
        P("水分守恒相对残差为 7.0899e-16。时间收敛比为 0.5008，空间收敛比为 0.2488，说明阈值时间不是由数值振荡或粗网格误差造成的。", body),
        table([
            [cell("问题三检查"), cell("实际结果"), cell("判定")],
            [cell("输出结构"), cell("完整表 3512 x 22；摘要含 6 h 节点"), cell("通过")],
            [cell("独立重算"), cell("最大误差=0"), cell("通过")],
            [cell("阈值跨越"), cell("0.1500097682 -> 0.1499928973"), cell("首次跨越正确")],
            [cell("结束时间"), cell("210634.7398 s = 58.50965 h"), cell("通过")],
            [cell("守恒/收敛"), cell("7.0899e-16；0.5008/0.2488"), cell("通过")],
        ], [4.0 * cm, 8.6 * cm, 4.0 * cm]),
        PageBreak(),
    ]

    s += [
        P("7.5  问题四结果检验", section),
        P("问题四从原始初态开始，采用附录4经验公式和附件2半径数据。固定材料坐标 xi=r/R(t) 随药材收缩，因此不再额外加入一次网格对流项。", body),
        P("文件和半径检验。result4.xlsx 包含水分浓度、表6摘要、无量纲网格和半径插值四个工作表；完整水分表从 0 s 保存到插值结束时间 184815.74 s。附件2经过 PCHIP 插值后，半径由 2.000 cm 单调下降到 1.198 cm，所有半径为正。", body),
        P("独立重算检验。重新调用 q4.solve_problem4()，将无量纲水分矩阵与 Excel 结果比较，四位小数最大误差为 0。该检验确认了材料坐标网格、半径索引、物理位置输出和写表过程一致。", body),
        P("材料坐标守恒检验。对离散水分方程积分，程序检查：", body),
        P("sum_i w_i(C_i^(n+1)-C_i^n) = [2 h_m dt/R_(n+1)](C_air^(n+1)-C_s^(n+1)).", formula),
        P("全时段最大绝对残差为 2.2118e-16，小于 1e-10。该量是材料坐标下的归一化储量检验，与当前离散方程使用同一时间层。", body),
        P("收敛检验。时间步 120、60、30 s 的误差为 0.0309269 和 0.0174469，收敛比为 0.5641；空间步 dxi=0.1、0.05、0.025 的误差为 0.0039481 和 0.0010325，收敛比为 0.2615。误差均下降，且分别接近 0.5 和 0.25。", body),
        P("阈值检验。C_max(184800 s)=0.1500079925，C_max(184860 s)=0.1499775244。线性插值得到：", body),
        P("t_d = 184815.7394 s = 51.33771 h.", formula),
        table([
            [cell("问题四检查"), cell("实际结果"), cell("判定")],
            [cell("半径"), cell("2.000 -> 1.198 cm，单调不增"), cell("通过")],
            [cell("独立重算"), cell("无量纲水分最大误差=0"), cell("通过")],
            [cell("守恒"), cell("2.2118e-16"), cell("小于 1e-10")],
            [cell("时间/空间收敛"), cell("0.5641；0.2615"), cell("接近 0.5/0.25")],
            [cell("结束时间"), cell("184815.7394 s = 51.33771 h"), cell("首次满足阈值")],
        ], [4.0 * cm, 8.6 * cm, 4.0 * cm]),
        PageBreak(),
    ]

    s += [
        P("7.6  四问结果的综合结论", section),
        P("四问的验证结果不是通过某一个最终数值得到的，而是由多个相互独立的检查共同支持。问题一和问题二的 Excel 数据均能被求解器逐元素重算，最大误差为 0；问题二的 5500 s 初值与 output3.xlsx 完全一致，且全过程重算到 5500 s 的差异小于 1e-4；问题三和问题四的结束时间均由阈值前后相邻点线性插值得到，并满足首次跨越条件。", body),
        P("四问的守恒残差均远小于 1%，其中问题一能量和水分残差分别为 2.9336e-14 和 1.0201e-14，问题二分别为 1.1742e-14 和 6.1149e-14，问题三水分残差为 7.0899e-16，问题四材料坐标积分残差为 2.2118e-16。时间收敛比均接近 0.5，空间收敛比均接近 0.25，说明结果已进入稳定收敛区。", body),
        P("因此，在题目给定的连续介质假设、圆柱一维径向假设、Robin 边界和经验物性公式下，当前四问数据与代码实现、离散方程和输出格式相互一致。问题四得到的 51.33771 h 不需要与问题三的 58.50965 h 相同，因为问题四同时改变了半径和附录4经验公式。", body),
        P("需要保留的模型限制是：上述检验证明数值实现正确和结果具有物理合理性，但不能在没有实验真值的情况下证明经验公式完全等于真实药材。若后续取得实验温度或水分浓度数据，应增加实验值与计算值的 MAE、RMSE 和相对误差检验。", body),
        P("表 7  四问代码检验结果汇总", subsection),
        table([
            [cell("问题"), cell("独立重算"), cell("守恒"), cell("收敛比"), cell("最终判定")],
            [cell("问题一"), cell("T/C=0"), cell("2.93e-14 / 1.02e-14"), cell("时间 0.4997/0.4987；空间 0.2524/0.2467"), cell("通过")],
            [cell("问题二"), cell("T/C=0；断点<1e-4"), cell("1.17e-14 / 6.11e-14"), cell("时间 0.5011/0.5001；空间 0.2508/0.2499"), cell("通过")],
            [cell("问题三"), cell("最大误差=0"), cell("7.09e-16"), cell("时间 0.5008；空间 0.2488"), cell("58.50965 h")],
            [cell("问题四"), cell("最大误差=0"), cell("2.21e-16"), cell("时间 0.5641；空间 0.2615"), cell("51.33771 h")],
        ], [2.0 * cm, 3.6 * cm, 3.8 * cm, 6.0 * cm, 2.2 * cm]),
        Spacer(1, 8),
        P("验证报告文件：output_excel/validation_report.json。执行命令：python q4.py；python validate_all.py；python -m py_compile q4.py validate_all.py。", small),
    ]
    doc.build(s, onFirstPage=page_header_footer, onLaterPages=page_header_footer)


def merge():
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    writer = PdfWriter()
    for page in PdfReader(str(SOURCE)).pages:
        writer.add_page(page)
    for page in PdfReader(str(SUPP)).pages:
        writer.add_page(page)
    writer.add_metadata({
        "/Title": "中药材热风干燥模型与四问代码检验结果",
        "/Subject": "基于 validate_all.py 的数据正确性补充",
    })
    with OUT.open("wb") as f:
        writer.write(f)


if __name__ == "__main__":
    make_supplement()
    merge()
    print(OUT)
