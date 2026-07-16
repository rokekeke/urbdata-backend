# ADR 002 - Registro de indicadores

- Status: aceito
- Data: 2026-07-16
- Aprovador de dominio: pendente

Metadados e funcao calculadora ficam em definicoes imutaveis, registradas por codigo unico. O orquestrador consulta o registro e nao conhece formulas concretas. Isso permite adicionar indicadores sem modificar o fluxo central e detectar duplicidades na inicializacao.
