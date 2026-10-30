"""Conexões SQLite e criação versionada da estrutura local."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3


class DomainError(ValueError):
    """Erro esperado que pode ser apresentado ao usuário."""


def database_error(error):
    message = str(error).lower()
    if "unique constraint" in message:
        return DomainError("Já existe um cadastro com esse código ou nome.")
    if "foreign key" in message:
        return DomainError("O cadastro relacionado não existe ou está em uso.")
    if "locked" in message or "busy" in message:
        return DomainError("O banco está ocupado. Aguarde um momento e tente novamente.")
    if "readonly" in message or "unable to open" in message:
        return DomainError("Não foi possível gravar o banco. Confira a pasta e suas permissões.")
    if "check constraint" in message or "not null" in message:
        return DomainError("Os dados não atendem às regras do cadastro.")
    return DomainError("Não foi possível concluir a operação no banco de dados.")


class Database:
    VERSION = 1

    def __init__(self, path):
        try:
            self.path = Path(path).expanduser().resolve()
        except (TypeError, ValueError, OSError) as error:
            raise DomainError("Informe um caminho válido para o banco.") from error

    def connect(self):
        try:
            connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            return connection
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as error:
            raise database_error(error) from error

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def initialize(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            schema = (Path(__file__).resolve().parent.parent / "sql" / "001_schema.sql").read_text(encoding="utf-8")
            with self.transaction() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > self.VERSION:
                    raise DomainError("Este banco foi criado por uma versão mais recente do Bancada.")
                if version == self.VERSION:
                    return
                existing = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone()
                if existing:
                    raise DomainError("O arquivo já contém tabelas sem uma versão reconhecida. Escolha outro banco.")
                statement = ""
                for line in schema.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise DomainError("O arquivo de estrutura está incompleto.")
                connection.execute("PRAGMA user_version = 1")
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as error:
            raise database_error(error) from error
        except OSError as error:
            raise DomainError("Não foi possível acessar a pasta ou o arquivo de estrutura do banco.") from error
