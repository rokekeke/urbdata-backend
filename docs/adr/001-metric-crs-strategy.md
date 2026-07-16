# ADR 001 - Estrategia de CRS metrico

- Status: aceito para a fundacao; selecao automatica pendente
- Data: 2026-07-16
- Aprovador de dominio: pendente

## Contexto e decisao

Dados podem entrar em EPSG:4326, mas area, distancia, comprimento e buffer exigem CRS projetado metrico. O padrao de dominio aprovado e `WGS 84 / UTM zone 22S`, representado de forma canonica por `EPSG:32722` e equivalente a WKT `WGS_1984_UTM_Zone_22S`. O seletor usa esse CRS quando toda a extensao do projeto esta contida no fuso 22S. Para outros locais, consulta a base do PyProj por outro WGS 84 / UTM e somente o aceita se um unico fuso contiver toda a extensao.

O EPSG selecionado deve ser registrado no run e cada camada deve ser reprojetada no maximo uma vez por execucao. Projeto sem CRS, vazio, com coordenadas invalidas ou atravessando limite de fuso falha explicitamente. Nenhuma geometria persistida e alterada.

## Alternativas e consequencias

Web Mercator, calculo em graus e aplicacao cega do fuso 22S foram rejeitados por distorcao. Escolher EPSG apenas por aritmetica de longitude tambem foi rejeitado; a selecao usa areas de uso da base do PyProj. A estrategia aumenta a validacao inicial, mas torna unidades e auditoria explicitas.
