# Fundação do frontend URBDATA

## Objetivo

Esta camada separa o contrato do backend, o transporte HTTP, os erros de aplicação, o cache assíncrono e os componentes visuais. A interface não deve conhecer detalhes do FastAPI nem chamar a rede diretamente.

## Estrutura

```text
contracts/openapi.json             snapshot versionado do backend
app/lib/api/schema.d.ts            tipos gerados, nunca editados à mão
app/lib/runtimeConfig.ts           validação da URL pública
app/lib/api/client.ts              única instância openapi-fetch
app/lib/api/request.ts             erros e resposta do transporte
app/lib/errors/appError.ts         erro estável para a interface
app/lib/query/                     políticas e chaves TanStack Query
app/features/<feature>/api/        operações tipadas por domínio de tela
app/features/<feature>/hooks/      queries e mutations consumidas pela UI
tests/                             testes sem backend ou internet
```

## Fluxo de uma consulta

```text
componente
→ hook TanStack Query
→ função de feature
→ cliente OpenAPI
→ executeApiRequest
→ normalizeAppError
→ estado de carregamento, sucesso, vazio ou erro
```

O schema de transporte vem do OpenAPI. Modelos locais são permitidos somente quando representam estado derivado de interface e não uma cópia do payload do servidor.

## Atualizar o contrato

1. Inicie o backend em `http://localhost:8000`.
2. Execute `pnpm api:update`.
3. Revise as diferenças em `contracts/openapi.json` e `app/lib/api/schema.d.ts`.
4. Ajuste operações afetadas e execute `pnpm api:check`.
5. Nunca edite o JSON ou o TypeScript gerado manualmente.

O CI usa o snapshot versionado e não inicia o backend. Mudanças contratuais precisam chegar ao frontend como uma atualização explícita e revisável.

## Criar uma nova query

1. Adicione uma chave determinística em `app/lib/query/queryKeys.ts`.
2. Crie a operação em `app/features/<feature>/api/`, usando `getApiClient()` e um path presente em `schema.d.ts`.
3. Passe o `AbortSignal` do TanStack Query por `createRequestSignal()`.
4. Converta falhas com `normalizeAppError()`.
5. Crie o hook em `app/features/<feature>/hooks/`.
6. Cubra carregamento, sucesso, vazio e erro em teste isolado.

Não use `fetch` em componentes ou stores. A regra de lint impede esse acoplamento.

## Política de erros

- `ApiRequestError` representa transporte: HTTP, rede, timeout, cancelamento e resposta inválida.
- `AppError` representa a decisão de UI: mensagem, código, contexto, possibilidade de retry e apresentação `inline`, `global` ou `silent`.
- erros de domínio preservam `message` e `context` fornecidos pelo backend;
- o `422` nativo do FastAPI é convertido em uma lista `validation_issues`;
- cancelamentos são silenciosos e nunca repetidos;
- rede, timeout, resposta inválida e erros 5xx podem ter uma tentativa automática;
- validação, conflito e dados ausentes não são repetidos automaticamente.

## Execução local integrada

Backend, em `C:\Users\URB\Documents\urbdata-backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend, em `C:\Users\URB\Documents\URBDATA-UX`:

```powershell
Copy-Item .env.example .env.local
pnpm dev
```

A configuração local usa `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. O prefixo `/v1` já pertence aos paths do OpenAPI.

## Validação local

```bash
pnpm install --frozen-lockfile
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Os testes simulam `fetch` e as funções de feature. Eles não dependem de Docker, banco, backend ativo ou acesso à internet.

## Limitações atuais

- sem autenticação;
- `useProjects()` é a primeira query; as demais entram na integração de leitura;
- mapa e telas ainda usam dados demonstrativos;
- sem CRUD de `MapDocument`;
- sem persistência do `feature_panel`;
- sem snapshot e upload integrado da exportação;
- o lint mantém um aviso conhecido em `MapCanvas.tsx` até a reorganização do ciclo de vida do mapa.
- `pnpm peers check` registra uma incompatibilidade não bloqueante entre `@cloudflare/workers-types 5.x` e o peer esperado pelo `wrangler 4.92.0`; build e testes passam, mas o alinhamento deve entrar na próxima manutenção do runtime antes da implantação.

## Política remota

Commit local, push, publicação e implantação devem seguir a autorização do responsável. Nenhuma automação de CI publica o site; o workflow atual apenas valida o código.
