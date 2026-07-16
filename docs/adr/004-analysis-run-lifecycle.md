# ADR 004 - Ciclo de vida da analise

- Status: aceito para o MVP
- Data: 2026-07-16
- Aprovador de dominio: pendente

O MVP executara a primeira fatia vertical de forma sincrona, conforme o backlog especifico, usando estados `pending`, `running`, `completed` e `failed`. O run deve existir antes do calculo e a falha deve sobreviver ao rollback dos resultados. As fronteiras de aplicacao serao mantidas compativeis com futura execucao em fila, exigida para cargas pesadas pela diretriz geral de backend. Qualquer mudanca do contrato HTTP sera documentada e versionada.

O estado legado `error` foi migrado para `failed` na revisao Alembic 0002. O tipo PostgreSQL pode reter o valor antigo por compatibilidade fisica, mas novas gravacoes usam apenas os quatro estados definidos acima.
