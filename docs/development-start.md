# Analise inicial e preparacao do desenvolvimento

## Diagnostico breve

O diretorio recebido estava vazio. Portanto, ainda nao existe arquitetura, contrato de API, modelo SQLAlchemy ou migration a preservar. A estrutura criada segue o backlog do motor e adota um monolito modular: transporte HTTP, casos de uso, dominio geoespacial, indicadores e persistencia permanecem separados.

Os quatro documentos convergem em cinco pontos: rastreabilidade integral; preservacao do dado original; calculos metricos em CRS projetado; formulas versionadas; e validacao com casos sinteticos e casos de ouro. A prioridade correta e uma fatia vertical de area territorial antes de lotes, redes viarias, densidade ou relatorios.

Ha uma divergencia de execucao: a diretriz geral de backend recomenda fila para operacoes pesadas, mas o backlog exige analise sincrona no MVP. A decisao inicial esta registrada no ADR 004.

## Fronteiras adotadas

- `app/api`: validacao HTTP e traducao de erros.
- `app/application`: casos de uso, ciclo do run e orquestracao.
- `app/domain/analysis`: definicoes, registro, resultados, avisos e excecoes.
- `app/domain/geospatial`: CRS, geometrias, camadas, topologia e relacoes espaciais.
- `app/domain/indicators`: formulas urbanisticas versionadas.
- `app/infrastructure`: PostGIS, repositorios, arquivos e jobs.
- `app/config`: parametros tipados e mapeamentos aprovados pelo dominio.
- `tests/reference_cases`: entradas e resultados verificaveis fora do projeto real.

## Proxima sequencia de trabalho

1. Confirmar o contrato atual de projetos, versoes, camadas, feicoes, runs e resultados.
2. Implementar selecao automatica de SIRGAS 2000 / UTM com casos de diferentes fusos brasileiros.
3. Implementar repositorio PostGIS preservando `feature_id`, CRS e versao do projeto.
4. Criar contexto de analise com cache apenas durante o run.
5. Implementar ciclo `pending -> running -> completed|failed` e migrations.
6. Concluir `territorial.total_area` ponta a ponta.
7. Validar com quadrado 100 x 100 m, multipartes, vazio, WGS84 reprojetado e falha persistida.

## Decisoes de dominio pendentes

- Inclusao ou nao de aneis internos no perimetro territorial.
- Matriz de precedencia para categorias territoriais sobrepostas.
- Tolerancia angular para consolidacao de faces de quadras.
- Tratamento de empate no uso predominante.
- Denominador de eficiencia de parcelamento.
- Eficiencia residencial e estimativa de unidades.
- Denominadores de densidade liquida e bruta.
- Larguras viarias padrao, raios e limiares por equipamento.

Esses itens nao devem ser implementados ate aprovacao do urbanista responsavel.
