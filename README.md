# URBDATA Backend

Base inicial do monolito modular para o motor de indicadores urbanos.

## Inicio rapido

```bash
python -m venv .venv
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

O primeiro marco funcional sera a fatia vertical `territorial.total_area`: carregar o perimetro, selecionar um CRS metrico, calcular a area, persistir o resultado e consulta-lo pela API.

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

A API fica em `http://localhost:8000` e o health check em `GET /health`. O schema ainda nao possui migrations de dominio: elas serao criadas depois da confirmacao do modelo relacional e do contrato da API.
