# EncScript

![License](https://img.shields.io/badge/License-GPLv3-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)

> ⚠️ **AVISO SOBRE MODIFICAÇÕES E RISCO DE BANIMENTO:**
> 
> Este software é distribuído sob a licença **GNU GPL v3.0**, permitindo livre estudo e modificação. No entanto, o código original foi rigorosamente calibrado para respeitar os limites de requisição (Rate Limits) do Telegram.
> 
> **Atenção:** Alterar os tempos de espera, descanso, pausa a cada x mensagens, remover verificações de segurança ou modificar a lógica de envio pode fazer com que o script viole os Termos de Serviço (ToS) do Telegram. Tais modificações aumentam drasticamente o risco de sua conta ser **restringida ou banida permanentemente**.
> 
> O desenvolvedor original **não se responsabiliza** por danos causados por versões modificadas ou uso indevido deste código. Mantenha as proteções ativas para sua segurança.

## Isenção de Garantias ("AS IS")

Este software é fornecido "no estado em que se encontra" (AS IS), sem garantias de qualquer tipo, expressas ou implícitas. O usuário assume total responsabilidade e risco pelo uso deste código.

📌 EncScript

EncScript é uma ferramenta profissional de automação (CLI) desenvolvida em Python para clonagem, espelhamento e backup de supergrupos do Telegram com a funcionalidade de Tópicos (Fóruns) ativada.

📖 Descrição Geral

Este aplicativo foi projetado para administradores de comunidades, arquivistas e engenheiros de dados que necessitam migrar ou fazer backup de grandes volumes de informações no Telegram.

O EncScript resolve a complexidade de manter a estrutura organizacional de fóruns (tópicos), garantindo que mensagens, mídias, fixados e estados (aberto/fechado) sejam replicados fielmente do grupo de origem para o grupo de destino. Ele opera como um userbot, utilizando a API MTProto do Telegram via Telethon.

⚙️ Funcionalidades

Clonagem de Tópicos: Replica o título, cor do ícone e emoji (se Premium) de cada tópico.

Sincronização de Mensagens: Clona texto, fotos, vídeos, documentos e adesivos, mantendo a ordem cronológica.

Gestão de Mensagens Longas: Divide automaticamente textos maiores que 4096 caracteres (ou limites de mídia) para evitar erros de API.

Persistência Granular: Salva o estado de cada mensagem processada em banco de dados SQLite, permitindo interrupções e retomadas seguras.

Manifesto de Seleção: Gera um arquivo topics_config.txt permitindo ao usuário escolher quais tópicos deseja clonar ou ignorar.

Espelhamento de Metadados: Clona foto do grupo, descrição (about) e fixa mensagens importantes conforme a origem.

Gestão de Estado do Tópico: Fecha tópicos no destino se estiverem fechados na origem (configurável).

Modo de Manutenção: Capaz de verificar e atualizar mensagens novas em tópicos já clonados anteriormente.

🧠 Como Funciona

O fluxo de execução do aplicativo segue uma lógica robusta de três fases:

Mapeamento: O app analisa a origem, gera um manifesto e identifica quais tópicos já existem no destino.

Fase 1 - Atualização (Opcional): Verifica tópicos já concluídos em busca de novas mensagens enviadas desde a última execução.

Fase 2 - Clonagem: Processa novos tópicos ou tópicos incompletos, clonando mensagens do mais antigo para o mais novo.

Fase 3 - Varredura Final (Opcional): Realiza uma última verificação em tópicos concluídos para garantir que nada foi perdido durante o processo.

O sistema utiliza pausas inteligentes para simular comportamento humano e evitar bloqueios temporários (FloodWait).

🖥️ Interface do Aplicativo (CLI)

O aplicativo é executado via terminal com uma interface visual rica. O menu principal oferece:

[1] Clonar: Inicia um processo do zero. Limpa todo o progresso salvo no banco de dados para os grupos selecionados e recomeça a clonagem. Ideal para novos setups.

[2] Continuar: Retoma o processo de onde parou. Respeita o banco de dados, não duplica mensagens e prioriza a atualização de conteúdo novo antes de criar novos tópicos.

[3] Configurações: Abre o menu de ajustes finos do comportamento do robô.

[4] Sair: Encerra a conexão e o aplicativo com segurança.

🔧 Configurações

O menu de configurações permite ajustar 12 parâmetros vitais. As alterações são salvas em settings.json.

Atualizar Mensagens no Início (ON/OFF): Se ativado, busca mensagens novas em tópicos já finalizados logo ao iniciar o script.

Atualizar Mensagens no Fim (ON/OFF): Se ativado, faz uma varredura final por mensagens novas antes de encerrar o ciclo.

Visual Limpo (ON/OFF): Se ativado, exibe apenas logs essenciais (início/fim de tópico) no console. Se desativado, mostra cada ID de mensagem processada.

Atualizar Foto (ON/OFF): Clona a foto de perfil do grupo origem para o destino.

Atualizar Descrição (ON/OFF): Clona a bio/descrição do grupo.

Fechar Tópico (ON/PARCIAL/OFF):

ON: Fecha todos os tópicos no destino após terminar.

PARCIAL: Fecha apenas se estiver fechado na origem.

OFF: Mantém todos abertos.

Fixar Tópicos (ON/OFF): Se ativado, fixa os tópicos no topo da lista conforme a origem.

Tempo Máximo de Clonagem (Horas): Define por quanto tempo o bot trabalha antes de forçar uma pausa longa de descanso. (0 = desativado).

Tempo Máximo de Descanso (Horas): Define a duração do "sono" após atingir o tempo máximo de clonagem.

Delay Entre cada Mensagem (Segundos): Tempo de espera após cada envio de mensagem. Aceita decimais (ex: 0.5). Aumentar evita flood.

Pausa a cada x mensagens (Inteiro): Define o tamanho do lote (ex: 200 mensagens) para disparar uma pausa curta preventiva.

Duração pausa a cada x mensagens (Segundos): Tempo que o bot fica parado após atingir o lote de mensagens acima.

⏱️ Controle de Flood e Pausas

O EncScript possui três camadas de proteção contra bloqueios da API do Telegram:

Pausa por Lote: Configurável (Opções 11 e 12). Pausa proativa para "esfriar" a conexão.

Pausa por Sessão: Configurável (Opções 8 e 9). Simula o descanso de um humano após horas de trabalho.

Tratamento de Erro (FloodWait): Se o Telegram retornar um erro de FloodWait, o script detecta automaticamente, exibe um alerta, aguarda o tempo exigido pelo servidor e retoma a operação sem cair.

📂 Persistência e Continuidade

Banco de Dados (cloner_data.db): Armazena o mapeamento entre IDs de origem e destino (topic_map) e o checkpoint da última mensagem (sync_state).

Opção Continuar: Ao selecionar [2], o sistema lê o last_message_id do banco e solicita à API apenas mensagens com ID superior a este. Isso garante eficiência e evita duplicações.

Limpeza: Ao selecionar [1], o sistema executa um DELETE nas tabelas referentes aos chats escolhidos, garantindo uma clonagem limpa.

📝 Logs e Saídas

Console: Exibe o progresso em tempo real.

Visual Limpo ON: Apenas status de tópicos (⚙️ Iniciando / ✅ Completo) e erros.

Visual Limpo OFF: Detalhes de cada mensagem processada.

Arquivo cloner.log: Registra todos os eventos, avisos e erros com timestamp, independente da configuração visual, útil para auditoria.

🚀 Como Usar

Instalação:

Tenha Python 3.8+ instalado.

Instale as dependências: pip install -r requirements.txt (Telethon, Rich, Python-Dotenv).

Configuração Inicial:

Execute python main.py.

Crie o grupo de destino e ative a opção de tópicos

Insira seu API_ID, API_HASH e Telefone quando solicitado (dados salvos em .env).

Primeira Clonagem:

Escolha a opção [1] Clonar.

Insira o ID do Grupo Origem e Destino (ex: -100123456789).

O script gerará o arquivo topics_config.txt. Edite-o se quiser ignorar tópicos (mude ON para OFF) e salve.

Pressione Enter no terminal para iniciar.

Acompanhamento:

O script criará os tópicos e clonará as mensagens.

Interrupção e Retomada:

Pode parar com Ctrl+C a qualquer momento.

Para voltar, execute novamente e escolha [2] Continuar.

🛑 Erros Comuns

FloodWaitError: O Telegram pediu para esperar. Ação: Não feche o script. Ele esperará automaticamente.

AuthKeyError / SessionRevoked: Sessão inválida. Ação: Apague o arquivo .session e faça login novamente.

"Tópico não encontrado": Pode ocorrer se o tópico foi deletado na origem durante o processo. O script pulará e registrará no log.

Hora Desatualizada: O script verifica se a data do sistema é válida (ano >= 2025). Ajuste o relógio do sistema se necessário.

📦 Requisitos

Linguagem: Python 3.8 ou superior.

Bibliotecas:

telethon (Comunicação MTProto)

rich (Interface CLI)

python-dotenv (Gestão de variáveis)

Conta Telegram: Recomenda-se uma conta secundária ou dedicada para clonagens massivas devido aos limites da plataforma.

Permissões: O usuário deve ser administrador no grupo de destino para criar tópicos, fixar mensagens e alterar dados do grupo.

⚠️ Avisos e Recomendações



Recomenda-se utilizar as configurações abaixo com os seguintes tempos:

Tempo Máximo de Clonagem ................ 6.0h
Tempo Máximo de Descanso ................ 1.0h
Delay Entre cada Mensagem .............. 1.0s
Pausa a cada x mensagens ............... 200
Duração pausa a cada x mensagens ....... 60s

Ao burlar os limites estabelicidos, tenha em mente que sua conta pode ser banida. Então ao usar o EncScript de modo extremo você estará ciente dos riscos envolvidos em tais atos.