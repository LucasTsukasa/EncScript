# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

O formato segue o padrão Semantic Versioning (SemVer).

---

## [1.4.0] - 2026-02-20

### Added
- Suporte completo a Canal ↔ Grupo ↔ Fórum
- Sistema de índice final navegável (Fórum → Canal)
- Cabeçalho automático por tópico com opção de fixação
- Opção de renomear destino existente
- Criação de Canal, Grupo ou Fórum via menu
- Retry automático para mensagens falhadas
- Persistência separada por (origem + destino)
- Configuração de batch size

### Changed
- Estrutura de banco de dados aprimorada
- Menu de criação de destino reorganizado
- Melhorias de performance e estabilidade

### Fixed
- Correção de avanço incorreto de checkpoint em falhas
- Melhor tratamento de FloodWait