#!/usr/bin/env python3
"""
Interface Tkinter do Lab01.

O app carrega output/coleta_1000.csv, resume as RQs 01-07, valida a coleta,
permite consultar os dados e pode disparar os scripts de coleta e snapshot.
"""

from __future__ import annotations

import csv
import json
import os
import queue
import statistics
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "output" / "coleta_1000.csv"
DEFAULT_SNAPSHOT = BASE_DIR / "snapshots" / "lab01s02_project_snapshot.csv"
QUERY_SCRIPT = BASE_DIR / "query.py"
PROJECT_SNAPSHOT_SCRIPT = BASE_DIR / "project_snapshot.py"

REQUIRED_COLUMNS = {
    "repository_rank",
    "name_with_owner",
    "url",
    "stargazer_count",
    "created_at",
    "age_days",
    "merged_pull_requests",
    "releases_count",
    "updated_at",
    "days_since_update",
    "primary_language",
    "issues_total",
    "issues_closed",
    "closed_issues_ratio",
}

COLORS = {
    "bg": "#eef2f7",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "border": "#d8dee9",
    "text": "#172033",
    "muted": "#5d6678",
    "primary": "#2563eb",
    "primary_dark": "#1d4ed8",
    "success": "#0f766e",
    "success_bg": "#e6f6f2",
    "hero": "#111827",
    "hero_alt": "#1f2937",
    "row_alt": "#f3f6fb",
    "selected": "#dbeafe",
}


def as_int(value: str) -> int | None:
    if value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def as_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def fmt_number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%".replace(".", ",")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV sem cabecalho.")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(missing)}")
        return list(reader)


def language_name(row: dict[str, str]) -> str:
    return row["primary_language"] or "Sem linguagem detectada"


def values_for(rows: list[dict[str, str]], column: str) -> list[float]:
    return [value for row in rows if (value := as_float(row[column])) is not None]


def analyze_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    names = [row["name_with_owner"] for row in rows]
    ranks = [as_int(row["repository_rank"]) for row in rows]
    ages = values_for(rows, "age_days")
    prs = values_for(rows, "merged_pull_requests")
    releases = values_for(rows, "releases_count")
    update_days = values_for(rows, "days_since_update")
    ratios = values_for(rows, "closed_issues_ratio")

    problems: list[str] = []
    if len(rows) != 1000:
        problems.append(f"Esperados 1000 repositorios; CSV possui {len(rows)}.")
    if len(set(names)) != len(names):
        problems.append("Ha repositorios duplicados no CSV.")
    if ranks != list(range(1, len(rows) + 1)):
        problems.append("repository_rank nao esta sequencial a partir de 1.")

    missing_language = 0
    missing_ratio = 0
    low_closed_ratio: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        repo_name = row["name_with_owner"] or f"linha {index}"
        issues_total = as_int(row["issues_total"])
        issues_closed = as_int(row["issues_closed"])
        closed_ratio = as_float(row["closed_issues_ratio"])

        for column in ("age_days", "merged_pull_requests", "releases_count", "days_since_update"):
            value = as_float(row[column])
            if value is None or value < 0:
                problems.append(f"{repo_name}: {column} ausente ou invalido.")

        if not row["primary_language"]:
            missing_language += 1

        if issues_total is None or issues_closed is None:
            problems.append(f"{repo_name}: contagens de issues ausentes ou invalidas.")
            continue
        if issues_total < 0 or issues_closed < 0:
            problems.append(f"{repo_name}: contagem de issues negativa.")
        if issues_closed > issues_total:
            problems.append(f"{repo_name}: issues fechadas maior que total de issues.")
        if closed_ratio is None:
            missing_ratio += 1
            if issues_total != 0:
                problems.append(f"{repo_name}: closed_issues_ratio ausente com issues_total > 0.")
        else:
            if issues_total == 0:
                problems.append(f"{repo_name}: closed_issues_ratio preenchido com issues_total = 0.")
            if closed_ratio < 0 or closed_ratio > 1:
                problems.append(f"{repo_name}: closed_issues_ratio fora de 0..1.")
            if closed_ratio < 0.5:
                low_closed_ratio.append(row)

    by_language: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_language.setdefault(language_name(row), []).append(row)

    language_rows = []
    for language, language_repos in by_language.items():
        language_rows.append(
            {
                "language": language,
                "count": len(language_repos),
                "median_prs": median(values_for(language_repos, "merged_pull_requests")),
                "median_releases": median(values_for(language_repos, "releases_count")),
                "median_update_days": median(values_for(language_repos, "days_since_update")),
            }
        )
    language_rows.sort(key=lambda item: item["count"], reverse=True)

    return {
        "total": len(rows),
        "unique": len(set(names)),
        "ranks_ok": ranks == list(range(1, len(rows) + 1)),
        "collected_at": rows[0].get("collected_at", "n/a") if rows else "n/a",
        "median_age": median(ages),
        "median_prs": median(prs),
        "median_releases": median(releases),
        "median_update_days": median(update_days),
        "median_ratio": median(ratios),
        "missing_language": missing_language,
        "missing_ratio": missing_ratio,
        "problems": problems,
        "language_rows": language_rows,
        "top_prs": sorted(
            rows, key=lambda row: as_int(row["merged_pull_requests"]) or 0, reverse=True
        )[:10],
        "top_releases": sorted(
            rows, key=lambda row: as_int(row["releases_count"]) or 0, reverse=True
        )[:10],
        "oldest": sorted(rows, key=lambda row: as_float(row["age_days"]) or 0, reverse=True)[:10],
        "stale": sorted(
            rows, key=lambda row: as_float(row["days_since_update"]) or 0, reverse=True
        )[:10],
        "low_closed_ratio": low_closed_ratio[:10],
    }


class Lab01App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lab01 - Repositorios populares")
        self.geometry("1120x740")
        self.minsize(820, 620)

        self.csv_path = tk.StringVar(value=str(DEFAULT_CSV))
        self.status_text = tk.StringVar(value="Carregue o CSV para iniciar.")
        self.search_text = tk.StringVar()
        self.language_filter = tk.StringVar(value="Todas")
        self.project_owner = tk.StringVar(value=os.environ.get("GITHUB_PROJECT_OWNER", ""))
        self.project_number = tk.StringVar(value=os.environ.get("GITHUB_PROJECT_NUMBER", ""))
        self.project_owner_type = tk.StringVar(value=os.environ.get("GITHUB_PROJECT_OWNER_TYPE", "user"))
        self.snapshot_path = tk.StringVar(value=str(DEFAULT_SNAPSHOT))
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.process_running = False
        self.rows: list[dict[str, str]] = []
        self.filtered_rows: list[dict[str, str]] = []
        self.repository_page = 0
        self.repository_page_size = tk.IntVar(value=50)
        self.repository_page_text = tk.StringVar(value="Pagina 0/0")
        self.analysis: dict[str, Any] | None = None
        self.summary_card_vars = {
            "total": tk.StringVar(value="n/a"),
            "unique": tk.StringVar(value="n/a"),
            "median_prs": tk.StringVar(value="n/a"),
            "median_ratio": tk.StringVar(value="n/a"),
        }

        self._build_style()
        self._build_layout()
        self.after(250, self._drain_log_queue)

        if DEFAULT_CSV.is_file():
            self.load_csv()

    def _build_style(self) -> None:
        self.configure(bg=COLORS["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Surface.TFrame", background=COLORS["surface"], relief=tk.FLAT)
        style.configure("Hero.TFrame", background=COLORS["hero"])
        style.configure("Toolbar.TFrame", background=COLORS["surface"])
        style.configure("Panel.TFrame", background=COLORS["surface"], relief=tk.FLAT)
        style.configure("Card.TFrame", background=COLORS["surface_alt"], relief=tk.FLAT)
        style.configure(
            "Header.TLabel",
            font=("TkDefaultFont", 18, "bold"),
            foreground=COLORS["text"],
            background=COLORS["bg"],
        )
        style.configure(
            "HeroTitle.TLabel",
            font=("TkDefaultFont", 20, "bold"),
            foreground="#ffffff",
            background=COLORS["hero"],
        )
        style.configure(
            "HeroSubtitle.TLabel",
            font=("TkDefaultFont", 11),
            foreground="#cbd5e1",
            background=COLORS["hero"],
        )
        style.configure(
            "PanelTitle.TLabel",
            font=("TkDefaultFont", 12, "bold"),
            foreground=COLORS["text"],
            background=COLORS["surface"],
        )
        style.configure(
            "CardLabel.TLabel",
            font=("TkDefaultFont", 9, "bold"),
            foreground=COLORS["muted"],
            background=COLORS["surface_alt"],
        )
        style.configure(
            "CardValue.TLabel",
            font=("TkDefaultFont", 20, "bold"),
            foreground=COLORS["text"],
            background=COLORS["surface_alt"],
        )
        style.configure(
            "Subtle.TLabel",
            foreground=COLORS["muted"],
            background=COLORS["bg"],
        )
        style.configure(
            "PanelSubtle.TLabel",
            foreground=COLORS["muted"],
            background=COLORS["surface"],
        )
        style.configure(
            "Status.TLabel",
            foreground=COLORS["success"],
            background=COLORS["success_bg"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.configure(
            "Step.TLabel",
            font=("TkDefaultFont", 11, "bold"),
            foreground=COLORS["text"],
            background=COLORS["surface"],
        )
        style.configure(
            "StepNumber.TLabel",
            font=("TkDefaultFont", 11, "bold"),
            foreground="#ffffff",
            background=COLORS["primary"],
            padding=(8, 4),
        )
        style.configure("TButton", padding=(10, 7), font=("TkDefaultFont", 10))
        style.map("TButton", background=[("active", COLORS["surface_alt"])])
        style.configure(
            "Primary.TButton",
            padding=(12, 10),
            font=("TkDefaultFont", 11, "bold"),
            foreground="#ffffff",
            background=COLORS["primary"],
            bordercolor=COLORS["primary"],
        )
        style.map(
            "Primary.TButton",
            background=[("active", COLORS["primary_dark"]), ("pressed", COLORS["primary_dark"])],
            foreground=[("disabled", "#e5e7eb"), ("!disabled", "#ffffff")],
        )
        style.configure(
            "Danger.TButton",
            padding=(10, 7),
            foreground="#991b1b",
            background="#fee2e2",
            bordercolor="#fecaca",
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#fecaca"), ("pressed", "#fecaca")],
            foreground=[("!disabled", "#991b1b")],
        )
        style.configure(
            "TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
            tabmargins=(0, 6, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            padding=(14, 9),
            font=("TkDefaultFont", 10, "bold"),
            background="#dce3ee",
            foreground=COLORS["muted"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["surface"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure(
            "Treeview",
            rowheight=28,
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=("TkDefaultFont", 10, "bold"),
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            relief=tk.FLAT,
        )
        style.map("Treeview", background=[("selected", COLORS["selected"])])

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=14, style="App.TFrame")
        root.pack(fill=tk.BOTH, expand=True)

        hero = ttk.Frame(root, padding=16, style="Hero.TFrame")
        hero.pack(fill=tk.X)
        ttk.Label(hero, text="Lab01 - Repositorios populares", style="HeroTitle.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            hero,
            text="Coleta GraphQL, CSV de 1.000 repositorios, validacao das RQs e snapshot do Project",
            style="HeroSubtitle.TLabel",
        ).pack(anchor=tk.W, pady=(5, 0))

        ttk.Label(root, textvariable=self.status_text, style="Status.TLabel", padding=8).pack(
            fill=tk.X, pady=(12, 10)
        )

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_collection_tab()
        self._build_summary_tab()
        self.rq_tree = self._add_tree_tab(
            "RQs",
            ("rq", "metric", "result", "note"),
            ("RQ", "Metrica", "Resultado", "Leitura"),
            (80, 220, 180, 560),
        )
        self.validation_tree = self._add_tree_tab(
            "Validacao",
            ("status", "detail"),
            ("Status", "Detalhe"),
            (160, 840),
        )
        self.language_tree = self._add_tree_tab(
            "Linguagens e RQ07",
            ("language", "count", "prs", "releases", "update"),
            ("Linguagem", "Repos", "Mediana PRs", "Mediana releases", "Mediana atualizacao (dias)"),
            (260, 90, 140, 150, 210),
        )
        self._build_repositories_tab()
        self._build_project_tab()
        self._build_log_tab()

    def _build_collection_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=14, style="App.TFrame")
        self.notebook.add(frame, text="Coleta")

        intro = ttk.Frame(frame, padding=14, style="Panel.TFrame")
        intro.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(intro, text="Fluxo de uso da interface", style="PanelTitle.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            intro,
            text=(
                "Busque os 1.000 repositorios na API do GitHub, gere o CSV da sprint "
                "e navegue pelas abas de analise sem sair da interface."
            ),
            style="PanelSubtle.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W, pady=(6, 0))

        steps = ttk.Frame(frame, style="App.TFrame")
        steps.pack(fill=tk.X)
        step_texts = (
            ("1", "Configure GITHUB_TOKEN", "Use .env ou variavel de ambiente antes de coletar."),
            ("2", "Clique em Coletar 1000", "A interface executa query.py --limit 1000."),
            ("3", "CSV gerado", "Arquivo salvo em output/coleta_1000.csv, compativel com Excel."),
            ("4", "Analise as abas", "Resumo, RQs, Validacao, Linguagens/RQ07, Repositorios e Project."),
        )
        for number, title, detail in step_texts:
            row = ttk.Frame(steps, padding=12, style="Panel.TFrame")
            row.pack(fill=tk.X, pady=(0, 6))
            ttk.Label(row, text=number, style="StepNumber.TLabel", width=3, anchor=tk.CENTER).pack(
                side=tk.LEFT, anchor=tk.N, padx=(0, 12)
            )
            text_box = ttk.Frame(row, style="Panel.TFrame")
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Label(text_box, text=title, style="Step.TLabel").pack(anchor=tk.W)
            ttk.Label(text_box, text=detail, style="PanelSubtle.TLabel", wraplength=680).pack(
                anchor=tk.W, pady=(3, 0)
            )

        actions = ttk.Frame(frame, padding=12, style="Panel.TFrame")
        actions.pack(fill=tk.X, pady=(4, 10))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        collect_button = ttk.Button(
            actions,
            text="Coletar 1000 repos e gerar CSV",
            style="Primary.TButton",
            command=self.collect_1000,
        )
        collect_button.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        ttk.Button(actions, text="Carregar CSV", command=self.load_csv).grid(
            row=1, column=0, sticky=tk.EW, padx=(0, 4)
        )
        ttk.Button(actions, text="Escolher CSV", command=self.choose_csv).grid(
            row=1, column=1, sticky=tk.EW, padx=(4, 0)
        )
        ttk.Button(
            actions,
            text="Limpar dados e CSV",
            style="Danger.TButton",
            command=self.clear_loaded_data,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))

        csv_box = ttk.Frame(frame, padding=12, style="Panel.TFrame")
        csv_box.pack(fill=tk.X, pady=(2, 10))
        ttk.Label(csv_box, text="Arquivo CSV da coleta", style="PanelTitle.TLabel").pack(anchor=tk.W)
        ttk.Entry(csv_box, textvariable=self.csv_path).pack(fill=tk.X, pady=(6, 0))

        ttk.Label(
            frame,
            text=(
                "Durante a coleta, acompanhe o progresso na aba Log. "
                "Ao terminar, o CSV e recarregado automaticamente e as abas de analise sao atualizadas."
            ),
            style="Subtle.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W)

    def _build_summary_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=18, style="App.TFrame")
        self.notebook.add(frame, text="Resumo")

        cards = ttk.Frame(frame, style="App.TFrame")
        cards.pack(fill=tk.X, pady=(0, 14))
        card_specs = (
            ("total", "REPOSITORIOS COLETADOS"),
            ("unique", "REPOSITORIOS UNICOS"),
            ("median_prs", "MEDIANA DE PRS"),
            ("median_ratio", "MEDIANA ISSUES FECHADAS"),
        )
        for column, (key, label) in enumerate(card_specs):
            card = ttk.Frame(cards, padding=16, style="Card.TFrame")
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            cards.columnconfigure(column, weight=1)
            ttk.Label(card, text=label, style="CardLabel.TLabel").pack(anchor=tk.W)
            ttk.Label(card, textvariable=self.summary_card_vars[key], style="CardValue.TLabel").pack(
                anchor=tk.W, pady=(8, 0)
            )

        detail = ttk.Frame(frame, padding=14, style="Panel.TFrame")
        detail.pack(fill=tk.BOTH, expand=True)
        ttk.Label(detail, text="Resumo completo da coleta", style="PanelTitle.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            detail,
            text="Indicadores consolidados usados para validar o CSV e apoiar o texto das RQs.",
            style="PanelSubtle.TLabel",
        ).pack(anchor=tk.W, pady=(4, 10))
        self.summary_tree = self._tree_widget(
            detail,
            ("metric", "value"),
            ("Metrica", "Valor"),
            (440, 280),
        )
        self.summary_tree.pack(fill=tk.BOTH, expand=True)

    def _add_tree_tab(
        self,
        label: str,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        widths: tuple[int, ...],
    ) -> ttk.Treeview:
        frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.notebook.add(frame, text=label)
        tree = self._tree_widget(frame, columns, headings, widths)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        return tree

    def _tree_widget(
        self,
        parent: tk.Widget,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        widths: tuple[int, ...],
    ) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        tree.tag_configure("odd", background=COLORS["surface"])
        tree.tag_configure("even", background=COLORS["row_alt"])
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor=tk.W)
        return tree

    def _build_repositories_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=14, style="App.TFrame")
        self.notebook.add(frame, text="Repositorios")

        controls = ttk.Frame(frame, padding=14, style="Panel.TFrame")
        controls.pack(fill=tk.X, pady=(0, 12))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        ttk.Label(controls, text="Busca:", style="PanelSubtle.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8), pady=3
        )
        ttk.Entry(controls, textvariable=self.search_text, width=24).grid(
            row=0, column=1, sticky=tk.EW, padx=(0, 12), pady=3
        )
        ttk.Label(controls, text="Linguagem:", style="PanelSubtle.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=(0, 8), pady=3
        )
        self.language_combo = ttk.Combobox(
            controls,
            textvariable=self.language_filter,
            values=("Todas",),
            state="readonly",
            width=20,
        )
        self.language_combo.grid(row=0, column=3, sticky=tk.EW, pady=3)
        ttk.Label(controls, text="Itens por pagina:", style="PanelSubtle.TLabel").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(8, 3)
        )
        ttk.Spinbox(
            controls,
            from_=25,
            to=200,
            increment=25,
            textvariable=self.repository_page_size,
            width=6,
            command=self.apply_repository_filters,
        ).grid(row=1, column=1, sticky=tk.W, pady=(8, 3))
        ttk.Button(controls, text="Filtrar", command=self.apply_repository_filters).grid(
            row=1, column=3, sticky=tk.E, pady=(8, 3)
        )

        table_panel = ttk.Frame(frame, padding=10, style="Panel.TFrame")
        table_panel.pack(fill=tk.BOTH, expand=True)
        self.repository_tree = self._tree_widget(
            table_panel,
            ("rank", "repo", "language", "age", "prs", "releases", "update", "ratio"),
            ("Rank", "Repositorio", "Linguagem", "Idade", "PRs", "Releases", "Atualizacao", "% issues"),
            (70, 330, 160, 90, 90, 100, 110, 100),
        )
        self.repository_tree.pack(fill=tk.BOTH, expand=True)

        pagination = ttk.Frame(frame, padding=(0, 10, 0, 0), style="Panel.TFrame")
        pagination.pack(fill=tk.X)
        ttk.Button(pagination, text="Primeira", command=self.first_repository_page).pack(side=tk.LEFT)
        ttk.Button(pagination, text="Anterior", command=self.previous_repository_page).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Label(pagination, textvariable=self.repository_page_text).pack(side=tk.LEFT, padx=10)
        ttk.Button(pagination, text="Proxima", command=self.next_repository_page).pack(side=tk.LEFT)
        ttk.Button(pagination, text="Ultima", command=self.last_repository_page).pack(
            side=tk.LEFT, padx=6
        )

    def _build_project_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=18, style="App.TFrame")
        self.notebook.add(frame, text="Project")

        form = ttk.Frame(frame, padding=16, style="Panel.TFrame")
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Snapshot do GitHub Projects", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )
        ttk.Label(form, text="Owner:", style="PanelSubtle.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.project_owner, width=24).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Label(form, text="Tipo:", style="PanelSubtle.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Combobox(
            form,
            textvariable=self.project_owner_type,
            values=("user", "org"),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Label(form, text="Numero do Project:", style="PanelSubtle.TLabel").grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        ttk.Entry(form, textvariable=self.project_number, width=12).grid(row=3, column=1, sticky=tk.W, pady=5)
        ttk.Label(form, text="CSV snapshot:", style="PanelSubtle.TLabel").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.snapshot_path, width=40).grid(row=4, column=1, sticky=tk.EW, pady=5)

        actions = ttk.Frame(frame, padding=(0, 12, 0, 0), style="App.TFrame")
        actions.pack(fill=tk.X)
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="Escolher saida", command=self.choose_snapshot_path).grid(
            row=0, column=0, sticky=tk.EW, padx=(0, 4)
        )
        ttk.Button(actions, text="Exportar snapshot", command=self.export_project_snapshot).grid(
            row=0, column=1, sticky=tk.EW, padx=(4, 0)
        )

        help_panel = ttk.Frame(frame, padding=14, style="Panel.TFrame")
        help_panel.pack(fill=tk.X, pady=(18, 0))
        help_text = (
            "O snapshot usa GitHub Projects v2 e exige token com permissao read:project. "
            "O CSV exportado serve como evidencia do estado do board ao fechar a sprint."
        )
        ttk.Label(help_panel, text=help_text, style="PanelSubtle.TLabel", wraplength=720).pack(
            fill=tk.X
        )

    def _build_log_tab(self) -> None:
        frame = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.notebook.add(frame, text="Log")
        self.log_text = tk.Text(
            frame,
            height=12,
            wrap=tk.WORD,
            bg="#0f172a",
            fg="#d1fae5",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=12,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def choose_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Escolher CSV da coleta",
            initialdir=str(DEFAULT_CSV.parent),
            filetypes=(("CSV", "*.csv"), ("Todos os arquivos", "*.*")),
        )
        if path:
            self.csv_path.set(path)
            self.load_csv()

    def choose_snapshot_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Salvar snapshot do Project",
            initialdir=str(DEFAULT_SNAPSHOT.parent),
            initialfile=DEFAULT_SNAPSHOT.name,
            defaultextension=".csv",
            filetypes=(("CSV", "*.csv"), ("Todos os arquivos", "*.*")),
        )
        if path:
            self.snapshot_path.set(path)

    def load_csv(self) -> None:
        path = Path(self.csv_path.get()).expanduser()
        try:
            self.rows = load_rows(path)
            self.analysis = analyze_rows(self.rows)
        except Exception as exc:
            messagebox.showerror("Erro ao carregar CSV", str(exc))
            self.status_text.set("Erro ao carregar CSV.")
            return

        self.render_summary()
        self.render_rqs()
        self.render_validation()
        self.render_languages()
        self.update_language_filter()
        self.apply_repository_filters()
        status = "OK" if not self.analysis["problems"] else "Atencao"
        self.status_text.set(
            f"{status}: {self.analysis['total']} repositorios, "
            f"{self.analysis['unique']} unicos, coletado em {self.analysis['collected_at']}."
        )

    def clear_loaded_data(self) -> None:
        if self.process_running:
            messagebox.showinfo("Processo em andamento", "Aguarde o processo atual terminar.")
            return

        should_clear = messagebox.askyesno(
            "Limpar dados",
            (
                "Isto vai limpar os dados carregados na interface e apagar "
                f"o CSV padrao:\n\n{DEFAULT_CSV}\n\nDeseja continuar?"
            ),
        )
        if not should_clear:
            return

        self.rows = []
        self.filtered_rows = []
        self.analysis = None
        self.repository_page = 0
        self.csv_path.set(str(DEFAULT_CSV))
        self.repository_page_text.set("Pagina 0/0")
        self.language_filter.set("Todas")
        self.language_combo["values"] = ("Todas",)
        self.search_text.set("")
        for value in self.summary_card_vars.values():
            value.set("n/a")

        for tree in (
            self.summary_tree,
            self.rq_tree,
            self.validation_tree,
            self.language_tree,
            self.repository_tree,
        ):
            self._clear_tree(tree)

        if DEFAULT_CSV.is_file():
            try:
                DEFAULT_CSV.unlink()
                self.log(f"CSV removido: {DEFAULT_CSV}")
            except OSError as exc:
                messagebox.showerror("Erro ao remover CSV", str(exc))
                self.status_text.set("Nao foi possivel remover o CSV.")
                return

        self.status_text.set(
            "Dados limpos. Clique em 'Coletar 1000 repositorios e gerar CSV' para recriar a coleta."
        )

    def render_summary(self) -> None:
        analysis = self._analysis()
        self._clear_tree(self.summary_tree)
        self.summary_card_vars["total"].set(fmt_number(analysis["total"]))
        self.summary_card_vars["unique"].set(fmt_number(analysis["unique"]))
        self.summary_card_vars["median_prs"].set(fmt_number(analysis["median_prs"]))
        self.summary_card_vars["median_ratio"].set(fmt_percent(analysis["median_ratio"]))
        rows = (
            ("Repositorios coletados", fmt_number(analysis["total"])),
            ("Repositorios unicos", fmt_number(analysis["unique"])),
            ("Ranks sequenciais", "sim" if analysis["ranks_ok"] else "nao"),
            ("Mediana idade RQ01 (dias)", fmt_number(analysis["median_age"])),
            ("Mediana PRs RQ02", fmt_number(analysis["median_prs"])),
            ("Mediana releases RQ03", fmt_number(analysis["median_releases"])),
            ("Mediana ultima atualizacao RQ04 (dias)", fmt_number(analysis["median_update_days"])),
            ("Mediana issues fechadas RQ06", fmt_percent(analysis["median_ratio"])),
            ("Repositorios sem linguagem RQ05", fmt_number(analysis["missing_language"])),
            ("Repositorios sem razao RQ06", fmt_number(analysis["missing_ratio"])),
        )
        for row in rows:
            self.summary_tree.insert("", tk.END, values=row)
        self._apply_zebra(self.summary_tree)

    def render_rqs(self) -> None:
        analysis = self._analysis()
        self._clear_tree(self.rq_tree)
        rows = (
            ("RQ01", "Idade do repositorio", f"{fmt_number(analysis['median_age'])} dias", "Mediana indica maturidade da amostra."),
            ("RQ02", "PRs aceitas", fmt_number(analysis["median_prs"]), "Mediana resume contribuicao externa."),
            ("RQ03", "Total de releases", fmt_number(analysis["median_releases"]), "Zeros e outliers devem ser revisados."),
            ("RQ04", "Dias desde update", fmt_number(analysis["median_update_days"]), "Valores altos indicam repositorios menos ativos."),
            ("RQ05", "Linguagem primaria", f"{fmt_number(analysis['missing_language'])} sem linguagem", "Comparar com fonte definida no relatorio."),
            ("RQ06", "% issues fechadas", fmt_percent(analysis["median_ratio"]), "Casos sem issues ficam sem razao."),
            ("RQ07", "Comparacao por linguagem", "ver aba Linguagens", "Usar PRs, releases e atualizacao por linguagem."),
        )
        for row in rows:
            self.rq_tree.insert("", tk.END, values=row)
        self._apply_zebra(self.rq_tree)

    def render_validation(self) -> None:
        analysis = self._analysis()
        self._clear_tree(self.validation_tree)
        if not analysis["problems"]:
            checks = (
                "CSV possui 1.000 repositorios.",
                "Nao ha repositorios duplicados.",
                "repository_rank esta sequencial.",
                "Campos numericos essenciais estao validos.",
                "closed_issues_ratio vazio aparece apenas sem issues.",
            )
            for check in checks:
                self.validation_tree.insert("", tk.END, values=("OK", check))
            self._apply_zebra(self.validation_tree)
            return
        for problem in analysis["problems"]:
            self.validation_tree.insert("", tk.END, values=("Revisar", problem))
        self._apply_zebra(self.validation_tree)

    def render_languages(self) -> None:
        analysis = self._analysis()
        self._clear_tree(self.language_tree)
        for item in analysis["language_rows"]:
            self.language_tree.insert(
                "",
                tk.END,
                values=(
                    item["language"],
                    fmt_number(item["count"]),
                    fmt_number(item["median_prs"]),
                    fmt_number(item["median_releases"]),
                    fmt_number(item["median_update_days"]),
                ),
            )
        self._apply_zebra(self.language_tree)

    def update_language_filter(self) -> None:
        languages = ["Todas"] + [item["language"] for item in self._analysis()["language_rows"]]
        self.language_combo["values"] = tuple(languages)
        if self.language_filter.get() not in languages:
            self.language_filter.set("Todas")

    def render_repository_rows(self) -> None:
        self._clear_tree(self.repository_tree)
        page_size = self.normalized_repository_page_size()
        total_rows = len(self.filtered_rows)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        self.repository_page = min(max(self.repository_page, 0), total_pages - 1)
        start = self.repository_page * page_size
        end = start + page_size
        page_rows = self.filtered_rows[start:end]

        for row in page_rows:
            self.repository_tree.insert(
                "",
                tk.END,
                values=(
                    row["repository_rank"],
                    row["name_with_owner"],
                    language_name(row),
                    fmt_number(as_float(row["age_days"])),
                    fmt_number(as_float(row["merged_pull_requests"])),
                    fmt_number(as_float(row["releases_count"])),
                    fmt_number(as_float(row["days_since_update"])),
                    fmt_percent(as_float(row["closed_issues_ratio"])),
                ),
            )
        self._apply_zebra(self.repository_tree)
        if total_rows == 0:
            self.repository_page_text.set("Nenhum repositorio encontrado")
        else:
            self.repository_page_text.set(
                f"Pagina {self.repository_page + 1}/{total_pages} "
                f"- mostrando {start + 1}-{min(end, total_rows)} de {total_rows}"
            )

    def apply_repository_filters(self) -> None:
        term = self.search_text.get().strip().lower()
        selected_language = self.language_filter.get()
        rows = self.rows
        if term:
            rows = [row for row in rows if term in row["name_with_owner"].lower()]
        if selected_language != "Todas":
            rows = [row for row in rows if language_name(row) == selected_language]
        self.filtered_rows = rows
        self.repository_page = 0
        self.render_repository_rows()

    def normalized_repository_page_size(self) -> int:
        try:
            page_size = int(self.repository_page_size.get())
        except (tk.TclError, ValueError):
            page_size = 50
        page_size = min(max(page_size, 1), 500)
        if page_size != self.repository_page_size.get():
            self.repository_page_size.set(page_size)
        return page_size

    def first_repository_page(self) -> None:
        self.repository_page = 0
        self.render_repository_rows()

    def previous_repository_page(self) -> None:
        self.repository_page -= 1
        self.render_repository_rows()

    def next_repository_page(self) -> None:
        self.repository_page += 1
        self.render_repository_rows()

    def last_repository_page(self) -> None:
        page_size = self.normalized_repository_page_size()
        total_rows = len(self.filtered_rows)
        self.repository_page = max(0, (total_rows + page_size - 1) // page_size - 1)
        self.render_repository_rows()

    def collect_1000(self) -> None:
        if self.process_running:
            messagebox.showinfo("Processo em andamento", "Ja existe um processo rodando.")
            return
        self._run_process([sys.executable, str(QUERY_SCRIPT), "--limit", "1000"], "Coleta")

    def export_project_snapshot(self) -> None:
        if self.process_running:
            messagebox.showinfo("Processo em andamento", "Ja existe um processo rodando.")
            return
        if not PROJECT_SNAPSHOT_SCRIPT.is_file():
            messagebox.showerror("Erro", f"Script nao encontrado: {PROJECT_SNAPSHOT_SCRIPT}")
            return
        owner = self.project_owner.get().strip()
        project_number = self.project_number.get().strip()
        if not owner or not project_number:
            messagebox.showerror("Erro", "Informe owner e numero do Project.")
            return
        command = [
            sys.executable,
            str(PROJECT_SNAPSHOT_SCRIPT),
            "--owner",
            owner,
            "--owner-type",
            self.project_owner_type.get(),
            "--project-number",
            project_number,
            "--output",
            self.snapshot_path.get(),
        ]
        self._run_process(command, "Snapshot")

    def _run_process(self, command: list[str], label: str) -> None:
        self.process_running = True
        self.status_text.set(f"{label} em andamento. Acompanhe pela aba Log.")
        self.log("$ " + " ".join(command))
        thread = threading.Thread(target=self._process_worker, args=(command, label), daemon=True)
        thread.start()

    def _process_worker(self, command: list[str], label: str) -> None:
        process = subprocess.Popen(
            command,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            self.log_queue.put(line.rstrip())
        self.log_queue.put(f"__PROCESS_DONE__:{label}:{process.wait()}")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line.startswith("__PROCESS_DONE__:"):
                    self.process_running = False
                    _marker, label, return_code_text = line.split(":", 2)
                    return_code = int(return_code_text)
                    if return_code == 0:
                        self.status_text.set(f"{label} finalizado.")
                        if label == "Coleta":
                            self.csv_path.set(str(DEFAULT_CSV))
                            self.load_csv()
                    else:
                        self.status_text.set(f"{label} falhou com codigo {return_code}.")
                    continue
                self.log(line)
        except queue.Empty:
            pass
        self.after(250, self._drain_log_queue)

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _analysis(self) -> dict[str, Any]:
        if self.analysis is None:
            raise RuntimeError("Analise ainda nao carregada.")
        return self.analysis

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def _apply_zebra(self, tree: ttk.Treeview) -> None:
        for index, item in enumerate(tree.get_children()):
            tree.item(item, tags=("even" if index % 2 else "odd",))


def main() -> None:
    app = Lab01App()
    app.mainloop()


if __name__ == "__main__":
    main()
