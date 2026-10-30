"""Interface desktop da Bancada, feita apenas com Tkinter e ttk."""

from __future__ import annotations

import re
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable


BG = "#F4F6F8"
SURFACE = "#FFFFFF"
NAVY = "#142738"
NAVY_LIGHT = "#233E50"
INK = "#203345"
MUTED = "#637685"
BORDER = "#DFE6EB"
TEAL = "#087F7E"
TEAL_LIGHT = "#E4F3F0"
AMBER = "#A56113"
RED = "#B43D41"
STATUS = {
    "aberta": "Aberta",
    "em_andamento": "Em andamento",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
}
PRIORITIES = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}
EXPECTED_ERRORS = (ValueError, OSError, sqlite3.Error)


def format_money(cents: int) -> str:
    """Formata dinheiro sem passar por ponto flutuante."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"R$ {sign}{whole:,}".replace(",", ".") + f",{fraction:02d}"


def parse_money(text: str) -> int:
    """Aceita 125,50, 1.250,50 e 125.50; retorna centavos inteiros."""
    cleaned = text.strip().removeprefix("R$").strip()
    if not cleaned:
        raise ValueError("Informe um valor. Use 0,00 quando não houver custo.")
    brazilian = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
    decimal_point = r"\d+(?:\.\d{1,2})?"
    if re.fullmatch(brazilian, cleaned):
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif re.fullmatch(decimal_point, cleaned):
        normalized = cleaned
    else:
        raise ValueError("Valor inválido. Use um número positivo, como 125,50.")
    try:
        return int(Decimal(normalized) * 100)
    except (InvalidOperation, OverflowError) as error:
        raise ValueError("Não foi possível interpretar o valor informado.") from error


def parse_integer(text: str, label: str, minimum: int = 0) -> int:
    if not re.fullmatch(r"\d+", text.strip()):
        raise ValueError(f"{label}: informe um número inteiro, sem casas decimais.")
    result = int(text)
    if result < minimum:
        raise ValueError(f"{label}: o valor mínimo é {minimum}.")
    return result


def money_input(cents: int) -> str:
    return f"{cents // 100},{cents % 100:02d}"


def format_date(value: str | None) -> str:
    if not value:
        return "Não informado"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def order_number(identifier: int) -> str:
    return f"OS {identifier:04d}"


@dataclass
class Field:
    key: str
    label: str
    kind: str = "entry"
    value: Any = ""
    choices: list[tuple[str, Any]] | None = None
    hint: str = ""
    required: bool = True


class Modal(tk.Toplevel):
    def __init__(self, app: "Bancada", title: str, subtitle: str = "", parent=None):
        super().__init__(parent or app.root)
        self.withdraw()
        self.app = app
        self.configure(bg=SURFACE)
        self.title(title + " | Bancada")
        self.transient(parent or app.root)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        header = tk.Frame(self, bg=SURFACE, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text=title, bg=SURFACE, fg=INK,
                 font=("Segoe UI", 17, "bold"), anchor="w").pack(fill="x")
        if subtitle:
            tk.Label(header, text=subtitle, bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 10), anchor="w", wraplength=850).pack(fill="x", pady=(5, 0))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self.body = tk.Frame(self, bg=SURFACE, padx=24, pady=18)
        self.footer = tk.Frame(self, bg=BG, padx=24, pady=14)
        self.footer.pack(side="bottom", fill="x")
        self.body.pack(fill="both", expand=True)

    def show(self, width: int = 560, height: int | None = None):
        self.update_idletasks()
        height = height or self.winfo_reqheight()
        height = min(height, self.winfo_screenheight() - 90)
        width = min(width, self.winfo_screenwidth() - 60)
        x = max(0, self.app.root.winfo_x() + (self.app.root.winfo_width() - width) // 2)
        y = max(10, self.app.root.winfo_y() + (self.app.root.winfo_height() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.grab_set()
        self.focus_set()
        self.wait_window()

    def destroy(self):
        parent = self.master
        super().destroy()
        if isinstance(parent, tk.Toplevel) and parent.winfo_exists():
            parent.grab_set()


class FormDialog(Modal):
    def __init__(self, app: "Bancada", title: str, subtitle: str,
                 fields: list[Field], submit: Callable[[dict], Any],
                 success: str, parent=None, after_save: Callable | None = None,
                 button_text: str = "Salvar"):
        super().__init__(app, title, subtitle, parent)
        self.fields = fields
        self.inputs: dict[str, Any] = {}
        self.submit = submit
        self.success = success
        self.after_save = after_save
        self.body.columnconfigure(0, weight=1)
        row = 0
        for field in fields:
            label = field.label + (" *" if field.required else "")
            tk.Label(self.body, text=label, bg=SURFACE, fg=INK,
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(
                         row=row, column=0, sticky="ew", pady=(0 if row == 0 else 13, 5))
            row += 1
            if field.kind == "text":
                widget = tk.Text(self.body, height=3, wrap="word", relief="solid", bd=1,
                                 bg=SURFACE, fg=INK, insertbackground=INK,
                                 highlightthickness=1, highlightbackground=BORDER,
                                 highlightcolor=TEAL, font=("Segoe UI", 10), padx=10, pady=8)
                widget.insert("1.0", str(field.value))
                widget.bind("<Tab>", self._next_field)
            elif field.kind == "select":
                labels = [label for label, _value in field.choices or []]
                widget = ttk.Combobox(self.body, values=labels, state="readonly")
                for index, (_label, value) in enumerate(field.choices or []):
                    if value == field.value:
                        widget.current(index)
                        break
                if widget.current() == -1 and labels:
                    widget.current(0)
            else:
                widget = ttk.Entry(self.body)
                widget.insert(0, str(field.value))
            widget.grid(row=row, column=0, sticky="ew")
            self.inputs[field.key] = widget
            row += 1
            if field.hint:
                tk.Label(self.body, text=field.hint, bg=SURFACE, fg=MUTED,
                         font=("Segoe UI", 9), anchor="w", justify="left", wraplength=520).grid(
                             row=row, column=0, sticky="ew", pady=(4, 0))
                row += 1
        ttk.Button(self.footer, text=button_text, style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(self.footer, text="Voltar", command=self.destroy).pack(side="right", padx=(0, 10))
        tk.Label(self.footer, text="* Campos obrigatórios", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self.bind("<Control-Return>", lambda _event: self.save())
        self.after_idle(lambda: next(iter(self.inputs.values())).focus_set() if self.inputs else None)

    @staticmethod
    def _next_field(event):
        event.widget.tk_focusNext().focus_set()
        return "break"

    def save(self):
        values = {}
        for field in self.fields:
            widget = self.inputs[field.key]
            if field.kind == "text":
                value = widget.get("1.0", "end-1c").strip()
            elif field.kind == "select":
                index = widget.current()
                value = field.choices[index][1] if index >= 0 else None
            else:
                value = widget.get().strip()
            if field.required and (value is None or (isinstance(value, str) and not value)):
                messagebox.showwarning("Campo obrigatório", f"Preencha {field.label.lower()}.", parent=self)
                widget.focus_set()
                return
            values[field.key] = value
        try:
            if self.submit(values) is False:
                return
        except EXPECTED_ERRORS as error:
            messagebox.showerror("Não foi possível salvar", str(error), parent=self)
            return
        self.destroy()
        self.app.refresh(self.success)
        if self.after_save:
            self.after_save()


class Bancada:
    PAGES = {
        "overview": ("Visão geral", "Acompanhe o atendimento e o que precisa da sua atenção."),
        "orders": ("Ordens de serviço", "Do diagnóstico à resolução, com peças e histórico no mesmo lugar."),
        "equipment": ("Equipamentos", "Organize os ativos e acompanhe suas ordens de manutenção."),
        "stock": ("Estoque de peças", "Controle entradas, consumo e os itens próximos do mínimo."),
    }

    def __init__(self, root: tk.Tk, service, demo: bool = False):
        self.root = root
        self.service = service
        self.demo = demo
        self.page = "overview"
        self.search = {page: tk.StringVar() for page in self.PAGES}
        self.order_filter = tk.StringVar(value="Todas as situações")
        self.include_inactive = tk.BooleanVar(value=True)
        self.stock_low_only = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="Pronto. Os dados ficam salvos neste computador.")
        self.nav_buttons = {}
        self.tables = {}
        root.title("Bancada | Manutenção e estoque" + (" | Demonstração" if demo else ""))
        width = min(1220, root.winfo_screenwidth() - 80)
        height = min(900, root.winfo_screenheight() - 100)
        root.geometry(f"{width}x{height}")
        root.minsize(1000, 680)
        root.configure(bg=BG)
        self._styles()
        self._shell()
        self.show_page("overview")

    def _styles(self):
        self.root.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("TButton", font=("Segoe UI", 10), foreground=INK, background=SURFACE,
                        bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                        padding=(14, 9), focuscolor=TEAL)
        style.map("TButton", background=[("active", "#EAF0F3"), ("disabled", "#F0F2F3")],
                  foreground=[("disabled", "#94A0A9")])
        style.configure("Accent.TButton", background=TEAL, foreground="white", bordercolor=TEAL,
                        lightcolor=TEAL, darkcolor=TEAL, font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#096967"), ("disabled", "#A8C3C2")],
                  foreground=[("disabled", "#F4FAFA")])
        style.configure("Danger.TButton", foreground=RED)
        style.configure("TEntry", fieldbackground=SURFACE, foreground=INK,
                        bordercolor=BORDER, padding=(9, 8))
        style.map("TEntry", bordercolor=[("focus", TEAL)])
        style.configure("TCombobox", padding=(9, 8), fieldbackground=SURFACE,
                        background=SURFACE, foreground=INK, arrowcolor=MUTED, bordercolor=BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
                  foreground=[("readonly", INK)], selectbackground=[("readonly", SURFACE)],
                  selectforeground=[("readonly", INK)])
        style.configure("TCheckbutton", background=BG, foreground=MUTED)
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=37,
                        background=SURFACE, fieldbackground=SURFACE, foreground=INK,
                        borderwidth=0, bordercolor=SURFACE)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(10, 11),
                        background="#EEF2F5", foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected", "#D7ECE8")], foreground=[("selected", "#075B58")])
        style.map("Treeview.Heading", background=[("active", "#E4EBEF")])
        style.configure("TNotebook", background=SURFACE, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=(18, 10),
                        background=BG, foreground=MUTED)
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", TEAL)])

    def _shell(self):
        sidebar = tk.Frame(self.root, bg=NAVY, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=NAVY, padx=24, pady=28)
        brand.pack(fill="x")
        tk.Label(brand, text="bancada", bg=NAVY, fg="white", font=("Segoe UI", 26, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(brand, text="MANUTENÇÃO E ESTOQUE", bg=NAVY, fg="#8FA9B9",
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(2, 0))
        tk.Frame(sidebar, bg="#2B4152", height=1).pack(fill="x", padx=22, pady=(0, 22))
        for index, (key, (title, _subtitle)) in enumerate(self.PAGES.items(), 1):
            button = tk.Button(sidebar, text=f"{index:02d}   {title}", anchor="w", relief="flat",
                               bd=0, padx=20, pady=14, bg=NAVY, fg="#C7D5DE",
                               activebackground=NAVY_LIGHT, activeforeground="white",
                               cursor="hand2", font=("Segoe UI", 10),
                               command=self.command(lambda page=key: self.show_page(page)))
            button.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = button
        bottom = tk.Frame(sidebar, bg=NAVY, padx=24, pady=24)
        bottom.pack(side="bottom", fill="x")
        if self.demo:
            tk.Label(bottom, text="DEMONSTRAÇÃO", bg="#244C51", fg="#9BE0D3",
                     font=("Segoe UI", 9, "bold"), padx=8, pady=7).pack(anchor="w", pady=(0, 12))
        tk.Label(bottom, text="Dados locais\nUma bancada, tudo em dia.", bg=NAVY, fg="#8FA9B9",
                 font=("Segoe UI", 9), justify="left").pack(anchor="w")
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=SURFACE, padx=28, pady=13)
        top.pack(fill="x")
        tk.Label(top, text="PAINEL DE OPERAÇÕES", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(top, text="Backup", command=self.command(self.backup)).pack(side="right")
        ttk.Button(top, text="Exportar ordens", command=self.command(self.export)).pack(side="right", padx=(0, 8))
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")
        footer = tk.Frame(right, bg=SURFACE, padx=28, pady=9)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, textvariable=self.status_text, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.content = tk.Frame(right, bg=BG, padx=28, pady=22)
        self.content.pack(fill="both", expand=True)

    def command(self, action: Callable):
        def wrapped(*_args):
            try:
                return action()
            except EXPECTED_ERRORS as error:
                messagebox.showerror("Não foi possível concluir", str(error), parent=self.root)
        return wrapped

    def show_page(self, page: str):
        self.page = page
        for child in self.content.winfo_children():
            child.destroy()
        self.tables.clear()
        for key, button in self.nav_buttons.items():
            button.configure(bg=NAVY_LIGHT if key == page else NAVY,
                             fg="white" if key == page else "#C7D5DE",
                             font=("Segoe UI", 10, "bold" if key == page else "normal"))
        title, subtitle = self.PAGES[page]
        heading = tk.Frame(self.content, bg=BG)
        heading.pack(fill="x", pady=(0, 20))
        self.heading_actions = tk.Frame(heading, bg=BG)
        self.heading_actions.pack(side="right", padx=(16, 0))
        tk.Label(heading, text=title, bg=BG, fg=INK,
                 font=("Segoe UI", 23, "bold"), anchor="w").pack(fill="x")
        tk.Label(heading, text=subtitle, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), anchor="w", wraplength=680).pack(fill="x", pady=(4, 0))
        getattr(self, f"page_{page}")()

    def refresh(self, message: str = "Dados atualizados."):
        self.show_page(self.page)
        self.status_text.set(message)

    def heading_button(self, text: str, command: Callable, primary: bool = True):
        ttk.Button(self.heading_actions, text=text, style="Accent.TButton" if primary else "TButton",
                   command=self.command(command)).pack(side="right", padx=(8, 0))

    @staticmethod
    def card(parent, title: str = "", subtitle: str = ""):
        frame = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        if title:
            head = tk.Frame(frame, bg=SURFACE, padx=18, pady=14)
            head.pack(fill="x")
            tk.Label(head, text=title, bg=SURFACE, fg=INK, font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x")
            if subtitle:
                tk.Label(head, text=subtitle, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
                         anchor="w").pack(fill="x", pady=(3, 0))
        return frame

    @staticmethod
    def table(parent, columns: list[tuple[str, str, int]], height: int = 8):
        frame = tk.Frame(parent, bg=SURFACE)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=[key for key, _name, _width in columns],
                            show="headings", selectmode="browse", height=height)
        for key, name, width in columns:
            tree.heading(key, text=name, anchor="w")
            tree.column(key, width=width, minwidth=min(width, 70), anchor="w", stretch=True)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree.tag_configure("alternate", background="#F8FAFB")
        tree.tag_configure("attention", foreground=RED)
        tree.tag_configure("inactive", foreground="#82919D")
        return tree

    @staticmethod
    def insert(tree, identifier, values, index, tags=()):
        tree.insert("", "end", iid=str(identifier), values=values,
                    tags=(("alternate",) if index % 2 else ()) + tuple(tags))

    def selected(self, tree, name: str, parent=None):
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Selecione um registro", f"Selecione {name} na tabela.", parent=parent or self.root)
            return None
        return int(selected[0])

    def search_bar(self, page: str, placeholder: str):
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", pady=(0, 14))
        tk.Label(toolbar, text=placeholder, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
        line = tk.Frame(toolbar, bg=BG)
        line.pack(fill="x")
        entry = ttk.Entry(line, textvariable=self.search[page], width=29)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", self.command(lambda: self.refresh("Pesquisa atualizada.")))
        ttk.Button(line, text="Buscar", command=self.command(lambda: self.refresh("Pesquisa atualizada."))).pack(side="left", padx=(8, 0))
        ttk.Button(line, text="Limpar", command=self.command(lambda: self.clear_search(page))).pack(side="left", padx=(8, 0))
        return line

    def clear_search(self, page):
        self.search[page].set("")
        self.refresh()

    @staticmethod
    def empty_message(parent, message):
        tk.Label(parent, text=message, bg=SURFACE, fg=MUTED, padx=18, pady=12,
                 font=("Segoe UI", 10), anchor="w", justify="left", wraplength=760).pack(fill="x")

    def page_overview(self):
        data = self.service.dashboard()
        self.heading_button("Nova ordem", self.new_order)
        viewport = tk.Canvas(self.content, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.content, orient="vertical", command=viewport.yview)
        viewport.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        viewport.pack(side="left", fill="both", expand=True)
        overview = tk.Frame(viewport, bg=BG)
        window = viewport.create_window((0, 0), window=overview, anchor="nw")
        viewport.bind("<Configure>", lambda event: viewport.itemconfigure(window, width=event.width))
        overview.bind("<Configure>", lambda _event: viewport.configure(scrollregion=viewport.bbox("all")))
        metrics = tk.Frame(overview, bg=BG)
        metrics.pack(fill="x", pady=(0, 16))
        values = [
            ("ORDENS ATIVAS", str(data["open_count"]), f'{data["in_progress_count"]} em atendimento', TEAL),
            ("PRAZO VENCIDO", str(data["overdue_count"]), "Entre as ordens ativas", RED if data["overdue_count"] else INK),
            ("ESTOQUE BAIXO", str(data["low_stock_count"]), "Itens no mínimo ou abaixo", AMBER if data["low_stock_count"] else INK),
            ("CUSTO CONCLUÍDO", format_money(data["total_closed_cents"]), f'{data["closed_count"]} ordens concluídas', INK),
        ]
        for index, (label, value, hint, color) in enumerate(values):
            metrics.columnconfigure(index, weight=1, uniform="metrics")
            frame = self.card(metrics)
            frame.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0 if index == 3 else 6))
            tk.Label(frame, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold"),
                     anchor="w").pack(fill="x", padx=15, pady=(14, 5))
            tk.Label(frame, text=value, bg=SURFACE, fg=color,
                     font=("Segoe UI", 23 if index < 3 else 17, "bold"), anchor="w").pack(fill="x", padx=15)
            tk.Label(frame, text=hint, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x", padx=15, pady=(4, 14))
        charts = tk.Frame(overview, bg=BG, height=225)
        charts.pack(fill="x", pady=(0, 16))
        charts.grid_propagate(False)
        charts.columnconfigure(0, weight=3, uniform="charts")
        charts.columnconfigure(1, weight=2, uniform="charts")
        charts.rowconfigure(0, weight=1)
        chart = self.card(charts, "Atendimentos concluídos", "Quantidade por mês nos últimos seis meses")
        chart.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        canvas = tk.Canvas(chart, bg=SURFACE, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        canvas.bind("<Configure>", lambda _event: self.draw_chart(canvas, data["monthly"]))
        ranking = self.card(charts, "Maiores custos de manutenção", "Valores das ordens concluídas")
        ranking.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        if not data["top_equipment"]:
            self.empty_message(ranking, "O ranking aparece após o primeiro atendimento.")
        for index, item in enumerate(data["top_equipment"][:3], 1):
            line = tk.Frame(ranking, bg=SURFACE, padx=18, pady=8)
            line.pack(fill="x")
            tk.Label(line, text=f"{index:02d}", bg=TEAL_LIGHT, fg=TEAL,
                     font=("Segoe UI", 10, "bold"), padx=6, pady=4).pack(side="left", padx=(0, 10))
            tk.Label(line, text=format_money(item["total_cents"]), bg=SURFACE, fg=INK,
                     font=("Segoe UI", 9, "bold")).pack(side="right")
            tk.Label(line, text=f'{item["tag"]}  |  {item["order_count"]} OS', bg=SURFACE, fg=INK,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=5)
        average = f'{data["avg_resolution_hours"]:.1f}'.replace(".", ",")
        tk.Label(overview, text=f"Tempo médio até a resolução: {average} horas corridas nas ordens concluídas.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0, 12))
        queue = self.card(overview, "Fila de atendimento", "Ordens ativas: abertas e em andamento. Duplo clique para abrir.")
        queue.pack(fill="both", expand=True)
        orders = [row for row in self.service.list_orders() if row["status"] in ("aberta", "em_andamento")][:5]
        if not orders:
            self.empty_message(queue, "Nenhuma ordem ativa. Cadastre um equipamento e abra a primeira ordem para começar.")
        tree = self.table(queue, [("id", "ORDEM", 80), ("equipment", "EQUIPAMENTO", 150),
                                 ("title", "DESCRIÇÃO", 230), ("status", "SITUAÇÃO", 140),
                                 ("due", "PRAZO", 135)], height=3)
        for index, row in enumerate(orders):
            self.insert(tree, row["id"], [order_number(row["id"]), row["equipment_tag"], row["title"],
                        STATUS[row["status"]], format_date(row["due_at"])], index,
                        ("attention",) if row["overdue"] else ())
        tree.bind("<Double-1>", self.command(lambda: self.open_selected_order(tree)))
        tree.bind("<Return>", self.command(lambda: self.open_selected_order(tree)))

    @staticmethod
    def draw_chart(canvas, months):
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 30 or height < 50 or not months:
            return
        left, top, base = 28, 24, height - 30
        usable = max(15, base - top)
        peak = max(1, max(item["count"] for item in months))
        canvas.create_line(left, base, width - 12, base, fill=BORDER)
        step = (width - left - 14) / len(months)
        names = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
        for index, item in enumerate(months):
            middle = left + step * (index + .5)
            bar_width = min(40, step * .55)
            bar_height = usable * item["count"] / peak
            canvas.create_rectangle(middle - bar_width / 2, base - max(2, bar_height),
                                    middle + bar_width / 2, base, fill=TEAL if item["count"] else TEAL_LIGHT, outline="")
            canvas.create_text(middle, base - bar_height - 12, text=str(item["count"]),
                               fill=INK, font=("Segoe UI", 9, "bold"))
            month = item["month"]
            label = names[int(month[5:7]) - 1] + "/" + month[2:4]
            canvas.create_text(middle, base + 16, text=label, fill=MUTED, font=("Segoe UI", 9))

    def page_equipment(self):
        self.heading_button("Novo equipamento", self.new_equipment)
        self.heading_button("Técnicos", self.technicians, False)
        toolbar = self.search_bar("equipment", "Buscar por identificação, nome, categoria ou local")
        ttk.Checkbutton(toolbar, text="Incluir inativos", variable=self.include_inactive,
                        command=self.command(self.refresh)).pack(side="left", padx=(12, 0))
        rows = self.service.list_equipment(self.search["equipment"].get(), self.include_inactive.get())
        panel = self.card(self.content)
        panel.pack(fill="both", expand=True)
        tree = self.table(panel, [("tag", "IDENTIFICAÇÃO", 120), ("name", "EQUIPAMENTO", 200),
                                 ("category", "CATEGORIA", 115), ("location", "LOCAL", 145),
                                 ("active", "SITUAÇÃO", 95), ("orders", "OS ATIVAS", 80)])
        for index, row in enumerate(rows):
            self.insert(tree, row["id"], [row["tag"], row["name"], row["category"], row["location"],
                        "Ativo" if row["active"] else "Inativo", row["open_orders"]], index,
                        () if row["active"] else ("inactive",))
        if not rows:
            self.empty_message(panel, "Nenhum equipamento encontrado. Use Novo equipamento para cadastrar o primeiro ativo.")
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Editar equipamento", command=self.command(lambda: self.edit_equipment(tree))).pack(side="left")
        ttk.Button(actions, text="Ativar / desativar", command=self.command(lambda: self.toggle_equipment(tree))).pack(side="left", padx=8)
        ttk.Button(actions, text="Abrir ordem", style="Accent.TButton", command=self.command(lambda: self.new_order(self.selected(tree, "um equipamento")) if tree.selection() else self.selected(tree, "um equipamento"))).pack(side="right")
        tree.bind("<Double-1>", self.command(lambda: self.edit_equipment(tree)))
        self.tables["equipment"] = tree

    def page_orders(self):
        self.heading_button("Nova ordem", self.new_order)
        toolbar = self.search_bar("orders", "Buscar por equipamento, título ou descrição")
        choice = ttk.Combobox(toolbar, textvariable=self.order_filter, state="readonly", width=18,
                              values=["Todas as situações", *STATUS.values()])
        choice.pack(side="left", padx=(12, 0))
        choice.bind("<<ComboboxSelected>>", self.command(self.refresh))
        status = next((key for key, label in STATUS.items() if label == self.order_filter.get()), "")
        rows = self.service.list_orders(status, self.search["orders"].get())
        panel = self.card(self.content)
        panel.pack(fill="both", expand=True)
        tree = self.table(panel, [("id", "ORDEM", 80), ("equipment", "EQUIPAMENTO", 115),
                                 ("title", "TÍTULO", 190), ("priority", "PRIORIDADE", 95),
                                 ("status", "SITUAÇÃO", 130), ("due", "PRAZO", 130),
                                 ("total", "CUSTO", 100)])
        for index, row in enumerate(rows):
            self.insert(tree, row["id"], [order_number(row["id"]), row["equipment_tag"], row["title"],
                        PRIORITIES[row["priority"]], STATUS[row["status"]], format_date(row["due_at"]),
                        format_money(row["total_cents"])], index, ("attention",) if row["overdue"] else ())
        if not rows:
            self.empty_message(panel, "Nenhuma ordem neste filtro. Use Nova ordem para registrar um atendimento.")
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        tk.Label(actions, text=f"{len(rows)} ordem(ns)  |  Vermelho indica prazo vencido em ordem ativa.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(actions, text="Abrir detalhes", style="Accent.TButton",
                   command=self.command(lambda: self.open_selected_order(tree))).pack(side="right")
        tree.bind("<Double-1>", self.command(lambda: self.open_selected_order(tree)))
        tree.bind("<Return>", self.command(lambda: self.open_selected_order(tree)))
        self.tables["orders"] = tree

    def page_stock(self):
        self.heading_button("Nova peça", self.new_part)
        toolbar = self.search_bar("stock", "Buscar por código ou nome da peça")
        ttk.Checkbutton(toolbar, text="Somente estoque baixo", variable=self.stock_low_only,
                        command=self.command(self.refresh)).pack(side="left", padx=(12, 0))
        rows = self.service.list_parts(self.search["stock"].get())
        if self.stock_low_only.get():
            rows = [row for row in rows if row["low_stock"]]
        panel = self.card(self.content)
        panel.pack(fill="both", expand=True)
        tree = self.table(panel, [("sku", "CÓDIGO", 110), ("name", "PEÇA", 220),
                                 ("stock", "EM ESTOQUE", 95), ("min", "MÍNIMO", 75),
                                 ("cost", "CUSTO UNIT.", 115), ("situation", "SITUAÇÃO", 160)])
        for index, row in enumerate(rows):
            self.insert(tree, row["id"], [row["sku"], row["name"], row["stock"], row["min_stock"],
                        format_money(row["unit_cost_cents"]), "Repor estoque" if row["low_stock"] else "Disponível"],
                        index, ("attention",) if row["low_stock"] else ())
        if not rows:
            self.empty_message(panel, "Nenhuma peça neste filtro. Cadastre uma peça e registre a primeira entrada de estoque.")
        actions = tk.Frame(self.content, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        tk.Label(actions, text="O consumo de peças é registrado dentro da ordem de serviço.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(actions, text="Receber estoque", style="Accent.TButton",
                   command=self.command(lambda: self.receive_stock(tree))).pack(side="right")
        tree.bind("<Double-1>", self.command(lambda: self.receive_stock(tree)))
        self.tables["stock"] = tree

    @staticmethod
    def equipment_fields(row=None):
        row = row or {}
        return [
            Field("tag", "Identificação", value=row.get("tag", ""), hint="Um código único, como NB-014 ou IMP-003."),
            Field("name", "Nome do equipamento", value=row.get("name", "")),
            Field("category", "Categoria", value=row.get("category", "")),
            Field("location", "Local", value=row.get("location", "")),
        ]

    def new_equipment(self):
        FormDialog(self, "Novo equipamento", "Cadastre um ativo para abrir e acompanhar ordens de serviço.",
                   self.equipment_fields(),
                   lambda data: self.service.create_equipment(data["tag"], data["name"], data["category"], data["location"]),
                   "Equipamento cadastrado.", button_text="Cadastrar equipamento").show()

    def edit_equipment(self, tree):
        identifier = self.selected(tree, "um equipamento")
        if identifier is None:
            return
        row = next((item for item in self.service.list_equipment() if item["id"] == identifier), None)
        if row is None:
            raise ValueError("O equipamento não foi encontrado. Atualize a tela.")
        FormDialog(self, "Editar equipamento", f'Identificação atual: {row["tag"]}',
                   self.equipment_fields(row),
                   lambda data: self.service.update_equipment(identifier, data["tag"], data["name"], data["category"], data["location"]),
                   "Equipamento atualizado.").show()

    def toggle_equipment(self, tree):
        identifier = self.selected(tree, "um equipamento")
        if identifier is None:
            return
        row = next((item for item in self.service.list_equipment() if item["id"] == identifier), None)
        if row is None:
            raise ValueError("O equipamento não foi encontrado. Atualize a tela.")
        action = "Desativar" if row["active"] else "Ativar"
        detail = "Não será possível abrir novas ordens enquanto estiver inativo." if row["active"] else "O equipamento poderá receber novas ordens."
        if messagebox.askyesno(f"{action} equipamento", f'{action} {row["tag"]}?\n\n{detail}', parent=self.root):
            self.service.set_equipment_active(identifier, not bool(row["active"]))
            self.refresh(f'Equipamento {row["tag"]} atualizado.')

    def technicians(self):
        dialog = Modal(self, "Técnicos", "Cadastre os responsáveis que poderão assumir um atendimento.")
        tree = self.table(dialog.body, [("name", "NOME", 360), ("active", "SITUAÇÃO", 110)], height=7)

        def reload():
            tree.delete(*tree.get_children())
            for index, row in enumerate(self.service.list_technicians()):
                self.insert(tree, row["id"], [row["name"], "Ativo" if row["active"] else "Inativo"], index)

        def create():
            FormDialog(self, "Novo técnico", "Use o nome pelo qual a pessoa será identificada nas ordens.",
                       [Field("name", "Nome")], lambda data: self.service.create_technician(data["name"]),
                       "Técnico cadastrado.", parent=dialog, after_save=reload,
                       button_text="Cadastrar técnico").show()

        ttk.Button(dialog.footer, text="Novo técnico", style="Accent.TButton", command=self.command(create)).pack(side="right")
        ttk.Button(dialog.footer, text="Fechar", command=dialog.destroy).pack(side="right", padx=(0, 8))
        reload()
        dialog.show(600, 465)

    def new_order(self, equipment_id=None):
        equipment = self.service.list_equipment(include_inactive=False)
        if not equipment:
            messagebox.showinfo("Primeiro, cadastre um equipamento",
                                "Abra Equipamentos e use Novo equipamento. Depois volte para abrir a ordem.", parent=self.root)
            return
        if equipment_id is not None and not any(row["id"] == equipment_id for row in equipment):
            raise ValueError("Ative o equipamento antes de abrir uma ordem.")
        technicians = [row for row in self.service.list_technicians() if row["active"]]
        fields = [
            Field("equipment", "Equipamento", "select", equipment_id or equipment[0]["id"],
                  [(f'{row["tag"]} | {row["name"]}', row["id"]) for row in equipment]),
            Field("title", "Título do atendimento", hint="Resumo do problema em até 120 caracteres."),
            Field("description", "Descrição do problema", "text", hint="Sintomas e contexto do diagnóstico. Até 2.000 caracteres."),
            Field("priority", "Prioridade", "select", "media", [(label, key) for key, label in PRIORITIES.items()],
                  "Prazo a partir da abertura: alta 24 h, média 72 h, baixa 168 h."),
            Field("technician", "Responsável inicial", "select", None,
                  [("Sem responsável", None)] + [(row["name"], row["id"]) for row in technicians], required=False),
        ]
        FormDialog(self, "Nova ordem de serviço", "O prazo é calculado pela prioridade. Todos os dados podem ser consultados no histórico.",
                   fields, lambda data: self.service.open_order(data["equipment"], data["title"], data["description"],
                                                              data["priority"], data["technician"]),
                   "Ordem aberta. Selecione-a na tela Ordens de serviço para iniciar o atendimento.",
                   button_text="Abrir ordem").show(620)

    def open_selected_order(self, tree):
        identifier = self.selected(tree, "uma ordem")
        if identifier is not None:
            OrderDialog(self, identifier).show(1000, 710)

    def new_part(self):
        fields = [
            Field("sku", "Código da peça", hint="Código único para identificar a peça no estoque."),
            Field("name", "Nome da peça"),
            Field("minimum", "Estoque mínimo", value="2", hint="O alerta aparece quando o estoque fica igual ou abaixo deste valor."),
            Field("cost", "Custo unitário de referência (R$)", value="0,00"),
        ]

        def create(data):
            return self.service.create_part(data["sku"], data["name"],
                                            parse_integer(data["minimum"], "Estoque mínimo"), parse_money(data["cost"]))

        FormDialog(self, "Nova peça", "A peça começa com estoque zero. Registre uma entrada após o cadastro.",
                   fields, create, "Peça cadastrada. Use Receber estoque para registrar a primeira entrada.",
                   button_text="Cadastrar peça").show()

    def receive_stock(self, tree):
        identifier = self.selected(tree, "uma peça")
        if identifier is None:
            return
        part = next((row for row in self.service.list_parts() if row["id"] == identifier), None)
        if part is None:
            raise ValueError("A peça não foi encontrada. Atualize a tela.")
        fields = [
            Field("quantity", "Quantidade recebida", value="1"),
            Field("cost", "Custo unitário da entrada (R$)", value=money_input(part["unit_cost_cents"]),
                  hint="Este será o novo custo de referência. Consumos anteriores mantêm o custo original."),
            Field("note", "Origem ou observação", "text", hint="Exemplo: compra para reposição, nota 1234."),
        ]

        def receive(data):
            self.service.receive_stock(identifier, parse_integer(data["quantity"], "Quantidade", 1),
                                       parse_money(data["cost"]), data["note"])

        FormDialog(self, "Receber estoque", f'{part["sku"]} | {part["name"]}\nSaldo atual: {part["stock"]} unidade(s).',
                   fields, receive, "Entrada registrada e saldo atualizado.", button_text="Registrar entrada").show()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Exportar todas as ordens",
                                            initialfile=f"ordens-{datetime.now():%Y%m%d-%H%M%S}.csv",
                                            defaultextension=".csv", filetypes=[("Arquivo CSV", "*.csv")],
                                            confirmoverwrite=False)
        if not path:
            return
        if Path(path).exists():
            raise ValueError("Este arquivo já existe. Escolha outro nome para preservar o conteúdo anterior.")
        quantity = self.service.export_orders(path)
        self.status_text.set(f"{quantity} ordem(ns) exportadas para {Path(path).name}.")
        messagebox.showinfo("Exportação concluída", f"{quantity} ordem(ns) exportadas.\n\n{path}\n\nO arquivo inclui todas as ordens, independentemente do filtro da tela.", parent=self.root)

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Salvar cópia do banco de dados",
                                            initialfile=f"bancada-backup-{datetime.now():%Y%m%d-%H%M%S}.sqlite3",
                                            defaultextension=".sqlite3", filetypes=[("Banco SQLite", "*.sqlite3")],
                                            confirmoverwrite=False)
        if not path:
            return
        if Path(path).exists():
            raise ValueError("Este arquivo já existe. Escolha outro nome para manter o backup anterior.")
        self.service.backup(path)
        self.status_text.set(f"Backup verificado e salvo em {Path(path).name}.")
        messagebox.showinfo("Backup concluído", f"A cópia do banco foi criada e verificada.\n\n{path}", parent=self.root)


class OrderDialog(Modal):
    def __init__(self, app: Bancada, identifier: int):
        self.identifier = identifier
        self.order = app.service.get_order(identifier)
        super().__init__(app, order_number(identifier), "Detalhes do atendimento, peças utilizadas e registro das operações.")
        self.body.configure(padx=20, pady=14)
        self.summary = tk.Frame(self.body, bg=SURFACE)
        self.summary.pack(fill="x", pady=(0, 14))
        self.heading = tk.StringVar()
        self.situation = tk.StringVar()
        tk.Label(self.summary, textvariable=self.situation, bg=TEAL_LIGHT, fg=TEAL,
                 font=("Segoe UI", 10, "bold"), padx=12, pady=7).pack(side="right")
        tk.Label(self.summary, textvariable=self.heading, bg=SURFACE, fg=INK,
                 font=("Segoe UI", 13, "bold"), anchor="w", wraplength=690).pack(fill="x", padx=(0, 12))
        self.notebook = ttk.Notebook(self.body)
        self.notebook.pack(fill="both", expand=True)
        self.tab_details = tk.Frame(self.notebook, bg=SURFACE, padx=16, pady=16)
        self.tab_parts = tk.Frame(self.notebook, bg=SURFACE, padx=16, pady=16)
        self.tab_events = tk.Frame(self.notebook, bg=SURFACE, padx=16, pady=16)
        self.notebook.add(self.tab_details, text="Atendimento")
        self.notebook.add(self.tab_parts, text="Peças utilizadas")
        self.notebook.add(self.tab_events, text="Histórico")
        ttk.Button(self.footer, text="Fechar", command=self.destroy).pack(side="right")
        self.footer_hint = tk.StringVar()
        tk.Label(self.footer, textvariable=self.footer_hint, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.refresh()

    def command(self, action):
        def wrapped():
            try:
                action()
            except EXPECTED_ERRORS as error:
                messagebox.showerror("Não foi possível concluir", str(error), parent=self)
        return wrapped

    def refresh(self):
        self.order = self.app.service.get_order(self.identifier)
        row = self.order
        self.heading.set(f'{row["equipment_tag"]} | {row["title"]}')
        self.situation.set(STATUS[row["status"]] + (" | Prazo vencido" if row["overdue"] else ""))
        terminal = row["status"] in ("concluida", "cancelada")
        self.footer_hint.set("Ordem encerrada. O histórico permanece disponível para consulta." if terminal
                             else "As operações são salvas imediatamente no banco local.")
        for tab in (self.tab_details, self.tab_parts, self.tab_events):
            for child in tab.winfo_children():
                child.destroy()
        self.details()
        self.parts()
        self.events()

    @staticmethod
    def read_text(parent, title, value, height=3, expand=False):
        tk.Label(parent, text=title, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", pady=(10, 5))
        frame = tk.Frame(parent, bg=SURFACE)
        frame.pack(fill="both" if expand else "x", expand=expand)
        text = tk.Text(frame, height=height, bg="#F7F9FA", fg=INK, wrap="word", relief="flat",
                       font=("Segoe UI", 10), padx=12, pady=10, cursor="arrow", takefocus=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.insert("1.0", value)
        text.configure(state="disabled")
        return text

    def details(self):
        row = self.order
        grid = tk.Frame(self.tab_details, bg=SURFACE)
        grid.pack(fill="x")
        values = [
            ("EQUIPAMENTO", row["equipment_name"]), ("RESPONSÁVEL", row["technician_name"]),
            ("PRIORIDADE", PRIORITIES[row["priority"]]), ("ABERTURA", format_date(row["opened_at"])),
            ("PRAZO", format_date(row["due_at"])), ("CONCLUSÃO", format_date(row["closed_at"]) if row["closed_at"] else "Em aberto"),
        ]
        for index, (label, value) in enumerate(values):
            column = index % 3
            grid.columnconfigure(column, weight=1, uniform="order_details")
            frame = tk.Frame(grid, bg=SURFACE, padx=0, pady=7)
            frame.grid(row=index // 3, column=column, sticky="ew", padx=(0, 15))
            tk.Label(frame, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
            tk.Label(frame, text=value, bg=SURFACE, fg=INK, font=("Segoe UI", 10), anchor="w", wraplength=260).pack(fill="x", pady=(4, 0))
        actions = tk.Frame(self.tab_details, bg=SURFACE)
        actions.pack(side="bottom", fill="x", pady=(14, 0))
        choices = [
            ("Iniciar atendimento", self.start, row["status"] == "aberta", "Accent.TButton"),
            ("Adicionar nota", self.note, row["status"] in ("aberta", "em_andamento"), "TButton"),
            ("Concluir ordem", self.close, row["status"] == "em_andamento", "Accent.TButton"),
            ("Cancelar ordem", self.cancel, row["status"] in ("aberta", "em_andamento"), "Danger.TButton"),
        ]
        for text, callback, enabled, style in choices:
            ttk.Button(actions, text=text, command=self.command(callback), style=style,
                       state="normal" if enabled else "disabled").pack(side="left", padx=(0, 8))
        totals = tk.Frame(self.tab_details, bg=TEAL_LIGHT, padx=12, pady=10)
        totals.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(totals, text=f'Peças: {format_money(row["parts_cents"])}   |   Mão de obra: {format_money(row["labor_cents"])}',
                 bg=TEAL_LIGHT, fg=TEAL, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(totals, text=f'Total: {format_money(row["total_cents"])}', bg=TEAL_LIGHT, fg=TEAL,
                 font=("Segoe UI", 11, "bold")).pack(side="right")
        self.read_text(self.tab_details, "DESCRIÇÃO DO PROBLEMA", row["description"], height=3,
                       expand=not bool(row["resolution"]))
        if row["resolution"]:
            self.read_text(self.tab_details, "RESOLUÇÃO", row["resolution"], height=3, expand=True)

    def parts(self):
        toolbar = tk.Frame(self.tab_parts, bg=SURFACE)
        toolbar.pack(fill="x", pady=(0, 12))
        can_change = self.order["status"] == "em_andamento"
        ttk.Button(toolbar, text="Registrar consumo", style="Accent.TButton", command=self.command(self.consume),
                   state="normal" if can_change else "disabled").pack(side="left")
        ttk.Button(toolbar, text="Devolver peça selecionada", command=self.command(self.return_part),
                   state="normal" if can_change else "disabled").pack(side="left", padx=(8, 0))
        rows = self.app.service.order_parts(self.identifier)
        self.parts_tree = self.app.table(self.tab_parts, [("sku", "CÓDIGO", 90), ("name", "PEÇA", 210),
                                         ("quantity", "QTDE", 60), ("cost", "CUSTO UNIT.", 110),
                                         ("total", "SUBTOTAL", 110), ("returned", "SITUAÇÃO", 110)], height=6)
        for index, part in enumerate(rows):
            self.app.insert(self.parts_tree, part["id"], [part["sku"], part["part_name"], part["quantity"],
                            format_money(part["unit_cost_cents"]), format_money(part["line_cents"]),
                            "Devolvida" if part["returned"] else "Em uso"], index,
                            ("inactive",) if part["returned"] else ())
        if not rows:
            hint = ("Use Registrar consumo para vincular uma peça à ordem." if can_change
                    else "O consumo só pode ser registrado durante o atendimento.")
            self.app.empty_message(self.tab_parts, "Nenhuma peça utilizada. " + hint)
        tk.Label(self.tab_parts, text="O custo é registrado no momento do consumo. A devolução repõe toda a quantidade da linha.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(12, 0))

    def events(self):
        rows = self.app.service.order_events(self.identifier)
        names = {
            "abertura": "Ordem aberta", "aberta": "Ordem aberta", "opened": "Ordem aberta",
            "inicio": "Atendimento iniciado", "iniciada": "Atendimento iniciado", "started": "Atendimento iniciado",
            "nota": "Nota de atendimento", "note": "Nota de atendimento",
            "consumo": "Peça utilizada", "devolucao": "Peça devolvida",
            "conclusao": "Ordem concluída", "concluida": "Ordem concluída", "closed": "Ordem concluída",
            "cancelamento": "Ordem cancelada", "cancelada": "Ordem cancelada", "cancelled": "Ordem cancelada",
        }
        text = tk.Text(self.tab_events, bg=SURFACE, fg=INK, wrap="word", relief="flat",
                       font=("Segoe UI", 10), padx=5, pady=5, cursor="arrow")
        scroll = ttk.Scrollbar(self.tab_events, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.tag_configure("date", foreground=TEAL, font=("Segoe UI", 9, "bold"))
        text.tag_configure("title", foreground=INK, font=("Segoe UI", 10, "bold"))
        text.tag_configure("detail", foreground=MUTED, spacing1=5, spacing3=18)
        for event in rows:
            text.insert("end", format_date(event["created_at"]) + "   ", "date")
            label = names.get(event["event"], str(event["event"]).replace("_", " ").capitalize())
            text.insert("end", label + "\n", "title")
            text.insert("end", event["detail"] + "\n", "detail")
        if not rows:
            text.insert("end", "Nenhum evento registrado.")
        text.configure(state="disabled")

    def start(self):
        technicians = [row for row in self.app.service.list_technicians() if row["active"]]
        if not technicians:
            messagebox.showinfo("Cadastre um técnico", "Feche os detalhes, abra Equipamentos e use Técnicos para cadastrar um responsável.", parent=self)
            return

        def submit(data):
            if not messagebox.askyesno("Iniciar atendimento", f"Iniciar o atendimento da {order_number(self.identifier)}?", parent=self):
                return False
            self.app.service.start_order(self.identifier, data["technician"])

        FormDialog(self.app, "Iniciar atendimento", "Defina quem ficará responsável pelo diagnóstico e pela execução.",
                   [Field("technician", "Técnico responsável", "select", self.order["technician_id"],
                          [(row["name"], row["id"]) for row in technicians])],
                   submit, "Atendimento iniciado.", parent=self, after_save=self.refresh,
                   button_text="Iniciar atendimento").show()

    def note(self):
        FormDialog(self.app, "Adicionar nota", "Registre o diagnóstico, os testes realizados ou o próximo passo.",
                   [Field("text", "Nota de atendimento", "text")],
                   lambda data: self.app.service.add_note(self.identifier, data["text"]),
                   "Nota adicionada ao histórico.", parent=self, after_save=self.refresh,
                   button_text="Adicionar nota").show()

    def consume(self):
        parts = [row for row in self.app.service.list_parts() if row["stock"] > 0]
        if not parts:
            messagebox.showinfo("Sem peças disponíveis", "Registre uma entrada na tela Estoque antes de consumir uma peça.", parent=self)
            return
        fields = [
            Field("part", "Peça", "select", parts[0]["id"],
                  [(f'{row["sku"]} | {row["name"]} | saldo {row["stock"]} | {format_money(row["unit_cost_cents"])}', row["id"]) for row in parts]),
            Field("quantity", "Quantidade", value="1"),
        ]
        FormDialog(self.app, "Registrar consumo", "A quantidade será retirada do estoque e o custo ficará vinculado à ordem.",
                   fields, lambda data: self.app.service.consume_part(self.identifier, data["part"], parse_integer(data["quantity"], "Quantidade", 1)),
                   "Consumo registrado e estoque atualizado.", parent=self, after_save=self.refresh,
                   button_text="Registrar consumo").show(680)

    def return_part(self):
        usage_id = self.app.selected(self.parts_tree, "uma peça utilizada", parent=self)
        if usage_id is None:
            return
        row = next((item for item in self.app.service.order_parts(self.identifier) if item["id"] == usage_id), None)
        if row is None:
            raise ValueError("O registro de uso não foi encontrado. Atualize a ordem.")
        if row["returned"]:
            raise ValueError("Esta peça já foi devolvida ao estoque.")
        if messagebox.askyesno("Devolver peça", f'Devolver {row["quantity"]} unidade(s) de {row["part_name"]}?\n\nO custo desta linha deixará de compor o total da ordem.', parent=self):
            self.app.service.return_part(usage_id)
            self.app.refresh("Peça devolvida ao estoque.")
            self.refresh()

    def close(self):
        fields = [
            Field("resolution", "O que foi feito para resolver?", "text"),
            Field("labor", "Custo da mão de obra (R$)", value="0,00", hint="Use zero quando o atendimento não tiver custo de mão de obra."),
        ]

        def submit(data):
            labor = parse_money(data["labor"])
            total = self.order["parts_cents"] + labor
            if not messagebox.askyesno("Concluir ordem", f'Concluir {order_number(self.identifier)} com custo total de {format_money(total)}?\n\nA ordem será encerrada e ficará disponível apenas para consulta.', parent=self):
                return False
            self.app.service.close_order(self.identifier, data["resolution"], labor)

        FormDialog(self.app, "Concluir ordem", "Descreva a solução e os testes que confirmaram o funcionamento.",
                   fields, submit, "Ordem concluída.", parent=self, after_save=self.refresh,
                   button_text="Concluir ordem").show(620)

    def cancel(self):
        in_use = [row for row in self.app.service.order_parts(self.identifier) if not row["returned"]]
        if in_use:
            messagebox.showinfo("Devolva as peças primeiro", "A ordem possui peças em uso. Na aba Peças utilizadas, devolva cada linha antes de cancelar.", parent=self)
            self.notebook.select(self.tab_parts)
            return

        def submit(data):
            if not messagebox.askyesno("Cancelar ordem", f"Cancelar {order_number(self.identifier)}?\n\nO cancelamento será registrado e a ordem ficará disponível apenas para consulta.", parent=self):
                return False
            self.app.service.cancel_order(self.identifier, data["reason"])

        FormDialog(self.app, "Cancelar ordem", "Informe o motivo para manter um histórico claro do atendimento.",
                   [Field("reason", "Motivo do cancelamento", "text")], submit, "Ordem cancelada.",
                   parent=self, after_save=self.refresh, button_text="Cancelar ordem").show(620)


def launch(service, demo: bool = False) -> None:
    """Abre a interface e mantém o loop de eventos até o usuário fechar a janela."""
    root = tk.Tk()
    try:
        Bancada(root, service, demo)
    except EXPECTED_ERRORS as error:
        messagebox.showerror("Não foi possível abrir a Bancada", str(error), parent=root)
        root.destroy()
        return
    root.mainloop()
