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
        self.logged_topics = set() # Correção 5: Controle de logs repetidos

    def _log_visual(self, message: str, is_error: bool = False, force_clean_view: bool = False):
        """Gerencia logs visuais vs detalhados."""
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
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=3)
        except OSError:
            self._log_visual("🌐 Internet Desconectada - Esperando Conexão", is_error=True)
        
        now = datetime.now()
        if now.year < 2025: 
            self._log_visual("🕛 Hora desatualizada - Corrija a hora para continuar", is_error=True)

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

        try:
            expected_title = f"{source.title} Backup"
            if target.title != expected_title:
                logging.info(f"Renomeando grupo destino para: {expected_title}")
                await self.client(EditTitleRequest(target, expected_title))
        except Exception: pass

        if self.settings.update_photo or self.settings.update_desc:
            await self._sync_group_info(source, target)

        while True:
            try:
                topic_map = await self._sync_topics_with_manifest(source, target)
                
                all_topics = sorted(topic_map.items())
                maintenance_queue = []
                cloning_queue = []

                for src_id, tgt_id in all_topics:
                    if self.storage.is_topic_completed(source.id, src_id):
                        maintenance_queue.append((src_id, tgt_id))
                    else:
                        cloning_queue.append((src_id, tgt_id))

                # FASE 1
                if self.settings.update_msgs_start and maintenance_queue:
                    self._log_visual("⚙️ Atualizando mensagens novas", force_clean_view=True)
                    for src_id, tgt_id in maintenance_queue:
                        self._check_work_time()
                        await self._process_topic_messages(source, target, src_id, tgt_id)
                    self._log_visual("✅ Atualização de mensagens completa", force_clean_view=True)

                # FASE 2
                if cloning_queue:
                    for src_id, tgt_id in cloning_queue:
                        self._check_work_time()
                        
                        # Correção 5: Log único por tópico na sessão
                        if src_id not in self.logged_topics:
                            self._log_visual(f"⚙️ Iniciando Clonagem Tópico {src_id}", force_clean_view=True)
                            self.logged_topics.add(src_id)
                        
                        success = await self._process_topic_messages(source, target, src_id, tgt_id)
                        
                        if success:
                            self.storage.mark_topic_completed(source.id, src_id)
                            self._log_visual("✅ Tópico Completo.", force_clean_view=True)

                self._log_visual("✅ Clonagem de Grupo Completa", force_clean_view=True)

                # FASE 3
                if self.settings.update_msgs_end and maintenance_queue:
                    self._log_visual("⚙️ Atualizando mensagens novas (Verificação Final)", force_clean_view=True)
                    for src_id, tgt_id in maintenance_queue:
                        self._check_work_time()
                        await self._process_topic_messages(source, target, src_id, tgt_id)
                    self._log_visual("✅ Atualização de mensagens completa", force_clean_view=True)

                logging.info(f"Ciclo concluído. Dormindo 60s...")
                await asyncio.sleep(60)

            except WorkTimeLimitReached:
                # Correção 3: Usa pause_duration_hours (convertido para segundos)
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

    async def _sync_topics_with_manifest(self, source, target) -> dict:
        self._check_work_time()
        
        source_topics = []
        offset_id = 0
        try:
            while True:
                req = await self.client(GetForumTopicsRequest(
                    channel=source, offset_date=None, offset_id=offset_id, offset_topic=0, limit=100
                ))
                if not req.topics: break
                source_topics.extend(req.topics)
                offset_id = req.topics[-1].top_message
                if len(req.topics) < 100: break
        except Exception as e:
            self._log_visual(f"Erro listando tópicos origem: {e}", is_error=True)
            return {}

        topics_list = [(t.id, t.title) for t in source_topics if not isinstance(t, ForumTopicDeleted)]
        
        if not os.path.exists("topics_config.txt"):
            logging.info("Gerando manifesto de tópicos...")
            txt_path = self.storage.export_topics_manifest(topics_list)
            console.print(f"\n[bold yellow]⚠️  ARQUIVO GERADO: {txt_path}[/]")
            console.print("[dim]Abra o arquivo .txt, mude 'ON' para 'OFF' nos tópicos indesejados.[/]")
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: input("Depois de salvar, aperte ENTER para continuar...")
            )
        
        allowed_ids = self.storage.read_topics_manifest()
        current_map = self.storage.get_topic_map(source.id, target.id)
        if 1 not in current_map: current_map[1] = 1 
        
        target_titles = {}
        try:
            t_req = await self.client(GetForumTopicsRequest(
                channel=target, offset_date=None, offset_id=0, offset_topic=0, limit=100
            ))
            target_titles = {t.title: t.id for t in t_req.topics}
        except: pass

        topics_to_process = [t for t in reversed(source_topics) if not isinstance(t, ForumTopicDeleted)]
        
        iter_topics = topics_to_process
        if not self.settings.clean_visual:
            iter_topics = track(topics_to_process, description="Sincronizando Tópicos...")

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

        return current_map

    async def _cleanup_service_messages(self, target, topic_id):
        try:
            msgs = await self.client.get_messages(target, limit=5, reply_to=topic_id)
            for m in msgs:
                if isinstance(m, MessageService):
                    await self.client.delete_messages(target, m.id)
        except Exception: pass

    async def _process_topic_messages(self, source, target, src_id, tgt_id) -> bool:
        last_id = self.storage.get_last_message_id(source.id, src_id)
        
        while True:
            self._check_work_time()
            
            messages = await self.client.get_messages(
                source, min_id=last_id, limit=self.config.batch_size, reverse=True, reply_to=src_id
            )
            
            if not messages: 
                return True 
            
            for msg in messages:
                # Correção 4: Evita duplicação absoluta
                if msg.id <= last_id: 
                    continue

                # Atualiza last_id localmente, mas só salva no banco ao final do loop seguro
                # Isso garante que se o processamento da msg falhar, tentamos de novo
                current_msg_id = msg.id
                
                if isinstance(msg, MessageService):
                    last_id = current_msg_id
                    self.storage.save_last_message_id(source.id, src_id, last_id)
                    continue

                if not self.settings.clean_visual:
                    logging.info(f"MENSAGEM ID -> {msg.id}")

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
                    
                    if should_split:
                        if not self.settings.clean_visual:
                            logging.info(f"Mensagem em Partes -> {msg.id}")

                        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
                        
                        # Correção 1: Split ainda perde formatação (limitação da API sem parser),
                        # mas garantimos que se couber, vai para o ELSE (preserva tudo).
                        s1 = await self.client.send_message(
                            target, parts[0], file=media, reply_to=tgt_id, link_preview=False
                        )
                        if not isinstance(s1, list): s1 = [s1]
                        sent_msgs.extend(s1)

                        for p in parts[1:]:
                            await asyncio.sleep(0.5)
                            s2 = await self.client.send_message(target, p, reply_to=tgt_id)
                            if not isinstance(s2, list): s2 = [s2]
                            sent_msgs.extend(s2)
                    else:
                        # Correção 1: Envio do OBJETO msg preserva formatação (Negrito, Links, etc)
                        # Adicionado link_preview=False para manter consistência
                        s = await self.client.send_message(
                            target, message=msg, reply_to=tgt_id, link_preview=False
                        )
                        if not isinstance(s, list): s = [s]
                        sent_msgs.extend(s)
                    
                    if getattr(msg, 'pinned', False) and sent_msgs:
                        try:
                            main_sent = sent_msgs[0]
                            await self.client.pin_message(target, main_sent, notify=False)
                            await asyncio.sleep(0.5)
                            await self._cleanup_service_messages(target, tgt_id)
                        except Exception: pass

                    # Correção 2: Pausa Anti-Flood consistente
                    self.messages_sent += len(sent_msgs)
                    if self.messages_sent >= self.config.pause_every_x_messages:
                        self._log_visual("⏸ Pausando para evitar flood...", force_clean_view=True)
                        await asyncio.sleep(self.config.pause_duration_s)
                        self.session_start_time += self.config.pause_duration_s
                        self.messages_sent = 0

                    last_id = current_msg_id
                    self.storage.save_last_message_id(source.id, src_id, last_id)
                    await asyncio.sleep(self.config.delay_between_messages)
                    
                except errors.FloodWaitError as e:
                    await self._handle_flood_wait(e)
                except Exception as e:
                    self._log_visual(f"Erro msg {msg.id}: {e}", is_error=True)
                    # Se der erro, salva o ID para não travar o loop, assumindo 'skip'
                    last_id = current_msg_id
                    self.storage.save_last_message_id(source.id, src_id, last_id)
        
        return True