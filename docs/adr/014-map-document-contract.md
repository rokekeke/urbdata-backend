# ADR 014 - Contrato do documento cartografico v1

- Status: aceito (decisoes travadas na nota Obsidian 28; refinamentos das notas 31/32)
- Data: 2026-07-18
- Emenda 19/07/2026: Decisao 7 (`feature_panel`, nota Obsidian 33)
- Emenda 19/07/2026: Decisao 8 (CRUD, rotas e leitura de referencias
  quebradas - checkpoint 4.1, nota Obsidian 38)
- Emenda 20/07/2026: item 4.6 implementado (rotas HTTP) - esclarecimento do
  formato do 409 da Decisao 4 (ver abaixo)
- Contexto: aba Documentacao (nota 24), backlog DOC-BE-001..010 (nota 25 /
  `docs/backlog/map-documentation-backend.md`), caminho definitivo do MVP
  (nota 28), analise do codigo-fonte do Kepler.gl (notas 31/32).

## Problema

A aba Documentacao precisa persistir a composicao cartografica (camadas,
representacao, estilos, mapa-base, viewport) de forma editavel, reproduzivel
e independente do renderizador, sem duplicar dados nem permitir que estilo
altere resultado analitico. O frontend vai construir o editor contra este
contrato desde o inicio - nao existe fase de "schema local improvisado".

## Decisao 1 - Separacao de conceitos persistidos

```text
MapDocument   documento editavel (novo, migration 0008)
StylePreset   regra visual reutilizavel / estilo recomendado (tabela existente)
Export        snapshot imutavel + artefato produzido (tabela existente)
```

- O documento referencia camadas por `project_layers.id` e indicadores por
  `indicator_code`. **Nunca** duplica GeoJSON, atributos ou valores de
  indicador dentro do JSON do documento.
- O join indicador-feicao no mapa usa o contrato ja publico: chave do dict
  de resultado == `feature.id` do GeoJSON (`feature_key: feature_id`) ou
  propriedade `quadra_id` da camada derivada (`feature_key: quadra_id`) -
  ver `GET /v1/catalog/indicators`.
- Estilo e configuracao derivada: nenhuma operacao deste contrato altera
  feicao, camada ou resultado persistido (invariante 2 do projeto).

## Decisao 2 - Schema v1 do MapDocument

Persistido em JSONB validado por Pydantic (autoridade unica de validacao;
Zod no cliente e conveniencia, nunca autoridade).

```text
MapDocument
├── schema_version: "1"            (obrigatorio)
├── name: str                      (nome interno)
├── title: str | null              (titulo exibido no mapa exportado)
├── basemap_id: str                (id do catalogo, Decisao 5)
├── viewport
│   ├── longitude: float
│   ├── latitude: float
│   ├── zoom: float
│   ├── bearing: float = 0
│   └── pitch: float = 0
└── layers: list[DocumentLayer]    (ordem da lista = ordem de desenho,
                                    primeiro = base, determinstica)

DocumentLayer
├── layer_id: UUID                 (project_layers.id, mesma ProjectVersion)
├── visible: bool = true
├── representation
│   ├── source: "property" | "indicator" | "none"
│   ├── field: str | null              (source=property: campo mapeado/fonte)
│   ├── indicator_code: str | null     (source=indicator)
│   ├── mode: "single" | "categorical" | "sequential" | "diverging"
│   ├── scale: "ordinal" | "quantile" | "quantize" | "linear"
│   │          | "sqrt" | "log" | "threshold" | null
│   ├── classes: int | null            (categorical/sequential/diverging)
│   ├── stops: list[float] | null      (scale=threshold: ordenados, unicos,
│   │                                   2..12 valores, dentro do dominio)
│   └── null_behavior: "transparent" | "color"  (default transparent;
│                                       "color" usa style.null_color)
├── style
│   ├── fill
│   │   ├── color: hex | null          (mode=single)
│   │   ├── palette: list[hex] | null  (demais modos; tamanho == classes)
│   │   └── opacity: float 0..1
│   ├── stroke
│   │   ├── color: hex
│   │   ├── width_px: float > 0, <= 20
│   │   ├── style: "solid" | "dashed" | "dotted"
│   │   └── opacity: float 0..1
│   ├── null_color: hex | null
│   └── labels: null                   (reservado, sem editor na v1)
└── interaction
    ├── tooltip_fields: list[str]       (legado; leitura simples, fallback
    │                                    quando feature_panel esta
    │                                    desabilitado - nota 33)
    ├── selectable: bool = true
    ├── feature_panel: FeaturePanelConfig  (Decisao 7 - nucleo implementado
    │                                       nesta emenda, nota 33)
    └── filters: null                   (reservado na v1 - filtros visuais
                                          NUNCA alteram resultado persistido)
```

Vocabulario de `scale` herdado do par kepler.gl/d3-scale (nota 32) - o
frontend usa `d3-scale`, que tem exatamente esses nomes. Correspondencia:

| `mode` | `scale` validas |
|---|---|
| `single` | null (cor fixa, sem canal) |
| `categorical` | `ordinal` |
| `sequential` | `quantile`, `quantize`, `linear`, `sqrt`, `log`, `threshold` |
| `diverging` | mesmas de sequential + pivot central (convencao de paleta) |

## Decisao 3 - Validacao autoritativa (Pydantic, na gravacao)

Configuracao invalida nao e persistida nem parcialmente; o erro segue o
envelope `{error, message, context}` e aponta o caminho do campo.

1. `layer_id` existe e pertence a `ProjectVersion` do documento;
2. `field` existe na camada (fonte ou mapeado) quando `source=property`;
3. `indicator_code` registrado no catalogo quando `source=indicator`,
   com `granularity=por_feicao` e `feature_key` compativel com a camada;
4. `mode` compativel com o tipo do dado e a geometria da camada;
5. `scale` valida para o `mode` (tabela acima);
6. cores em hex canonico (`#RRGGBB` ou `#RRGGBBAA`);
7. opacidades em [0, 1]; largura de linha (0, 20] px;
8. `stops` ordenados, unicos, 2..12, dentro do dominio do campo;
9. cardinalidade categorica: **aviso acima de 12 classes, bloqueio acima
   de 32** (limites da nota 28, sujeitos a validacao do urbanista);
10. `basemap_id` existente no catalogo (Decisao 5);
11. comportamento de nulos explicito (`null_behavior`, default transparent -
    espelha o `NO_VALUE_COLOR` transparente do Kepler.gl, nota 32).

Regras 1-3 e 4 (metade "tipo do dado") dependem de contexto de banco e sao
aplicadas pelo modulo `contextual_validation.py` na Fase 3 (item 4.3,
19/07/2026), nao pelos modelos Pydantic (esta secao descreve o contrato
completo; a fronteira exata entre o que o Pydantic valida sem banco e o
que so a Fase 3 pode validar esta documentada no docstring do modulo). A
metade "geometria" da regra 4 nao precisou de codigo adicional: `LayerStyle`
sempre carrega `fill` e `stroke`, o valor nao usado pela geometria real
simplesmente nao renderiza - nao existe combinacao mode x geometria
estruturalmente invalida. Regra 4 (tipo do dado) cobre: campo vazio/misto/
cardinalidade categorica excedida rejeita qualquer modo alem de `single`;
`sequential`/`diverging` exigem campo numerico ou indicador escalar
(`unit != "composto"` no catalogo - `quadras.stats` e
`quadras.min_rotated_rectangle` sao os dois casos reais hoje).

## Decisao 4 - Versionamento e concorrencia

- `schema_version` obrigatorio no JSON. Leitura de versao antiga: upcast
  puro em memoria (`vN -> v(N+1)` encadeado), persistencia so na proxima
  gravacao. Na v1 existe apenas a identidade `1 -> 1`, testada, e um
  fixture valido por versao mantido em `tests/fixtures/map_documents/`.
- Concorrencia otimista: coluna `revision` (int) incrementada pelo
  servidor a cada `PUT`; o cliente envia a revisao esperada; divergencia
  responde `409` com o documento atual no corpo (o cliente decide como
  reconciliar). Sem autosave no servidor: so gravacoes explicitas.
  **Esclarecimento (item 4.6, 20/07/2026)**: "no corpo" implementado como
  `detail.context.current_document` (um `MapDocumentOut` completo) dentro
  do envelope unico `{error, message, context}` - nao um `MapDocumentOut`
  cru substituindo o envelope. Motivo: o guard `test_openapi_contract.py`
  (Fase 1) ja exige que **todo** 4xx declarado use `ErrorEnvelopeOut`, sem
  excecao por rota; aninhar o documento em `context` preserva essa garantia
  automatizada para 100% das rotas (inclusive esta, o primeiro 409 da API)
  sem abrir um precedente de "response_model variavel por status", e o
  cliente ainda recebe o documento inteiro sem uma segunda consulta.
- Multiplos documentos por versao, sem limite rigido na v1.

## Decisao 5 - Catalogo de mapas-base v1

Catalogo controlado, definido no servidor (`GET /v1/map-basemaps`), sem
URL livre e sem credencial na v1 (elimina proxy/token/SSRF). Entradas:

| id | label | style_url | color_mode |
|---|---|---|---|
| `none` | Sem mapa-base | - | none |
| `positron` | Claro (Positron) | `https://basemaps.cartocdn.com/gl/positron-gl-style/style.json` | light |
| `dark_matter` | Escuro (Dark Matter) | `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json` | dark |
| `voyager` | Detalhado (Voyager) | `https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json` | light |

- Estilos vetoriais publicos do CARTO - os mesmos que o proprio Kepler.gl
  usa como default MapLibre (nota 32), sem chave de acesso.
- **Atribuicao obrigatoria e nao removivel**: `(c) OpenStreetMap
  contributors, (c) CARTO` - gravada no catalogo, exibida no mapa e
  incluida em toda exportacao. Exportar com mapa-base sem atribuicao no
  snapshot e erro de validacao.
- Disponibilidade nao e garantida contratualmente pelo provedor: o
  catalogo carrega estado de indisponibilidade e o fallback e `none`.
- `export_allowed: true` para as quatro entradas na v1.

## Decisao 6 - Snapshot de exportacao (`exports.config`)

Congelado **antes** do render, imutavel depois - edicoes posteriores do
documento nao afetam exportacao em andamento ou concluida. Shape:

```text
exports.config (JSONB)
├── document_id, document_revision, schema_version
├── project_version_id
├── analysis_run_id: UUID | null    (run cujos resultados estao no mapa)
├── viewport                        (completo, como na Decisao 2)
├── layers                          (copia resolvida: ordem, visibilidade,
│                                    representacao e estilo POR VALOR,
│                                    incluindo dominios/classes/paleta
│                                    efetivamente calculados - a legenda
│                                    permanece reproduzivel mesmo se a
│                                    logica de paleta mudar depois)
├── basemap: {id, label, style_url, attribution}
├── legend: bool                    (toggle explicito, nota 32)
├── image: {ratio_id: "screen" | "four_by_three" | "sixteen_by_nine",
│           resolution_id: "1x" | "2x", scale: 1 | 2,
│           width_px, height_px}
├── renderer: {agent: "frontend-maplibre", maplibre_version,
│              frontend_version}
├── requested_at: timestamp UTC
└── checksum: sha256 do JSON canonico do snapshot
```

- Contrato com shape de job, execucao sincrona na v1 (nota 28, decisao 18):
  `POST /documents/{id}/exports` cria o registro com status e devolve o id;
  `GET` consulta; o PNG renderizado no cliente e recebido e arquivado em
  `exports.file_path` (storage local existente). Migrar para fila real nao
  quebra o contrato.
- Formato v1: PNG. Presets de prancha (A4/A3, DPI) aguardam definicao do
  urbanista - fora da v1.

## Decisao 7 - Painel informativo de feicao (feature_panel, nota 33)

Emenda de 19/07/2026. `DocumentLayer.interaction.feature_panel` deixa de
ser campo reservado e passa a ter schema proprio - nucleo minimo da nota
Obsidian 33 (painel que abre ao clicar numa feicao, combinando atributos
e indicadores pelo mesmo UUID). `tooltip_fields` permanece como fallback
de leitura simples quando o painel esta desabilitado.

```text
FeaturePanelConfig
├── enabled: bool = false
├── title_field: str | null              (nome de propriedade; existencia
│                                          na camada verificada na Fase 3,
│                                          mesma regra de representation.field)
├── width: "compact" | "medium" = "compact"
└── blocks: list[TextBlock | TableBlock]  (max 8, discriminado por "type")

TextBlock
├── type: "text"
├── source: "property" | "indicator"
├── field: str                            (nome de propriedade OU
│                                          indicator_code, conforme source)
└── style: "body" | "subtitle" = "body"

TableBlock
├── type: "table"
├── layout: "key_value" = "key_value"     (unico layout na v1)
└── fields: list[TableField]              (1..12, sem (source,key) repetido)

TableField
├── source: "property" | "indicator"
├── key: str
├── label: str                            (1..60 caracteres)
└── format: FieldFormat | null
    ├── type: "text" | "number"
    ├── decimals: int | null              (0..6, so com type=number)
    ├── prefix: str | null                (so com type=number, <=8 chars)
    └── suffix: str | null                (so com type=number, <=16 chars)
```

Regras estruturais (Pydantic, `extra=forbid`):

1. `source=indicator` em `TextBlock`/`TableField` exige `indicator_code`
   registrado e com `granularity=por_feicao` - mesma checagem de
   `Representation` (Decisao 2), fatorada em helper compartilhado;
2. `source=property` nao valida a existencia do campo na camada aqui -
   como `Representation.field`, isso e responsabilidade do CRUD (Fase 3);
3. `format.type=text` nao aceita `decimals`/`prefix`/`suffix` - formato
   invalido para o tipo e rejeitado, nunca ignorado silenciosamente;
4. `TableBlock.fields` nao aceita duas entradas com o mesmo par
   `(source, key)`;
5. limites de tamanho (8 blocos, 12 campos por tabela, rotulo ate 60
   caracteres) - o painel nunca carrega texto livre extenso: blocos
   referenciam campos/indicadores, nunca uma string arbitraria do
   usuario (sem editor de HTML/CSS, por definicao da nota 33).

### Exemplo valido

```json
{"type": "table", "layout": "key_value", "fields": [
  {"source": "property", "key": "quadra_id", "label": "Quadra", "format": null},
  {"source": "indicator", "key": "lots.frontage_length", "label": "Testada",
   "format": {"type": "number", "decimals": 1, "prefix": null, "suffix": "m"}}
]}
```

### Exemplos invalidos

- `{"type": "text", "source": "indicator", "field": "territorial.total_area", ...}`
  (indicador de projeto, nao por feicao);
- `{"type": "table", "layout": "key_value", "fields": []}` (minimo 1 campo);
- `format: {"type": "text", "decimals": 2}` (decimals so com type=number);
- dois campos com `source=property, key=quadra_id` no mesmo `TableBlock`.

### Fora desta decisao (nota 33, pendente de validacao de produto)

Ancoragem do painel na feicao vs. painel fixo durante navegacao; alcance
dos blocos de texto (somente campo, por decisao desta emenda, nao texto
estatico livre); disponibilidade de indicadores alem dos por-feicao;
inclusao do painel na exportacao cartografica (Decisao 6).

## Decisao 8 - CRUD, rotas e leitura de referencias quebradas

Emenda de 19/07/2026, checkpoint 4.1 (nota Obsidian 38) - resolvida com o
responsavel antes de qualquer codigo, por tocar comportamento ja
publicado (ADR 009) e por definir semantica que a Fase 3 inteira
depende.

### Rotas - aninhado para a colecao, achatado para o item

`MapDocument` nao segue a convencao de "versao corrente" que `/analyze`
e `/runs` usam - multiplos documentos por versao, incluindo versoes
antigas/arquivadas (Decisao 4). A versao precisa ser explicita na URL
para listar/criar; uma vez com o id do documento em maos, ele e unico
por si so (mesmo padrao ja usado por `/runs/{run_id}`):

```text
POST   /v1/projects/{project_id}/versions/{version_id}/documents
GET    /v1/projects/{project_id}/versions/{version_id}/documents
GET    /v1/projects/{project_id}/documents/{document_id}
PUT    /v1/projects/{project_id}/documents/{document_id}
DELETE /v1/projects/{project_id}/documents/{document_id}
```

`project_id` mantido no path das rotas de item por consistencia com o
resto da API e para a checagem de pertencimento (404 se o documento nao
pertence ao projeto), nao porque o id do documento precise dele para ser
unico.

**Implementado 20/07/2026** (item 4.6, `app/api/v1/routes/map_documents.py`
+ `app/api/v1/schemas/map_document.py`): as 5 rotas acima, mais o novo
fragmento `CONFLICT` (409) em `app/api/v1/schemas/error.py` - o primeiro
409 declarado na API. `DELETE` responde `204` sem corpo; isso exigiu um
ajuste minimo no guard `test_openapi_contract.py` (que so conhecia 2xx
com corpo) para tratar 204 como estruturalmente sem schema (RFC 9110), nao
como uma operacao que esqueceu de declarar seu `response_model`. Testes de
integracao HTTP em `tests/integration/test_map_documents_api.py` (item
4.7) cobrem o checklist da nota 39 completo, incluindo a armadilha de
quadras (ADR 009) alcancada via `GET` real, nao so via repositorio.

### Leitura com referencia quebrada - diagnostico, nunca falha

Um documento salvo pode ficar com `layer_id` apontando para camada
apagada, ou `indicator_code` incompativel apos remapeamento de atributos.
`GET` **sempre** devolve o documento integro - nunca falha e nunca corrige
a configuracao salva silenciosamente (regra invariante 2 do projeto) -
acompanhado de um bloco `integrity_warnings` separado, calculado em cada
leitura (nao persistido), listando toda referencia invalida encontrada:

```text
IntegrityWarning
├── code: "layer_not_found" | "indicator_incompatible"
├── layer_id: UUID
└── message: str
```

O documento continua editavel e salvavel nesse estado - o proximo `PUT`
roda a validacao contextual normal (Decisao 8, validacao na escrita)
sobre o que o cliente de fato enviar, nao sobre o estado antigo.

### A armadilha da camada de quadras (ADR 009) - resolvida pelo mecanismo acima, sem mudanca de codigo

`POST /layers/quadras/derive` apaga e recria a camada derivada com
**UUID novo** a cada chamada (ADR 009, comportamento ja publicado). Um
documento que referenciava a quadra antiga fica orfao no proximo
re-derive. Decisao: **nao alterar `derive_quadras_layer`** - o
diagnostico de leitura acima ja cobre esse caso como mais uma instancia
de `layer_not_found`, sem codigo especifico para quadras. Estabilizar o
id da camada derivada (UPDATE em vez de DELETE+INSERT) fica registrado
como opcao futura caso o diagnostico se mostre insuficiente na pratica,
mas nao e feito agora - menor risco, nao mexe em ADR 009.

### DELETE - hard, nao soft

`exports.config` ja copia a composicao inteira **por valor** no momento
do snapshot (Decisao 6) - o export nunca releem o documento vivo depois
de criado. O schema atual de `exports` nao tem uma FK real para
`map_documents`; quando `document_id` aparecer, e um valor dentro do
JSONB do snapshot, nao uma constraint de banco. Logo, apagar um
`MapDocument` nunca invalida um export ja produzido. **DELETE e hard**
(`DELETE FROM map_documents WHERE id = ...`), sem coluna `deleted_at` nem
filtro extra em toda leitura - o caso de uso que justificaria soft delete
(auditoria de documentos apagados) nao existe hoje e nao deve ser
antecipado.

## Fronteira de renderizacao (reafirmada, com correcao tecnica)

Renderiza o **cliente**; o backend congela o snapshot e arquiva o artefato.
Diretriz tecnica para o frontend (nota 32, corrigindo a inspiracao da
nota 31): instancia MapLibre dedicada a exportacao, dimensionada para a
resolucao final, com `preserveDrawingBuffer: true`, captura via
`map.getCanvas().toDataURL()` apos `idle`, e composicao de legenda/escala/
atribuicao em canvas 2D separado. **Nao usar** dom-to-image/html2canvas
(serializacao de DOM nao garante o conteudo WebGL - e o mecanismo interno
do Kepler.gl, e nao deve ser copiado).

## Influencias e divergencias do Kepler.gl

- **Herdado**: separacao dados x configuracao visual (`dataId` -> nossos
  ids estaveis); vocabulario de escalas; nulos transparentes por default;
  resolucoes 1x/2x; catalogo de basemaps CARTO; instancia dedicada de
  render para exportacao.
- **Divergente**: schema proprio URBDATA (nunca o JSON interno do Kepler
  como contrato - acoplaria banco e API ao renderizador); validacao
  autoritativa no backend (Kepler valida no cliente); persistencia
  versionada por `ProjectVersion` com concorrencia (Kepler salva arquivo
  unico); sem Redux/deck.gl/editor Kepler no frontend principal; snapshot
  imutavel server-side (Kepler nao tem esse conceito).

## Exemplos (aceite DOC-BE-001)

Validos - poligono categorico por indicador e linha em estilo unico:

```json
{"layer_id": "<uuid-lotes>", "visible": true,
 "representation": {"source": "indicator",
   "indicator_code": "lots.frontage_length", "field": null,
   "mode": "sequential", "scale": "quantile", "classes": 5,
   "stops": null, "null_behavior": "transparent"},
 "style": {"fill": {"color": null,
     "palette": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
     "opacity": 0.8},
   "stroke": {"color": "#1a1a1a", "width_px": 0.5,
     "style": "solid", "opacity": 1.0},
   "null_color": null, "labels": null},
 "interaction": {"tooltip_fields": ["quadra_id"], "selectable": true,
   "filters": null}}
```

```json
{"layer_id": "<uuid-eixo-viario>", "visible": true,
 "representation": {"source": "none", "field": null,
   "indicator_code": null, "mode": "single", "scale": null,
   "classes": null, "stops": null, "null_behavior": "transparent"},
 "style": {"fill": {"color": null, "palette": null, "opacity": 0},
   "stroke": {"color": "#d95f02", "width_px": 2.0,
     "style": "dashed", "opacity": 1.0},
   "null_color": null, "labels": null},
 "interaction": {"tooltip_fields": [], "selectable": true,
   "filters": null}}
```

Invalidos (devem ser rejeitados com caminho do campo):

- `mode: "categorical"` com `scale: "linear"` (escala incompativel);
- `mode: "sequential"` sobre campo de texto (tipo incompativel);
- `stops: [10, 5, 20]` (desordenados) ou 13+ stops;
- `palette` com tamanho diferente de `classes`;
- `layer_id` de outra `ProjectVersion`;
- `basemap_id: "osm-custom"` (fora do catalogo);
- 33 classes categoricas (acima do bloqueio).

## Fora da v1

Labels com editor, simbologia de pontos alem do default, filtros com UI,
mapas-base com credencial (exigira proxy), PDF/SVG, render server-side,
presets de prancha A4/A3, exportacao para Kepler.gl (pos-MVP, nota 31).
Do `feature_panel` (Decisao 7): ancoragem alternativa (painel fixado
durante a navegacao), inclusao do painel na exportacao cartografica,
blocos alem de texto/tabela, formatacao de campo alem de
decimais/prefixo/sufixo - pendencias explicitas da nota 33.
