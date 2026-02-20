import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt
from rich.text import Text
from .config import AppSettings, save_env_variable

console = Console()

class CLIWizard:
    
    @staticmethod
    def clear_screen():
        console.clear()

    @staticmethod
    def show_header():
        console.print("[bold cyan]EncScript[/]")
        console.print()

    @staticmethod
    def show_welcome():
        CLIWizard.clear_screen()
        welcome_text = Text("Bem Vindo(a)!", justify="center", style="bold green")
        panel = Panel(welcome_text, title="EncScript", subtitle="1.4.0", style="cyan")
        console.print(panel)
        console.print("\n[1] Conectar Conta (Aperte [bold white]Enter[/] Para continuar)")
        console.input()

    @staticmethod
    def get_initial_credentials() -> tuple[int, str, str]:
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        phone = os.getenv('PHONE')

        if not api_id:
            CLIWizard.clear_screen()
            CLIWizard.show_header()
            api_id = IntPrompt.ask("Qual seu [bold yellow]api_id[/]?")
            save_env_variable('API_ID', str(api_id))
        
        if not api_hash:
            CLIWizard.clear_screen()
            CLIWizard.show_header()
            console.print(f"API ID: [green]{api_id}[/]")
            api_hash = Prompt.ask("Qual o seu [bold yellow]api_hash[/]?")
            save_env_variable('API_HASH', api_hash)
            
        if not phone:
            CLIWizard.clear_screen()
            CLIWizard.show_header()
            console.print(f"API ID: [green]{api_id}[/]")
            console.print(f"API HASH: [green]{api_hash[:5]}...[/]")
            phone = Prompt.ask("Qual o seu número de telefone? (Ex: [green]+55...[/])")
            save_env_variable('PHONE', phone)

        return int(api_id), api_hash, phone

    @staticmethod
    def request_otp() -> str:
        CLIWizard.clear_screen()
        CLIWizard.show_header()
        console.print("[bold green]Código enviado![/]")
        return Prompt.ask("Qual o [bold yellow]código[/] que chegou no Telegram?")

    @staticmethod
    def request_password() -> str:
        CLIWizard.clear_screen()
        CLIWizard.show_header()
        return Prompt.ask("Qual a sua [bold yellow]senha (2FA)[/]?", password=True)

    @staticmethod
    def main_menu(is_premium: bool) -> int:
        CLIWizard.clear_screen()
        account_type = "[bold gold1]Premium[/]" if is_premium else "[bold white]Normal[/]"
        
        menu_text = f"""
        Conta Conectada: {account_type}
        
        [1] Clonar
        [2] Continuar
        [3] Configurações
        [4] Créditos
        [5] Sair
        """
        panel = Panel(menu_text, title="EncScript", style="cyan")
        console.print(panel)
        
        choice = IntPrompt.ask("Escolha", choices=["1", "2", "3", "4", "5"], default="1")
        return choice

    @staticmethod
    def show_credits():
        CLIWizard.clear_screen()
        
        credits_content = """
  Desenvolvido por: LucasTsukasa
  Github: https://github.com/LucasTsukasa
  Licença: GNU General Public License v3
  Versão: 1.4.0

  Este software é open-source e distribuído sob os termos da GPL v3.
  Veja o arquivo LICENSE para mais informações.
        """
        
        text = Text(credits_content, justify="center", style="white")
        panel = Panel(text, title="Créditos", style="cyan")
        console.print(panel)
        console.input("\nPressione [bold white]Enter[/] para voltar...")

    @staticmethod
    def get_chat_ids() -> tuple[int, int]:
        CLIWizard.clear_screen()
        console.print(Panel("Configuração de Clonagem", style="cyan"))

        console.print("[1] Criar Novo Destino")
        console.print("[2] Usar Destino Existente (grupo/canal/fórum)")
        console.print("[3] Voltar")
        console.print()

        mode = IntPrompt.ask("Escolha uma opção", choices=["1", "2", "3"], default="1")

        if mode == 3:
            return 0, 0

        src = Prompt.ask("ID do Chat [bold red]Origem[/] (Ex: -100...)")

        tgt = 0
        if mode == 2:
            tgt_raw = Prompt.ask("ID do Chat [bold green]Destino[/] (Ex: -100...)")
            tgt = int(tgt_raw)
        else:
            # Criar novo destino: escolhe o tipo
            while True:
                CLIWizard.clear_screen()
                console.print(Panel("Criar Novo Destino", style="cyan"))
                console.print("[1] Canal")
                console.print("[2] Grupo Normal (sem tópicos)")
                console.print("[3] Grupo com Tópicos (Fórum)")
                console.print("[4] Voltar")
                console.print()
                dest_mode = IntPrompt.ask("Escolha o tipo", choices=["1", "2", "3", "4"], default="3")

                if dest_mode == 4:
                    return 0, 0

                # Usamos sentinelas (não são IDs reais) para o main criar o destino correto
                if dest_mode == 1:
                    tgt = -2  # criar CANAL
                elif dest_mode == 2:
                    tgt = -1  # criar GRUPO normal
                else:
                    tgt = 0   # criar GRUPO com tópicos (Fórum)
                break

        save_env_variable('SOURCE_CHAT', str(src))
        save_env_variable('TARGET_CHAT', str(tgt))

        return int(src), tgt

    @staticmethod
    def _save_settings_to_file(settings: AppSettings):
        """Helper interno para salvar as configurações no JSON."""
        with open("settings.json", "w") as f:
            json.dump(settings.__dict__, f, indent=4)

    @staticmethod
    def _channel_settings_menu(current: AppSettings) -> AppSettings:
        while True:
            CLIWizard.clear_screen()
            
            def fmt(val): return "[bold green]ON[/] " if val else "[bold red]OFF[/]"
            
            color_topic = "[bold red]OFF[/]"
            if current.close_topics == "ON": color_topic = "[bold green]ON[/] "
            elif current.close_topics == "PARCIAL": color_topic = "[bold yellow]PARCIAL[/]"

            menu_content = f"""
            [1] Atualizar Mensagens no Início ........... {fmt(current.update_msgs_start)} [dim](Atualiza msgs novas em tópicos já clonados ao iniciar)[/]
            [2] Atualizar Mensagens no Fim .............. {fmt(current.update_msgs_end)} [dim](Atualiza msgs novas em tópicos já clonados ao final)[/]
            [3] Visual Limpo ............................ {fmt(current.clean_visual)} [dim](Reduz logs no console)[/]
            [4] Atualizar Foto .......................... {fmt(current.update_photo)} [dim](Clona a foto do grupo origem)[/]
            [5] Atualizar Descrição ..................... {fmt(current.update_desc)} [dim](Clona descrição/bio do grupo)[/]
            [6] Fechar Tópico ........................... {color_topic} [dim](ON = todos / PARCIAL = igual ao grupo origem)[/]
            [7] Fixar Tópicos ........................... {fmt(current.fix_topics)} [dim](Fixa tópicos conforme grupo origem)[/]

            [8] Renomear Destino Existente .............. {fmt(current.rename_existing_target)} [dim](Só quando você usa destino já existente)[/]
            [9] Fórum → Canal: Cabeçalho por Tópico ..... {fmt(current.forum_to_channel_topic_header)} [dim](Envia e fixa o nome do tópico antes de clonar)[/]
            [10] Fórum → Canal: Índice Final ............ {fmt(current.forum_to_channel_final_index)} [dim](Cria um menu com links no final)[/]
            [11] Fixar Índice Final ..................... {fmt(current.forum_to_channel_pin_final_index)} [dim](Fixa o menu do índice final)[/]

            [0] Voltar
            """
            
            console.print(Panel(menu_content, title="Configurações de Canais/Grupo", style="yellow"))
            choice = Prompt.ask(
                "Digite o número para alternar",
                choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
                default="0"
            )
            
            if choice == '0':
                break
            elif choice == '1': current.update_msgs_start = not current.update_msgs_start
            elif choice == '2': current.update_msgs_end = not current.update_msgs_end
            elif choice == '3': current.clean_visual = not current.clean_visual
            elif choice == '4': current.update_photo = not current.update_photo
            elif choice == '5': current.update_desc = not current.update_desc
            elif choice == '6': 
                if current.close_topics == "ON": current.close_topics = "PARCIAL"
                elif current.close_topics == "PARCIAL": current.close_topics = "OFF"
                else: current.close_topics = "ON"
            elif choice == '7': current.fix_topics = not current.fix_topics
            elif choice == '8': current.rename_existing_target = not current.rename_existing_target
            elif choice == '9': current.forum_to_channel_topic_header = not current.forum_to_channel_topic_header
            elif choice == '10': current.forum_to_channel_final_index = not current.forum_to_channel_final_index
            elif choice == '11': current.forum_to_channel_pin_final_index = not current.forum_to_channel_pin_final_index
            
            CLIWizard._save_settings_to_file(current)
            
        return current

    @staticmethod
    def _time_settings_menu(current: AppSettings) -> AppSettings:
        while True:
            CLIWizard.clear_screen()
            
            menu_content = f"""
            [1] Tempo Máximo de Clonagem ................ [bold cyan]{current.max_session_hours}h[/]
            [2] Tempo Máximo de Descanso ................ [bold cyan]{current.pause_duration_hours}h[/]
            [3] Delay Entre cada Mensagem .............. [bold cyan]{current.delay_between_messages}s[/]
            [4] Pausa a cada x mensagens ............... [bold cyan]{current.pause_every_x_messages}[/]
            [5] Duração pausa a cada x mensagens ....... [bold cyan]{current.pause_duration_s}s[/]

            [6] Tamanho do Lote (batch) ................. [bold cyan]{current.batch_size}[/]

            [0] Voltar
            """
            
            console.print(Panel(menu_content, title="Configurações de Tempo", style="yellow"))
            choice = Prompt.ask("Digite o número para editar", choices=["0", "1", "2", "3", "4", "5", "6"], default="0")
            
            if choice == '0':
                break
            elif choice == '1':
                current.max_session_hours = FloatPrompt.ask("Novo tempo máximo (horas, 0 para desativar)")
            elif choice == '2':
                current.pause_duration_hours = FloatPrompt.ask("Novo tempo de descanso (horas, 0 para desativar)")
            elif choice == '3':
                current.delay_between_messages = FloatPrompt.ask("Novo delay (segundos, 0 para desativar)")
            elif choice == '4':
                current.pause_every_x_messages = IntPrompt.ask("Pausar a cada quantas mensagens? (0 para desativar)")
            elif choice == '5':
                current.pause_duration_s = IntPrompt.ask("Duração da pausa curta (segundos, 0 para desativar)")
            elif choice == '6':
                current.batch_size = IntPrompt.ask("Novo batch size (ex: 20-100)", default=current.batch_size)
            
            CLIWizard._save_settings_to_file(current)
            
        return current

    @staticmethod
    def settings_menu(current: AppSettings) -> AppSettings:
        while True:
            CLIWizard.clear_screen()
            
            menu_content = """
            [1] Configurações de Canais/Grupo
            [2] Configurações de Tempo
            
            [0] Voltar ao Menu Principal
            """
            
            console.print(Panel(menu_content, title="Menu de Configurações", style="yellow"))
            
            choice = Prompt.ask("Escolha uma categoria", choices=["0", "1", "2"], default="0")
            
            if choice == '0':
                break
            elif choice == '1':
                current = CLIWizard._channel_settings_menu(current)
            elif choice == '2':
                current = CLIWizard._time_settings_menu(current)
        
        return current

    @staticmethod
    def load_settings() -> AppSettings:
        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r") as f:
                    data = json.load(f)
                    default = AppSettings()
                    for k, v in data.items():
                        if hasattr(default, k):
                            setattr(default, k, v)
                    return default
            except Exception:
                return AppSettings()
        return AppSettings()
    
    @staticmethod
    def show_start_feedback():
        console.print()
        console.print("[bold yellow]Iniciando motores... Aguarde a conexão com o Telegram...[/]")
        console.print("[dim]O processo de encaminhamento começará em instantes.[/]")
        console.print()