# Fundação do frontend URBDATA

## Objetivo

Esta camada separa o contrato do backend, o transporte HTTP, os erros de aplicação, o cache assíncrono e os componentes visuais. A interface não deve conhecer detalhes do FastAPI nem chamar a rede diretamente.

## Estrutura

```text
frontend/contracts/openapi.json             snapshot versionado do backend
frontend/app/lib/api/schema.d.ts            tipos gerados, nunca editados à mão
frontend/app/lib/runtimeConfig.ts           validação da URL pública
frontend/app/lib/api/client.ts              única instância openapi-fetch
frontend/app/lib/api/request.ts             erros e resposta do transporte
frontend/app/lib/errors/appError.ts         erro estável para a interface
frontend/app/lib/query/                     políticas e chaves TanStack Query
frontend/app/features/<feature>/api/        operações tipadas por domínio de tela
frontend/app/features/<feature>/hooks/      queries e mutations consumidas pela UI
frontend/tests/                             testes sem backend ou internet
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

Na raiz do monorepo, inicie o backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Em outro terminal, ainda a partir da raiz, inicie o frontend:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
pnpm dev
```

A configuração local usa `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. O prefixo `/v1` já pertence aos paths do OpenAPI.

## Validação local

```bash
cd frontend
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
- a configuração avançada de `feature_panel` ainda não pertence ao contrato persistido;
- o snapshot OpenAPI precisa ser atualizado explicitamente quando o backend mudar;
- PDF e SVG permanecem fora do primeiro recorte de exportação;
- a exportação PNG depende de fontes raster que permitam leitura do canvas no navegador;
- `pnpm peers check` registra uma incompatibilidade não bloqueante entre `@cloudflare/workers-types 5.x` e o peer esperado pelo `wrangler 4.92.0`; build e testes passam, mas o alinhamento deve entrar na próxima manutenção do runtime antes da implantação.

## Política remota

Commit local, push, publicação e implantação devem seguir a autorização do responsável. Nenhuma automação de CI publica o site; o workflow atual apenas valida o código.
