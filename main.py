import asyncio
import logging
import os
import sys
from telethon import TelegramClient, errors

from src.config import setup_logging, AppConfig
from src.ui import CLIWizard, console
from src.storage import StorageRepository
from src.service import ClonerService

async def main():
    CLIWizard.show_welcome()
    
    api_id, api_hash, phone = CLIWizard.get_initial_credentials()
    
    console.print("\n[yellow]Conectando aos servidores do Telegram...[/]")
    client = TelegramClient("cloner_session", api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        try:
            console.print(f"[yellow]Enviando código para {phone}...[/]")
            await client.send_code_request(phone)
        except Exception as e:
            console.print(f"[bold red]Erro ao enviar código:[/]. {e}")
            return

        code = CLIWizard.request_otp()
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            pwd = CLIWizard.request_password()
            await client.sign_in(password=pwd)
        except Exception as e:
            console.print(f"[bold red]Falha no Login:[/]. {e}")
            return

    console.print("[bold green]Login realizado com sucesso![/]")
    await asyncio.sleep(1)

    me = await client.get_me()
    is_premium = getattr(me, 'premium', False)

    settings = CLIWizard.load_settings()
    setup_logging(clean_visual=settings.clean_visual)

    storage = StorageRepository()
    
    src = 0
    tgt = 0

    while True:
        choice = CLIWizard.main_menu(is_premium)
        
        if choice == 1: 
            if os.path.exists("topics_config.txt"):
                os.remove("topics_config.txt")
            src, tgt = CLIWizard.get_chat_ids()
            
            console.print("[yellow]Limpando dados anteriores para novo clone...[/]")
            storage.reset_chat_progress(src, tgt)
            break
            
        elif choice == 2:
            src_raw = os.getenv('SOURCE_CHAT')
            tgt_raw = os.getenv('TARGET_CHAT')
            if not src_raw or not tgt_raw:
                console.print("\n[red]❌ Nenhuma configuração anterior encontrada.[/]")
                input("\nEnter para voltar...")
                continue
            src, tgt = int(src_raw), int(tgt_raw)
            break
            
        elif choice == 3:
            settings = CLIWizard.settings_menu(settings)
            setup_logging(clean_visual=settings.clean_visual)
            
        elif choice == 4:
            await client.disconnect()
            sys.exit(0)
    
    # ATUALIZAÇÃO: AppConfig agora recebe os valores dinâmicos do settings
    config = AppConfig(
        api_id=api_id, api_hash=api_hash, phone=phone,
        source_chat_id=src, target_chat_id=tgt,
        max_session_hours=settings.max_session_hours,
        pause_duration_hours=settings.pause_duration_hours,
        delay_between_messages=settings.delay_between_messages,
        pause_every_x_messages=settings.pause_every_x_messages,
        pause_duration_s=settings.pause_duration_s
    )
    
    service = ClonerService(client, config, settings, storage)

    CLIWizard.show_start_feedback()

    try:
        await service.run_cloning_cycle()
    except KeyboardInterrupt:
        console.print("\n[yellow]Parado pelo usuário.[/]")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSaindo...")