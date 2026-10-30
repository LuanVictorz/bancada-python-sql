"""Base de exemplo montada pelas mesmas regras usadas na aplicação."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db import Database
from app.service import Service


def create_demo(path, now=None):
    """Cria uma demo nova. Nunca reinicia uma base que já existe."""
    path = Path(path).resolve()
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    reference = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    if reference.tzinfo is None:
        raise ValueError("A data da demonstração precisa incluir o fuso horário.")
    with TemporaryDirectory(prefix="bancada-demo-", dir=path.parent) as temporary:
        database = Database(Path(temporary) / "preparo.sqlite3")
        database.initialize()
        moment = [reference - timedelta(days=210)]
        service = Service(database, clock=lambda: moment[0])
        technicians = [service.create_technician(name) for name in
                       ("Ana Ribeiro", "Bruno Costa", "Carla Mendes", "Diego Alves")]
        inventory = [
            ("TI-001", "Notebook administrativo", "Computador", "Administrativo"),
            ("TI-002", "Desktop do estoque", "Computador", "Estoque"),
            ("TI-003", "Impressora de etiquetas", "Impressora", "Expedição"),
            ("TI-004", "Switch 24 portas", "Rede", "Sala técnica"),
            ("TI-005", "Notebook de atendimento", "Computador", "Recepção"),
            ("TI-006", "Impressora multifuncional", "Impressora", "Administrativo"),
            ("TI-007", "Ponto de acesso Wi-Fi", "Rede", "Recepção"),
            ("TI-008", "Monitor 24 polegadas", "Periférico", "Financeiro"),
            ("TI-009", "Desktop de relatórios", "Computador", "Financeiro"),
            ("TI-010", "Leitor de código de barras", "Periférico", "Estoque"),
            ("TI-011", "Notebook de reserva", "Computador", "Sala técnica"),
            ("TI-012", "Projetor da sala de reunião", "Audiovisual", "Reunião"),
        ]
        equipment = [service.create_equipment(*item) for item in inventory]
        supplies = [
            ("SSD-480", "SSD SATA 480 GB", 3, 21990, 16),
            ("RAM-8", "Memória DDR4 8 GB", 3, 13990, 16),
            ("CAB-RJ45", "Cabo de rede 2 m", 6, 1890, 28),
            ("FONT-65", "Fonte para notebook 65 W", 2, 12900, 12),
            ("TON-PB", "Toner preto", 2, 15900, 12),
            ("CON-RJ45", "Conector RJ45", 20, 180, 60),
            ("CAB-HDMI", "Cabo HDMI 2 m", 5, 3590, 3),
            ("ROL-IMP", "Rolete de impressora", 2, 6900, 1),
        ]
        parts = []
        for sku, name, minimum, cost, initial in supplies:
            part = service.create_part(sku, name, minimum, cost)
            service.receive_stock(part, initial, cost, "Carga inicial fictícia da demonstração")
            parts.append(part)

        ages = [165, 158, 151, 145, 138, 131, 125, 118, 111, 105, 98, 91,
                85, 78, 71, 65, 58, 51, 45, 38, 31, 22, 12, 3]
        titles = ["Inicialização lenta", "Falha intermitente de conexão", "Equipamento não liga",
                  "Impressão com falhas", "Revisão preventiva", "Instabilidade após atualização"]
        for index, age in enumerate(ages):
            moment[0] = reference - timedelta(days=age)
            order = service.open_order(
                equipment[index % 10], titles[index % len(titles)],
                "Ocorrência fictícia para demonstrar registro, diagnóstico e custos.",
                ("baixa", "media", "alta")[index % 3], technicians[index % 3])
            moment[0] += timedelta(hours=1)
            service.start_order(order, technicians[index % 3])
            service.add_note(order, "Inspeção inicial concluída. Testes de funcionamento registrados.")
            if index % 3 != 1:
                service.consume_part(order, parts[index % 6], 1)
            moment[0] += timedelta(hours=(2, 6, 18, 30, 48)[index % 5])
            service.close_order(order, "Correção aplicada e funcionamento conferido em teste local.",
                                (4500, 6500, 9000, 12000)[index % 4])

        pending = [
            (8, "Desktop sem acesso ao sistema", "alta", 72, True),
            (2, "Etiquetas saem desalinhadas", "media", 98, True),
            (6, "Wi-Fi com quedas na recepção", "alta", 40, False),
            (0, "Notebook aquece durante o uso", "media", 52, True),
            (7, "Monitor perde sinal de vídeo", "baixa", 190, False),
            (4, "Bateria não mantém carga", "media", 14, False),
            (3, "Porta de rede sem conexão", "alta", 6, True),
            (9, "Leitor não reconhece etiquetas", "baixa", 22, False),
            (5, "Revisão da alimentação de papel", "baixa", 3, False),
        ]
        for index, (asset, title, priority, hours, in_progress) in enumerate(pending):
            moment[0] = reference - timedelta(hours=hours)
            order = service.open_order(equipment[asset], title,
                                       "Chamado fictício em acompanhamento.", priority,
                                       technicians[index % 4] if in_progress else None)
            if in_progress:
                moment[0] += timedelta(hours=1)
                service.start_order(order, technicians[index % 4])
                service.add_note(order, "Diagnóstico em andamento; aguardando teste complementar.")
                if index == 0:
                    service.consume_part(order, parts[0], 1)

        for index in range(2):
            moment[0] = reference - timedelta(days=9 - index)
            order = service.open_order(equipment[index], "Solicitação duplicada",
                                       "Exemplo de cancelamento com justificativa.", "baixa")
            service.cancel_order(order, "A mesma ocorrência já foi registrada em outra ordem.")
        moment[0] = reference
        service.backup(path)
    return True
