# ADR 003 - Versionamento de formulas

- Status: aceito conceitualmente; migration pendente
- Data: 2026-07-16
- Aprovador de dominio: pendente

Cada resultado carrega versao semantica da formula. Correcao sem mudanca conceitual incrementa patch; parametro opcional compativel incrementa minor; mudanca de formula ou interpretacao incrementa major. A coluna `formula_version` sera nao nula quando o modelo existente for confirmado.
