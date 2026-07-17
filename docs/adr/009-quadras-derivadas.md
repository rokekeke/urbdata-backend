# ADR 009 - Quadras derivadas por agrupamento de lotes

- Status: parcial (BT-050/051/052 aceitos; BT-053/054 adiados)
- Data: 2026-07-17
- Aprovador de dominio: pendente (limiar de face longa, BT-053/054)

## Contexto e decisao

O arquivo de exportacao real confirma que quadra nao e uma macroarea propria
nem uma geometria desenhada separadamente: cada feicao de Lote carrega um
campo (`QUADRA` no template atual) referenciando a qual quadra ela pertence.
A geometria da quadra e obtida dissolvendo os lotes que compartilham esse
valor - nao ha necessidade de pedir a equipe de exportacao para desenhar
quadras a parte.

Decisao:

- `Feature.quadra_id` (string, indexado, nullable) - ao contrario de
  `macroarea`, nao e uma taxonomia fechada com alias: qualquer valor serve
  como chave de agrupamento, populado pelo mesmo mecanismo de mapeamento de
  atributos ja existente.
- `app/domain/geospatial/geometry.py::dissolve_by_group` - agrupa um
  `GeoDataFrame` por uma coluna e aplica `dissolve()` (ja existente) em cada
  grupo. Linhas com a coluna de agrupamento nula sao excluidas (pandas
  `groupby` descarta chaves nulas por padrao) - um lote sem `quadra_id` nao
  entra em nenhuma quadra, o que e o comportamento correto (nao existe uma
  quadra "nula" coerente da mesma forma que existe uma macroarea "Nulo").
- BT-050 (estatisticas: area, perimetro, contagem de lotes), BT-051
  (compacidade, mesmo indice de Polsby-Popper ja usado em territorio) e
  BT-052 (dimensoes do retangulo minimo rotacionado, via
  `shapely.minimum_rotated_rectangle`) sao implementados agora - geometria
  computacional padrao, sem ambiguidade de dominio.
- Uma camada derivada `LayerType.QUADRAS` (ja existia no enum, antes pensada
  para upload direto) passa a tambem poder ser gerada pelo sistema: um novo
  endpoint (`POST /projects/{id}/layers/quadras/derive`) dissolve os lotes
  por `quadra_id` e persiste o resultado como uma camada normal - o
  frontend usa os endpoints de camada que ja existem (`GET /layers`,
  `GET /layers/{id}/geojson`) para exibir e ocultar, sem endpoint novo de
  leitura. Geracao e explicita (o usuario aciona), nunca automatica, e cada
  chamada **substitui** a camada de quadras derivada anterior da mesma
  versao (apaga e recria) em vez de acumular - evita o `DuplicateLayerError`
  do BT-011 e evita que a camada fique desatualizada em relacao aos lotes.

## Adiado: BT-053/054 (deteccao de face longa)

O backlog registra o limiar como "face > 120m". A nota 07 do Obsidian
(benchmarks de dominio) ja registra Jane Jacobs recomendando quarteiroes
**curtos** de 120-240m como pre-condicao de vitalidade urbana - ou seja, a
propria literatura citada trata esse intervalo como bom, nao como problema.
Implementar ">120m = alerta" contradiz a referencia que o proprio backlog
usa em outro lugar. Isso nao foi resolvido nesta ADR; fica registrado como
pendente de confirmacao explicita do limiar e da semantica antes de
codificar (regra 6 do contrato de trabalho deste projeto).

## Fora de escopo

- Validacao espacial de que um lote realmente esta contido na quadra que
  seu `quadra_id` referencia (nenhuma checagem geometrica lote-quadra e
  feita aqui - so agrupamento por atributo). Fica para o Epico 8 se for
  necessario.
- Regeneracao automatica da camada de quadras ao editar um lote.

## Alternativas e consequencias

Pedir que a equipe de exportacao desenhe quadras como poligonos separados
foi descartado pelo mesmo motivo que motivou a decisao de macroarea: nao
bate com o fluxo de desenho que ja usam (geometria unica subdividida).
Persistir a camada derivada (em vez de so calcular em memoria a cada
analise) foi uma troca deliberada: o usuario pediu explicitamente uma
camada que possa ser ocultada no mapa, o que exige que ela exista como
feicao real, consultavel pelos endpoints de camada ja existentes.
