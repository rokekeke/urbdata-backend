# ADR 007 - Selecao interativa entre camadas

- Status: aceito
- Data: 2026-07-16
- Aprovador de dominio: pendente

## Contexto e decisao

A equipe pediu para correlacionar a selecao de geometrias com filtros entre
camadas (ex.: selecionar quadras e destacar os lotes dentro delas), com
resposta interativa (sub-segundo) ao clicar ou desenhar no mapa. Isso e uma
operacao de consulta, distinta do motor de indicadores (`/analyze`), que roda
em lote e persiste um `analysis_run`.

Foi criado um endpoint proprio, `POST /v1/projects/{id}/selection`, que:

- recebe uma camada-alvo (`target_layer_type`);
- opcionalmente, uma relacao espacial (`intersects`, `contains`, `within`,
  `dwithin`) contra um conjunto de `feature_id`s de origem (de qualquer
  camada do mesmo projeto e versao);
- opcionalmente, filtros de atributo por igualdade (`land_use` ou qualquer
  chave de `mapped_properties`);
- devolve somente os `feature_id`s correspondentes - nunca geometria, que o
  frontend ja tem carregada via `GET /layers/{id}/geojson`.

A consulta e feita diretamente no PostGIS (nao pelo GeoPandas do motor de
analise), usando os operadores `ST_Intersects`, `ST_Contains`, `ST_Within` e
`ST_DWithin` (este ultimo com `cast(..., Geography)` para distancia em metros
sem exigir selecao de CRS metrico por requisicao) sobre o indice espacial ja
existente na coluna `geom`. Uma camada-alvo ainda nao enviada para o projeto
retorna lista vazia, nao erro - "sem correspondencia" e um estado valido de
filtro, nao uma falha.

Por ora, o resultado de uma selecao/filtro nao e persistido: e estado
efemero de sessao no frontend.

## Alternativas e consequencias

Reaproveitar o `GeospatialContext`/GeoPandas do motor de analise foi
rejeitado: carregar a camada inteira para memoria a cada clique nao atende a
exigencia de latencia interativa, especialmente em projetos grandes. A
consulta direta no PostGIS abre uma segunda via de acesso a dados (nao passa
por `LoadedFeatureLayer`), mas e o padrao correto para consulta interativa e
reaproveita o mesmo indice espacial que o Epico 8 (associacao lote-quadra)
tambem vai usar. Persistencia de selecoes nomeadas foi adiada ate existir
demanda concreta de reuso ou exportacao em relatorio.
