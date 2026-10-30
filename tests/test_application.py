from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import io
from unittest.mock import patch

from app.db import Database
from app.demo import create_demo
from app.service import Service
from main import main
from tests import BancadaTestCase


class ApplicationTests(BancadaTestCase):
    def test_demo_is_complete_and_repeated_open_preserves_changes(self):
        path = self.folder / "demo.sqlite3"
        now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        self.assertTrue(create_demo(path, now))
        service = Service(Database(path), clock=lambda: now)
        self.assertEqual(len(service.list_equipment()), 12)
        self.assertEqual(len(service.list_technicians()), 4)
        self.assertEqual(len(service.list_parts()), 8)
        self.assertEqual(len(service.list_orders()), 35)
        dashboard = service.dashboard()
        self.assertEqual(dashboard["closed_count"], 24)
        self.assertEqual(dashboard["open_count"], 9)
        self.assertEqual(dashboard["in_progress_count"], 4)
        self.assertEqual(dashboard["total_closed_cents"], 339840)
        equipment = service.list_equipment()[0]
        service.update_equipment(equipment["id"], equipment["tag"], "Nome alterado",
                                 equipment["category"], equipment["location"])
        before = path.read_bytes()
        self.assertFalse(create_demo(path, now))
        self.assertEqual(path.read_bytes(), before)

    def test_demo_failure_does_not_publish_partial_database(self):
        path = self.folder / "incompleta.sqlite3"
        with patch("app.demo.Service.open_order", side_effect=ValueError("Falha simulada")):
            with self.assertRaises(ValueError):
                create_demo(path)
        self.assertFalse(path.exists())

    def test_check_opens_existing_database_without_creating_demo_records(self):
        self.equipment()
        before = self.snapshot()
        with redirect_stdout(io.StringIO()) as output:
            code = main(["--db", str(self.db.path), "--check"])
        self.assertEqual(code, 0)
        self.assertIn("Banco íntegro", output.getvalue())
        self.assertEqual(self.snapshot(), before)

    def test_invalid_database_is_reported_without_traceback(self):
        path = self.folder / "invalido.sqlite3"
        path.write_bytes(b"Nao e um banco SQLite")
        with redirect_stderr(io.StringIO()) as output:
            code = main(["--db", str(path), "--check"])
        self.assertEqual(code, 1)
        self.assertIn("Não foi possível iniciar", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
        self.assertEqual(path.read_bytes(), b"Nao e um banco SQLite")
