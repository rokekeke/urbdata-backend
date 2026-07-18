# ADR 012 - Testada de lote e eficiencia de parcelamento

- Status: aceito para a primeira fatia do Epico 8
- Data: 2026-07-17
- Aprovador de dominio: responsavel do projeto

## Contexto

A relacao lote-quadra em si nao precisa de nenhum indicador novo: quadras sao
derivadas dissolvendo lotes que compartilham `quadra_id` (ADR 009), entao a
relacao existe por construcao. O que faltava do Epico 8 eram dois calculos que
dependiam de decisoes de dominio nunca fechadas: testada e eficiencia de
parcelamento.

## Decisao - testada (`lots.frontage_length`)

Entre usar o poligono de footprint do sistema viario (ja carregado na camada
`territorio`, ADR 008) ou o eixo/centerline do grafo viario (ADR 010), a
opcao mais simples e funcional foi escolhida: **poligono de footprint**. Nao
depende do grafo viario (`app/domain/geospatial/networks.py`), evita
qualquer problema de correspondencia topologica entre o limite do lote e uma
aresta do grafo, e reaproveita uma camada que ja esta carregada sempre que
`territorio` participa da execucao.

```text
testada_m = comprimento do limite do lote dentro do buffer de tolerancia
            em torno do poligono de sistema viario dissolvido
```

Tolerancia: 3m (`FRONTAGE_TOLERANCE_M`) - o unico valor ja associado a
testada nas notas de dominio do projeto (Obsidian nota 07), reaproveitado em
vez de propor um novo. Um lote sem nenhum trecho de sistema viario proximo
recebe `0.0` - valor legitimo (lote interno), nao aviso. Um projeto sem
nenhuma feicao de `sistema_viario` gera aviso `no_road_footprint_for_frontage`
e zera a testada de todos os lotes, em vez de falhar a execucao inteira.

## Decisao - eficiencia de parcelamento (`lots.parceling_efficiency`)

```text
eficiencia[quadra_id] = area_bruta_dos_lotes_da_quadra / area_da_quadra
```

"Area util" = area bruta de **todos** os lotes da quadra, sem filtro por
`parcelavel` ou por uso do solo - confirmado 2026-07-17. Cada lote usa
`resolve_feature_area` (mesma funcao e mesma regra de precedencia de
`reference_area_m2` usada por territorio, uso do solo, areas verdes e
densidade - ver a regra invariante no docstring de
`app/domain/geospatial/geometry.py::resolve_feature_area`); a area da quadra
e sempre geometrica (quadras nao tem `reference_area_m2` proprio, sao
geometria derivada). Reaproveita o mesmo agrupamento por `quadra_id` que o
tema `quadras` ja calcula (`quadras_from_context`, promovida de helper
privado do modulo `quadras.py` para uso compartilhado) em vez de dissolver os
lotes uma segunda vez.

## Fora desta fatia

- `Feature.parent_lote_feature_id` e `RelationMethod.SPATIAL` permanecem sem
  uso - mantidos no schema para uma futura relacao espacial lote-edificacao
  ou lote-equipamento, fora do escopo desta ADR.
- Estatisticas de distribuicao de area de lote (min/max/media/mediana) nao
  foram pedidas nem implementadas.
- Hierarquia viaria e larguras (ja fora de escopo da ADR 010) continuam sem
  impacto aqui - a testada usa o footprint bruto do sistema viario, nao a
  classificacao por hierarquia.
