"""Gera o artigo final do Laboratorio 03 em PDF."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    Image,
    KeepTogether,
    LongTable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "results"
FIGURES = RESULTS / "figures"
OUTPUT = ROOT / "output" / "pdf" / "Relatorio_Final_LAB03_Flavio_Luidi.pdf"

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = RIGHT = 14 * mm
TOP = 14 * mm
BOTTOM = 15 * mm
FRAME_WIDTH = PAGE_WIDTH - LEFT - RIGHT
FRAME_HEIGHT = PAGE_HEIGHT - TOP - BOTTOM

INK = colors.HexColor("#22313F")
TEAL = colors.HexColor("#147D78")
CORAL = colors.HexColor("#D95F59")
PALE = colors.HexColor("#EDF5F4")
LIGHT = colors.HexColor("#F5F7F8")
MID = colors.HexColor("#708090")
WHITE = colors.white


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ArticleTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            alignment=TA_LEFT,
            textColor=INK,
            spaceAfter=7,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=TEAL,
            spaceAfter=7,
        ),
        "authors": ParagraphStyle(
            "Authors",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceAfter=2,
        ),
        "affiliation": ParagraphStyle(
            "Affiliation",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MID,
            spaceAfter=8,
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=10.5,
            alignment=TA_JUSTIFY,
            textColor=INK,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.3,
            leading=10.7,
            alignment=TA_JUSTIFY,
            textColor=INK,
            spaceAfter=4.5,
        ),
        "body_small": ParagraphStyle(
            "BodySmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.3,
            leading=9.1,
            alignment=TA_JUSTIFY,
            textColor=INK,
            spaceAfter=3,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=TEAL,
            spaceBefore=7,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=9.4,
            leading=11.5,
            textColor=INK,
            spaceBefore=5,
            spaceAfter=2.5,
            keepWithNext=True,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.2,
            leading=9,
            alignment=TA_CENTER,
            textColor=INK,
            spaceBefore=2,
            spaceAfter=5,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.1,
            leading=8.5,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.1,
            leading=8.5,
            textColor=WHITE,
            alignment=TA_LEFT,
        ),
        "reference": ParagraphStyle(
            "Reference",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.9,
            leading=8.4,
            textColor=INK,
            leftIndent=7,
            firstLineIndent=-7,
            spaceAfter=2.5,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10.4,
            textColor=INK,
            alignment=TA_LEFT,
        ),
    }


STYLES = make_styles()


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def section(number: str, title: str) -> Paragraph:
    return para(f"{number}. {title}", "section")


def subsection(number: str, title: str) -> Paragraph:
    return para(f"{number} {title}", "subsection")


def styled_table(
    rows: list[list[object]],
    widths: list[float],
    *,
    header: bool = True,
    font_size: float = 7.1,
) -> Table:
    formatted: list[list[object]] = []
    for row_index, row in enumerate(rows):
        style = STYLES["table_header"] if header and row_index == 0 else STYLES["table"]
        formatted.append(
            [value if hasattr(value, "wrap") else Paragraph(str(value), style) for value in row]
        )
    table = LongTable(formatted, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL if header else LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE if header else INK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold" if header else "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, TEAL),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D4D8")),
    ]
    if len(rows) > 1:
        for row in range(1, len(rows)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), LIGHT))
    table.setStyle(TableStyle(commands))
    return table


def figure(path: Path, caption_text: str, width: float) -> KeepTogether:
    image_width, image_height = ImageReader(str(path)).getSize()
    height = width * image_height / image_width
    image = Image(str(path), width=width, height=height)
    return KeepTogether([image, para(caption_text, "caption")])


def cover_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(CORAL)
    canvas.rect(PAGE_WIDTH - 48 * mm, PAGE_HEIGHT - 8 * mm, 48 * mm, 8 * mm, stroke=0, fill=1)
    footer(canvas, doc, include_header=False)
    canvas.restoreState()


def article_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D6DEE1"))
    canvas.setLineWidth(0.45)
    canvas.line(LEFT, PAGE_HEIGHT - 10.5 * mm, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 10.5 * mm)
    canvas.setFillColor(MID)
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(LEFT, PAGE_HEIGHT - 8.5 * mm, "LAB03 - Mineracao de Metricas DORA")
    label = "Flavio Ferreira e Luidi Cadete Silva"
    canvas.drawRightString(PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 8.5 * mm, label)
    footer(canvas, doc, include_header=True)
    canvas.restoreState()


def page_chrome(canvas, doc) -> None:
    if doc.page == 1:
        cover_page(canvas, doc)
    else:
        article_page(canvas, doc)


def footer(canvas, doc, *, include_header: bool) -> None:
    canvas.setFillColor(MID)
    canvas.setFont("Helvetica", 6.8)
    page = str(doc.page)
    canvas.drawCentredString(PAGE_WIDTH / 2, 7.5 * mm, page)
    if not include_header:
        canvas.drawString(LEFT, 7.5 * mm, "Laboratorio de Experimentacao de Software")


def build_document() -> BaseDocTemplate:
    full = Frame(
        LEFT,
        BOTTOM,
        FRAME_WIDTH,
        FRAME_HEIGHT,
        id="full",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    gap = 7 * mm
    column_width = (FRAME_WIDTH - gap) / 2
    columns = [
        Frame(
            LEFT,
            BOTTOM,
            column_width,
            FRAME_HEIGHT,
            id="left-column",
            leftPadding=0,
            rightPadding=2 * mm,
            topPadding=0,
            bottomPadding=0,
        ),
        Frame(
            LEFT + column_width + gap,
            BOTTOM,
            column_width,
            FRAME_HEIGHT,
            id="right-column",
            leftPadding=2 * mm,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        ),
    ]
    mixed_top_height = 345
    mixed_gap = 5 * mm
    mixed_bottom_height = FRAME_HEIGHT - mixed_top_height - mixed_gap
    mixed_frames = [
        Frame(
            LEFT,
            BOTTOM + mixed_bottom_height + mixed_gap,
            FRAME_WIDTH,
            mixed_top_height,
            id="mixed-top",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        ),
        Frame(
            LEFT,
            BOTTOM,
            column_width,
            mixed_bottom_height,
            id="mixed-left",
            leftPadding=0,
            rightPadding=2 * mm,
            topPadding=0,
            bottomPadding=0,
        ),
        Frame(
            LEFT + column_width + gap,
            BOTTOM,
            column_width,
            mixed_bottom_height,
            id="mixed-right",
            leftPadding=2 * mm,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        ),
    ]
    document = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        title="Mineracao de Metricas DORA em Repositorios Open Source Populares",
        author="Flavio Ferreira; Luidi Cadete Silva",
        subject="Relatorio final do Laboratorio 03",
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP,
        bottomMargin=BOTTOM,
    )
    document.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[full], onPage=page_chrome),
            PageTemplate(
                id="TwoColumn",
                frames=columns,
                onPage=page_chrome,
                autoNextPageTemplate="TwoColumn",
            ),
            PageTemplate(
                id="Wide",
                frames=[full],
                onPage=page_chrome,
                autoNextPageTemplate="Wide",
            ),
            PageTemplate(
                id="Mixed",
                frames=mixed_frames,
                onPage=page_chrome,
                autoNextPageTemplate="TwoColumn",
            ),
        ]
    )
    return document


def metric_row(descriptive: pd.DataFrame, metric: str, classification: str) -> list[str]:
    row = descriptive.loc[descriptive["metric"] == metric].iloc[0]
    median = row["median"]
    q1 = row["q1"]
    q3 = row["q3"]
    if "rate" in metric or "proportion" in metric:
        format_value = lambda value: f"{100 * value:.2f}%"
    else:
        format_value = lambda value: f"{value:.2f}"
    return [
        row["label"],
        str(int(row["n"])),
        format_value(median),
        f"{format_value(q1)} - {format_value(q3)}",
        classification,
    ]


def build_story() -> list[object]:
    descriptive = pd.read_csv(RESULTS / "descriptive_statistics.csv")
    rq06 = pd.read_csv(RESULTS / "rq06_tests.csv")
    sensitivity = pd.read_csv(RESULTS / "rq07_sensitivity.csv")
    heuristic_evaluations = json.loads(
        (ROOT / "data" / "validation" / "heuristic_evaluations.json").read_text(
            encoding="utf-8"
        )
    )["evaluations"]
    story: list[object] = []

    story.extend(
        [
            Spacer(1, 9 * mm),
            para("Mineração de Métricas DORA em Repositórios Open Source Populares", "title"),
            para(
                "Uma análise de velocidade, estabilidade e sensibilidade das definições operacionais",
                "subtitle",
            ),
            para("Flavio Ferreira; Luidi Cadete Silva", "authors"),
            para(
                "Engenharia de Software - Laboratório de Experimentação de Software - 21 de outubro de 2026",
                "affiliation",
            ),
        ]
    )
    abstract = (
        "<b>Resumo.</b> Este estudo minera proxies das métricas DORA em 300 repositórios públicos "
        "populares que usam GitHub Actions. Releases representam deploys; commits compõem o lead "
        "time; e execuções de CI e releases corretivas representam falhas. O pipeline processou 922 "
        "candidatos até atingir a amostra final, preservando censura, cache e retomada. A frequência "
        "mediana foi 0,422 release/semana, o lead time por release foi 260,12 h, o CFR de CI foi "
        "6,30% e o tempo de recuperação foi 3,54 h. A classificação de referência concentrou 247 "
        "repositórios em Medium ou High. Entretanto, trocar o proxy de falha mudou 39,6% das "
        "categorias, e a heurística corretiva atingiu F1 máximo de 0,649. Os resultados descrevem "
        "o comportamento observável no GitHub, mas não substituem métricas de produção."
    )
    abstract_box = Table([[para(abstract, "abstract")]], colWidths=[FRAME_WIDTH - 12 * mm])
    abstract_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B8D6D3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    story.extend(
        [
            abstract_box,
            Spacer(1, 3 * mm),
            para(
                "<b>Palavras-chave:</b> DORA; GitHub Actions; mineração de repositórios; "
                "métricas de software; análise de sensibilidade.",
                "body_small",
            ),
            section("1", "Introdução"),
            para(
                "As métricas DORA combinam throughput e estabilidade para observar a capacidade de "
                "entrega de software. A definição original inclui frequência de deploy, lead time, "
                "change failure rate e tempo de recuperação; a nomenclatura e o conjunto evoluíram "
                "ao longo dos relatórios DORA [1, 2]. Em repositórios open source, porém, o GitHub "
                "não registra diretamente deploys e incidentes em produção. Este trabalho mede "
                "aproximações observáveis e testa o quanto as conclusões dependem dessas escolhas."
            ),
            para(
                "O objetivo é caracterizar 300 projetos populares com CI/CD e responder sete questões "
                "sobre velocidade, falha, recuperação, fatores associados e robustez. As hipóteses "
                "foram registradas antes da coleta."
            ),
        ]
    )
    hypothesis_rows = [
        ["RQ", "Hipótese prévia", "Síntese observada"],
        ["RQ01", "Cadência predominantemente mensal a semanal", "Parcialmente confirmada"],
        ["RQ02", "Lead time por release maior e mais variável", "Contradita no agregado"],
        ["RQ03", "CFR de CI maior que CFR por entrega", "Contradita; proxy b frágil"],
        ["RQ04", "Recuperação majoritariamente abaixo de 24 h", "Confirmada"],
        ["RQ05", "Associação fraca ou inversa entre frequência e CFR", "Contradita"],
        ["RQ06", "Características associadas às métricas DORA", "Parcialmente confirmada"],
        ["RQ07", "Parte das categorias muda com a definição", "Confirmada"],
    ]
    story.extend(
        [
            styled_table(hypothesis_rows, [35, 255, 195]),
            NextPageTemplate("TwoColumn"),
            PageBreak(),
            section("2", "Metodologia"),
            subsection("2.1", "Delineamento e amostra"),
            para(
                "O estudo observacional usa dados públicos da API REST, GraphQL e do protocolo Git. "
                "A janela inclusiva vai de 01/10/2025 a 30/09/2026. Entraram candidatos com pelo "
                "menos 1.000 estrelas, GitHub Actions, cinco releases principais e 50 runs válidos "
                "de push no branch padrão. A ordem pseudoaleatória usa semente 42. Dos 922 candidatos "
                "processados, 163 não tinham Actions, 393 tinham releases insuficientes, 60 não "
                "atingiram o mínimo de runs e seis falharam na coleta; 300 foram incluídos."
            ),
            subsection("2.2", "Definições operacionais"),
            para(
                "Deployment frequency é o número de releases principais por semana. O lead time por "
                "release usa o commit mais antigo de cada comparação; a variante por commit usa a "
                "mediana de todos os commits. O CFR de CI é falhas/(falhas+sucessos). O CFR por "
                "entrega identifica uma release falha quando a próxima release, em até sete dias, é "
                "classificada como corretiva. O tempo de recuperação liga a primeira falha após um "
                "sucesso ao próximo sucesso do mesmo workflow. Episódios abertos permanecem "
                "censurados."
            ),
            subsection("2.3", "Análise estatística"),
            para(
                "As RQ01-RQ04 usam mediana e IQR. A RQ05 aplica correlação de Spearman. Na RQ06, "
                "cinco fatores - estrelas, contribuidores, idade, linguagem e tipo de projeto - são "
                "comparados com quatro métricas por Kruskal-Wallis ou Mann-Whitney. Os 20 p-valores "
                "recebem correção de Holm [4], e cada teste informa epsilon quadrado ou delta de "
                "Cliff. A RQ07 compara quatro cenários por percentual de mudança e kappa de Cohen "
                "ponderado."
            ),
            FrameBreak(),
            subsection("2.4", "Validação e consenso"),
            para(
                "A amostra-ouro contém 60 repositórios e 300 releases. A planilha de Flavio foi "
                "produzida com apoio da pré-classificação por IA; a de Luidi foi independente. Logo, "
                "as duas não são apresentadas como dois julgamentos humanos cegos. Em divergências, "
                "o consenso adotou a avaliação independente de Luidi. Esse desvio do protocolo "
                "planejado é reportado como ameaça interna."
            ),
        ]
    )
    validation_rows = [
        ["Dimensão", "Acordo", "Fleiss"],
        ["Tipo", "88,3%", "0,827"],
        ["Entrega", "98,3%", "0,658"],
        ["Corretiva", "51,0%", "-0,163"],
    ]
    story.extend(
        [
            styled_table(validation_rows, [118, 57, 57]),
            para(
                "A heurística v1 (patch SemVer ou fix/hotfix/revert) obteve precisão 0,484, recall "
                "0,986 e F1 0,649. Quatro refinamentos produziram F1 entre 0,257 e 0,649; nenhum "
                "atingiu 0,70. A v1 foi mantida por melhor F1, com interpretação exploratória."
            ),
            subsection("2.5", "Engenharia e reprodutibilidade"),
            para(
                "O pipeline possui paginação, cache comprimido, checkpoint SQLite, retomada, rate "
                "limit compartilhado, backoff exponencial e coleta concorrente. A configuração fixa "
                "janela, filtros, semente e meta. Os CSVs e o dicionário documentam unidades e "
                "fórmulas. A suíte possui 130 testes, executados sem rede, com 95,5% de cobertura do "
                "módulo de métricas."
            ),
            subsection("2.6", "Classificação DORA"),
            para(
                "Cada métrica recebe Elite, High, Medium ou Low pelos limiares do protocolo. A classe "
                "geral é a mediana das quatro notas, arredondada para baixo, e fica ausente se alguma "
                "métrica não puder ser calculada."
            ),
            NextPageTemplate("Wide"),
            PageBreak(),
            section("3", "Resultados"),
            subsection("3.1", "RQ01 a RQ04 - desempenho de referência"),
        ]
    )
    metric_rows = [
        ["Métrica", "n", "Mediana", "IQR", "Distribuição DORA"],
        metric_row(descriptive, "deployment_frequency_per_week", "E 7 | H 64 | M 139 | L 90"),
        metric_row(descriptive, "lead_time_release_median_hours", "E 48 | H 71 | M 87 | L 94"),
        metric_row(descriptive, "lead_time_commit_median_hours", "Variante obrigatória"),
        metric_row(descriptive, "ci_change_failure_rate", "E 236 | H 41 | M 5 | L 18"),
        metric_row(descriptive, "release_change_failure_rate", "Proxy exploratório"),
        metric_row(descriptive, "median_recovery_hours", "E 69 | H 167 | M 35 | L 10"),
        metric_row(descriptive, "censored_episodes_proportion", "18 sem proporção"),
    ]
    story.extend(
        [
            styled_table(metric_rows, [150, 32, 70, 120, 120]),
            Spacer(1, 2 * mm),
            figure(
                FIGURES / "fig1_funnel_dora.png",
                "Figura 1. Funil de seleção e classificação geral de referência C1. Dezenove "
                "repositórios ficaram sem classe geral por ausência de recuperação.",
                FRAME_WIDTH,
            ),
            para(
                "<b>RQ01.</b> A mediana de 0,422 release/semana (IQR 0,211-0,964) coloca a categoria "
                "Medium como a mais frequente, mas 90 projetos ficaram em Low. <b>RQ02.</b> O lead "
                "time por release foi 260,12 h (IQR 75,91-998,06), contra 275,78 h (IQR "
                "69,78-1.039,11) por commit. A variante por release foi maior em 178 pares, menor em "
                "121 e igual em um. <b>RQ03.</b> O CFR de CI foi 6,30%, muito abaixo do CFR por "
                "entrega de 43,48%; a baixa validade da heurística limita a segunda variante. "
                "<b>RQ04.</b> Entre 281 projetos com recuperação, a mediana foi 3,54 h e 236 (84,0%) "
                "ficaram abaixo de 24 h."
            ),
            subsection("3.2", "RQ05 - frequência e taxa de falha"),
            figure(
                FIGURES / "fig2_rq02_rq05.png",
                "Figura 2. Dispersões em escala logarítmica. A correlação entre frequência e CFR "
                "é fraca para CI e forte para a heurística de releases corretivas.",
                FRAME_WIDTH,
            ),
            para(
                "O CFR de CI apresentou associação positiva fraca com frequência (rho=0,131; "
                "p=0,0228; n=300). O CFR por entrega apresentou associação positiva forte "
                "(rho=0,662; p<0,001; n=299). A hipótese de relação fraca ou inversa foi contradita, "
                "mas a diferença entre proxies impede interpretar o segundo coeficiente como "
                "instabilidade de produção."
            ),
            subsection("3.3", "RQ06 - fatores associados"),
        ]
    )
    significant = rq06[rq06["significant_holm"]].sort_values("p_value_holm")
    rq06_rows = [["Fator", "Métrica", "p Holm", "Efeito", "Magnitude"]]
    for _, row in significant.iterrows():
        rq06_rows.append(
            [
                row["factor_label"],
                row["metric_label"],
                f"{row['p_value_holm']:.3g}",
                f"{row['effect_size']:.3f}",
                row["effect_magnitude"],
            ]
        )

    scenario_short = {
        "C1_ref_LT_release_CFR_CI": "C1",
        "C2_LT_commit_CFR_release": "C2",
        "C3_LT_commit_CFR_CI": "C3",
        "C4_LT_release_CFR_release": "C4",
    }
    sensitivity_rows = [["Comparação", "n", "Mudaram", "%", "Kappa ponderado"]]
    for _, row in sensitivity.iterrows():
        sensitivity_rows.append(
            [
                f"{scenario_short[row['scenario_a']]} x {scenario_short[row['scenario_b']]}",
                str(int(row["n"])),
                str(int(row["changed_count"])),
                f"{100 * row['changed_proportion']:.1f}%",
                f"{row['weighted_cohen_kappa']:.3f}",
            ]
        )

    heuristic_rows = [["Versão", "Precisão", "Recall", "F1", "Resultado"]]
    for item in heuristic_evaluations:
        heuristic_rows.append(
            [
                item["heuristic"]["version"],
                f"{item['precision']:.3f}",
                f"{item['recall']:.3f}",
                f"{item['f1']:.3f}",
                "refinar" if item["refinement_required"] else "aceita",
            ]
        )
    story.extend(
        [
            styled_table(rq06_rows, [105, 155, 75, 70, 80]),
            Spacer(1, 2 * mm),
            figure(
                FIGURES / "fig3_rq06_effects.png",
                "Figura 3. Mapa de calor dos tamanhos de efeito. O asterisco marca associações que "
                "permaneceram significativas após a correção de Holm.",
                0.78 * FRAME_WIDTH,
            ),
            para(
                "Idade foi o fator mais forte: projetos no quartil mais novo tiveram frequência "
                "mediana de 0,777/semana e lead time de 86,73 h, contra 0,288/semana e 865,61 h no "
                "quartil mais antigo. Linguagem se associou a frequência e lead time; contribuidores, "
                "apenas ao lead time. Popularidade e tipo de projeto não permaneceram significativos."
            ),
            subsection("3.4", "RQ07 - análise de sensibilidade"),
            para(
                "C1 combina lead time por release e CFR de CI; C2, lead time por commit e CFR por "
                "release; C3, lead time por commit e CFR de CI; C4, lead time por release e CFR por "
                "release. Deployment frequency e recuperação permanecem constantes."
            ),
            figure(
                FIGURES / "fig4_rq07_sensitivity.png",
                "Figura 4. Distribuição das categorias e comparação par a par. A troca isolada do "
                "lead time (C1-C3) muda 15,7%; a troca isolada do CFR (C1-C4), 39,6%.",
                FRAME_WIDTH,
            ),
            para(
                "A maior diferença ocorreu entre C1 e C2: 48,6% dos 280 casos completos mudaram de "
                "categoria, com kappa ponderado 0,305. C1-C3 apresentou 15,7% e kappa 0,785; C1-C4, "
                "39,6% e kappa 0,446. Portanto, a classificação é relativamente robusta à variante "
                "de lead time, mas sensível à escolha do proxy de falha."
            ),
            styled_table(sensitivity_rows, [95, 45, 65, 65, 115]),
            Spacer(1, 2 * mm),
            NextPageTemplate("Mixed"),
            PageBreak(),
            subsection("3.5", "Qualidade dos rótulos e da heurística"),
            figure(
                FIGURES / "fig5_validation.png",
                "Figura 5. Concordância das planilhas e desempenho das cinco versões da heurística. "
                "Nenhuma versão atingiu a meta de F1=0,70.",
                0.80 * FRAME_WIDTH,
            ),
            styled_table(heuristic_rows, [135, 75, 75, 65, 80]),
            para(
                "A v1 maximizou recall, porém gerou 145 falsos positivos. A regra somente de patch "
                "elevou a precisão para 0,621, mas perdeu 48 corretivas. A ausência de uma versão "
                "acima de 0,70 reforça que notas e convenções de versão variam entre projetos."
            ),
            FrameBreak(),
            section("4", "Discussão"),
            para(
                "A amostra combina velocidade moderada, lead time de aproximadamente 11 dias, baixo "
                "CFR de CI e recuperação em poucas horas. O perfil geral C1 concentra 247 projetos "
                "em Medium ou High. Isso não significa que os projetos possuam o mesmo desempenho em "
                "produção: releases de bibliotecas e runs de CI representam fenômenos diferentes de "
                "deploys e incidentes de serviços."
            ),
            para(
                "A divergência mais importante está na estabilidade. O DORA relata que throughput e "
                "estabilidade frequentemente avançam juntos em equipes de alto desempenho [2, 7]. "
                "Aqui, frequência e CFR de CI tiveram associação positiva, porém fraca. A associação "
                "forte com CFR por entrega parece incompatível com essa leitura, mas depende de uma "
                "heurística com baixo acordo e F1. O contraste é evidência sobre a limitação do proxy, "
                "não uma refutação direta dos estudos DORA."
            ),
            para(
                "Idade, linguagem e contribuidores se associaram a algumas métricas. Projetos mais "
                "novos entregaram com maior frequência e menor lead time, mas o delineamento não "
                "identifica causa. Ecossistema, arquitetura, governança e estratégia de versionamento "
                "podem explicar parte das diferenças."
            ),
            section("5", "Ameaças à validade"),
            subsection("5.1", "Construto"),
            para(
                "Release não é necessariamente deploy, falha de CI não é falha em produção e patch "
                "SemVer não é sinônimo de correção. O F1 máximo de 0,649 e a mudança de 39,6% ao "
                "trocar somente o CFR quantificam essa ameaça."
            ),
            subsection("5.2", "Interna"),
            para(
                "O estudo não controla maturidade, equipe, domínio ou estratégia de release. Datas de "
                "autor podem ser distorcidas por rebase e squash. A planilha de Flavio foi assistida "
                "por IA e não constitui avaliação cega; o consenso privilegiou o único julgamento "
                "independente nas divergências."
            ),
            subsection("5.3", "Externa"),
            para(
                "A amostra inclui apenas projetos públicos, populares, com Actions e volume mínimo de "
                "releases e runs. Os resultados não se generalizam automaticamente a projetos "
                "privados, pequenos, sem releases formais ou fora do GitHub."
            ),
            subsection("5.4", "Conclusão"),
            para(
                "Mediana, IQR e testes não paramétricos reduzem o impacto de assimetria e extremos. "
                "A correção de Holm controla comparações múltiplas, mas subgrupos da amostra rotulada "
                "têm tamanho reduzido. Ausência e censura foram preservadas, evitando imputação como "
                "zero, mas reduzem o número de casos completos."
            ),
            section("6", "Replicação cruzada"),
            para(
                "Até a consolidação deste artigo, o professor não havia fornecido ao grupo o pipeline "
                "sorteado de outra equipe nem a subamostra externa de 30 repositórios. A replicação "
                "cruzada e eventuais Issues recebidas, portanto, não foram inventadas. O protocolo "
                "preparado registra ambiente limpo, execução apenas pelo README, diferença relativa "
                "por métrica, percentual de classes iguais e Issues com evidências. Esta seção deve "
                "ser atualizada assim que a atribuição externa for disponibilizada."
            ),
            section("7", "Conclusão"),
            para(
                "O pipeline caracterizou 300 repositórios com rastreabilidade e resultados "
                "reexecutáveis. A definição de referência descreve desempenho majoritariamente "
                "Medium/High e recuperação rápida, mas a estabilidade por release não se mostrou "
                "confiável. O achado central é metodológico: em mineração de métricas DORA no GitHub, "
                "a definição operacional pode alterar substancialmente a categoria final, logo toda "
                "comparação deve publicar proxies, censura e sensibilidade."
            ),
            section("8", "Artefatos e links"),
            para(
                "Repositório: <link href='https://github.com/flaviojuniordev/Software-Measurement-and-Experimentation' "
                "color='#147D78'>github.com/flaviojuniordev/Software-Measurement-and-Experimentation</link><br/>"
                "GitHub Projects: <link href='https://github.com/flaviojuniordev/Software-Measurement-and-Experimentation/projects' "
                "color='#147D78'>página de projetos do repositório</link><br/>"
                "Comando de análise: <font name='Courier'>python -m analysis.analyze_lab03</font>"
            ),
            para("Referências", "section"),
        ]
    )
    references = [
        "[1] DORA. <i>A history of DORA's software delivery metrics</i>. 2026. "
        "https://dora.dev/insights/dora-metrics-history/.",
        "[2] DORA. <i>DORA's software delivery metrics: the four keys</i>. "
        "https://dora.dev/guides/dora-metrics-four-keys/.",
        "[3] Landis, J. R.; Koch, G. G. The measurement of observer agreement for "
        "categorical data. <i>Biometrics</i>, 33(1), 159-174, 1977. PMID 843571.",
        "[4] Holm, S. A simple sequentially rejective multiple test procedure. "
        "<i>Scandinavian Journal of Statistics</i>, 6, 65-70, 1979. DOI 10.2307/4615733.",
        "[5] Wohlin, C. et al. <i>Experimentation in Software Engineering</i>. Springer, "
        "2012. DOI 10.1007/978-3-642-29044-2.",
        "[6] GitHub. <i>REST API documentation</i>. https://docs.github.com/en/rest.",
        "[7] DORA. <i>Accelerate State of DevOps Report 2024</i>. "
        "https://dora.dev/research/2024/dora-report/2024-dora-accelerate-state-of-devops-report.pdf.",
    ]
    story.extend(para(reference, "reference") for reference in references)
    story.extend(
        [
            FrameBreak(),
            para("Síntese para apresentação", "section"),
            para(
                "Os números abaixo concentram a resposta de cada bloco do estudo e podem ser usados "
                "como apoio durante a apresentação oral.",
                "body_small",
            ),
            styled_table(
                [
                    ["Indicador", "Resultado"],
                    ["Funil", "922 processados; 300 incluídos"],
                    ["Frequência", "0,422 release/semana"],
                    ["Lead time", "260,12 h por release"],
                    ["CFR de CI", "6,30%"],
                    ["Recuperação", "3,54 h; 84% abaixo de 24 h"],
                    ["DORA C1", "18 E; 112 H; 135 M; 16 L; 19 ausentes"],
                    ["RQ05", "rho 0,131 (CI); 0,662 (release)"],
                    ["RQ06", "idade, linguagem e contribuidores"],
                    ["RQ07", "39,6% mudam ao trocar somente o CFR"],
                    ["Validação", "melhor F1 = 0,649"],
                ],
                [78, 157],
            ),
            Spacer(1, 3 * mm),
            para("Mensagem central", "subsection"),
            para(
                "O pipeline é reexecutável e a amostra é ampla, mas os resultados mostram que uma "
                "classificação DORA minerada do GitHub depende fortemente do proxy escolhido. O CFR "
                "por release não deve ser apresentado como falha real de produção.",
                "callout",
            ),
            Spacer(1, 3 * mm),
            para("Pendência externa", "subsection"),
            para(
                "A replicação cruzada só pode ser concluída após o professor informar o pipeline do "
                "outro grupo. O protocolo já está preparado no repositório.",
                "body_small",
            ),
        ]
    )
    return story


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = build_document()
    document.build(build_story())
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
