# Baseline do banco e reconciliacao Alembic

O banco compartilhado ja continha o schema do prototipo quando recebeu `alembic stamp 0001`. Nenhum DDL da revisao 0001 foi executado nesse banco. A coluna `features.external_id` foi adicionada manualmente antes da revisao 0002.

A revisao `0002_reconcile_analysis_schema` transforma esse conhecimento operacional em historico reproduzivel:

- trata `features.external_id` de forma idempotente;
- amplia o ciclo do run para `pending`, `running`, `completed` e `failed`;
- converte registros legados `error` para `failed`;
- adiciona timestamps, duracao e erro estruturado ao run;
- adiciona versao da formula, CRS, parametros, camadas e avisos aos resultados;
- preserva a coluna fisica `indicator_results.value` para nao alterar o contrato atual.

Testes destrutivos de migration exigem um banco isolado informado por `URBDATA_TEST_DATABASE_URL`. Nunca aponte essa variavel para o banco compartilhado.
