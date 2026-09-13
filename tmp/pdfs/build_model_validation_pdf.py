from pathlib import Path
import html

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE = Path(__file__).resolve().parents[2]
SOURCE = Path(
    r"E:\xwechat_files\wxid_7mpmo8qdgm6m22_2d7f\msg\file\2026-09\model.pdf"
)
TMP = BASE / "tmp" / "pdfs"
OUT = BASE / "output" / "pdf"
SUPPLEMENT = TMP / "model_validation_supplement.pdf"
FINAL = OUT / "model_with_validation.pdf"
PIC = BASE / "pic"


pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))
pdfmetrics.registerFont(TTFont("SimSun", r"C:\Windows\Fonts\simsun.ttc"))
pdfmetrics.registerFontFamily("SimHei", normal="SimHei", bold="SimHei")

styles = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "TitleCN", parent=styles["Title"], fontName="SimHei", fontSize=20,
    leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"),
    spaceAfter=18,
)
SUBTITLE = ParagraphStyle(
    "SubtitleCN", parent=styles["Normal"], fontName="SimSun", fontSize=11,
    leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#444444"),
)
H1 = ParagraphStyle(
    "H1CN", parent=styles["Heading1"], fontName="SimHei", fontSize=15,
    leading=22, textColor=colors.HexColor("#17365D"), spaceBefore=4,
    spaceAfter=10,
)
H2 = ParagraphStyle(
    "H2CN", parent=styles["Heading2"], fontName="SimHei", fontSize=12,
    leading=18, textColor=colors.HexColor("#2F5597"), spaceBefore=8,
    spaceAfter=5,
)
BODY = ParagraphStyle(
    "BodyCN", parent=styles["BodyText"], fontName="SimSun", fontSize=9.8,
    leading=16, alignment=TA_LEFT, spaceAfter=6,
)
SMALL = ParagraphStyle(
    "SmallCN", parent=BODY, fontSize=8.3, leading=12,
)
FORMULA = ParagraphStyle(
    "FormulaCN", parent=BODY, fontName="SimHei", fontSize=10.2,
    leading=17, alignment=TA_CENTER, backColor=colors.HexColor("#F4F7FB"),
    borderColor=colors.HexColor("#D9E2F3"), borderWidth=0.5,
    borderPadding=6, spaceBefore=4, spaceAfter=8,
)
CAPTION = ParagraphStyle(
    "CaptionCN", parent=SMALL, alignment=TA_CENTER,
    textColor=colors.HexColor("#555555"), spaceAfter=8,
)


def P(text, style=BODY):
    return Paragraph(text, style)


def para_cell(text, style=SMALL):
    return Paragraph(text, style)


def add_header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D9E2F3"))
    canvas.line(1.8 * cm, height - 1.35 * cm, width - 1.8 * cm, height - 1.35 * cm)
    canvas.setFont("SimSun", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(1.8 * cm, height - 1.05 * cm, "模型思路与数值结果正确性补充说明")
    canvas.drawRightString(width - 1.8 * cm, 1.0 * cm, f"补充页 {doc.page}")
    canvas.restoreState()


def chart(path, width=16.7 * cm, height=None):
    p = PIC / path
    if not p.exists():
        return P(f"图文件不存在：{html.escape(str(p))}", SMALL)
    if height is None:
        height = width / 1.8
    return Image(str(p), width=width, height=height)


def make_supplement():
    TMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(SUPPLEMENT), pagesize=A4, rightMargin=1.8 * cm,
        leftMargin=1.8 * cm, topMargin=1.7 * cm, bottomMargin=1.55 * cm,
        title="模型思路与数值结果正确性补充说明",
        author="数值模型验证",
    )
    story = []
    story += [
        Spacer(1, 1.1 * cm),
        P("模型思路与数值结果正确性补充说明", TITLE),
        P("本部分接续用户提供的 model.pdf，原文 12 页保持不变。本补充将原有四问建模步骤与实际程序检验逐一对应，给出可复现的判据、当前计算值和论文可直接采用的表述。", SUBTITLE),
        Spacer(1, 1.0 * cm),
        P("使用范围", H1),
        P("本说明针对项目目录中的 q1_1.py、q1_2.py、q1_3.py、q2_1.py、q2_2.py、q2_3.py、q3.py、q4.py 和 validate_all.py。检验目标是确认数据读取、时间和空间索引、边界切换、公式离散、半径插值、结束时间判定以及结果写表均与模型一致。由于题目没有给出完整实验真值，以下检验证明的是数值实现的正确性和物理合理性，不能替代对经验公式的实验标定。", BODY),
        P("运行命令", H2),
        P("python q4.py<br/>python validate_all.py<br/>python -m py_compile q4.py validate_all.py", FORMULA),
        P("验证报告位置：output_excel/validation_report.json。当前报告的 summary.all_passed 为 true。", BODY),
        PageBreak(),
    ]

    story += [
        P("一、总体验证框架", H1),
        P("验证不能只看一张曲线或一个最终时间，而应同时检查以下五类证据。任何一项失败，都应先定位程序或模型实现问题，再使用结果。", BODY),
    ]
    data = [
        [para_cell("验证层次"), para_cell("检验内容"), para_cell("合格标准")],
        [para_cell("文件结构"), para_cell("工作表、行数、时间起点终点、径向列、四位小数、NaN"), para_cell("结构与题目模板一致")],
        [para_cell("初值与边界"), para_cell("t=0 初值、5500 s 阶段切换、空气边界范围"), para_cell("逐项相等或误差小于设定阈值")],
        [para_cell("物理约束"), para_cell("半径单调、水分非负、温度范围、恒温段最大水分不增"), para_cell("全部满足")],
        [para_cell("数值验证"), para_cell("独立重算、时间步收敛、空间步收敛、离散守恒"), para_cell("误差递减，收敛比接近理论值")],
        [para_cell("结果判定"), para_cell("全域最大水分浓度首次跨越 0.15"), para_cell("阈值前大于 0.15，阈值后不大于 0.15")],
    ]
    tab = Table(data, colWidths=[2.2 * cm, 8.8 * cm, 5.7 * cm], repeatRows=1)
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("FONTNAME", (0, 0), (-1, -1), "SimSun"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [tab, Spacer(1, 8), P("validate_all.py 会重新读取输入文件并重新运行求解器，再将重新计算结果与已写入 Excel 的结果逐元素比较。该步骤可排除写表索引错误和结果文件被旧程序覆盖的问题。", BODY), PageBreak()]

    story += [
        P("二、按建模步骤对应的检验", H1),
        P("1. 初始条件。问题一、问题三、问题四均从 T=28 °C、C=2.55 开始；问题二的 t=0 是绝对时间 5500 s，必须读取 output3.xlsx 的温度和水分剖面。检验方法是直接比较计算矩阵的第一行与规定初值或 output3.xlsx。当前问题二温度和水分最大初值误差均为 0。", BODY),
        P("2. 阶段边界。程序使用绝对时间查询空气边界：0 至 5500 s 使用附件1，5500 s 后使用恒温边界。检验方法是检查 5500 s 左右查询值，并将全过程重算到 5500 s 后与 output3.xlsx 比较。当前最大差异为：温度 4.4195e-5 °C，水分 4.8757e-5 kg/kg，均小于 1e-4。", BODY),
        P("3. 物性公式。问题一使用附录2，问题二和问题三使用附录3，问题四使用附录4。温度指数项统一使用 T_K=T+273.15。检验方法是抽取若干 C、T 输入，独立代入公式，并检查 D、rho、cp、k 为有限正值。程序同时检查状态量没有触及保护边界。", BODY),
        P("4. 变半径坐标。问题四采用 xi=r/R(t)，固定 xi 网格跟随材料点，因此材料导数变为固定 xi 的时间导数；空间导数满足 d/dr=(1/R)d/dxi。检验方法是检查附件2插值后 R&gt;0、R 单调不增、R(0)=2.000 cm、R(259200)=1.198 cm，并确认计算中使用 R^-2 的扩散项和 R^-1 的表面项。", BODY),
        P("5. 边界条件。中心使用零通量对称条件；表面使用 Robin 换热和换质条件。检验方法是核对表面方程符号，并通过守恒残差检查边界通量方向。若 C_air&lt;C_s，水分应从药材流向空气，C_max 不应因边界符号错误而上升。", BODY),
        PageBreak(),
    ]

    story += [
        P("三、离散方程与守恒检验", H1),
        P("问题四在材料坐标下的水分方程为", H2),
        P("dC/dt = [1/(R(t)^2 xi)] d/dxi [ xi D(C,T) dC/dxi ]", FORMULA),
        P("将方程在无量纲控制体上积分，设 w_i 为控制体权重，得到程序应满足的离散恒等式：", BODY),
        P("sum_i w_i(C_i^(n+1)-C_i^n) = [2 h_m dt / R_(n+1)] [C_air^(n+1)-C_s^(n+1)]", FORMULA),
        P("定义左右两端之差为逐步守恒残差 E_M^n。内部相邻控制体的扩散通量必须成对抵消，剩余变化只能由表面换质项解释。当前全时段最大残差为 2.21e-16，小于程序判据 1e-10，说明界面通量、表面符号和控制体权重彼此一致。这个检验是材料坐标下的归一化储量检验；若将 C 解释为体积浓度，则需另建包含收缩稀释项的守恒模型。", BODY),
        P("时间步收敛检验", H2),
        P("分别使用 dt=120、60、30 s，在相同物理时刻比较解的最大差异。后向 Euler 时间离散为一阶，理论上误差减半时收敛比约为 0.5。当前误差为 0.0309269 和 0.0174469，收敛比为 0.5641。", BODY),
        P("空间步收敛检验", H2),
        P("分别使用 dxi=0.1、0.05、0.025，在相同时间比较解的最大差异。控制体通量中心离散在平滑区域具有二阶空间精度，理论收敛比约为 0.25。当前误差为 0.0039481 和 0.0010325，收敛比为 0.2615。两类误差均随网格加密下降，说明 R^-2、R^-1 和中心控制体处理均已进入稳定收敛区。", BODY),
        PageBreak(),
    ]

    story += [
        P("四、结束时间与当前结果", H1),
        P("结束条件不是只检查表面，而是检查全域最大水分浓度：C_max(t)=max_i C_i(t)。首次找到 C_max<=0.15 的时间步后，对相邻两个时间点做线性插值：", BODY),
        P("t_d=t_b+(0.15-C_b)/(C_a-C_b)·(t_a-t_b)", FORMULA),
        P("当前相邻点为：C_max(184800 s)=0.1500079925，C_max(184860 s)=0.1499775244。因此：", BODY),
        P("t_d=184815.7394 s = 51.33771 h", FORMULA),
        P("该时间满足阈值前一点仍大于 0.15，阈值后一点已经小于 0.15，因此它是离散计算范围内首次满足全域限制的时间。结束时半径约为 1.200 cm。", BODY),
    ]
    result_data = [
        [para_cell("问题"), para_cell("主要结果"), para_cell("验证结论")],
        [para_cell("问题一"), para_cell("1800 s 完整温度和水分场"), para_cell("独立重算误差 0；能量和水分守恒残差远小于 1%")],
        [para_cell("问题二"), para_cell("5500 s 剖面起算，继续 3 h"), para_cell("初值误差 0；5500 s 断点最大误差小于 10^-4")],
        [para_cell("问题三"), para_cell("固定半径烘干时间 58.50965 h"), para_cell("阈值和收敛检验通过")],
        [para_cell("问题四"), para_cell("变半径烘干时间 51.33771 h"), para_cell("半径、守恒、物理范围、收敛和独立重算全部通过")],
    ]
    rtab = Table(result_data, colWidths=[2.0 * cm, 6.8 * cm, 7.9 * cm], repeatRows=1)
    rtab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A6A6A6")),
        ("FONTNAME", (0, 0), (-1, -1), "SimSun"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [rtab, Spacer(1, 7), P("需要注意：问题三和问题四不能要求得到相同烘干时间，因为问题四同时改变了半径和附录4物性公式。问题四时间比问题三短，是模型改变后的结果，不是程序必须与问题三相等。", BODY), PageBreak()]

    story += [
        P("五、图形证据及论文写法", H1),
        P("下列图形不是单独的证明，而是对数值判据的可视化。论文中应同时给出图、公式和数值判据。", BODY),
        chart("q4_综合图.png", width=16.2 * cm, height=8.9 * cm),
        P("图 1  半径收缩、水分浓度演化和阈值判定。半径曲线由附件2的 PCHIP 插值得到。", CAPTION),
        chart("q4_三维图.png", width=16.2 * cm, height=8.9 * cm),
        P("图 2  物理半径坐标下的水分浓度三维分布。表面区域先变干，中心区域保持较高水分浓度。", CAPTION),
        PageBreak(),
    ]

    story += [
        P("六、空间分布与收敛图的判读", H1),
        chart("q3_三维图.png", width=16.2 * cm, height=8.9 * cm),
        P("图 3  固定半径模型的水分浓度三维时空分布。颜色变化连续且没有明显数值振荡。", CAPTION),
        chart("验证_问题四收敛.png", width=16.2 * cm, height=6.4 * cm),
        P("图 4  时间步和空间步收敛。横坐标减小后误差下降，图中标出的收敛比分别为 0.5641 和 0.2615。", CAPTION),
        PageBreak(),
    ]

    story += [
        P("七、可直接放入论文的验证结论", H1),
        P("为检验数值结果的可靠性，本文从结果文件结构、初始条件和阶段边界、半径插值、物理范围、离散守恒、时间步收敛、空间步收敛以及独立重算八个方面进行交叉验证。问题四中，附件2半径由 2.000 cm 单调下降至 1.198 cm，PCHIP 插值未产生过冲；材料坐标离散的水分积分恒等式最大残差为 2.21×10^-16；时间步和空间步收敛比为 0.5641 和 0.2615，分别接近一阶时间离散和二阶空间离散的理论值；Excel 结果与重新运行求解器的无量纲水分矩阵最大误差为 0；水分浓度始终非负，恒温阶段全域最大水分浓度单调下降。最后，184800 s 时全域最大水分浓度为 0.1500079925，184860 s 时为 0.1499775244，线性插值得到烘干结束时间 184815.7394 s，即 51.33771 h。上述结果表明，程序实现与本文建立的数学模型、边界条件和结束判据相互一致。由于缺少完整实验真值，经验公式引起的模型误差仍需通过实验数据进一步评价。", BODY),
        P("最终文件", H2),
        P("合并版 PDF：output/pdf/model_with_validation.pdf<br/>原始结果：output_excel/result4.xlsx<br/>验证报告：output_excel/validation_report.json<br/>图表目录：pic/", BODY),
        Spacer(1, 5),
        P("阅读方式：先阅读前 12 页原 model.pdf 的建模过程，再从本补充第 1 页开始逐项核对检验。", SMALL),
    ]
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)


def merge_pdfs():
    if not SOURCE.exists():
        raise FileNotFoundError(f"找不到源 PDF：{SOURCE}")
    reader_a = PdfReader(str(SOURCE))
    reader_b = PdfReader(str(SUPPLEMENT))
    writer = PdfWriter()
    for page in reader_a.pages:
        writer.add_page(page)
    for page in reader_b.pages:
        writer.add_page(page)
    writer.add_metadata({
        "/Title": "中药材热风干燥模型与数值结果正确性说明",
        "/Subject": "原模型文档与数值结果交叉验证补充",
        "/Producer": "ReportLab + pypdf",
    })
    with FINAL.open("wb") as stream:
        writer.write(stream)


if __name__ == "__main__":
    make_supplement()
    merge_pdfs()
    print(FINAL)
