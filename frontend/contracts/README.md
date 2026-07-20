# Contrato OpenAPI do URBDATA

`openapi.json` é o snapshot versionado do contrato publicado pelo backend. Ele permite que o frontend gere e valide seus tipos sem depender de uma API ativa durante o CI.

## Atualização local

Com o backend ativo em `http://localhost:8000`:

```bash
pnpm api:update
```

Para usar outra origem somente durante a atualização:

```powershell
$env:URBDATA_OPENAPI_URL = "http://localhost:8000/openapi.json"
pnpm api:update
```

`URBDATA_OPENAPI_URL` é uma variável de ferramenta e não é exposta ao navegador.

## Verificação

```bash
pnpm api:check
```

A verificação regenera os tipos em memória e falha se `app/lib/api/schema.d.ts` estiver diferente do snapshot. Nem o JSON nem o arquivo TypeScript gerado devem ser editados manualmente.
