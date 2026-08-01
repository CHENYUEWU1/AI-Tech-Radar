-- analysis_results 表：AI 分析结果
-- 对应 analyzers/schemas.py 中的 AnalysisResult

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键
    article_id INTEGER NOT NULL,            -- 关联 articles 表的文章 ID
    importance INTEGER NOT NULL
        CHECK (importance BETWEEN 1 AND 10),-- 重要性评分，范围 1-10
    category TEXT NOT NULL,                 -- 新闻分类
    tags TEXT NOT NULL,                     -- 标签列表，使用 JSON 字符串保存
    summary TEXT NOT NULL,                  -- AI 生成的摘要
    impact TEXT NOT NULL,                   -- 对行业的影响分析
    action TEXT NOT NULL,                   -- 后续关注建议
    model TEXT NOT NULL,                    -- 使用的 AI 模型名称
    created_at TEXT NOT NULL
        DEFAULT (datetime('now')),          -- 分析结果创建时间
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);
