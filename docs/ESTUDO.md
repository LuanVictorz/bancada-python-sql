# Estudar e evoluir o projeto

O projeto tem mais camadas que os exercícios anteriores. Vale acompanhar uma operação completa antes de tentar entender todos os arquivos.

## Primeira leitura

1. Execute a demonstração e complete um atendimento.
2. Abra `sql/001_schema.sql`. Localize a ordem e suas relações com equipamento, técnico e peças.
3. Em `app/service.py`, acompanhe `open_order`, `start_order` e `close_order`.
4. Veja como a interface chama esses métodos em `app/ui.py`.
5. Leia um teste de consumo válido e um de saldo insuficiente.

## Experimento com estoque

Crie uma peça fictícia e receba duas unidades. Consuma uma unidade em uma ordem. Tente consumir mais duas. A segunda operação deve falhar, mantendo uma unidade no estoque e apenas o primeiro consumo registrado.

Confira os dados com consultas de leitura:

```sql
SELECT sku, name, stock FROM parts;

SELECT o.id, o.title, p.sku, op.quantity, op.unit_cost_cents, op.returned
FROM orders AS o
JOIN order_parts AS op ON op.order_id = o.id
JOIN parts AS p ON p.id = op.part_id
ORDER BY o.id, op.id;
```

## Mudanças possíveis

1. **Filtro por prioridade.** Acrescente o filtro no serviço e na tela de ordens. Mantenha a busca atual e escreva um teste combinando os dois filtros.
2. **Cadastro de fornecedor.** Crie uma migração de versão 2, preserve bases da versão 1 e relacione fornecedores com entradas de estoque. Teste uma migração com dados existentes.
3. **Relatório por período.** Aceite datas inicial e final, defina se a referência é abertura ou conclusão e teste os limites do intervalo.
4. **Devolução parcial.** Defina quantidade devolvida, impeça excesso e preserve o custo da quantidade restante. Essa alteração afeta banco, serviço, interface e testes.

Faça uma mudança por vez. Registre no commit o comportamento que mudou e os testes executados.

## Perguntas que vale saber responder

- Por que SQLite é suficiente para esta versão local?
- Por que o preço da peça precisa ficar registrado no consumo?
- O que acontece se o estoque for atualizado, mas a gravação do histórico falhar?
- Qual é a diferença entre validar no formulário e usar uma restrição no banco?
- Por que somar mão de obra após juntar várias peças pode duplicar valores?
- O que precisaria mudar para várias pessoas usarem o sistema em computadores diferentes?

A demonstração usa dados fictícios e serve para explicar comportamentos. Ela não representa uso em uma empresa nem resultados comerciais.
