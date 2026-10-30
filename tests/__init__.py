"""Preparação compartilhada dos testes, com banco temporário e relógio fixo."""

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from app.db import Database
from app.service import DomainError, Service


class FrozenClock:
    def __init__(self):
        self.current = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.current

    def set(self, value):
        self.current = datetime.fromisoformat(value.replace("Z", "+00:00"))


class BancadaTestCase(unittest.TestCase):
    def setUp(self):
        # Pasta única e descartável, criada com as permissões normais do projeto.
        # Isso também funciona em terminais Windows com usuário restrito.
        work = Path(__file__).resolve().parents[1] / "work"
        work.mkdir(exist_ok=True)
        self.folder = work / f"teste-{uuid4().hex}"
        self.folder.mkdir()
        self.addCleanup(shutil.rmtree, self.folder)
        self.db = Database(self.folder / "teste.sqlite3")
        self.db.initialize()
        self.clock = FrozenClock()
        self.service = Service(self.db, clock=self.clock)

    def equipment(self, tag="NOTE-01"):
        return self.service.create_equipment(tag, "Notebook fictício", "Notebook", "Sala de teste")

    def technician(self, name="Técnico de teste"):
        return self.service.create_technician(name)

    def part(self, sku="P-01", price=1999, stock=0, minimum=1):
        part_id = self.service.create_part(sku, "Peça de teste", minimum, price)
        if stock:
            self.service.receive_stock(part_id, stock, price, "Entrada de teste")
        return part_id

    def order(self, tag="NOTE-01", priority="media", started=False):
        order_id = self.service.open_order(self.equipment(tag), "Falha de teste", "Descrição fictícia", priority)
        if started:
            self.service.start_order(order_id, self.technician())
        return order_id

    def rows(self, sql, parameters=()):
        with closing(self.db.connect()) as connection:
            return [dict(row) for row in connection.execute(sql, parameters)]

    def execute(self, sql, parameters=()):
        with closing(self.db.connect()) as connection:
            connection.execute(sql, parameters)

    def snapshot(self):
        tables = ("equipment", "technicians", "parts", "orders", "order_parts", "stock_movements", "order_events")
        return {table: self.rows(f"SELECT * FROM {table} ORDER BY id") for table in tables}

    def rejected_without_changes(self, action):
        before = self.snapshot()
        with self.assertRaises(DomainError):
            action()
        self.assertEqual(self.snapshot(), before)

    def stock(self, part_id):
        return self.rows("SELECT stock FROM parts WHERE id = ?", (part_id,))[0]["stock"]


def parsed_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
