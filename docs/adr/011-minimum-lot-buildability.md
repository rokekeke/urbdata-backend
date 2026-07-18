# ADR 011 - Potencial construtivo minimo por lote

- Status: aceito para a primeira fatia do Epico 10
- Data: 2026-07-17
- Aprovador de dominio: responsavel urbanista

## Correcao (17/07/2026)

A primeira versao desta ADR descrevia `reference_area_m2` como mera
conferencia que "nunca substitui a geometria importada". Isso contrariava um
invariante ja confirmado do projeto (ver `resolve_feature_area` em
`app/domain/geospatial/geometry.py` e Obsidian nota 11): quando
`reference_area_m2` esta presente e valido, ele - nao a geometria - e o valor
usado no calculo. A implementacao original desta fatia alterou esse helper
compartilhado para sempre usar a geometria, o que tambem mudou silenciosamente
os resultados ja publicados de territorio por categoria, uso do solo e areas
verdes. Revertido no mesmo dia; o texto abaixo reflete a regra correta e
permanente.

## Decisao

O primeiro incremento de densidade usa somente a area resolvida do lote (regra
do projeto: `reference_area_m2` tem precedencia quando presente, geometria e o
fallback e a conferencia - nunca o contrario) e seu coeficiente de
aproveitamento maximo:

```text
area_computavel_maxima_m2 = area_resolvida_lote_m2 * ca_max
```

Entram apenas feicoes da camada `territorio` com `macroarea = lote`. A area e
resolvida por `resolve_feature_area` (mesma funcao usada por territorio, uso
do solo e areas verdes) no CRS metrico selecionado para a execucao:
`reference_area_m2`, quando presente e valido, e o valor usado; a geometria e
sempre calculada tambem, e uma divergencia relativa igual ou superior a 5%
gera aviso.

`ca_max = 0` e um valor valido. CA ausente, negativo ou invalido permanece sem
valor e o lote nao entra no potencial calculado. O resultado informa cobertura
ponderada pela area geometrica, evitando apresentar uma amostra parcial como se
fosse o empreendimento completo.

## Indicadores desta fatia

- `density.max_computable_area`: soma de `area_lote_m2 * ca_max`;
- `density.lot_count_with_ca`: quantidade de lotes com CA valido, incluindo zero;
- `density.ca_coverage`: area de lotes com CA / area de todos os lotes validos.

## Fora desta fatia

O estudo de massa recebido por imagem esta em desenvolvimento. Nao sao entradas
obrigatorias agora: lajes, pavimentos, area privativa/vendavel, distribuicao por
uso, unidades, vagas ou populacao. Essas decisoes estao registradas na nota 17 do
Obsidian e serao incorporadas por precedencia sem alterar a formula minima acima.
