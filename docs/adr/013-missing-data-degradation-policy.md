# ADR 013 - Politica de degradacao para dados ausentes

- Status: aceito
- Data: 2026-07-18
- Contexto: teste de ponta a ponta com arquivo real de exportacao (ver nota
  Obsidian 23) revelou tratamento inconsistente entre temas quando o dado
  qualificador esta ausente.

## Problema

Com o mesmo arquivo de entrada (nenhum lote com uso do solo classificado,
nenhum lote com `quadra_id`, nenhum lote com `ca_max`):

- `quadras.*` completava com valores vazios e aviso `lot_without_quadra` (info);
- `density.*` completava com zeros e aviso `lot_ca_missing` (info);
- `land_use.*` **falhava o run inteiro** com `indicator_calculation_failed`
  (erro disparado pelo indice de Shannon sem area classificada);
- `territorial.percent_by_category` falharia da mesma forma com zero area
  parcelavel.

O mesmo tipo de situacao (universo qualificador vazio) produzia dois
comportamentos opostos, e uma unica formula degenerada derrubava os demais
indicadores do tema.

## Decisao

Distinguir duas classes de situacao:

1. **Universo qualificador vazio** (nenhum lote classificado, nenhum lote com
   quadra, nenhuma area parcelavel, nenhum CA valido): o indicador **completa**
   com valor vazio/`None`/zero conforme seu tipo, acompanhado de aviso
   estruturado. O run nunca falha por isso. Avisos por feicao (ex.:
   `lot_without_land_use`, `lot_without_quadra`, `lot_ca_missing`) usam
   severidade `info`; a ausencia total de um universo inteiro do projeto
   (ex.: `no_parcelavel_area`) usa severidade `warning`.

2. **Impossibilidade estrutural** (camada obrigatoria ausente, geometria
   invalida, falha de selecao de CRS, area de projeto nao positiva em
   `green_areas.percent_of_project`): erro tipado, run marcado `failed`.
   Dado estrutural quebrado nao deve produzir resultado silenciosamente
   plausivel.

## Aplicacao nesta rodada

- `land_use.percent_by_category`, `land_use.predominant_use`,
  `land_use.diversity_shannon`: deixam de lancar erro com zero area
  classificada; retornam `{}`/`None` com aviso `lot_without_land_use`
  (por feicao, info). `formula_version` incrementada para `1.0.1`
  (correcao sem mudanca conceitual, ADR 003).
- `land_use.area_by_category`: passa a emitir o mesmo aviso por feicao
  (valor calculado inalterado - `formula_version` mantida).
- `territorial.percent_by_category`: retorna `{}` com aviso
  `no_parcelavel_area` (warning) em vez de erro; `1.0.1`.

## Complemento de API (mesma rodada)

As respostas de erro de `POST /analyze` e `POST /layers/quadras/derive`
passam a incluir `detail.context` (ex.: `{"layer_type": "perimetro"}` em
`required_layer_missing`) - o dicionario ja existia em `AnalysisError.context`
e era descartado na borda HTTP, deixando o cliente sem saber qual camada
faltava. Contrato aditivo: nenhum campo existente mudou.
