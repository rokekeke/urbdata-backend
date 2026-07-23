# Migração do frontend para o monorepo

## Decisão

O `URBDATA-UX` passa a ser mantido em `frontend/` no mesmo repositório do
backend. O backend permanece na raiz nesta etapa para não ampliar o impacto da
migração durante o desenvolvimento dos contratos de `MapDocument` e exportação.

## Como o histórico foi preservado

- o estado acumulado do frontend foi consolidado na branch local
  `codex/frontend-fundacao-fb009`, commit `b2c406c`;
- a importação foi feita sem squash, mantendo os commits anteriores consultáveis;
- a integração foi preparada na branch `codex/monorepo-frontend-migration`;
- o diretório original `C:\Users\URB\Documents\URBDATA-UX` não foi apagado e
  permanece como cópia de segurança até a validação da equipe.

## Organização adotada

```text
frontend/                         aplicação web e runtime de hospedagem
docs/frontend/                    decisões e documentação funcional do frontend
.github/workflows/frontend-ci.yml validação isolada do frontend
```

O workflow do frontend só é acionado quando `frontend/**` ou o próprio workflow
muda. Seus comandos são executados com `frontend/` como diretório de trabalho.
O workflow do backend foi preservado nesta primeira etapa.

## Contrato entre as aplicações

`frontend/contracts/openapi.json` continua sendo o snapshot versionado usado
para gerar `frontend/app/lib/api/schema.d.ts`. O CI do frontend não depende de
uma API em execução. Quando o contrato mudar, a atualização deve ser explícita,
revisada junto com os consumidores afetados e validada por `pnpm api:check`.

## Integração segura

A branch de migração parte do último commit publicado em `main` (`86860a1`) e
não incorpora as alterações locais ainda em revisão no diretório principal do
backend. Depois que a equipe consolidar essas alterações, a branch deve ser
atualizada com `main`, validada novamente e só então integrada.

O diretório antigo do frontend só deve ser arquivado ou removido depois de:

1. a branch de migração estar integrada ao repositório remoto;
2. frontend e backend passarem nas validações do monorepo;
3. a execução local integrada ser confirmada pela equipe;
4. a configuração de hospedagem reconhecer `frontend/` como raiz da aplicação.

## Validação desta etapa

- frontend: contrato OpenAPI, TypeScript, lint, 71 testes e build aprovados;
- backend: Ruff, mypy e 227 testes unitários aprovados;
- testes de integração do backend: pendentes, pois exigem um banco descartável
  informado por `URBDATA_TEST_DATABASE_URL`;
- integração com as alterações locais mais recentes do backend: pendente até a
  equipe consolidar o trabalho em andamento na branch principal.
