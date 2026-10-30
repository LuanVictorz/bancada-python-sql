from contextlib import closing
import csv
from datetime import timedelta
import sqlite3

from app.db import Database
from app.service import DomainError, Service
from tests import BancadaTestCase


class DashboardTests(BancadaTestCase):
    def test_empty_dashboard_has_all_statuses_and_six_zero_months(self):
        result = self.service.dashboard()
        for key in ["open_count", "in_progress_count", "overdue_count", "low_stock_count", "closed_count", "total_closed_cents"]:
            self.assertEqual(result[key], 0)
        self.assertEqual(result["avg_resolution_hours"], 0)
        self.assertEqual({row["status"]: row["count"] for row in result["status_counts"]},
                         {"aberta": 0, "em_andamento": 0, "concluida": 0, "cancelada": 0})
        self.assertEqual([row["month"] for row in result["monthly"]],
                         ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"])
        self.assertTrue(all(row["count"] == 0 and row["total_cents"] == 0 for row in result["monthly"]))
        self.assertEqual(result["top_equipment"], [])

    def test_dashboard_does_not_multiply_totals_by_parts_or_events(self):
        equipment_id = self.equipment()
        technician_id = self.technician()
        first_part = self.part("A", price=100, stock=10, minimum=1)
        second_part = self.part("B", price=200, stock=10, minimum=1)
        first = self.service.open_order(equipment_id, "Primeira falha", "", "media")
        self.service.start_order(first, technician_id)
        self.service.consume_part(first, first_part, 2)
        self.service.consume_part(first, second_part, 1)
        self.service.add_note(first, "Primeira observação")
        self.service.add_note(first, "Segunda observação")
        self.clock.current += timedelta(hours=2)
        self.service.close_order(first, "Primeira solução", 300)
        second = self.service.open_order(equipment_id, "Segunda falha", "", "media")
        self.service.start_order(second, technician_id)
        self.service.consume_part(second, first_part, 1)
        self.service.consume_part(second, second_part, 3)
        self.clock.current += timedelta(hours=4)
        self.service.close_order(second, "Segunda solução", 500)
        cancelled = self.service.open_order(equipment_id, "Não executar", "", "baixa")
        self.service.cancel_order(cancelled, "Cancelado antes do atendimento")
        self.service.open_order(equipment_id, "Falha pendente", "", "alta")
        self.clock.current += timedelta(hours=25)

        result = self.service.dashboard()
        self.assertEqual(result["closed_count"], 2)
        self.assertEqual(result["total_closed_cents"], 1900)
        self.assertAlmostEqual(result["avg_resolution_hours"], 3.0)
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["overdue_count"], 1)
        self.assertEqual(result["in_progress_count"], 0)
        june = next(row for row in result["monthly"] if row["month"] == "2026-06")
        self.assertEqual((june["count"], june["total_cents"]), (2, 1900))
        self.assertEqual(len(result["top_equipment"]), 1)
        self.assertEqual(result["top_equipment"][0]["total_cents"], 1900)

    def test_open_count_includes_in_progress_and_low_stock_is_counted_once(self):
        first = self.order()
        second_equipment = self.equipment("NOTE-02")
        second = self.service.open_order(second_equipment, "Outra falha", "", "baixa")
        self.service.start_order(second, self.technician())
        self.part(minimum=2, stock=2)
        result = self.service.dashboard()
        self.assertEqual(result["open_count"], 2)
        self.assertEqual(result["in_progress_count"], 1)
        self.assertEqual(result["low_stock_count"], 1)
        self.assertEqual(len(self.service.list_orders(status="aberta")), 1)
        self.assertEqual(self.service.list_orders(status="aberta")[0]["id"], first)

    def test_months_cross_year_boundary_and_follow_injected_clock(self):
        self.clock.set("2026-02-01T00:00:00+00:00")
        result = self.service.dashboard()
        self.assertEqual([row["month"] for row in result["monthly"]],
                         ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"])


class ArquivoTests(BancadaTestCase):
    def test_backup_reopens_with_identical_data_and_passes_integrity(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=3)
        self.service.consume_part(order_id, part_id, 2)
        self.service.close_order(order_id, "Solução documentada", 1515)
        destination = self.folder / "backup.sqlite3"
        self.service.backup(destination)
        copied_db = Database(destination)
        copied_db.initialize()
        copied = Service(copied_db, clock=self.clock)
        self.assertEqual(copied.list_equipment(), self.service.list_equipment())
        self.assertEqual(copied.list_orders(), self.service.list_orders())
        self.assertEqual(copied.list_parts(), self.service.list_parts())
        self.assertEqual(copied.order_events(order_id), self.service.order_events(order_id))
        self.assertEqual(copied.order_parts(order_id), self.service.order_parts(order_id))
        with closing(sqlite3.connect(destination)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_backup_refuses_overwrite_source_and_sidecar_paths(self):
        self.equipment()
        target = self.folder / "existing.sqlite3"
        target.write_bytes(b"preservar arquivo existente")
        with self.assertRaises(DomainError):
            self.service.backup(target)
        self.assertEqual(target.read_bytes(), b"preservar arquivo existente")
        self.rejected_without_changes(lambda: self.service.backup(self.db.path))
        self.rejected_without_changes(lambda: self.service.backup(str(self.db.path) + "-wal"))
        self.rejected_without_changes(lambda: self.service.backup(str(self.db.path) + "-shm"))

    def test_second_backup_to_same_path_keeps_first_snapshot(self):
        self.equipment("A")
        target = self.folder / "backup.sqlite3"
        self.service.backup(target)
        before = target.read_bytes()
        self.equipment("B")
        with self.assertRaises(DomainError):
            self.service.backup(target)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(len(self.service.list_equipment()), 2)

    def test_csv_uses_bom_semicolon_and_sanitizes_formula_prefixes(self):
        equipment_id = self.service.create_equipment("EQ-X", "  +SOMA(1;1)", "Notebook", "Sala")
        technician_id = self.technician("  @SOMA(1;1)")
        titles = ["=1+1", "  +1+1", "\t-1+1", "  @SOMA(1;1)"]
        for title in titles:
            self.service.open_order(equipment_id, title, "Descrição com ; e acentuação", "baixa", technician_id)
        path = self.folder / "ordens.csv"
        self.assertEqual(self.service.export_orders(path), 4)
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        with path.open(encoding="utf-8-sig", newline="") as exported:
            rows = list(csv.reader(exported, delimiter=";"))
        self.assertEqual(len(rows), 5)
        self.assertGreater(len(rows[0]), 3)
        self.assertTrue(all(len(row) == len(rows[0]) for row in rows[1:]))
        for row in rows[1:]:
            for cell in row:
                self.assertNotIn(cell.lstrip()[:1], ["=", "+", "-", "@"], msg=f"Célula de fórmula não protegida: {cell!r}")
        # A proteção pertence à exportação e não deve adulterar o cadastro.
        self.assertEqual(self.service.list_equipment()[0]["name"], "+SOMA(1;1)")
        self.assertTrue(any(row["title"] == "=1+1" for row in self.service.list_orders()))

    def test_csv_formats_integer_cents_and_refuses_existing_file(self):
        order_id = self.order(started=True)
        part_id = self.part(price=101, stock=1)
        self.service.consume_part(order_id, part_id, 1)
        self.service.close_order(order_id, "Solução", 203)
        path = self.folder / "valores.csv"
        self.assertEqual(self.service.export_orders(path), 1)
        with path.open(encoding="utf-8-sig", newline="") as exported:
            values = list(csv.reader(exported, delimiter=";"))[1]
        for expected in ["1,01", "2,03", "3,04"]:
            self.assertTrue(any(expected in cell or expected.replace(",", ".") in cell for cell in values), msg=f"Valor monetário ausente: {expected}")
        before = path.read_bytes()
        with self.assertRaises(DomainError):
            self.service.export_orders(path)
        self.assertEqual(path.read_bytes(), before)

    def test_empty_export_has_header_and_no_records(self):
        path = self.folder / "vazio.csv"
        self.assertEqual(self.service.export_orders(path), 0)
        with path.open(encoding="utf-8-sig", newline="") as exported:
            rows = list(csv.reader(exported, delimiter=";"))
        self.assertEqual(len(rows), 1)
        self.assertGreater(len(rows[0]), 3)

    def test_file_operations_reject_directory_destinations(self):
        for operation in [self.service.export_orders, self.service.backup]:
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(DomainError):
                    operation(self.folder)
