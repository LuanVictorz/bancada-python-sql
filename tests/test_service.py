from datetime import timedelta

from app.service import DomainError
from tests import BancadaTestCase, parsed_date


class CadastroTests(BancadaTestCase):
    def test_equipment_strips_text_and_detects_duplicate_tag_case(self):
        equipment_id = self.service.create_equipment("  Note-A  ", "  Equipamento fictício  ", " Notebook ", " Sala 1 ")
        equipment = self.service.list_equipment()[0]
        self.assertEqual(equipment["id"], equipment_id)
        self.assertEqual(equipment["tag"], "Note-A")
        self.assertEqual(equipment["name"], "Equipamento fictício")
        self.assertEqual(equipment["category"], "Notebook")
        self.assertEqual(equipment["location"], "Sala 1")
        self.assertEqual(equipment["open_orders"], 0)
        self.rejected_without_changes(lambda: self.equipment("note-a"))

    def test_equipment_edit_persists_and_refuses_conflicting_tag(self):
        first = self.equipment("A")
        second = self.equipment("B")
        self.service.update_equipment(first, " A-2 ", "Nome alterado", "Monitor", "Sala 2")
        changed = next(row for row in self.service.list_equipment() if row["id"] == first)
        self.assertEqual((changed["tag"], changed["name"], changed["category"], changed["location"]),
                         ("A-2", "Nome alterado", "Monitor", "Sala 2"))
        self.rejected_without_changes(lambda: self.service.update_equipment(second, "a-2", "Outro", "Monitor", "Sala 2"))

    def test_inactive_equipment_cannot_receive_order_and_can_be_filtered(self):
        equipment_id = self.equipment()
        self.service.set_equipment_active(equipment_id, False)
        self.assertEqual(self.service.list_equipment(include_inactive=False), [])
        self.assertEqual(len(self.service.list_equipment()), 1)
        self.rejected_without_changes(lambda: self.service.open_order(equipment_id, "Falha", "", "baixa"))
        self.service.set_equipment_active(equipment_id, True)
        self.assertEqual(len(self.service.list_equipment(include_inactive=False)), 1)

    def test_equipment_with_active_order_cannot_be_deactivated(self):
        order_id = self.order()
        equipment_id = self.service.get_order(order_id)["equipment_id"]
        self.rejected_without_changes(lambda: self.service.set_equipment_active(equipment_id, False))
        self.service.start_order(order_id, self.technician())
        self.rejected_without_changes(lambda: self.service.set_equipment_active(equipment_id, False))
        self.service.cancel_order(order_id, "Atendimento não será necessário")
        self.service.set_equipment_active(equipment_id, False)
        self.assertFalse(self.service.list_equipment()[0]["active"])

    def test_case_insensitive_technician_and_sku_uniqueness(self):
        self.technician("Técnico A")
        self.part("SKU-A")
        self.rejected_without_changes(lambda: self.technician("técnico a"))
        self.rejected_without_changes(lambda: self.part("sku-a"))

    def test_empty_required_text_is_rejected(self):
        actions = [
            lambda: self.equipment(" "),
            lambda: self.service.create_equipment("A", " ", "Notebook", "Sala"),
            lambda: self.technician(" "),
            lambda: self.service.create_part(" ", "Peça", 1, 100),
            lambda: self.service.create_part("P", " ", 1, 100),
        ]
        for action in actions:
            with self.subTest(action=actions.index(action)):
                self.rejected_without_changes(action)

    def test_search_uses_parameters(self):
        order_id = self.order()
        self.part()
        self.assertEqual(self.service.list_equipment(search="' OR 1=1 --"), [])
        self.assertEqual(self.service.list_parts(search="' OR 1=1 --"), [])
        self.assertEqual(self.service.list_orders(search="' OR 1=1 --"), [])
        self.assertEqual(self.service.get_order(order_id)["title"], "Falha de teste")

    def test_missing_and_invalid_ids_are_domain_errors(self):
        for invalid in [999999, 0, -1, True, 1.5, "1", None]:
            actions = [
                lambda: self.service.get_order(invalid),
                lambda: self.service.update_equipment(invalid, "A", "Nome", "Tipo", "Sala"),
                lambda: self.service.set_equipment_active(invalid, False),
                lambda: self.service.receive_stock(invalid, 1, 10, "Entrada"),
                lambda: self.service.return_part(invalid),
            ]
            for action in actions:
                with self.subTest(identifier=invalid, operation=actions.index(action)):
                    self.rejected_without_changes(action)


class OrdemTests(BancadaTestCase):
    def test_priority_deadlines_use_fixed_clock(self):
        for index, (priority, hours) in enumerate([( "alta", 24), ("media", 72), ("baixa", 168)]):
            order_id = self.order(tag=f"EQ-{index}", priority=priority)
            row = self.service.get_order(order_id)
            self.assertEqual(parsed_date(row["opened_at"]), self.clock())
            self.assertEqual(parsed_date(row["due_at"]), self.clock() + timedelta(hours=hours))
            self.assertEqual(row["status"], "aberta")
            self.assertEqual(row["technician_name"], "Sem responsável")
            self.assertEqual((row["parts_cents"], row["total_cents"]), (0, 0))

    def test_overdue_changes_only_after_deadline_and_ignores_terminal(self):
        order_id = self.order(priority="alta")
        due = self.clock() + timedelta(hours=24)
        self.clock.current = due
        self.assertFalse(self.service.get_order(order_id)["overdue"])
        self.clock.current = due + timedelta(seconds=1)
        self.assertTrue(self.service.get_order(order_id)["overdue"])
        self.assertEqual(self.service.dashboard()["overdue_count"], 1)
        self.service.cancel_order(order_id, "Cancelamento de teste")
        self.assertFalse(self.service.get_order(order_id)["overdue"])
        self.assertEqual(self.service.dashboard()["overdue_count"], 0)

    def test_open_order_field_limits_and_priority(self):
        equipment_id = self.equipment()
        valid = self.service.open_order(equipment_id, "T" * 120, "D" * 2000, "baixa")
        self.assertEqual(len(self.service.get_order(valid)["title"]), 120)
        for title, description, priority in [("T" * 121, "", "baixa"), ("Título", "D" * 2001, "baixa"), (" ", "", "baixa"), ("Título", "", "urgente")]:
            with self.subTest(title_length=len(title), description_length=len(description), priority=priority):
                self.rejected_without_changes(lambda: self.service.open_order(equipment_id, title, description, priority))

    def test_unknown_technician_is_rejected_on_open_and_start(self):
        equipment_id = self.equipment()
        self.rejected_without_changes(lambda: self.service.open_order(equipment_id, "Falha", "", "media", 999999))
        order_id = self.service.open_order(equipment_id, "Falha", "", "media")
        self.rejected_without_changes(lambda: self.service.start_order(order_id, 999999))
        self.rejected_without_changes(lambda: self.service.start_order(order_id, None))

    def test_inactive_technician_cannot_be_assigned_to_new_work(self):
        equipment_id = self.equipment()
        technician_id = self.technician()
        self.execute("UPDATE technicians SET active = 0 WHERE id = ?", (technician_id,))
        self.rejected_without_changes(lambda: self.service.open_order(equipment_id, "Falha", "", "media", technician_id))
        order_id = self.service.open_order(equipment_id, "Falha", "", "media")
        self.rejected_without_changes(lambda: self.service.start_order(order_id, technician_id))

    def test_list_orders_keeps_active_work_before_older_closed_work(self):
        closed_id = self.order(started=True)
        self.service.close_order(closed_id, "Resolvido", 0)
        self.clock.current += timedelta(hours=1)
        equipment_id = self.service.get_order(closed_id)["equipment_id"]
        older_open = self.service.open_order(equipment_id, "Primeira pendência", "", "baixa")
        self.clock.current += timedelta(hours=1)
        newer_open = self.service.open_order(equipment_id, "Segunda pendência", "", "alta")
        self.assertEqual([row["id"] for row in self.service.list_orders()], [older_open, newer_open, closed_id])

    def test_start_note_close_records_correct_dates_and_totals(self):
        order_id = self.order()
        technician_id = self.technician()
        self.clock.current += timedelta(hours=2)
        started = self.clock()
        self.service.start_order(order_id, technician_id)
        self.service.add_note(order_id, "Conector revisado em bancada")
        self.clock.current += timedelta(hours=3)
        self.service.close_order(order_id, "Conector substituído e teste concluído", 12550)
        row = self.service.get_order(order_id)
        self.assertEqual(row["status"], "concluida")
        self.assertEqual(row["technician_id"], technician_id)
        self.assertEqual(parsed_date(row["started_at"]), started)
        self.assertEqual(parsed_date(row["closed_at"]), self.clock())
        self.assertEqual(row["total_cents"], 12550)
        self.assertEqual(row["resolution"], "Conector substituído e teste concluído")
        events = self.service.order_events(order_id)
        self.assertGreaterEqual(len(events), 4)
        self.assertTrue(any("Conector revisado em bancada" in row["detail"] for row in events))
        self.assertEqual([parsed_date(row["created_at"]) for row in events], sorted(parsed_date(row["created_at"]) for row in events))

    def test_unstarted_order_cannot_close_or_consume(self):
        order_id = self.order()
        part_id = self.part(stock=1)
        self.rejected_without_changes(lambda: self.service.close_order(order_id, "Solução", 100))
        self.rejected_without_changes(lambda: self.service.consume_part(order_id, part_id, 1))

    def test_second_start_and_empty_note_or_resolution_are_rejected(self):
        order_id = self.order(started=True)
        technician_id = self.service.list_technicians()[0]["id"]
        self.rejected_without_changes(lambda: self.service.start_order(order_id, technician_id))
        self.rejected_without_changes(lambda: self.service.add_note(order_id, " "))
        self.rejected_without_changes(lambda: self.service.close_order(order_id, " ", 0))
        self.rejected_without_changes(lambda: self.service.cancel_order(order_id, " "))

    def test_cancel_open_order_is_terminal(self):
        order_id = self.order()
        technician_id = self.technician()
        part_id = self.part(stock=1)
        self.service.cancel_order(order_id, "Equipamento retirado de uso")
        self.assertEqual(self.service.get_order(order_id)["status"], "cancelada")
        actions = [
            lambda: self.service.start_order(order_id, technician_id),
            lambda: self.service.add_note(order_id, "Nota posterior"),
            lambda: self.service.consume_part(order_id, part_id, 1),
            lambda: self.service.close_order(order_id, "Solução posterior", 0),
            lambda: self.service.cancel_order(order_id, "Novo motivo"),
        ]
        for action in actions:
            with self.subTest(operation=actions.index(action)):
                self.rejected_without_changes(action)

    def test_closed_order_is_terminal_including_part_return(self):
        order_id = self.order(started=True)
        technician_id = self.service.list_technicians()[0]["id"]
        part_id = self.part(stock=2)
        usage = self.service.consume_part(order_id, part_id, 1)
        self.service.close_order(order_id, "Teste final aprovado", 0)
        actions = [
            lambda: self.service.start_order(order_id, technician_id),
            lambda: self.service.add_note(order_id, "Nota posterior"),
            lambda: self.service.consume_part(order_id, part_id, 1),
            lambda: self.service.return_part(usage),
            lambda: self.service.close_order(order_id, "Outra solução", 0),
            lambda: self.service.cancel_order(order_id, "Cancelamento posterior"),
        ]
        for action in actions:
            with self.subTest(operation=actions.index(action)):
                self.rejected_without_changes(action)


class EstoqueTests(BancadaTestCase):
    def test_part_starts_empty_and_low_stock_uses_inclusive_limit(self):
        part_id = self.part(minimum=2)
        row = self.service.list_parts()[0]
        self.assertEqual(row["stock"], 0)
        self.assertTrue(row["low_stock"])
        self.service.receive_stock(part_id, 2, 1999, "Reposição")
        self.assertTrue(self.service.list_parts()[0]["low_stock"])
        self.service.receive_stock(part_id, 1, 1999, "Reposição adicional")
        self.assertFalse(self.service.list_parts()[0]["low_stock"])

    def test_money_remains_integer_and_consumption_keeps_price_snapshot(self):
        order_id = self.order(started=True)
        part_id = self.part(price=101, stock=4)
        first_usage = self.service.consume_part(order_id, part_id, 3)
        self.service.receive_stock(part_id, 2, 203, "Preço atualizado")
        second_usage = self.service.consume_part(order_id, part_id, 2)
        usages = {row["id"]: row for row in self.service.order_parts(order_id)}
        self.assertEqual((usages[first_usage]["unit_cost_cents"], usages[first_usage]["line_cents"]), (101, 303))
        self.assertEqual((usages[second_usage]["unit_cost_cents"], usages[second_usage]["line_cents"]), (203, 406))
        self.service.close_order(order_id, "Substituição concluída", 1001)
        result = self.service.get_order(order_id)
        self.assertEqual(result["parts_cents"], 709)
        self.assertEqual(result["total_cents"], 1710)
        self.assertIs(type(result["total_cents"]), int)
        self.assertEqual(self.stock(part_id), 1)

    def test_zero_cost_is_valid(self):
        order_id = self.order(started=True)
        part_id = self.part(price=0, stock=1, minimum=0)
        self.service.consume_part(order_id, part_id, 1)
        self.service.close_order(order_id, "Peça sem custo", 0)
        self.assertEqual(self.service.get_order(order_id)["total_cents"], 0)

    def test_return_uses_original_cost_after_reference_price_changes(self):
        order_id = self.order(started=True)
        part_id = self.part(price=101, stock=2)
        usage_id = self.service.consume_part(order_id, part_id, 2)
        self.service.receive_stock(part_id, 1, 999, "Preço alterado depois do consumo")
        self.service.return_part(usage_id)
        movement = self.rows("SELECT quantity, unit_cost_cents FROM stock_movements WHERE kind = 'devolucao'")[0]
        self.assertEqual(movement, {"quantity": 2, "unit_cost_cents": 101})
        self.assertEqual(self.service.list_parts()[0]["unit_cost_cents"], 999)
        self.assertEqual(self.stock(part_id), 3)
        self.assertEqual(self.service.get_order(order_id)["parts_cents"], 0)

    def test_integers_reject_boolean_float_text_and_negative_values(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=4)
        for invalid in [True, False, 1.5, 1.0, "1", -1, None]:
            actions = [
                lambda: self.service.create_part("INVALID-A", "Peça", invalid, 10),
                lambda: self.service.create_part("INVALID-B", "Peça", 0, invalid),
                lambda: self.service.receive_stock(part_id, invalid, 10, "Entrada"),
                lambda: self.service.receive_stock(part_id, 1, invalid, "Entrada"),
                lambda: self.service.consume_part(order_id, part_id, invalid),
                lambda: self.service.close_order(order_id, "Solução", invalid),
            ]
            for action in actions:
                with self.subTest(value=invalid, operation=actions.index(action)):
                    self.rejected_without_changes(action)

    def test_zero_quantity_and_missing_receipt_note_are_rejected(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=2)
        self.rejected_without_changes(lambda: self.service.receive_stock(part_id, 0, 100, "Entrada"))
        self.rejected_without_changes(lambda: self.service.receive_stock(part_id, 1, 100, " "))
        self.rejected_without_changes(lambda: self.service.consume_part(order_id, part_id, 0))

    def test_insufficient_stock_creates_no_usage_movement_or_event(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=1)
        self.rejected_without_changes(lambda: self.service.consume_part(order_id, part_id, 2))
        self.service.consume_part(order_id, part_id, 1)
        self.assertEqual(self.stock(part_id), 0)
        self.rejected_without_changes(lambda: self.service.consume_part(order_id, part_id, 1))

    def test_cancel_requires_all_parts_returned_and_return_cannot_repeat(self):
        order_id = self.order(started=True)
        part_id = self.part(stock=4)
        first = self.service.consume_part(order_id, part_id, 2)
        second = self.service.consume_part(order_id, part_id, 1)
        self.rejected_without_changes(lambda: self.service.cancel_order(order_id, "Cancelamento"))
        self.service.return_part(first)
        self.assertEqual(self.stock(part_id), 3)
        self.rejected_without_changes(lambda: self.service.return_part(first))
        self.rejected_without_changes(lambda: self.service.cancel_order(order_id, "Cancelamento"))
        self.service.return_part(second)
        self.service.cancel_order(order_id, "Todas as peças foram devolvidas")
        self.assertEqual(self.stock(part_id), 4)
        self.assertEqual(self.service.get_order(order_id)["parts_cents"], 0)
        self.assertTrue(all(row["returned"] and row["line_cents"] == 0 for row in self.service.order_parts(order_id)))
        movements = self.rows("SELECT kind, quantity FROM stock_movements WHERE part_id = ? ORDER BY id", (part_id,))
        self.assertEqual([(row["kind"], row["quantity"]) for row in movements],
                         [("entrada", 4), ("consumo", -2), ("consumo", -1), ("devolucao", 2), ("devolucao", 1)])
