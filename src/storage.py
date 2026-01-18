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
            
            # Tabela de Última Mensagem (Checkpoint por mensagem)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    source_chat_id INTEGER,
                    topic_id INTEGER,
                    last_message_id INTEGER,
                    PRIMARY KEY (source_chat_id, topic_id)
                )
            """)

            # Tabela de Status do Tópico
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_status (
                    source_chat_id INTEGER,
                    topic_id INTEGER,
                    completed INTEGER DEFAULT 0,
                    PRIMARY KEY (source_chat_id, topic_id)
                )
            """)
            
            conn.commit()

    def reset_chat_progress(self, source_chat: int, target_chat: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM topic_map 
                WHERE source_chat_id = ? AND target_chat_id = ?
            """, (source_chat, target_chat))
            
            cursor.execute("DELETE FROM sync_state WHERE source_chat_id = ?", (source_chat,))
            cursor.execute("DELETE FROM topic_status WHERE source_chat_id = ?", (source_chat,))
            conn.commit()

    def is_topic_completed(self, source_chat: int, topic_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT completed FROM topic_status
                WHERE source_chat_id = ? AND topic_id = ?
            """, (source_chat, topic_id))
            row = cursor.fetchone()
            return bool(row and row[0])

    def mark_topic_completed(self, source_chat: int, topic_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO topic_status (source_chat_id, topic_id, completed)
                VALUES (?, ?, 1)
            """, (source_chat, topic_id))
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

    def get_last_message_id(self, source_chat: int, topic_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT last_message_id FROM sync_state 
                WHERE source_chat_id = ? AND topic_id = ?
            """, (source_chat, topic_id))
            res = cursor.fetchone()
            return res[0] if res else 0

    def save_last_message_id(self, source_chat: int, topic_id: int, msg_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sync_state VALUES (?, ?, ?)
            """, (source_chat, topic_id, msg_id))
            conn.commit()