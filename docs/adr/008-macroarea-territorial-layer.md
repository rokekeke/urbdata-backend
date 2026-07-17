# ADR 008 - Camada territorial unica classificada por macroarea

- Status: aceito
- Data: 2026-07-17
- Aprovador de dominio: pendente (nomes de campo do export continuam com a
  equipe de exportacao; a arquitetura em si e decisao de engenharia)

## Contexto e decisao

BT-043/044 (area/percentual por categoria territorial), o modulo de uso do
solo (BT-060-066) e o modulo de areas verdes (BT-120/121) tinham a mesma
logica de calculo pronta e testada, mas nenhum estava conectado ao motor:
faltava uma forma de carregar "todas as feicoes classificadas como Lote" (ou
AVL, ou Sistema viario) a partir dos dados reais. A evidencia de um arquivo
de exportacao real (Obsidian nota 11) mostrou que essas categorias nao
chegam em camadas separadas - vem todas juntas num unico GeoJSON, onde a
geometria da matricula foi subdividida (nao redesenhada como poligonos
independentes) e cada pedaco carrega sua categoria macro.

A decisao: um novo `LayerType.TERRITORIO`, upload unico contendo todas as
subdivisoes (Lote, Sistema viario, AVL, APP, ACI, Nulo), geometria
`Polygon`/`MultiPolygon`. Tres campos novos em `Feature`, todos opcionais e
populados pelo mecanismo de mapeamento de atributos que ja existe
(`PATCH /layers/{id}/attributes`), exatamente como `land_use` ja funciona
hoje - nenhum nome de campo do export precisa ser fixo em codigo:

- `macroarea` (string, indexado): valores normalizados para o enum
  `Macroarea` (`lote`, `sistema_viario`, `avl`, `app`, `aci`, `nulo`).
- `parcelavel` (booleano): confirmado no arquivo real como o campo
  `P_Area de Projeto` (0/1) - nao e derivado de `macroarea`, e mapeado
  direto (ADR revisando a hipotese anterior, descartada em conversa).
- `reference_area_m2` (numerico): area calculada fora da plataforma,
  usada para conferencia contra a area geometrica (limiar de divergencia
  ja definido em 5%, Obsidian nota 11) - a logica de comparacao em si
  ainda nao foi implementada, fica para quando os indicadores forem
  conectados.

`FeatureRepository.load_layer` passa a incluir `macroarea`, `parcelavel`,
`land_use` e `reference_area_m2` como colunas do `GeoDataFrame` retornado,
para qualquer camada (nao so `territorio`) - colunas ficam `None` para
camadas que nao as usam. Isso permite que um calculador filtre
`gdf[gdf["macroarea"] == "lote"]` sem precisar de uma camada dedicada.

## Escopo desta decisao

Esta ADR cobre a arquitetura de dados (tipo de camada, colunas, mapeamento,
carregamento). **Nao** inclui, propositalmente:

- Ligar `territorial.area_by_category` (BT-043/044 - a formula em si ainda
  nao foi escrita), uso do solo ou areas verdes ao orquestrador/catalogo.
- A logica de comparacao geometria-vs-`reference_area_m2` com aviso de
  divergencia.
- Agrupamento de lotes por quadra (Epico 5) - a coluna `macroarea` resolve
  "que tipo de subdivisao e essa feicao", nao "a qual quadra ela pertence";
  isso seria um campo adicional (`quadra_id`) fora do escopo desta ADR.

Cada um fica como proximo passo explicito, nao implicito nesta mudanca.

## Alternativas e consequencias

Manter tipos de camada separados por categoria (como `LayerType.LOTES`,
`LayerType.AREAS_VERDES` ja existentes) foi descartado: exigiria que a
equipe de exportacao dividisse o arquivo em varios uploads, contrariando o
fluxo de desenho que ja usam (uma geometria de referencia, subdividida).
Promover `macroarea`/`parcelavel`/`reference_area_m2` a colunas proprias
(em vez de deixar só em `mapped_properties` JSONB) segue o mesmo precedente
de `land_use`: todas sao consultadas diretamente por calculadores, entao
justificam indice e tipo proprio. O custo e uma migration aditiva
(`0003`), de baixo risco - todas as colunas sao opcionais.
