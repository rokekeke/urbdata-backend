# URBDATA UX

Interface web do URBDATA, agora mantida na pasta `frontend/` do monorepo da
plataforma e construída a partir das decisões registradas no vault do projeto.

Este é o frontend oficial do projeto. O runtime adotado nesta fase é Next.js 16 com React 19, Vinext/Vite e saída compatível com Cloudflare Workers/Sites.

## Escopo desta primeira versão

- shell responsivo da plataforma;
- navegação entre as áreas principais;
- aba Documentação como editor cartográfico;
- múltiplas camadas MapLibre;
- visibilidade e ordem das camadas;
- representação única, categórica e sequencial;
- paletas, transparência, cor e estilo de linha;
- opção sem mapa-base e OSM claro;
- legenda vinculada à configuração;
- leitura de projetos, versões, camadas, atributos e resultados pela API;
- disponibilidade e execução de diagnósticos;
- CRUD de composições cartográficas (`MapDocument`) com controle de conflito;
- exportação PNG reproduzível com snapshot e upload do arquivo;
- estados explícitos de carregamento, vazio, erro e indisponibilidade.

## Limites intencionais

- a configuração avançada do painel de feição ainda é mantida apenas no frontend;
- PDF, SVG, autenticação e deck.gl estão fora do MVP atual;
- novas capacidades só são integradas após atualização formal do contrato OpenAPI.

## Runtime oficial

- Node.js `22.13.0` recomendado, com mínimo `>=22.13.0`;
- pnpm `11.9.0`;
- Next.js `16.2.6` e React `19.2.6`;
- Vinext `0.0.50` e Vite `8.0.13`;
- Cloudflare Workers como alvo atual de build e hospedagem.

O arquivo `.node-version` registra a versão recomendada do Node e o campo `packageManager` do `package.json` fixa a versão do pnpm. Não use npm ou yarn para instalar ou atualizar dependências e não gere outros lockfiles.

## Instalação

```bash
pnpm install --frozen-lockfile
```

Crie a configuração local a partir do modelo versionado:

```bash
cp .env.example .env.local
```

No Windows/PowerShell, use:

```powershell
Copy-Item .env.example .env.local
```

Variável disponível:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

O valor é público porque será usado pelo navegador; nunca inclua usuário, senha, token ou outra credencial nessa URL. Informe a origem do serviço sem `/v1`, pois os caminhos gerados pelo OpenAPI já contêm esse prefixo. O módulo `app/lib/runtimeConfig.ts` valida a configuração e remove barras finais antes que o cliente HTTP a utilize.

## Comandos oficiais

```bash
pnpm dev        # servidor local com atualização automática
pnpm build      # build de produção Vinext/Cloudflare
pnpm start      # executa o build de produção
pnpm typecheck  # validação TypeScript sem gerar arquivos
pnpm lint       # análise estática
pnpm test       # suíte isolada Vitest do frontend
pnpm test:watch # suíte em modo de desenvolvimento
pnpm api:update # captura o OpenAPI local e gera os tipos TypeScript
pnpm api:check  # verifica se os tipos correspondem ao snapshot versionado
```

O lint atual não possui erros. Existe um aviso conhecido sobre dependências de `useEffect` em `MapCanvas.tsx`, que será tratado sem bloquear esta fundação.

A arquitetura da integração, o fluxo para atualizar o OpenAPI e as regras para
novas queries estão em [`docs/frontend/foundation.md`](../docs/frontend/foundation.md).

## Estrutura do runtime

### Mantida

- `app/`: aplicação e componentes do URBDATA;
- `public/`: ativos públicos;
- `build/sites-vite-plugin.ts`: empacotamento dos metadados de Sites;
- `worker/index.ts`: ponto de entrada do Cloudflare Worker;
- `.openai/hosting.json`: declaração lógica dos recursos de hospedagem;
- `vite.config.ts`, `next.config.ts` e arquivos de TypeScript/PostCSS: configuração do runtime;
- `../docs/frontend/`: documentação funcional e decisões de integração.
- `app/lib/api/`: cliente OpenAPI único, tipos gerados e fronteira de erros de transporte;

### Preservada, mas candidata à remoção em tarefa separada

- `db/` e `drizzle.config.ts`: infraestrutura opcional de D1, ainda não usada pelo URBDATA;
- `drizzle/`: metadados vazios do starter;
- `examples/`: exemplo de integração D1, sem importação pela aplicação;
- script `db:generate`: só será mantido se o frontend precisar de persistência própria.

Esses itens não devem ser removidos durante a integração inicial. A persistência oficial do URBDATA permanece no backend FastAPI/PostgreSQL; qualquer remoção deve ser feita em mudança própria, depois de confirmar que Sites não exige os arquivos.

## Política de versionamento

- somente `pnpm-lock.yaml` é aceito;
- `.env.local`, logs, caches e artefatos de build não entram no Git;
- tipos gerados, quando introduzidos, devem ser atualizados pelo script oficial e nunca editados manualmente;
- `contracts/openapi.json` é o snapshot versionado que desacopla o CI do servidor local;
- componentes e stores não podem chamar `fetch` diretamente; novas operações passam pelo cliente tipado em `app/lib/api/`;
- publicação ou envio para repositório remoto exige autorização expressa do responsável pelo projeto.
