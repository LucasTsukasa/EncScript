import os
import sys
import logging
from dataclasses import dataclass
from dotenv import load_dotenv, set_key

load_dotenv()

@dataclass
class AppSettings:
    """Configurações dinâmicas do usuário."""
    update_msgs_start: bool = False
    update_msgs_end: bool = True
    clean_visual: bool = False
    update_photo: bool = True
    update_desc: bool = True
    close_topics: str = "PARCIAL"
    fix_topics: bool = True

    # NOVAS CONFIGURAÇÕES (controle de destino / canais)
    rename_existing_target: bool = True
    forum_to_channel_topic_header: bool = True  # envia e fixa "Nome do Tópico" ao iniciar cada tópico
    forum_to_channel_final_index: bool = True   # envia um índice no final (pode virar múltiplas msgs)
    forum_to_channel_pin_final_index: bool = True
    
    # NOVAS CONFIGURAÇÕES (Itens 8 a 12)
    max_session_hours: float = 6.0
    pause_duration_hours: float = 1.0
    delay_between_messages: float = 5.0
    pause_every_x_messages: int = 300
    pause_duration_s: int = 60

    # Performance
    batch_size: int = 100

@dataclass
class AppConfig:
    """Configurações de infraestrutura e credenciais."""
    api_id: int
    api_hash: str
    phone: str
    
    source_chat_id: int = 0
    target_chat_id: int = 0
    
    max_session_hours: float = 6.0
    pause_duration_hours: float = 1.0
    batch_size: int = 100
    delay_between_messages: float = 5.0
    pause_every_x_messages: int = 300
    pause_duration_s: int = 60
    
    session_name: str = "cloner_session"

    # Ajuda o serviço a decidir comportamentos (ex: renomear destino)
    target_created_by_app: bool = False

    # Padrão único para nome do backup
    backup_title_template: str = "{title} [Backup]"

    def build_backup_title(self, source_title: str) -> str:
        return self.backup_title_template.format(title=source_title)

    @property
    def max_session_seconds(self) -> float:
        return self.max_session_hours * 3600

def setup_logging(clean_visual: bool = False):
    """Configura logging."""
    root = logging.getLogger()
    
    if root.handlers:
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    level_console = logging.ERROR if clean_visual else logging.INFO

    file_handler = logging.FileHandler("cloner.log", encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_console)
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    
    logging.getLogger('telethon').setLevel(logging.WARNING)

def save_env_variable(key: str, value: str):
    set_key('.env', key, str(value))