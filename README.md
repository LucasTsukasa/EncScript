<div align="center">

# EncScript

![License](https://img.shields.io/badge/License-GPLv3-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)
![Version](https://img.shields.io/badge/version-1.4.0-orange)
![Safety](https://img.shields.io/badge/Rate%20Limit-Protected-green)

</div>

---

## 📌 Sobre o Projeto

EncScript é uma ferramenta CLI profissional desenvolvida em Python para clonagem, espelhamento e backup estrutural de chats do Telegram.

Projetado para administradores, arquivistas digitais e engenheiros que necessitam migrar ou preservar grandes volumes de dados mantendo a organização original do chat.

Utiliza Telethon (MTProto) como userbot.

---

## ⚠️ Aviso Importante – Uso e Riscos

Este projeto é distribuído sob a licença GNU GPL v3.0, permitindo livre estudo, modificação e redistribuição.

O EncScript foi cuidadosamente calibrado para respeitar os limites de requisição (Rate Limits) da API do Telegram. No entanto, alterações nos parâmetros de tempo, remoção de pausas de segurança ou modificações na lógica de envio podem resultar em comportamento que viole os Termos de Serviço (ToS) do Telegram.

O uso inadequado, configurações agressivas ou versões modificadas podem ocasionar:

- Restrições temporárias de conta
- Limitações de envio
- Bloqueios permanentes

Este software é fornecido "AS IS", sem garantias de qualquer tipo. O usuário assume total responsabilidade pelo uso da ferramenta.

Recomenda-se fortemente a utilização de uma conta secundária dedicada.

---

## 📑 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Recursos Principais](#-recursos-principais)
- [Tipos de Clonagem Suportados](#-tipos-de-clonagem-suportados)
- [Arquitetura](#-arquitetura)
- [Funcionalidades Técnicas](#-funcionalidades-técnicas)
- [Instalação](#-instalação)
- [Configurações](#-configurações)
- [Controle de Flood](#-controle-de-flood)
- [Limitações Conhecidas](#-limitações-conhecidas)
- [Licença](#-licença)
- [Versões](#-versões)

---

## 🚀 Recursos Principais

- Clonagem estrutural completa (Canais, Grupos e Fóruns)
- Suporte bidirecional entre tipos de chat
- Cabeçalho automático por tópico (Fórum → Canal)
- Índice navegável automático ao final da clonagem
- Retry automático de mensagens falhadas
- Persistência segura com SQLite
- Controle granular de Flood e pausas inteligentes
- Criação automática de Canal, Grupo ou Fórum de destino

---

## 🔄 Tipos de Clonagem Suportados

| Origem | Destino | Estrutura Preservada |
|--------|----------|----------------------|
| Canal | Canal | Mensagens |
| Canal | Grupo | Mensagens |
| Canal | Fórum | Tópico único |
| Grupo | Canal | Mensagens |
| Fórum | Canal | Blocos organizados |
| Fórum | Fórum | Estrutura completa |

---

## 🏗 Arquitetura

```
main.py      → Orquestrador principal
service.py   → Motor de clonagem
storage.py   → Persistência SQLite
config.py    → Configurações e ambiente
ui.py        → Interface CLI
```

---

## ⚙️ Funcionalidades Técnicas

### Estrutura
- Replica tópicos (título, estado, fixação)
- Mantém ordem cronológica
- Preserva mídias e mensagens longas
- Mantém fixações configuráveis

### Organização (Fórum → Canal)
- Envia cabeçalho por tópico
- Fixa cabeçalho (configurável)
- Gera índice final com links navegáveis
- Divide índice automaticamente se ultrapassar limite do Telegram

### Persistência
Banco `cloner_data.db` armazena:
- Mapeamento estrutural
- Checkpoint por (origem + destino)
- Status de tópicos
- Fila de falhas (retry automático)

---

## 📦 Instalação

### Requisitos
- Python 3.8+
- Conta Telegram
- Permissão de administrador no destino

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Executar

```bash
python main.py
```

Na primeira execução:
- Insira API_ID
- Insira API_HASH
- Informe telefone
- Sessão será salva automaticamente

---

## 🔧 Configurações

### Canais/Grupo
- Atualizar mensagens no início/fim
- Visual limpo
- Atualizar foto/descrição
- Fechar tópicos
- Fixar tópicos
- Renomear destino existente
- Cabeçalho por tópico (Fórum → Canal)
- Índice final
- Fixar índice final

### Tempo
- Tempo máximo de clonagem
- Tempo máximo de descanso
- Delay entre mensagens
- Pausa por lote
- Duração da pausa
- Batch size

---

## ⏱ Controle de Flood

EncScript possui três camadas de proteção:

1. Micro pausas configuráveis
2. Macro pausas por sessão
3. Tratamento automático de FloodWait

---

## ⚠️ Limitações Conhecidas

- Não clona chats com proteção de conteúdo ativada.
- Não contorna bloqueios de encaminhamento.
- Grandes volumes (1000+ tópicos) podem levar vários minutos para indexação.
- Requer permissões administrativas no destino.

---

## 📜 Licença

Este projeto é distribuído sob a licença **GNU GPL v3.0**.

Consulte o arquivo `LICENSE` para detalhes completos.

---

## 📈 Versões

Consulte o arquivo `CHANGELOG.md` para histórico detalhado de versões.