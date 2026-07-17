# URBDATA Backend

Monolito modular para upload de dados geoespaciais e calculo rastreavel de
indicadores territoriais, de uso do solo, areas verdes, quadras e rede viaria.

## Inicio rapido

```bash
python -m venv .venv
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

O motor seleciona um CRS metrico por projeto, executa os temas pelo catalogo de
indicadores e registra formula, parametros, camadas, feicoes contribuintes e avisos.

## Rede viaria

- Envie os eixos como `sistema_viario` (`LineString`/`MultiLineString`).
- Mapeie um atributo de origem para `road_status`; valores aceitos sao
  `existente` e `proposta` (aliases comuns sao normalizados).
- Opcionalmente, envie pontos `desconexoes_viarias` nos cruzamentos em planta
  que nao sao conexoes reais, seguindo a semantica *unlink* da sintaxe espacial.
- Execute o tema `road_network` em `POST /v1/projects/{id}/analyze`.

O snapping e o noding ocorrem somente durante a analise. As geometrias enviadas
e persistidas nunca sao alteradas. Consulte
[ADR 010](docs/adr/010-road-network-topology.md).

## Potencial construtivo por lote

Mapeie o coeficiente de aproveitamento maximo da camada `territorio` para o
campo interno `ca_max` e execute o tema `density`. A primeira fatia calcula
somente `area geometrica do lote x ca_max`, contagem de lotes atendidos e
cobertura dos dados. Informacoes de edificio e populacao nao sao exigidas.

Consulte [ADR 011](docs/adr/011-minimum-lot-buildability.md).

## Regras invariantes

- Nunca calcular area, distancia, comprimento ou buffer em EPSG:4326.
- Usar EPSG:32722 como CRS metrico preferencial apenas quando o projeto estiver integralmente no fuso 22S; fora dele, selecionar e registrar o UTM adequado.
- Nunca corrigir ou sobrescrever silenciosamente geometrias persistidas.
- Preservar valores brutos; arredondar somente na apresentacao.
- Manter formulas urbanisticas fora de routers, repositorios e modelos ORM.
- Versionar formulas e registrar parametros, CRS, camadas, feicoes e avisos.
- Justificar e documentar qualquer mudanca no contrato da API.

Consulte [docs/development-start.md](docs/development-start.md) para a analise inicial e a ordem de implementacao.

## Ambiente local com PostGIS

```bash
docker compose up --build
```

A API fica em `http://localhost:8000` e o health check em `GET /health`. O Alembic
aplica o schema e suas evolucoes ate a revisao atual.
