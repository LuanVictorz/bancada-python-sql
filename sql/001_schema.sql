-- A aplicação executa este arquivo em uma transação na primeira abertura.
CREATE TABLE equipment (
    id INTEGER PRIMARY KEY,
    tag TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(tag)) BETWEEN 1 AND 40),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
    category TEXT NOT NULL CHECK(length(trim(category)) BETWEEN 1 AND 80),
    location TEXT NOT NULL CHECK(length(trim(location)) BETWEEN 1 AND 120),
    active INTEGER NOT NULL DEFAULT 1 CHECK(typeof(active) = 'integer' AND active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE technicians (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) BETWEEN 1 AND 120),
    active INTEGER NOT NULL DEFAULT 1 CHECK(typeof(active) = 'integer' AND active IN (0, 1))
);

CREATE TABLE parts (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(sku)) BETWEEN 1 AND 40),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
    stock INTEGER NOT NULL DEFAULT 0 CHECK(typeof(stock) = 'integer' AND stock BETWEEN 0 AND 1000000000),
    min_stock INTEGER NOT NULL CHECK(typeof(min_stock) = 'integer' AND min_stock BETWEEN 0 AND 1000000000),
    unit_cost_cents INTEGER NOT NULL CHECK(typeof(unit_cost_cents) = 'integer' AND unit_cost_cents BETWEEN 0 AND 1000000000)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    technician_id INTEGER REFERENCES technicians(id),
    title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 120),
    description TEXT NOT NULL CHECK(length(description) <= 2000),
    priority TEXT NOT NULL CHECK(priority IN ('baixa', 'media', 'alta')),
    status TEXT NOT NULL DEFAULT 'aberta' CHECK(status IN ('aberta', 'em_andamento', 'concluida', 'cancelada')),
    opened_at TEXT NOT NULL,
    started_at TEXT,
    closed_at TEXT,
    due_at TEXT NOT NULL,
    resolution TEXT NOT NULL DEFAULT '' CHECK(length(resolution) <= 2000),
    labor_cents INTEGER NOT NULL DEFAULT 0 CHECK(typeof(labor_cents) = 'integer' AND labor_cents BETWEEN 0 AND 1000000000),
    CHECK(due_at >= opened_at),
    CHECK(started_at IS NULL OR started_at >= opened_at),
    CHECK(closed_at IS NULL OR closed_at >= COALESCE(started_at, opened_at)),
    CHECK((status IN ('aberta', 'em_andamento') AND closed_at IS NULL AND resolution = '' AND labor_cents = 0)
       OR (status IN ('concluida', 'cancelada') AND closed_at IS NOT NULL AND length(trim(resolution)) > 0)),
    CHECK(status != 'aberta' OR started_at IS NULL),
    CHECK(status NOT IN ('em_andamento', 'concluida') OR (started_at IS NOT NULL AND technician_id IS NOT NULL)),
    CHECK(status != 'cancelada' OR labor_cents = 0)
);

CREATE TABLE order_parts (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    part_id INTEGER NOT NULL REFERENCES parts(id),
    quantity INTEGER NOT NULL CHECK(typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 1000000),
    unit_cost_cents INTEGER NOT NULL CHECK(typeof(unit_cost_cents) = 'integer' AND unit_cost_cents BETWEEN 0 AND 1000000000),
    returned INTEGER NOT NULL DEFAULT 0 CHECK(typeof(returned) = 'integer' AND returned IN (0, 1))
);

CREATE TABLE stock_movements (
    id INTEGER PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id),
    order_id INTEGER REFERENCES orders(id),
    kind TEXT NOT NULL CHECK(kind IN ('entrada', 'consumo', 'devolucao')),
    quantity INTEGER NOT NULL CHECK(typeof(quantity) = 'integer' AND quantity != 0 AND abs(quantity) <= 1000000),
    unit_cost_cents INTEGER NOT NULL CHECK(typeof(unit_cost_cents) = 'integer' AND unit_cost_cents BETWEEN 0 AND 1000000000),
    created_at TEXT NOT NULL,
    note TEXT NOT NULL CHECK(length(trim(note)) BETWEEN 1 AND 2000),
    CHECK((kind = 'entrada' AND quantity > 0 AND order_id IS NULL)
       OR (kind = 'consumo' AND quantity < 0 AND order_id IS NOT NULL)
       OR (kind = 'devolucao' AND quantity > 0 AND order_id IS NOT NULL))
);

CREATE TABLE order_events (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    created_at TEXT NOT NULL,
    event TEXT NOT NULL CHECK(length(trim(event)) > 0),
    detail TEXT NOT NULL CHECK(length(trim(detail)) > 0)
);

CREATE INDEX idx_orders_equipment ON orders(equipment_id);
CREATE INDEX idx_orders_status_due ON orders(status, due_at);
CREATE INDEX idx_orders_technician ON orders(technician_id);
CREATE INDEX idx_orders_closed ON orders(closed_at);
CREATE INDEX idx_order_parts_order ON order_parts(order_id);
CREATE INDEX idx_order_parts_part ON order_parts(part_id);
CREATE INDEX idx_movements_part_date ON stock_movements(part_id, created_at);
CREATE INDEX idx_movements_order ON stock_movements(order_id);
CREATE INDEX idx_events_order_date ON order_events(order_id, created_at, id);
