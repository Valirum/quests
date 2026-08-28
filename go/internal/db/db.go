package db

import (
	"database/sql"
	"fmt"
	"os"

	_ "modernc.org/sqlite"
)

const expectedAlembic = "a1c2e3f4b5d6"

func Open(path string) (*sql.DB, error) {
	if err := os.MkdirAll(dirOf(path), 0o755); err != nil {
		return nil, err
	}
	// WAL + busy timeout — match Python db.py
	dsn := fmt.Sprintf("file:%s?_pragma=busy_timeout(30000)&_pragma=journal_mode(WAL)&_pragma=foreign_keys(ON)", path)
	sqlDB, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	sqlDB.SetMaxOpenConns(1) // SQLite: single writer
	sqlDB.SetMaxIdleConns(1)
	if err := sqlDB.Ping(); err != nil {
		_ = sqlDB.Close()
		return nil, err
	}
	if err := assertMigrated(sqlDB); err != nil {
		_ = sqlDB.Close()
		return nil, err
	}
	return sqlDB, nil
}

func dirOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' {
			return path[:i]
		}
	}
	return "."
}

func assertMigrated(db *sql.DB) error {
	var ver string
	err := db.QueryRow(`SELECT version_num FROM alembic_version LIMIT 1`).Scan(&ver)
	if err == sql.ErrNoRows {
		return fmt.Errorf("quests.db has no alembic_version; run: uv run quests-migrate")
	}
	if err != nil {
		return fmt.Errorf("read alembic_version: %w (run Python migrate first)", err)
	}
	if ver != expectedAlembic {
		return fmt.Errorf("alembic_version=%s want %s; upgrade with Python Alembic first", ver, expectedAlembic)
	}
	return nil
}
