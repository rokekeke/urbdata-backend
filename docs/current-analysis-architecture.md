# Arquitetura atual de analise

Data do inventario: 2026-07-16.

O repositorio estava vazio no inicio do inventario. Nao havia rotas 501, modelos SQLAlchemy, schemas Pydantic, services, repositories, migrations, configuracao PostGIS ou testes a mapear. Assim, o fluxo `projeto -> versao -> camada -> feicao` ainda depende da confirmacao do modelo relacional e do contrato da API.

A base criada estabelece somente fronteiras importaveis e invariantes geoespaciais. Nenhuma tabela ou endpoint de analise foi inventado. Os pontos de extensao sao os casos de uso em `app/application/analysis`, os adaptadores em `app/infrastructure/database/repositories` e o registro de indicadores em `app/domain/analysis`.
