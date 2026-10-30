from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading

from app.db import Database
from app.service import DomainError, Service
from tests import BancadaTestCase


class SchemaTests(BancadaTestCase):
    def test_connection_enables_foreign_keys_and_has_row_access(self):
        self.assertTrue(self.db.path.is_absolute())
        with closing(self.db.connect()) as connection:
            self.assertIsNone(connection.isolation_level)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT 7 AS value").fetchone()["value"], 7)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_initialize_is_idempotent_and_preserves_existing_data(self):
        self.order(started=True)
        self.part(stock=2)
        before = self.snapshot()
        self.db.initialize()
        reopened = Database(self.db.path)
        reopened.initialize()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(Service(reopened, clock=self.clock).list_orders(), self.service.list_orders())

    def test_future_schema_version_is_refused_without_modification(self):
        self.equipment()
        before = self.snapshot()
        self.execute("PRAGMA user_version = 99")
        with self.assertRaises((DomainError, ValueError, RuntimeError)):
            self.db.initialize()
        self.assertEqual(self.rows("PRAGMA user_version")[0]["user_version"], 99)
        self.assertEqual(self.snapshot(), before)

    def test_foreign_keys_prevent_orphan_order_usage_movement_and_event(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=1)
        usage_id = self.service.consume_part(order_id, part_id, 1)
        updates = [
            ("UPDATE orders SET equipment_id = ? WHERE id = ?", (999999, order_id)),
            ("UPDATE orders SET technician_id = ? WHERE id = ?", (999999, order_id)),
            ("UPDATE order_parts SET order_id = ? WHERE id = ?", (999999, usage_id)),
            ("UPDATE order_parts SET part_id = ? WHERE id = ?", (999999, usage_id)),
            ("UPDATE stock_movements SET part_id = ? WHERE part_id = ?", (999999, part_id)),
            ("UPDATE stock_movements SET order_id = ? WHERE order_id = ?", (999999, order_id)),
            ("UPDATE order_events SET order_id = ? WHERE order_id = ?", (999999, order_id)),
        ]
        before = self.snapshot()
        for sql, parameters in updates:
            with self.subTest(sql=sql):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.execute(sql, parameters)
                self.assertEqual(self.snapshot(), before)

    def test_checks_reject_invalid_stock_money_quantity_and_states(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=2)
        self.service.consume_part(order_id, part_id, 1)
        statements = [
            "UPDATE parts SET stock = -1",
            "UPDATE parts SET min_stock = -1",
            "UPDATE parts SET unit_cost_cents = -1",
            "UPDATE orders SET labor_cents = -1",
            "UPDATE orders SET status = 'inexistente'",
            "UPDATE orders SET priority = 'urgente'",
            "UPDATE equipment SET active = 2",
            "UPDATE technicians SET active = 2",
            "UPDATE order_parts SET quantity = 0",
            "UPDATE order_parts SET unit_cost_cents = -1",
            "UPDATE order_parts SET returned = 2",
            "UPDATE stock_movements SET quantity = 0",
            "UPDATE stock_movements SET unit_cost_cents = -1",
            "UPDATE stock_movements SET kind = 'inexistente'",
        ]
        before = self.snapshot()
        for sql in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.execute(sql)
                self.assertEqual(self.snapshot(), before)


class AtomicidadeTests(BancadaTestCase):
    def reject_insert(self, table):
        # O erro é injetado só no banco temporário para verificar o rollback.
        self.execute(f"CREATE TRIGGER fail_test BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'falha simulada de teste'); END")

    def clear_failure(self):
        self.execute("DROP TRIGGER fail_test")

    def test_consume_rolls_back_stock_usage_and_movement_when_event_fails(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=2)
        self.reject_insert("order_events")
        self.rejected_without_changes(lambda: self.service.consume_part(order_id, part_id, 1))
        self.clear_failure()
        self.service.consume_part(order_id, part_id, 1)
        self.assertEqual(self.stock(part_id), 1)

    def test_receive_rolls_back_quantity_and_reference_price_when_movement_fails(self):
        part_id = self.part(price=100, stock=1)
        self.reject_insert("stock_movements")
        self.rejected_without_changes(lambda: self.service.receive_stock(part_id, 3, 999, "Entrada de teste"))
        self.clear_failure()
        self.service.receive_stock(part_id, 3, 999, "Entrada de teste")
        self.assertEqual(self.stock(part_id), 4)
        self.assertEqual(self.service.list_parts()[0]["unit_cost_cents"], 999)

    def test_return_rolls_back_stock_flag_and_movement_when_event_fails(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=2)
        usage_id = self.service.consume_part(order_id, part_id, 2)
        self.reject_insert("order_events")
        self.rejected_without_changes(lambda: self.service.return_part(usage_id))
        self.clear_failure()
        self.service.return_part(usage_id)
        self.assertEqual(self.stock(part_id), 2)

    def test_open_order_rolls_back_if_event_cannot_be_written(self):
        equipment_id = self.equipment()
        self.reject_insert("order_events")
        self.rejected_without_changes(lambda: self.service.open_order(equipment_id, "Falha", "", "alta"))
        self.clear_failure()
        self.assertIsInstance(self.service.open_order(equipment_id, "Falha", "", "alta"), int)

    def test_operational_error_becomes_domain_error_and_rolls_back(self):
        equipment_id = self.equipment()
        self.execute("CREATE TRIGGER fail_test BEFORE INSERT ON order_events BEGIN SELECT * FROM missing_test_table; END")
        self.rejected_without_changes(lambda: self.service.open_order(equipment_id, "Falha", "", "alta"))
        self.clear_failure()
        self.assertIsInstance(self.service.open_order(equipment_id, "Falha", "", "alta"), int)

    def test_start_close_and_cancel_roll_back_when_event_fails(self):
        order_id = self.order()
        technician_id = self.technician()
        self.reject_insert("order_events")
        self.rejected_without_changes(lambda: self.service.start_order(order_id, technician_id))
        self.clear_failure()
        self.service.start_order(order_id, technician_id)
        self.reject_insert("order_events")
        self.rejected_without_changes(lambda: self.service.close_order(order_id, "Solução", 500))
        self.rejected_without_changes(lambda: self.service.cancel_order(order_id, "Cancelamento"))
        self.clear_failure()
        self.service.close_order(order_id, "Solução", 500)
        self.assertEqual(self.service.get_order(order_id)["status"], "concluida")

    def test_two_instances_cannot_consume_the_same_last_unit(self):
        first_order = self.order(started=True)
        second_equipment = self.equipment("NOTE-02")
        second_order = self.service.open_order(second_equipment, "Outra falha", "", "media")
        self.service.start_order(second_order, self.service.list_technicians()[0]["id"])
        part_id = self.part(stock=1)
        other_service = Service(Database(self.db.path), clock=self.clock)
        barrier = threading.Barrier(2)

        def consume(service, order_id):
            barrier.wait(timeout=5)
            try:
                service.consume_part(order_id, part_id, 1)
                return "accepted"
            except DomainError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(consume, self.service, first_order)
            second = executor.submit(consume, other_service, second_order)
            outcomes = [first.result(timeout=10), second.result(timeout=10)]
        self.assertCountEqual(outcomes, ["accepted", "rejected"])
        self.assertEqual(self.stock(part_id), 0)
        self.assertEqual(len(self.rows("SELECT * FROM order_parts")), 1)
        self.assertEqual(len(self.rows("SELECT * FROM stock_movements WHERE kind = 'consumo'")), 1)
        self.assertEqual(self.rows("PRAGMA foreign_key_check"), [])
