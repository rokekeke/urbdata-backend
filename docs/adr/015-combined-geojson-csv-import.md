# ADR 015 - Importacao combinada de geometria GeoJSON e atributos CSV

- Status: aceito (checkpoint 20/07/2026, nota Obsidian 53; subetapas na
  nota Obsidian 54)
- Data: 2026-07-21
- Contexto: proposta da equipe de exportacao (nota 23), avaliacao de uma
  amostra real (`PROJETO_R01_GEOMETRIA.json` +
  `DATA_EXPORT_PROJETO_01.csv`, nota 53), marcada pelo usuario como
  essencial para o MVP.

## Problema

A equipe de exportacao entrega, em alguns casos, a geometria e a tabela de
atributos de negocio em dois arquivos separados (GeoJSON + CSV) em vez de
um GeoJSON unico com tudo embutido em `properties`. O upload de camada
precisava aceitar esse caminho sem quebrar o comportamento existente
(GeoJSON unico continua sendo o caso mais comum) e sem relaxar nenhuma das
garantias de integridade ja estabelecidas (rule 6 do projeto: nunca
adivinhar um vinculo ambiguo).

## Decisao 1 - Rastreabilidade em colunas aditivas, nao uma tabela nova

Ao contrario da primeira alternativa considerada (tabela dedicada de
"fontes de camada"), a rastreabilidade da importacao vive em colunas
aditivas de `project_layers` - relacao 1:1 com a camada, sem necessidade
de outra entidade:

```text
project_layers
├── import_profile         ENUM('combined','split') NOT NULL DEFAULT 'combined'
├── attributes_filename    VARCHAR NULL
├── attributes_join_key    VARCHAR NULL
├── geometry_join_key      VARCHAR NULL   (NULL = feature.id foi usado)
└── join_summary           JSONB NULL
```

`join_summary` e calculado uma unica vez, na importacao, e nunca
recalculado depois:

```json
{
  "geometry_count": 102,
  "attribute_count": 102,
  "matched": 102,
  "missing_geometry_keys": [],
  "missing_attribute_keys": [],
  "duplicate_geometry_keys": [],
  "duplicate_attribute_keys": []
}
```

Migration `0010_add_layer_import_profile.py` (aditiva, reversivel -
upgrade/downgrade verificado em banco descartavel isolado, nunca no banco
compartilhado). Exposto em `LayerOut` - rastreabilidade que ninguem
consegue ver pela API nao cumpre a funcao de rastreabilidade.

## Decisao 2 - `import_profile` como conceito formal, nao um campo opcional solto

**Ao contrario da recomendacao inicial** (deixar o CSV sempre opcional,
sem marcador explicito), o usuario optou por formalizar um enum
`import_profile` (`combined` | `split`) desde o inicio:

- `combined` (default) e exatamente o comportamento anterior - GeoJSON com
  atributos embutidos em `properties`. Retrocompativel: nenhum upload
  existente muda de comportamento.
- `split` exige os tres campos abaixo e ativa a juncao.

```text
POST /v1/projects/{project_id}/layers

layer_type            (existente)
file                   GeoJSON, obrigatorio (geometria; combined = geometria+atributos)
import_profile         "combined" (padrao) | "split"
attributes_file        CSV, obrigatorio quando import_profile=split;
                       rejeitado se enviado com combined
attributes_join_key    coluna do CSV usada como chave, obrigatorio quando split
geometry_join_key      nome de uma property do GeoJSON a usar como chave;
                       ausente/null = usa feature.id (padrao)
```

Validado antes de qualquer parsing (`invalid_import_profile`, 400).

## Decisao 3 - Unidade de `Area`: apenas `m2`, nunca conversao automatica

A amostra real trouxe `Area` como texto com sufixo (`"1338.63 m2"`, o `2`
sobrescrito). Decisao do checkpoint: aceitar numero puro ou exatamente
esse sufixo; qualquer outra unidade ou texto nao reconhecido vira `null`
**com aviso** (nunca convertido automaticamente - regra invariante 2/6 do
projeto). `_coerce_area_m2` (`feature_repository.py`) implementa isso;
`apply_attribute_mapping` agora devolve os avisos coletados, expostos em
`PATCH /layers/{id}/attributes` (`LayerAttributeMappingOut.warnings`).

## Decisao 4 - Chave geometrica configuravel, nao fixa em `feature.id`

**Ao contrario da recomendacao inicial** (travar em `feature.id`), o
usuario optou por tornar a chave do lado geometria configuravel:
`geometry_join_key` aceita o nome de uma `properties.X` do GeoJSON; nulo
mantem o padrao (`feature.id`). Motivo: uma chave de longo prazo estavel
(`URBDATA_ID`) ainda nao foi adotada pela equipe de exportacao - o
contrato ja fica generico o suficiente para nao exigir mudanca quando
isso acontecer.

## Regras da juncao (travadas com a equipe de exportacao, nao reabrir)

- nunca relacionar por posicao/ordem das linhas - somente por igualdade de
  chave, e somente igualdade exata (sem aproximacao, busca textual ou
  correcao de caixa);
- chave vazia em qualquer lado bloqueia a operacao inteira;
- chave duplicada em qualquer lado bloqueia a operacao inteira;
- correspondencia 1:1 exigida no primeiro recorte - qualquer ausencia de
  par (dos dois lados) bloqueia;
- toda violacao encontrada e coletada antes de rejeitar (nao fail-fast -
  mesma filosofia da validacao contextual do `MapDocument`, ADR 014
  Decisao 3), listando as chaves problematicas na resposta;
- os dois arquivos originais sao preservados sem alteracao
  (`LocalStorage`), inclusive quando o upload e rejeitado por qualquer
  outra causa - nada e persistido nem arquivado nesse caso;
- codificacao/delimitador do CSV nao reconhecidos rejeitam com mensagem
  orientativa (amostra confirmada: UTF-8 com/sem BOM, delimitador `;`).

## Implementado (21/07/2026)

- **b1** - migration 0010 + `ImportProfile` (`app/infrastructure/database/models/layer.py`).
- **b2** - `app/domain/csv_import.py::parse_csv` (dominio puro): decodifica
  via `utf-8-sig` (cobre BOM opcional num unico passo), delimitador
  detectado por contagem estrita entre `,`/`;`/tab, limites de
  20.000 linhas/200 colunas.
- **b3** - `app/domain/layer_join.py::join_geometry_and_attributes` +
  `resolve_geometry_join_keys` (dominio puro): aplica todas as regras
  acima, devolve pares casados por indice de feicao (nunca por posicao)
  ou `AttributeJoinError` com o contexto completo.
- **b4** - `attribute_suggestions.py`: aliases confirmados
  `TIPO DE MACROAREA`->`macroarea` (alem de `Comments`, ja existente),
  `Uso do solo`->`land_use`, `07.COEFICIENTE DE APROVEITAMENTO`->`ca_max`.
- **b5** - `_coerce_area_m2` (Decisao 3 acima).
- **b6** - `POST /layers` estendido (`app/api/v1/routes/layers.py`):
  validacao do perfil, parse+juncao, fusao dos atributos do CSV em
  `source_properties` (CSV vence em colisao de chave), persistencia dos
  campos de rastreabilidade, preservacao dos dois arquivos - tudo antes de
  qualquer escrita (nao ha "rollback" porque nao ha nada para desfazer:
  toda validacao acontece antes do primeiro `LocalStorage().save`/commit).
- **b7** - cobertura de teste completa: uma regra de bloqueio por teste
  HTTP (chave vazia/duplicada em cada lado, ausencia de par, CSV
  malformado, combinacao invalida de perfil), upload com `geometry_join_key`
  nomeado e multiplas feicoes, confirmacao de que uma juncao rejeitada nao
  deixa camada nenhuma, e um teste fim-a-fim com a amostra real completa
  (102 pares, `tests/PROJETO_R01_GEOMETRIA.json` +
  `tests/DATA_EXPORT_PROJETO_01.csv` - fixtures permanentes).

## Comportamento observado, nao um bug

`GET /layers/{id}/geojson` sempre devolve o UUID interno da `Feature` como
`id` (contrato ja publicado, mesmo raciocinio do join indicador-feicao da
ADR 014 Decisao 1) - nunca o `feature.id`/`external_id` original do
GeoJSON enviado, mesmo quando `geometry_join_key` aponta para outra
property. Clientes que precisam do identificador original devem ler a
property correspondente, nao o campo `id` da resposta.

## Fora do escopo desta ADR

- chave de longo prazo `URBDATA_ID` - o contrato ja e generico o
  suficiente (Decisao 4) para nao exigir mudanca quando a equipe de
  exportacao adotar;
- qual `import_profile` e o padrao por tipo de camada (ex.: `territorio`
  sempre `split` no futuro) - decisao de produto, nao tecnica;
- frontend (formulario de dois arquivos, resumo de validacao, operacao
  multipart tipada) - subetapas `f1`-`f6` da nota Obsidian 54, comecam
  depois deste contrato publicado.
