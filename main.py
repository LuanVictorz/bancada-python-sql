"""Entrada da aplicação e conferência da base sem abrir a interface."""

import argparse
from pathlib import Path
import sqlite3
import sys

from app.db import Database
from app.service import DomainError, Service

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bancada: manutenção de equipamentos e estoque.")
    parser.add_argument("--demo", action="store_true", help="abre dados fictícios em uma base separada")
    parser.add_argument("--db", type=Path, help="caminho alternativo para a base SQLite")
    parser.add_argument("--check", action="store_true", help="confere banco e indicadores sem abrir janela")
    args = parser.parse_args(argv)
    path = args.db or ROOT / "dados" / ("demo.sqlite3" if args.demo else "bancada.sqlite3")
    try:
        if args.demo:
            from app.demo import create_demo
            create_demo(path)
        db = Database(path)
        db.initialize()
        service = Service(db)
        if args.check:
            connection = db.connect()
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            finally:
                connection.close()
            if integrity != "ok" or foreign_keys:
                raise DomainError("A base tem inconsistências. Preserve uma cópia antes de investigar.")
            data = service.dashboard()
            print("Banco íntegro. Relacionamentos conferidos.")
            print(f"Ordens pendentes: {data['open_count']}")
            print(f"Ordens concluídas: {data['closed_count']}")
            return 0
        try:
            from app.ui import launch
        except ImportError as error:
            if error.name not in ("tkinter", "_tkinter"):
                raise
            print("Tkinter não está disponível. Instale uma distribuição Python com suporte a Tk.", file=sys.stderr)
            return 1
        launch(service, demo=args.demo)
        return 0
    except (DomainError, sqlite3.Error, OSError, ValueError) as error:
        print(f"Não foi possível iniciar o Bancada: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
