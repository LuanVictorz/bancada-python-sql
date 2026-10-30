"""Regras de negócio. Cada alteração e seu registro de auditoria são atômicos."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
import csv
import sqlite3

from .db import Database, DomainError, database_error


STATUSES = ("aberta", "em_andamento", "concluida", "cancelada")
ACTIVE_STATUSES = ("aberta", "em_andamento")
DEADLINES = {"alta": 24, "media": 72, "baixa": 168}
MAX_COST = 1_000_000_000
MAX_QUANTITY = 1_000_000
MAX_STOCK = 1_000_000_000

ORDER_SELECT = """
SELECT o.*, e.tag AS equipment_tag, e.name AS equipment_name,
       COALESCE(t.name, 'Sem responsável') AS technician_name,
       COALESCE(p.parts_cents, 0) AS parts_cents,
       o.labor_cents + COALESCE(p.parts_cents, 0) AS total_cents,
       CASE WHEN o.status IN ('aberta', 'em_andamento') AND o.due_at < ?
            THEN 1 ELSE 0 END AS overdue
FROM orders AS o
JOIN equipment AS e ON e.id = o.equipment_id
LEFT JOIN technicians AS t ON t.id = o.technician_id
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_cost_cents) AS parts_cents
    FROM order_parts WHERE returned = 0 GROUP BY order_id
) AS p ON p.order_id = o.id
"""


def public(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except sqlite3.DatabaseError as error:
            raise database_error(error) from error
        except OSError as error:
            raise DomainError("Não foi possível acessar o arquivo. Confira o caminho e as permissões.") from error
    return wrapped


def integer(value, label, minimum=0, maximum=MAX_COST):
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainError(f"{label} deve ser um número inteiro.")
    if not minimum <= value <= maximum:
        raise DomainError(f"{label} deve ficar entre {minimum} e {maximum}.")
    return value


def identifier(value):
    return integer(value, "Identificador", 1, 9_223_372_036_854_775_807)


def validate_text(value, label, maximum, required=True, multiline=False):
    if not isinstance(value, str):
        raise DomainError(f"{label} deve ser um texto.")
    value = value.strip()
    if required and not value:
        raise DomainError(f"Preencha {label.lower()}.")
    if len(value) > maximum:
        raise DomainError(f"{label} deve ter no máximo {maximum} caracteres.")
    if any(ord(char) < 32 and (not multiline or char not in "\n\r\t") for char in value):
        raise DomainError(f"{label} contém caracteres de controle inválidos.")
    return value


def search_pattern(value):
    value = validate_text(value, "Busca", 200, required=False)
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def stamp(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def money(cents):
    return f"{cents // 100},{cents % 100:02d}"


def spreadsheet_text(value):
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class Service:
    def __init__(self, db: Database, clock=None):
        self.db = db
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise DomainError("O relógio precisa informar uma data com fuso horário.")
        return value.astimezone(timezone.utc)

    @contextmanager
    def _read(self):
        connection = self.db.connect()
        try:
            connection.execute("BEGIN")
            yield connection
        finally:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            connection.close()

    def _record(self, connection, table, id, label):
        # Os nomes de tabela são constantes internas, nunca entrada do usuário.
        identifier(id)
        row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise DomainError(f"{label} não encontrado.")
        return dict(row)

    def _technician(self, connection, id):
        row = self._record(connection, "technicians", id, "Técnico")
        if not row["active"]:
            raise DomainError("O técnico está inativo.")
        return row

    def _order(self, connection, id, allowed=None):
        row = self._record(connection, "orders", id, "Ordem")
        if allowed is not None and row["status"] not in allowed:
            raise DomainError("A situação atual da ordem não permite esta operação.")
        return row

    def _order_time(self, connection, order):
        current = stamp(self.now())
        last = connection.execute(
            "SELECT MAX(created_at) FROM order_events WHERE order_id = ?", (order["id"],)
        ).fetchone()[0]
        if current < max(order["opened_at"], order["started_at"] or "", last or ""):
            raise DomainError("A data da operação não pode ser anterior ao histórico da ordem.")
        return current

    def _event(self, connection, id, date, event, detail):
        connection.execute(
            "INSERT INTO order_events(order_id, created_at, event, detail) VALUES (?, ?, ?, ?)",
            (id, date, event, detail),
        )

    @public
    def create_equipment(self, tag, name, category, location):
        values = (
            validate_text(tag, "Patrimônio", 40), validate_text(name, "Nome", 120),
            validate_text(category, "Categoria", 80), validate_text(location, "Local", 120),
            stamp(self.now()),
        )
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO equipment(tag, name, category, location, created_at) VALUES (?, ?, ?, ?, ?)",
                values,
            )
            return int(cursor.lastrowid)

    @public
    def update_equipment(self, id, tag, name, category, location):
        values = (
            validate_text(tag, "Patrimônio", 40), validate_text(name, "Nome", 120),
            validate_text(category, "Categoria", 80), validate_text(location, "Local", 120),
            identifier(id),
        )
        with self.db.transaction() as connection:
            self._record(connection, "equipment", id, "Equipamento")
            connection.execute(
                "UPDATE equipment SET tag = ?, name = ?, category = ?, location = ? WHERE id = ?", values
            )

    @public
    def set_equipment_active(self, id, active):
        identifier(id)
        if not isinstance(active, bool):
            raise DomainError("A situação do equipamento deve ser verdadeira ou falsa.")
        with self.db.transaction() as connection:
            self._record(connection, "equipment", id, "Equipamento")
            if not active and connection.execute(
                "SELECT 1 FROM orders WHERE equipment_id = ? AND status IN ('aberta', 'em_andamento') LIMIT 1",
                (id,),
            ).fetchone():
                raise DomainError("Conclua ou cancele as ordens ativas antes de desativar o equipamento.")
            connection.execute("UPDATE equipment SET active = ? WHERE id = ?", (int(active), id))

    @public
    def list_equipment(self, search="", include_inactive=True):
        if not isinstance(include_inactive, bool):
            raise DomainError("A opção de incluir inativos deve ser verdadeira ou falsa.")
        pattern = search_pattern(search)
        with self._read() as connection:
            rows = connection.execute(
                """SELECT e.*, (SELECT COUNT(*) FROM orders AS o
                       WHERE o.equipment_id = e.id AND o.status IN ('aberta', 'em_andamento')) AS open_orders
                   FROM equipment AS e
                   WHERE (? OR e.active = 1)
                     AND (e.tag LIKE ? ESCAPE '!' OR e.name LIKE ? ESCAPE '!'
                          OR e.location LIKE ? ESCAPE '!' OR e.category LIKE ? ESCAPE '!')
                   ORDER BY e.active DESC, e.tag COLLATE NOCASE""",
                (include_inactive, pattern, pattern, pattern, pattern),
            )
            return [dict(row) for row in rows]

    @public
    def create_technician(self, name):
        name = validate_text(name, "Nome do técnico", 120)
        with self.db.transaction() as connection:
            return int(connection.execute("INSERT INTO technicians(name) VALUES (?)", (name,)).lastrowid)

    @public
    def list_technicians(self):
        with self._read() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM technicians ORDER BY active DESC, name COLLATE NOCASE"
            )]

    @public
    def create_part(self, sku, name, min_stock, unit_cost_cents):
        values = (
            validate_text(sku, "Código da peça", 40), validate_text(name, "Nome da peça", 120),
            integer(min_stock, "Estoque mínimo", 0, MAX_STOCK),
            integer(unit_cost_cents, "Custo unitário"),
        )
        with self.db.transaction() as connection:
            return int(connection.execute(
                "INSERT INTO parts(sku, name, min_stock, unit_cost_cents) VALUES (?, ?, ?, ?)", values
            ).lastrowid)

    @public
    def receive_stock(self, part_id, quantity, unit_cost_cents, note):
        identifier(part_id)
        integer(quantity, "Quantidade", 1, MAX_QUANTITY)
        integer(unit_cost_cents, "Custo unitário")
        note = validate_text(note, "Justificativa da entrada", 2000, multiline=True)
        current = stamp(self.now())
        with self.db.transaction() as connection:
            part = self._record(connection, "parts", part_id, "Peça")
            if part["stock"] + quantity > MAX_STOCK:
                raise DomainError("A entrada ultrapassa o limite de estoque da peça.")
            connection.execute(
                "UPDATE parts SET stock = stock + ?, unit_cost_cents = ? WHERE id = ?",
                (quantity, unit_cost_cents, part_id),
            )
            connection.execute(
                """INSERT INTO stock_movements
                   (part_id, order_id, kind, quantity, unit_cost_cents, created_at, note)
                   VALUES (?, NULL, 'entrada', ?, ?, ?, ?)""",
                (part_id, quantity, unit_cost_cents, current, note),
            )

    @public
    def list_parts(self, search=""):
        pattern = search_pattern(search)
        with self._read() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT *, (stock <= min_stock) AS low_stock FROM parts
                   WHERE sku LIKE ? ESCAPE '!' OR name LIKE ? ESCAPE '!'
                   ORDER BY sku COLLATE NOCASE""", (pattern, pattern)
            )]

    @public
    def open_order(self, equipment_id, title, description, priority, technician_id=None):
        identifier(equipment_id)
        title = validate_text(title, "Título", 120)
        description = validate_text(description, "Descrição", 2000, required=False, multiline=True)
        if not isinstance(priority, str) or priority not in DEADLINES:
            raise DomainError("Escolha a prioridade baixa, media ou alta.")
        now = self.now()
        opened = stamp(now)
        try:
            due = stamp(now + timedelta(hours=DEADLINES[priority]))
        except OverflowError as error:
            raise DomainError("A data de abertura não permite calcular o prazo.") from error
        with self.db.transaction() as connection:
            equipment = self._record(connection, "equipment", equipment_id, "Equipamento")
            if not equipment["active"]:
                raise DomainError("Ative o equipamento antes de abrir uma ordem.")
            if technician_id is not None:
                self._technician(connection, technician_id)
            cursor = connection.execute(
                """INSERT INTO orders(equipment_id, technician_id, title, description, priority, opened_at, due_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (equipment_id, technician_id, title, description, priority, opened, due),
            )
            id = int(cursor.lastrowid)
            self._event(connection, id, opened, "abertura", f"Ordem aberta com prioridade {priority}.")
            return id

    @public
    def list_orders(self, status="", search=""):
        if not isinstance(status, str) or (status and status not in STATUSES):
            raise DomainError("Escolha uma situação válida para filtrar as ordens.")
        pattern = search_pattern(search)
        query = ORDER_SELECT + """
            WHERE (? = '' OR o.status = ?)
              AND (o.title LIKE ? ESCAPE '!' OR e.tag LIKE ? ESCAPE '!'
                   OR e.name LIKE ? ESCAPE '!' OR CAST(o.id AS TEXT) LIKE ? ESCAPE '!')
            ORDER BY CASE WHEN o.status IN ('aberta', 'em_andamento') THEN 0 ELSE 1 END,
                     o.opened_at, o.id"""
        with self._read() as connection:
            return [dict(row) for row in connection.execute(
                query, (stamp(self.now()), status, status, pattern, pattern, pattern, pattern)
            )]

    @public
    def get_order(self, id):
        identifier(id)
        with self._read() as connection:
            row = connection.execute(ORDER_SELECT + " WHERE o.id = ?", (stamp(self.now()), id)).fetchone()
            if row is None:
                raise DomainError("Ordem não encontrada.")
            return dict(row)

    @public
    def start_order(self, id, technician_id):
        identifier(id)
        with self.db.transaction() as connection:
            order = self._order(connection, id, ("aberta",))
            technician = self._technician(connection, technician_id)
            current = self._order_time(connection, order)
            connection.execute(
                "UPDATE orders SET status = 'em_andamento', technician_id = ?, started_at = ? WHERE id = ?",
                (technician_id, current, id),
            )
            self._event(connection, id, current, "inicio", f"Atendimento iniciado por {technician['name']}.")

    @public
    def add_note(self, id, text):
        note = validate_text(text, "Anotação", 2000, multiline=True)
        identifier(id)
        with self.db.transaction() as connection:
            order = self._order(connection, id, ACTIVE_STATUSES)
            self._event(connection, id, self._order_time(connection, order), "nota", note)

    @public
    def consume_part(self, order_id, part_id, quantity):
        identifier(order_id)
        identifier(part_id)
        integer(quantity, "Quantidade", 1, MAX_QUANTITY)
        with self.db.transaction() as connection:
            order = self._order(connection, order_id, ("em_andamento",))
            part = self._record(connection, "parts", part_id, "Peça")
            current = self._order_time(connection, order)
            if part["stock"] < quantity:
                raise DomainError("Estoque insuficiente para consumir essa quantidade.")
            connection.execute("UPDATE parts SET stock = stock - ? WHERE id = ?", (quantity, part_id))
            cursor = connection.execute(
                "INSERT INTO order_parts(order_id, part_id, quantity, unit_cost_cents) VALUES (?, ?, ?, ?)",
                (order_id, part_id, quantity, part["unit_cost_cents"]),
            )
            usage_id = int(cursor.lastrowid)
            detail = f"Consumo de {quantity} unidade(s) de {part['sku']}. Uso #{usage_id}."
            connection.execute(
                """INSERT INTO stock_movements
                   (part_id, order_id, kind, quantity, unit_cost_cents, created_at, note)
                   VALUES (?, ?, 'consumo', ?, ?, ?, ?)""",
                (part_id, order_id, -quantity, part["unit_cost_cents"], current, detail),
            )
            self._event(connection, order_id, current, "consumo", detail)
            return usage_id

    @public
    def return_part(self, usage_id):
        identifier(usage_id)
        with self.db.transaction() as connection:
            usage = self._record(connection, "order_parts", usage_id, "Uso de peça")
            order = self._order(connection, usage["order_id"], ("em_andamento",))
            if usage["returned"]:
                raise DomainError("Esta utilização já foi devolvida ao estoque.")
            part = self._record(connection, "parts", usage["part_id"], "Peça")
            if part["stock"] + usage["quantity"] > MAX_STOCK:
                raise DomainError("A devolução ultrapassa o limite de estoque da peça.")
            current = self._order_time(connection, order)
            connection.execute("UPDATE parts SET stock = stock + ? WHERE id = ?", (usage["quantity"], part["id"]))
            connection.execute("UPDATE order_parts SET returned = 1 WHERE id = ?", (usage_id,))
            detail = f"Devolução de {usage['quantity']} unidade(s) de {part['sku']}. Uso #{usage_id}."
            connection.execute(
                """INSERT INTO stock_movements
                   (part_id, order_id, kind, quantity, unit_cost_cents, created_at, note)
                   VALUES (?, ?, 'devolucao', ?, ?, ?, ?)""",
                (part["id"], order["id"], usage["quantity"], usage["unit_cost_cents"], current, detail),
            )
            self._event(connection, order["id"], current, "devolucao", detail)

    @public
    def close_order(self, id, resolution, labor_cents=0):
        identifier(id)
        resolution = validate_text(resolution, "Solução", 2000, multiline=True)
        integer(labor_cents, "Custo de mão de obra")
        with self.db.transaction() as connection:
            order = self._order(connection, id, ("em_andamento",))
            current = self._order_time(connection, order)
            connection.execute(
                "UPDATE orders SET status = 'concluida', closed_at = ?, resolution = ?, labor_cents = ? WHERE id = ?",
                (current, resolution, labor_cents, id),
            )
            self._event(connection, id, current, "conclusao", resolution)

    @public
    def cancel_order(self, id, reason):
        identifier(id)
        reason = validate_text(reason, "Motivo do cancelamento", 2000, multiline=True)
        with self.db.transaction() as connection:
            order = self._order(connection, id, ACTIVE_STATUSES)
            if connection.execute(
                "SELECT 1 FROM order_parts WHERE order_id = ? AND returned = 0 LIMIT 1", (id,)
            ).fetchone():
                raise DomainError("Devolva todas as peças utilizadas antes de cancelar a ordem.")
            current = self._order_time(connection, order)
            connection.execute(
                "UPDATE orders SET status = 'cancelada', closed_at = ?, resolution = ? WHERE id = ?",
                (current, reason, id),
            )
            self._event(connection, id, current, "cancelamento", reason)

    @public
    def order_parts(self, order_id):
        identifier(order_id)
        with self._read() as connection:
            self._order(connection, order_id)
            return [dict(row) for row in connection.execute(
                """SELECT op.*, p.sku, p.name AS part_name,
                          CASE WHEN op.returned = 1 THEN 0 ELSE op.quantity * op.unit_cost_cents END AS line_cents
                   FROM order_parts AS op JOIN parts AS p ON p.id = op.part_id
                   WHERE op.order_id = ? ORDER BY op.id""", (order_id,)
            )]

    @public
    def order_events(self, order_id):
        identifier(order_id)
        with self._read() as connection:
            self._order(connection, order_id)
            return [dict(row) for row in connection.execute(
                "SELECT * FROM order_events WHERE order_id = ? ORDER BY created_at, id", (order_id,)
            )]

    @public
    def dashboard(self):
        now = self.now()
        with self._read() as connection:
            counts = {status: 0 for status in STATUSES}
            for row in connection.execute("SELECT status, COUNT(*) AS count FROM orders GROUP BY status"):
                counts[row["status"]] = row["count"]
            totals = connection.execute(
                """SELECT COUNT(*) AS count,
                          COALESCE(SUM(o.labor_cents + COALESCE(p.cost, 0)), 0) AS cost,
                          COALESCE(AVG((julianday(o.closed_at) - julianday(o.opened_at)) * 24), 0) AS hours
                   FROM orders AS o
                   LEFT JOIN (SELECT order_id, SUM(quantity * unit_cost_cents) AS cost
                              FROM order_parts WHERE returned = 0 GROUP BY order_id) AS p ON p.order_id = o.id
                   WHERE o.status = 'concluida'"""
            ).fetchone()
            overdue = connection.execute(
                "SELECT COUNT(*) FROM orders WHERE status IN ('aberta', 'em_andamento') AND due_at < ?",
                (stamp(now),),
            ).fetchone()[0]
            low_stock = connection.execute("SELECT COUNT(*) FROM parts WHERE stock <= min_stock").fetchone()[0]
            month_number = now.year * 12 + now.month - 1
            months = []
            for offset in range(5, -1, -1):
                year, month_zero = divmod(month_number - offset, 12)
                months.append(f"{year:04d}-{month_zero + 1:02d}")
            monthly_rows = connection.execute(
                """SELECT substr(o.closed_at, 1, 7) AS month, COUNT(*) AS count,
                          SUM(o.labor_cents + COALESCE(p.cost, 0)) AS total_cents
                   FROM orders AS o
                   LEFT JOIN (SELECT order_id, SUM(quantity * unit_cost_cents) AS cost
                              FROM order_parts WHERE returned = 0 GROUP BY order_id) AS p ON p.order_id = o.id
                   WHERE o.status = 'concluida' AND substr(o.closed_at, 1, 7) BETWEEN ? AND ?
                   GROUP BY substr(o.closed_at, 1, 7)""", (months[0], months[-1])
            )
            by_month = {row["month"]: dict(row) for row in monthly_rows}
            monthly = [by_month.get(month, {"month": month, "count": 0, "total_cents": 0}) for month in months]
            top = [dict(row) for row in connection.execute(
                """SELECT e.tag, e.name, COUNT(o.id) AS order_count,
                          COALESCE(SUM(o.labor_cents + COALESCE(p.cost, 0)), 0) AS total_cents
                   FROM equipment AS e
                   JOIN orders AS o ON o.equipment_id = e.id AND o.status = 'concluida'
                   LEFT JOIN (SELECT order_id, SUM(quantity * unit_cost_cents) AS cost
                              FROM order_parts WHERE returned = 0 GROUP BY order_id) AS p ON p.order_id = o.id
                   GROUP BY e.id, e.tag, e.name
                   ORDER BY total_cents DESC, order_count DESC, e.tag COLLATE NOCASE LIMIT 5"""
            )]
            return {
                "open_count": counts["aberta"] + counts["em_andamento"],
                "in_progress_count": counts["em_andamento"], "overdue_count": overdue,
                "low_stock_count": low_stock, "closed_count": totals["count"],
                "total_closed_cents": totals["cost"], "avg_resolution_hours": float(totals["hours"]),
                "status_counts": [{"status": status, "count": counts[status]} for status in STATUSES],
                "monthly": monthly, "top_equipment": top,
            }

    def _destination(self, path):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise DomainError("Escolha um caminho válido para salvar o arquivo.")
        try:
            destination = Path(path).expanduser().resolve()
            forbidden = {self.db.path, Path(str(self.db.path) + "-wal"),
                         Path(str(self.db.path) + "-shm"), Path(str(self.db.path) + "-journal")}
            if destination in forbidden:
                raise DomainError("Escolha um arquivo diferente do banco em uso e de seus arquivos auxiliares.")
            if not destination.parent.is_dir():
                raise DomainError("A pasta escolhida não existe.")
            if destination.exists():
                raise DomainError("O arquivo já existe. Escolha outro nome para preservar o conteúdo.")
            return destination
        except (OSError, ValueError) as error:
            if isinstance(error, DomainError):
                raise
            raise DomainError("O caminho escolhido não é válido.") from error

    @public
    def export_orders(self, path):
        destination = self._destination(path)
        rows = self.list_orders()
        created = False
        try:
            with destination.open("x", encoding="utf-8-sig", newline="") as stream:
                created = True
                writer = csv.writer(stream, delimiter=";")
                writer.writerow([
                    "Ordem", "Patrimônio", "Equipamento", "Título", "Descrição", "Técnico",
                    "Prioridade", "Situação", "Abertura UTC", "Início UTC", "Conclusão UTC",
                    "Prazo UTC", "Peças (R$)", "Mão de obra (R$)", "Total (R$)", "Atrasada", "Solução",
                ])
                for row in rows:
                    writer.writerow([
                        row["id"], spreadsheet_text(row["equipment_tag"]),
                        spreadsheet_text(row["equipment_name"]), spreadsheet_text(row["title"]),
                        spreadsheet_text(row["description"]), spreadsheet_text(row["technician_name"]),
                        row["priority"], row["status"], row["opened_at"], row["started_at"] or "",
                        row["closed_at"] or "", row["due_at"], money(row["parts_cents"]),
                        money(row["labor_cents"]), money(row["total_cents"]),
                        "Sim" if row["overdue"] else "Não", spreadsheet_text(row["resolution"]),
                    ])
            return len(rows)
        except (OSError, UnicodeError, csv.Error) as error:
            if created:
                destination.unlink(missing_ok=True)
            raise DomainError("Não foi possível exportar. Confira o nome, a pasta e as permissões do arquivo.") from error

    @public
    def backup(self, path):
        destination = self._destination(path)
        created = False
        source = target = None
        try:
            with destination.open("xb"):
                created = True
            source = self.db.connect()
            target = sqlite3.connect(destination, isolation_level=None)
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchall()
            if len(integrity) != 1 or integrity[0][0] != "ok":
                raise DomainError("A cópia não passou na verificação de integridade.")
            if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise DomainError("A cópia contém referências inconsistentes.")
        except BaseException:
            if target is not None:
                target.close()
                target = None
            if source is not None:
                source.close()
                source = None
            if created:
                destination.unlink(missing_ok=True)
            raise
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()


