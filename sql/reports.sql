-- Consultas de estudo para executar sobre uma cópia do banco SQLite.
-- Os valores monetários permanecem em centavos inteiros.
-- A aplicação usa parâmetros para buscas e datas; aqui a data fixa permite reproduzir o exemplo.

-- 1. Fila ativa com prazo e equipamento. A comparação usa datas UTC no mesmo formato.
SELECT o.id, e.tag, e.name, o.title, o.priority, o.status, o.opened_at, o.due_at,
       COALESCE(t.name, 'Sem responsável') AS technician_name,
       CASE WHEN o.due_at < '2026-10-29T12:00:00+00:00' THEN 1 ELSE 0 END AS overdue
FROM orders AS o
JOIN equipment AS e ON e.id = o.equipment_id
LEFT JOIN technicians AS t ON t.id = o.technician_id
WHERE o.status IN ('aberta', 'em_andamento')
ORDER BY o.opened_at, o.id;

-- 2. Custo das ordens concluídas por equipamento.
-- Primeiro somamos as peças por ordem; assim a mão de obra não se repete por peça.
SELECT e.tag, e.name, COUNT(o.id) AS order_count,
       COALESCE(SUM(o.labor_cents + COALESCE(p.parts_cents, 0)), 0) AS total_cents
FROM equipment AS e
LEFT JOIN orders AS o ON o.equipment_id = e.id AND o.status = 'concluida'
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_cost_cents) AS parts_cents
    FROM order_parts
    WHERE returned = 0
    GROUP BY order_id
) AS p ON p.order_id = o.id
GROUP BY e.id, e.tag, e.name
ORDER BY total_cents DESC, e.tag;

-- 3. Encerramentos por mês, usando a data da conclusão e excluindo cancelamentos.
-- Esta consulta mostra meses com movimento; o serviço preenche os meses vazios na tela.
SELECT substr(o.closed_at, 1, 7) AS month, COUNT(*) AS count,
       SUM(o.labor_cents + COALESCE(p.parts_cents, 0)) AS total_cents
FROM orders AS o
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_cost_cents) AS parts_cents
    FROM order_parts WHERE returned = 0 GROUP BY order_id
) AS p ON p.order_id = o.id
WHERE o.status = 'concluida'
GROUP BY substr(o.closed_at, 1, 7)
ORDER BY month;

-- 4. Duração corrida da abertura à conclusão. Inclui noites e fins de semana.
SELECT COUNT(*) AS closed_count,
       ROUND(AVG((julianday(closed_at) - julianday(opened_at)) * 24), 2) AS avg_resolution_hours
FROM orders
WHERE status = 'concluida';

-- 5. Peças no mínimo ou abaixo dele. Estoque zero também entra.
SELECT sku, name, stock, min_stock, unit_cost_cents
FROM parts
WHERE stock <= min_stock
ORDER BY stock, sku;

-- 6. Conciliação do estoque com os movimentos: deve retornar zero linhas.
-- Entrada e devolução são positivas; consumo é negativo.
SELECT p.sku, p.stock, COALESCE(SUM(m.quantity), 0) AS movement_balance
FROM parts AS p
LEFT JOIN stock_movements AS m ON m.part_id = p.id
GROUP BY p.id, p.sku, p.stock
HAVING p.stock <> COALESCE(SUM(m.quantity), 0);

-- 7. Equipamentos sem qualquer ordem. LEFT JOIN mantém o cadastro sem correspondência.
SELECT e.tag, e.name, e.location
FROM equipment AS e
LEFT JOIN orders AS o ON o.equipment_id = e.id
WHERE o.id IS NULL
ORDER BY e.tag;

-- 8. Histórico de uma ordem. Substitua 1 pelo identificador que deseja investigar.
SELECT created_at, event, detail
FROM order_events
WHERE order_id = 1
ORDER BY created_at, id;
