-- importance_scores 表：AI 信息价值评分

CREATE TABLE IF NOT EXISTS importance_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    importance_score INTEGER NOT NULL
        CHECK (importance_score BETWEEN 0 AND 10),
    impact TEXT NOT NULL,
    reason TEXT NOT NULL,
    trend TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);
