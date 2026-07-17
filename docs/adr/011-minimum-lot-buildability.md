# ADR 011 - Potencial construtivo minimo por lote

- Status: aceito para a primeira fatia do Epico 10
- Data: 2026-07-17
- Aprovador de dominio: responsavel urbanista

## Decisao

O primeiro incremento de densidade usa somente a geometria do lote e seu
coeficiente de aproveitamento maximo:

```text
area_computavel_maxima_m2 = area_geometrica_lote_m2 * ca_max
```

Entram apenas feicoes da camada `territorio` com `macroarea = lote`. A area e
calculada no CRS metrico selecionado para a execucao. `reference_area_m2` e
somente uma conferencia: divergencia igual ou superior a 5% gera aviso, mas
nunca substitui a geometria importada.

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
