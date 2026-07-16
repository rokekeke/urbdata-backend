# ADR 001 - Estrategia de CRS metrico

- Status: aceito para a fundacao; selecao automatica pendente
- Data: 2026-07-16
- Aprovador de dominio: pendente

## Contexto e decisao

Dados podem entrar em EPSG:4326, mas area, distancia, comprimento e buffer exigem CRS projetado metrico. O contexto da analise selecionara um SIRGAS 2000 / UTM compativel via base do PyProj, registrara o EPSG e reprojetara cada camada no maximo uma vez por run. Extensoes fora do Brasil, sem CRS, sem perimetro ou incompatíveis com UTM falharao explicitamente.

## Alternativas e consequencias

Web Mercator e calculo em graus foram rejeitados por distorcao. Escolher EPSG apenas pela longitude tambem foi rejeitado como regra unica. A estrategia aumenta a validacao inicial, mas torna unidades e auditoria explicitas.
