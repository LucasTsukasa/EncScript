import sqlite3
import os
from typing import Dict, List, Tuple

class StorageRepository:
    def __init__(self, db_path: str = "cloner_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabela de Mapeamento
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_map (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    source_topic_id INTEGER,
                    target_topic_id INTEGER,
                    PRIMARY KEY (source_chat_id, target_chat_id, source_topic_id)
                )
            """)
            
            # ===== V2: Estado por (source + target) =====
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    last_message_id INTEGER,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_status (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    completed INTEGER DEFAULT 0,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id)
                )
            """)

            # Cabeçalho (forum -> canal): guarda ID da msg de "Nome do Tópico" para montar índice
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_header (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    header_message_id INTEGER,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id)
                )
            """)

            # Mensagens que falharam (para retry em ciclos futuros)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failed_messages (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    message_id INTEGER,
                    error TEXT,
                    attempts INTEGER DEFAULT 0,
                    last_attempt_ts INTEGER DEFAULT 0,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id, message_id)
                )
            """)

            # Migração leve de bancos antigos (v1) caso existam em instalações anteriores.
            self._migrate_if_needed(cursor)
            
            conn.commit()

    def _migrate_if_needed(self, cursor: sqlite3.Cursor):
        """Migra instalações antigas onde sync_state/topic_status não tinham target_chat_id."""
        try:
            cursor.execute("PRAGMA table_info(sync_state)")
            cols = [r[1] for r in cursor.fetchall()]
            # Se a tabela já é v2 (tem target_chat_id), não faz nada.
            if "target_chat_id" in cols:
                return

            # Caso raro: usuário já tinha uma tabela sync_state antiga. Faz swap para v2.
            cursor.execute("ALTER TABLE sync_state RENAME TO sync_state_v1")
            cursor.execute("""
                CREATE TABLE sync_state (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    last_message_id INTEGER,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id)
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO sync_state (source_chat_id, target_chat_id, topic_id, last_message_id)
                SELECT source_chat_id, 0, topic_id, last_message_id FROM sync_state_v1
            """)
        except Exception:
            # Se algo falhar, segue sem bloquear; o app recria o DB conforme necessário.
            return

        try:
            cursor.execute("PRAGMA table_info(topic_status)")
            cols = [r[1] for r in cursor.fetchall()]
            if "target_chat_id" in cols:
                return
            cursor.execute("ALTER TABLE topic_status RENAME TO topic_status_v1")
            cursor.execute("""
                CREATE TABLE topic_status (
                    source_chat_id INTEGER,
                    target_chat_id INTEGER,
                    topic_id INTEGER,
                    completed INTEGER DEFAULT 0,
                    PRIMARY KEY (source_chat_id, target_chat_id, topic_id)
                )
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO topic_status (source_chat_id, target_chat_id, topic_id, completed)
                SELECT source_chat_id, 0, topic_id, completed FROM topic_status_v1
            """)
        except Exception:
            return

    def reset_chat_progress(self, source_chat: int, target_chat: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM topic_map 
                WHERE source_chat_id = ? AND target_chat_id = ?
            """, (source_chat, target_chat))
            
            cursor.execute("DELETE FROM sync_state WHERE source_chat_id = ? AND target_chat_id = ?", (source_chat, target_chat))
            cursor.execute("DELETE FROM topic_status WHERE source_chat_id = ? AND target_chat_id = ?", (source_chat, target_chat))
            cursor.execute("DELETE FROM topic_header WHERE source_chat_id = ? AND target_chat_id = ?", (source_chat, target_chat))
            cursor.execute("DELETE FROM failed_messages WHERE source_chat_id = ? AND target_chat_id = ?", (source_chat, target_chat))
            conn.commit()

    def is_topic_completed(self, source_chat: int, target_chat: int, topic_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT completed FROM topic_status
                WHERE source_chat_id = ? AND target_chat_id = ? AND topic_id = ?
            """, (source_chat, target_chat, topic_id))
            row = cursor.fetchone()
            return bool(row and row[0])

    def mark_topic_completed(self, source_chat: int, target_chat: int, topic_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO topic_status (source_chat_id, target_chat_id, topic_id, completed)
                VALUES (?, ?, ?, 1)
            """, (source_chat, target_chat, topic_id))
            conn.commit()

    def export_topics_manifest(self, topics: List[Tuple[int, str]]) -> str:
        filename = "topics_config.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            # ATUALIZAÇÃO 4: Cabeçalho com nova instrução 'P'
            f.write("# ID | Tópico | Clonar (ON/OFF/P)\n")
            f.write("# ON = Clonar | OFF = Ignorar | P = Prioridade (Clona SÓ os marcados com P)\n")
            f.write("# Edite 'ON' para 'OFF' ou 'P'.\n\n")
            
            for t_id, t_title in topics:
                safe_title = t_title.replace("|", "-")
                f.write(f"{t_id} | {safe_title} | ON\n")
        return filename

    def read_topics_manifest(self) -> List[int]:
        filename = "topics_config.txt"
        
        # ATUALIZAÇÃO 3: Listas separadas para lógica de prioridade
        on_ids = []
        p_ids = []
        
        if not os.path.exists(filename):
            return []
        
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split('|')
                if len(parts) >= 3:
                    try:
                        t_id = int(parts[0].strip())
                        status = parts[2].strip().upper()
                        
                        # Captura flags
                        if status == "P":
                            p_ids.append(t_id)
                        elif status == "ON":
                            on_ids.append(t_id)
                            
                    except ValueError:
                        continue
        
        # ATUALIZAÇÃO 3: Algoritmo de decisão
        # Se houver ALGUM 'P', retorna apenas os 'P's (ignora ONs e OFFs)
        if p_ids:
            return p_ids
        
        # Caso contrário, retorna os 'ON's (comportamento padrão)
        return on_ids

    def get_topic_map(self, source_chat: int, target_chat: int) -> Dict[int, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT source_topic_id, target_topic_id 
                FROM topic_map 
                WHERE source_chat_id = ? AND target_chat_id = ?
            """, (source_chat, target_chat))
            return {row[0]: row[1] for row in cursor.fetchall()}

    def save_topic_mapping(self, source_chat: int, target_chat: int, src_id: int, tgt_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO topic_map 
                (source_chat_id, target_chat_id, source_topic_id, target_topic_id)
                VALUES (?, ?, ?, ?)
            """, (source_chat, target_chat, src_id, tgt_id))
            conn.commit()

    def get_last_message_id(self, source_chat: int, target_chat: int, topic_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT last_message_id FROM sync_state 
                WHERE source_chat_id = ? AND target_chat_id = ? AND topic_id = ?
            """, (source_chat, target_chat, topic_id))
            res = cursor.fetchone()
            return res[0] if res else 0

    def save_last_message_id(self, source_chat: int, target_chat: int, topic_id: int, msg_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sync_state VALUES (?, ?, ?, ?)
            """, (source_chat, target_chat, topic_id, msg_id))
            conn.commit()

    # ===== Cabeçalho / Índice =====
    def get_topic_header_message_id(self, source_chat: int, target_chat: int, topic_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT header_message_id FROM topic_header
                WHERE source_chat_id = ? AND target_chat_id = ? AND topic_id = ?
            """, (source_chat, target_chat, topic_id))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else 0

    def save_topic_header_message_id(self, source_chat: int, target_chat: int, topic_id: int, msg_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO topic_header VALUES (?, ?, ?, ?)
            """, (source_chat, target_chat, topic_id, msg_id))
            conn.commit()

    # ===== Falhas / Retry =====
    def record_failed_message(self, source_chat: int, target_chat: int, topic_id: int, msg_id: int, error: str):
        import time
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO failed_messages (source_chat_id, target_chat_id, topic_id, message_id, error, attempts, last_attempt_ts)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(source_chat_id, target_chat_id, topic_id, message_id)
                DO UPDATE SET
                    error=excluded.error,
                    attempts=attempts+1,
                    last_attempt_ts=excluded.last_attempt_ts
            """, (source_chat, target_chat, topic_id, msg_id, error[:500], int(time.time())))
            conn.commit()

    def clear_failed_message(self, source_chat: int, target_chat: int, topic_id: int, msg_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM failed_messages
                WHERE source_chat_id = ? AND target_chat_id = ? AND topic_id = ? AND message_id = ?
            """, (source_chat, target_chat, topic_id, msg_id))
            conn.commit()

    def list_failed_messages(self, source_chat: int, target_chat: int, topic_id: int, limit: int = 200):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_id FROM failed_messages
                WHERE source_chat_id = ? AND target_chat_id = ? AND topic_id = ?
                ORDER BY message_id ASC
                LIMIT ?
            """, (source_chat, target_chat, topic_id, limit))
            return [int(r[0]) for r in cursor.fetchall()]