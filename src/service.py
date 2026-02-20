import asyncio
import time
import logging
import os
import socket
from datetime import datetime
from rich.progress import track
from rich.console import Console
from telethon import TelegramClient, errors
from telethon.tl.types import (
    MessageService, 
    ForumTopicDeleted, 
    MessageMediaWebPage,
    MessageActionPinMessage
)
from telethon.tl.functions.channels import (
    GetForumTopicsRequest, 
    CreateForumTopicRequest,
    EditTitleRequest,
    EditPhotoRequest,
    EditForumTopicRequest,
    UpdatePinnedForumTopicRequest,
    GetFullChannelRequest
)
from telethon.tl.functions.messages import EditChatAboutRequest

from .config import AppConfig, AppSettings
from .storage import StorageRepository

console = Console()

class WorkTimeLimitReached(Exception): pass

class ClonerService:
    def __init__(self, client: TelegramClient, config: AppConfig, settings: AppSettings, storage: StorageRepository):
        self.client = client
        self.config = config
        self.settings = settings
        self.storage = storage
        self.is_premium = False
        self.session_start_time = 0
        self.messages_sent = 0
        self.logged_topics = set()
        self.session_message_count = 0

    def _log_visual(self, message: str, is_error: bool = False, force_clean_view: bool = False):
        if is_error:
            console.print(f"[bold red]{message}[/]")
            logging.error(message)
            return

        if self.settings.clean_visual:
            if force_clean_view:
                console.print(message)
        else:
            logging.info(message)

    def _check_work_time(self):
        if self.session_start_time > 0:
            elapsed = time.time() - self.session_start_time
            if elapsed >= self.config.max_session_seconds:
                raise WorkTimeLimitReached()

    async def _handle_flood_wait(self, error: errors.FloodWaitError):
        msg = f"⚠️ FloodWait detectado. Aguardando {error.seconds}s..."
        self._log_visual(msg, is_error=True)
        await asyncio.sleep(error.seconds + 5)

    def _check_internet_and_time(self):
        """Bloqueia o ciclo até ter internet e hora OK."""
        while True:
            ok = True
            try:
                socket.create_connection(("1.1.1.1", 53), timeout=3)
            except OSError:
                ok = False
                self._log_visual("🌐 Internet Desconectada - Aguardando Conexão...", is_error=True)

            now = datetime.now()
            if now.year < 2025:
                ok = False
                self._log_visual("🕛 Hora desatualizada - Corrija a hora para continuar", is_error=True)

            if ok:
                return
            time.sleep(10)

    async def run_cloning_cycle(self):
        self.session_start_time = time.time()
        self._check_internet_and_time()
        
        me = await self.client.get_me()
        self.is_premium = getattr(me, 'premium', False)
        
        try:
            source = await self.client.get_entity(self.config.source_chat_id)
            target = await self.client.get_entity(self.config.target_chat_id)
        except Exception as e:
            self._log_visual(f"Erro ao acessar chats: {e}", is_error=True)
            return

        source_is_forum = bool(getattr(source, 'forum', False))
        target_is_forum = bool(getattr(target, 'forum', False))
        source_is_channel = bool(getattr(source, 'broadcast', False))
        target_is_channel = bool(getattr(target, 'broadcast', False))

        # Renomear destino (apenas quando o destino é um grupo existente e o usuário permitir)
        try:
            if (not self.config.target_created_by_app) and self.settings.rename_existing_target:
                # Não renomeia canais por padrão
                if not target_is_channel and getattr(target, 'title', None):
                    expected_title = self.config.build_backup_title(getattr(source, 'title', 'Backup'))
                    if target.title != expected_title:
                        logging.info(f"Renomeando destino para: {expected_title}")
                        await self.client(EditTitleRequest(target, expected_title))
        except Exception:
            pass

        if self.settings.update_photo or self.settings.update_desc:
            await self._sync_group_info(source, target)

        while True:
            try:
                topic_map, topic_titles = await self._sync_topics_with_manifest(
                    source, target,
                    source_is_forum=source_is_forum,
                    target_is_forum=target_is_forum,
                    source_is_channel=source_is_channel,
                    target_is_channel=target_is_channel,
                )
                
                all_topics = sorted(topic_map.items())
                maintenance_queue = []
                cloning_queue = []

                for src_id, tgt_id in all_topics:
                    if self.storage.is_topic_completed(source.id, target.id, src_id):
                        maintenance_queue.append((src_id, tgt_id))
                    else:
                        cloning_queue.append((src_id, tgt_id))

                if self.settings.update_msgs_start and maintenance_queue:
                    self._log_visual("⚙️ Atualizando mensagens novas", force_clean_view=True)
                    for src_id, tgt_id in maintenance_queue:
                        self._check_work_time()
                        await self._process_topic_messages(
                            source, target, src_id, tgt_id,
                            source_is_forum=source_is_forum,
                            target_is_forum=target_is_forum,
                            target_is_channel=target_is_channel,
                            topic_titles=topic_titles,
                        )
                    self._log_visual("✅ Atualização de mensagens completa", force_clean_view=True)

                if cloning_queue:
                    for src_id, tgt_id in cloning_queue:
                        self._check_work_time()
                        
                        if src_id not in self.logged_topics:
                            self._log_visual(f"⚙️ Iniciando Clonagem Tópico {src_id}", force_clean_view=True)
                            self.logged_topics.add(src_id)
                        
                        # Forum -> Canal: envia cabeçalho (nome do tópico) antes de clonar
                        if source_is_forum and target_is_channel and self.settings.forum_to_channel_topic_header:
                            await self._ensure_topic_header_in_channel(
                                source, target,
                                topic_id=src_id,
                                topic_title=topic_titles.get(src_id, f"Tópico {src_id}"),
                            )

                        success = await self._process_topic_messages(
                            source, target, src_id, tgt_id,
                            source_is_forum=source_is_forum,
                            target_is_forum=target_is_forum,
                            target_is_channel=target_is_channel,
                            topic_titles=topic_titles,
                        )
                        
                        if success:
                            self.storage.mark_topic_completed(source.id, target.id, src_id)
                            self._log_visual("✅ Tópico Completo.", force_clean_view=True)

                self._log_visual("✅ Clonagem de Grupo Completa", force_clean_view=True)

                # Forum -> Canal: cria índice final com links para cada cabeçalho
                if source_is_forum and target_is_channel and self.settings.forum_to_channel_final_index:
                    await self._send_final_navigation_index(source, target, topic_titles)

                if self.settings.update_msgs_end and maintenance_queue:
                    self._log_visual("⚙️ Atualizando mensagens novas (Verificação Final)", force_clean_view=True)
                    for src_id, tgt_id in maintenance_queue:
                        self._check_work_time()
                        await self._process_topic_messages(
                            source, target, src_id, tgt_id,
                            source_is_forum=source_is_forum,
                            target_is_forum=target_is_forum,
                            target_is_channel=target_is_channel,
                            topic_titles=topic_titles,
                        )
                    self._log_visual("✅ Atualização de mensagens completa", force_clean_view=True)

                logging.info(f"Ciclo concluído. Dormindo 60s...")
                await asyncio.sleep(60)

            except WorkTimeLimitReached:
                sleep_time = self.config.pause_duration_hours * 3600
                self._log_visual(f"🛑 Pausa para descanso ({self.config.pause_duration_hours}h)...", force_clean_view=True)
                await asyncio.sleep(sleep_time)
                self.session_start_time = time.time()
                
            except errors.FloodWaitError as e:
                await self._handle_flood_wait(e)
            except Exception as e:
                self._log_visual(f"Erro crítico no ciclo: {e}", is_error=True)
                await asyncio.sleep(10)

    async def _sync_group_info(self, source, target):
        if self.settings.update_photo and getattr(source, 'photo', None):
            try:
                path = await self.client.download_profile_photo(source, file="temp_photo.jpg")
                if path:
                    file = await self.client.upload_file(path)
                    await self.client(EditPhotoRequest(target, photo=file))
                    os.remove(path)
            except Exception: pass
            
        if self.settings.update_desc:
            try:
                full_source = await self.client(GetFullChannelRequest(source))
                source_desc = full_source.full_chat.about
                if source_desc:
                    await self.client(EditChatAboutRequest(target, source_desc))
            except Exception: pass

    async def _sync_topics_with_manifest(self, source, target, *, source_is_forum: bool, target_is_forum: bool, source_is_channel: bool, target_is_channel: bool):
        self._check_work_time()
        topic_titles: dict[int, str] = {}

        # ===== Origem: fórum (tópicos) =====
        if source_is_forum:
            source_topics = []
            offset_id = 0
            try:
                while True:
                    req = await self.client(GetForumTopicsRequest(
                        channel=source, offset_date=None, offset_id=offset_id, offset_topic=0, limit=100
                    ))
                    if not req.topics:
                        break
                    source_topics.extend(req.topics)
                    offset_id = req.topics[-1].top_message
                    if len(req.topics) < 100:
                        break
            except Exception as e:
                self._log_visual(f"Erro listando tópicos origem: {e}", is_error=True)
                return {}, {}

            topics_list = [(t.id, t.title) for t in source_topics if not isinstance(t, ForumTopicDeleted)]
            topic_titles = {t_id: title for t_id, title in topics_list}

            if not os.path.exists("topics_config.txt"):
                logging.info("Gerando manifesto de tópicos...")
                txt_path = self.storage.export_topics_manifest(topics_list)
                console.print(f"\n[bold yellow]⚠️  ARQUIVO GERADO: {txt_path}[/]")
                console.print("[dim]Abra o arquivo .txt, mude 'ON' para 'OFF' nos tópicos indesejados.[/]")
                await asyncio.get_running_loop().run_in_executor(
                    None, lambda: input("Depois de salvar, aperte ENTER para continuar...")
                )

            allowed_ids = self.storage.read_topics_manifest()
            if not allowed_ids:
                # se o usuário apagou tudo, não faz nada
                return {}, {}

        # ===== Origem: grupo normal / canal =====
        else:
            # Sem tópicos: tratamos como um único "tópico" 1
            allowed_ids = [1]
            topic_titles = {1: getattr(source, 'title', 'Chat')}

        current_map = self.storage.get_topic_map(source.id, target.id)

        # Se destino NÃO é fórum, não existe topic_id no target. Mantemos 0 como "sem reply_to".
        if not target_is_forum:
            for t_id in allowed_ids:
                current_map.setdefault(t_id, 0)
            return current_map, topic_titles

        # ===== Destino: fórum =====
        target_titles = {}
        try:
            # Paginação completa do destino (evita limite de 100)
            all_target = []
            offset_id = 0
            while True:
                t_req = await self.client(GetForumTopicsRequest(
                    channel=target, offset_date=None, offset_id=offset_id, offset_topic=0, limit=100
                ))
                if not t_req.topics:
                    break
                all_target.extend(t_req.topics)
                offset_id = t_req.topics[-1].top_message
                if len(t_req.topics) < 100:
                    break
            target_titles = {t.title: t.id for t in all_target}
        except Exception:
            target_titles = {}

        # Lista de "tópicos" a criar no destino
        if source_is_forum:
            topics_to_process = [t for t in reversed(source_topics) if not isinstance(t, ForumTopicDeleted)]
        else:
            topics_to_process = []
        
        iter_topics = topics_to_process
        if not self.settings.clean_visual:
            iter_topics = track(topics_to_process, description="Sincronizando Tópicos...")

        # Caso origem NÃO seja fórum (grupo/canal), garantimos um tópico único no destino
        if not source_is_forum:
            if 1 not in current_map:
                title = topic_titles.get(1, 'Chat')
                if title in target_titles:
                    current_map[1] = target_titles[title]
                    self.storage.save_topic_mapping(source.id, target.id, 1, current_map[1])
                else:
                    try:
                        await self.client(CreateForumTopicRequest(channel=target, title=title, icon_color=0x6FB9F0, icon_emoji_id=None))
                        await asyncio.sleep(1)
                        # Recarrega com paginação e encontra
                        t_req = await self.client(GetForumTopicsRequest(channel=target, offset_date=None, offset_id=0, offset_topic=0, limit=100))
                        real_id = None
                        for t in t_req.topics:
                            if t.title == title:
                                real_id = t.id
                                break
                        if real_id:
                            current_map[1] = real_id
                            self.storage.save_topic_mapping(source.id, target.id, 1, real_id)
                    except Exception as e:
                        self._log_visual(f"Erro criando tópico único: {e}", is_error=True)

            return current_map, topic_titles

        for topic in iter_topics:
            self._check_work_time()
            if topic.id not in allowed_ids and topic.id != 1: continue
            if topic.id in current_map: continue

            if topic.title in target_titles:
                tgt_id = target_titles[topic.title]
                self.storage.save_topic_mapping(source.id, target.id, topic.id, tgt_id)
                current_map[topic.id] = tgt_id
                continue

            try:
                icon_color = getattr(topic, 'icon_color', 0x6FB9F0)
                icon_emoji = getattr(topic, 'icon_emoji_id', None)
                if not self.is_premium: icon_emoji = None
                
                await self.client(CreateForumTopicRequest(
                    channel=target, title=topic.title, 
                    icon_color=icon_color, icon_emoji_id=icon_emoji
                ))
                await asyncio.sleep(2)

                req = await self.client(GetForumTopicsRequest(
                    channel=target, offset_date=None, offset_id=0, offset_topic=0, limit=100
                ))
                
                real_id = None
                for t in req.topics:
                    if t.title == topic.title:
                        real_id = t.id
                        break
                
                if not real_id: continue
                
                self.storage.save_topic_mapping(source.id, target.id, topic.id, real_id)
                current_map[topic.id] = real_id
                
                await asyncio.sleep(0.5)
                await self._cleanup_service_messages(target, real_id)

                if self.settings.fix_topics and getattr(topic, 'pinned', False):
                    try:
                        await self.client(UpdatePinnedForumTopicRequest(
                            channel=target, topic_id=real_id, pinned=True
                        ))
                    except Exception: pass

                should_close = (
                    self.settings.close_topics == "ON" or 
                    (self.settings.close_topics == "PARCIAL" and getattr(topic, 'closed', False))
                )
                if should_close:
                    await self.client(EditForumTopicRequest(
                        channel=target, topic_id=real_id, closed=True
                    ))

            except errors.FloodWaitError as e:
                await self._handle_flood_wait(e)
            except Exception as e:
                self._log_visual(f"Erro criando tópico {topic.title}: {e}", is_error=True)

        return current_map, topic_titles

        

    async def _cleanup_service_messages(self, target, topic_id):
        try:
            msgs = await self.client.get_messages(target, limit=5, reply_to=topic_id)
            for m in msgs:
                if isinstance(m, MessageService):
                    await self.client.delete_messages(target, m.id)
        except Exception: pass

    async def _process_topic_messages(self, source, target, src_id, tgt_id, *, source_is_forum: bool, target_is_forum: bool, target_is_channel: bool, topic_titles: dict[int, str]) -> bool:
        last_id = self.storage.get_last_message_id(source.id, target.id, src_id)

        # 1) Tenta reenviar falhas antigas primeiro
        try:
            for failed_id in self.storage.list_failed_messages(source.id, target.id, src_id):
                if failed_id <= last_id:
                    # já passou desse ponto
                    self.storage.clear_failed_message(source.id, target.id, src_id, failed_id)
                    continue
                ok = await self._clone_single_message(source, target, failed_id, src_id, tgt_id, source_is_forum, target_is_forum)
                if ok:
                    last_id = max(last_id, failed_id)
                    self.storage.save_last_message_id(source.id, target.id, src_id, last_id)
                    self.storage.clear_failed_message(source.id, target.id, src_id, failed_id)
                    await asyncio.sleep(self.config.delay_between_messages)
        except Exception:
            pass
        
        while True:
            self._check_work_time()
            
            get_kwargs = dict(min_id=last_id, limit=self.config.batch_size, reverse=True)
            if source_is_forum:
                get_kwargs['reply_to'] = src_id

            messages = await self.client.get_messages(source, **get_kwargs)
            
            if not messages: 
                return True 
            
            for msg in messages:
                if msg.id <= last_id: 
                    continue

                current_msg_id = msg.id
                
                if isinstance(msg, MessageService):
                    last_id = current_msg_id
                    self.storage.save_last_message_id(source.id, target.id, src_id, last_id)
                    continue

                if not self.settings.clean_visual:
                    # ATUALIZAÇÃO 2: Contador sequencial no log
                    self.session_message_count += 1
                    logging.info(f"MENSAGEM {self.session_message_count} ID -> {msg.id}")

                media = msg.media
                if isinstance(media, MessageMediaWebPage):
                    media = None 

                text = msg.message or ""
                limit = 4096
                if media:
                    limit = 2048 if self.is_premium else 1024
                
                should_split = len(text) > limit

                try:
                    sent_msgs = []

                    reply_to = tgt_id if target_is_forum and tgt_id else None
                    
                    if should_split:
                        if not self.settings.clean_visual:
                            logging.info(f"Mensagem em Partes -> {msg.id}")

                        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
                        
                        s1 = await self.client.send_message(
                            target, parts[0], file=media, reply_to=reply_to, link_preview=False
                        )
                        if not isinstance(s1, list): s1 = [s1]
                        sent_msgs.extend(s1)

                        for p in parts[1:]:
                            await asyncio.sleep(0.5)
                            s2 = await self.client.send_message(target, p, reply_to=reply_to)
                            if not isinstance(s2, list): s2 = [s2]
                            sent_msgs.extend(s2)
                    else:
                        s = await self.client.send_message(
                            target, message=msg, reply_to=reply_to, link_preview=False
                        )
                        if not isinstance(s, list): s = [s]
                        sent_msgs.extend(s)
                    
                    if getattr(msg, 'pinned', False) and sent_msgs:
                        try:
                            main_sent = sent_msgs[0]
                            await self.client.pin_message(target, main_sent, notify=False)
                            await asyncio.sleep(0.5)
                            if target_is_forum and tgt_id:
                                await self._cleanup_service_messages(target, tgt_id)
                        except Exception: pass

                    self.messages_sent += len(sent_msgs)
                    if self.messages_sent >= self.config.pause_every_x_messages:
                        self._log_visual("⏸ Pausando para evitar flood...", force_clean_view=True)
                        await asyncio.sleep(self.config.pause_duration_s)
                        self.session_start_time += self.config.pause_duration_s
                        self.messages_sent = 0

                    last_id = current_msg_id
                    self.storage.save_last_message_id(source.id, target.id, src_id, last_id)
                    await asyncio.sleep(self.config.delay_between_messages)
                    
                except errors.FloodWaitError as e:
                    await self._handle_flood_wait(e)
                except Exception as e:
                    # Não avança checkpoint em erro: registra para retry
                    self._log_visual(f"Erro msg {msg.id}: {e}", is_error=True)
                    self.storage.record_failed_message(source.id, target.id, src_id, current_msg_id, str(e))
                    await asyncio.sleep(2)
        
        return True

    async def _clone_single_message(self, source, target, message_id: int, src_topic_id: int, tgt_topic_id: int, source_is_forum: bool, target_is_forum: bool) -> bool:
        """Reenvia uma msg específica (usado no retry)."""
        try:
            msg = await self.client.get_messages(source, ids=message_id)
            if not msg:
                return True
            if isinstance(msg, MessageService):
                return True

            media = msg.media
            if isinstance(media, MessageMediaWebPage):
                media = None

            text = msg.message or ""
            limit = 4096
            if media:
                limit = 2048 if self.is_premium else 1024
            should_split = len(text) > limit
            reply_to = tgt_topic_id if target_is_forum and tgt_topic_id else None

            if should_split:
                parts = [text[i:i+limit] for i in range(0, len(text), limit)]
                await self.client.send_message(target, parts[0], file=media, reply_to=reply_to, link_preview=False)
                for p in parts[1:]:
                    await asyncio.sleep(0.5)
                    await self.client.send_message(target, p, reply_to=reply_to)
            else:
                await self.client.send_message(target, message=msg, reply_to=reply_to, link_preview=False)

            return True
        except errors.FloodWaitError as e:
            await self._handle_flood_wait(e)
            return False
        except Exception:
            return False

    async def _ensure_topic_header_in_channel(self, source, target, *, topic_id: int, topic_title: str):
        """Forum -> Canal: manda uma msg com o nome do tópico e fixa (uma vez por tópico)."""
        existing = self.storage.get_topic_header_message_id(source.id, target.id, topic_id)
        if existing:
            return

        try:
            sent = await self.client.send_message(target, topic_title)
            msg_id = sent.id if hasattr(sent, 'id') else 0
            if msg_id:
                self.storage.save_topic_header_message_id(source.id, target.id, topic_id, msg_id)
            try:
                await self.client.pin_message(target, sent, notify=False)
            except Exception:
                pass
        except Exception as e:
            self._log_visual(f"Erro ao enviar cabeçalho do tópico '{topic_title}': {e}", is_error=True)

    def _build_message_link(self, chat, message_id: int) -> str:
        """Gera link para mensagem (público via @username ou privado via /c/...)."""
        username = getattr(chat, 'username', None)
        if username:
            return f"https://t.me/{username}/{message_id}"

        # Para supergrupos/canais privados: t.me/c/<id_sem_-100>/<msg_id>
        cid = int(getattr(chat, 'id', 0))
        cid_abs = abs(cid)
        if str(cid_abs).startswith('100'):
            internal = str(cid_abs)[3:]
        else:
            internal = str(cid_abs)
        return f"https://t.me/c/{internal}/{message_id}"

    async def _send_final_navigation_index(self, source, target, topic_titles: dict[int, str]):
        """Forum -> Canal: envia índice final com links para cada cabeçalho."""
        # Monta linhas com base em headers já enviados
        lines = []
        for topic_id, title in topic_titles.items():
            header_id = self.storage.get_topic_header_message_id(source.id, target.id, topic_id)
            if not header_id:
                continue
            link = self._build_message_link(target, header_id)
            lines.append(f"• {title} — {link}")

        if not lines:
            return

        header = "📌 Índice dos tópicos clonados:\n"
        max_len = 4000
        chunks = []
        current = header
        for line in lines:
            if len(current) + len(line) + 1 > max_len:
                chunks.append(current)
                current = "📌 Índice (continuação):\n" + line
            else:
                current += line + "\n"
        chunks.append(current)

        first_sent = None
        for text in chunks:
            sent = await self.client.send_message(target, text, link_preview=False)
            if not first_sent:
                first_sent = sent
            await asyncio.sleep(0.5)

        if first_sent and self.settings.forum_to_channel_pin_final_index:
            try:
                await self.client.pin_message(target, first_sent, notify=False)
            except Exception:
                pass