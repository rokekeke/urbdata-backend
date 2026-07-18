# Backlog backend - Documentacao e composicao cartografica

Data: 2026-07-18.

## Objetivo

Estruturar o suporte de backend para a aba `Documentacao`, na qual o usuario
prepara a apresentacao de um mapa antes da exportacao. A configuracao visual e
um documento derivado e nunca altera geometrias, atributos, camadas originais
ou resultados de analise.

## Escopo funcional recebido

- escolher a camada e o campo/indicador usados na representacao;
- configurar espessura e estilo de linha por camada;
- ajustar cores, gradientes e transparencia;
- selecionar uma base raster de fundo;
- preservar a configuracao para reabertura e exportacao reproduzivel.

## Premissas de arquitetura

- O documento pertence a uma `ProjectVersion`, nao apenas ao projeto.
- Referencias a camadas usam `project_layers.id`; nao duplicar GeoJSON.
- A especificacao visual tem `schema_version` explicita.
- O backend persiste e valida intencao cartografica; o frontend traduz essa
  intencao para o estilo de visualizacao.
- A exportacao deve registrar a revisao do documento e as atribuicoes da base
  raster usadas na renderizacao.
- URLs raster arbitrarias ficam fora da primeira fatia para evitar SSRF,
  indisponibilidade, problemas de CORS e violacao de licenca.

## Contrato conceitual inicial

```json
{
  "schema_version": 1,
  "name": "Mapa de uso do solo",
  "viewport": {
    "bounds": [-48.60, -27.70, -48.40, -27.50],
    "bearing": 0,
    "pitch": 0
  },
  "basemap_id": "light-neutral",
  "layers": [
    {
      "layer_id": "uuid",
      "visible": true,
      "order": 10,
      "representation": {
        "source": "property",
        "field": "macroarea",
        "mode": "categorical"
      },
      "style": {
        "fill": {
          "colors": {"lote": "#8BA7A0"},
          "opacity": 0.72
        },
        "stroke": {
          "color": "#273532",
          "width_px": 1.25,
          "style": "solid",
          "opacity": 0.9
        }
      }
    }
  ]
}
```

O JSON acima orienta a elaboracao do contrato; os nomes finais devem ser
formalizados no ticket DOC-BE-001 antes da migration.

## Epico DOC-BE - Documento cartografico e exportacao

### Quadro de execucao

- [ ] DOC-BE-001 - Registrar ADR e contrato v1
- [ ] DOC-BE-002 - Persistir documentos cartograficos
- [ ] DOC-BE-003 - Expor CRUD de documentos
- [ ] DOC-BE-004 - Publicar metadados de representacao por camada
- [ ] DOC-BE-005 - Validar especificacao visual
- [ ] DOC-BE-006 - Criar catalogo controlado de mapas-base
- [ ] DOC-BE-007 - Preparar snapshot reproduzivel para exportacao
- [ ] DOC-BE-008 - Implementar geracao do mapa exportado
- [ ] DOC-BE-009 - Implementar seguranca, limites e observabilidade
- [ ] DOC-BE-010 - Criar testes integrados e caso de referencia visual

### DOC-BE-001 - Registrar ADR e contrato v1

**Objetivo:** decidir limite de responsabilidade entre frontend, API e
renderizador e publicar o JSON Schema/OpenAPI da configuracao.

**Entregas:**

- ADR sobre documento cartografico derivado;
- ownership por `ProjectVersion`;
- enums de geometria, representacao, gradiente e linha;
- politica de evolucao por `schema_version`;
- decisao sobre uma ou varias composicoes por versao.

**Aceite:** exemplos validos e invalidos cobrem poligono, linha e ponto; fica
explicito que nenhuma operacao atualiza `features.geom` ou propriedades fonte.

### DOC-BE-002 - Persistir documentos cartograficos

**Depende de:** DOC-BE-001.

**Objetivo:** adicionar migration e modelos para documento, revisao e estado de
exportacao. A primeira proposta e uma tabela `map_documents` com configuracao
JSONB validada, `project_version_id`, nome, revisao e timestamps.

**Aceite:** constraints impedem documento sem versao; revisao cresce de forma
deterministica; exclusao de projeto segue a politica existente; downgrade e
upgrade da migration sao testados.

### DOC-BE-003 - Expor CRUD de documentos

**Depende de:** DOC-BE-002.

**Endpoints propostos:**

```text
POST   /v1/projects/{project_id}/documents
GET    /v1/projects/{project_id}/documents
GET    /v1/projects/{project_id}/documents/{document_id}
PUT    /v1/projects/{project_id}/documents/{document_id}
DELETE /v1/projects/{project_id}/documents/{document_id}
```

**Aceite:** todas as referencias pertencem a versao corrente; atualizacao usa
controle otimista por revisao; respostas 404 e 409 seguem envelope de erro
consistente; round-trip preserva a configuracao sem perda.

### DOC-BE-004 - Publicar metadados de representacao por camada

**Objetivo:** fornecer ao frontend campos realmente utilizaveis em legenda e
simbologia, sem obrigar o cliente a inferir tipos a partir de 20 amostras.

**Endpoint proposto:**

```text
GET /v1/projects/{project_id}/layers/{layer_id}/representation-options
```

**Resposta minima por campo:** nome, origem (`source`/`mapped`/`indicator`),
tipo, contagem de nulos, valores distintos limitados ou `min/max`, unidade e
modo recomendado (`single`, `categorical`, `sequential`, `diverging`).

**Aceite:** campos inexistentes, inteiramente nulos ou de cardinalidade alta sao
identificados; limites numericos preservam valor bruto; consulta nao carrega
toda a camada na memoria da aplicacao.

### DOC-BE-005 - Validar especificacao visual

**Depende de:** DOC-BE-003 e DOC-BE-004.

**Regras minimas:**

- `opacity` entre 0 e 1;
- largura de linha dentro do intervalo aprovado pelo produto;
- estilos de linha em allowlist (`solid`, `dashed`, `dotted` na primeira fatia);
- cores em formato canonico;
- gradiente com stops ordenados e sem intervalos ambiguos;
- campo de representacao existente na camada;
- modo compativel com o tipo do campo e da geometria;
- `layer_id` pertencente ao mesmo `ProjectVersion`;
- ordem de desenho unica ou normalizada explicitamente.

**Aceite:** erros retornam codigo, mensagem em portugues e contexto preciso do
caminho invalido; configuracao invalida nunca e persistida parcialmente.

### DOC-BE-006 - Criar catalogo controlado de mapas-base

**Objetivo:** expor apenas bases raster aprovadas, com licenca e atribuicao.

**Endpoint proposto:**

```text
GET /v1/map-basemaps
```

**Metadados:** id estavel, nome, miniatura opcional, template interno,
atribuicao, limites de zoom, disponibilidade para exportacao e termos de uso.

**Aceite:** inclui opcao `sem mapa-base`; credenciais nunca chegam ao cliente;
bases sem direito de exportacao sao bloqueadas no servidor; falha do provedor
gera resultado explicito e nao remove a camada silenciosamente.

### DOC-BE-007 - Preparar snapshot reproduzivel para exportacao

**Depende de:** DOC-BE-003, DOC-BE-005 e DOC-BE-006.

**Objetivo:** congelar documento, revisao, viewport, ordem de camadas, estilos,
versoes de dados e atribuicao do mapa-base no momento da solicitacao.

**Aceite:** alterar o documento depois do pedido nao muda a exportacao em curso;
o snapshot registra ids e versoes suficientes para auditoria; fonte e data dos
dados podem ser exibidas no produto final.

### DOC-BE-008 - Implementar geracao do mapa exportado

**Depende de:** DOC-BE-007.

**Objetivo:** gerar ao menos PNG na primeira fatia; PDF e SVG dependem de
avaliacao tecnica do renderizador.

**Endpoint proposto:**

```text
POST /v1/projects/{project_id}/documents/{document_id}/exports
GET  /v1/projects/{project_id}/documents/{document_id}/exports/{export_id}
```

**Aceite:** saida respeita ordem, visibilidade, cores, opacidade, linha,
gradiente, viewport e mapa-base; inclui atribuicao obrigatoria; erro de tile,
timeout ou estilo invalido fica registrado; repeticao com o mesmo snapshot e
renderizador produz resultado visual equivalente.

### DOC-BE-009 - Seguranca, limites e observabilidade

**Depende de:** DOC-BE-008.

**Objetivo:** limitar tamanho, resolucao, numero de camadas, classes, stops e
tempo de renderizacao; registrar duracao e falhas sem expor segredos.

**Aceite:** payload excessivo retorna 422; exportacao dispendiosa nao bloqueia
indefinidamente o processo web; logs incluem `project_id`, `document_id`,
`export_id` e revisao, sem dados sensiveis.

### DOC-BE-010 - Testes integrados e caso de referencia visual

**Depende de:** DOC-BE-003 a DOC-BE-009.

**Objetivo:** cobrir persistencia, validacao, isolamento por projeto e exportacao
com um caso sintetico estavel.

**Aceite:** testes verificam schema, migration, CRUD, concorrencia, estilos
invalidos, allowlist de mapa-base e snapshot; imagem de referencia usa tolerancia
documentada para evitar falsos negativos entre ambientes.

## Sequenciamento recomendado

```text
DOC-BE-001
  -> DOC-BE-002 -> DOC-BE-003
  -> DOC-BE-004 -> DOC-BE-005
  -> DOC-BE-006
  -> DOC-BE-007 -> DOC-BE-008 -> DOC-BE-009 -> DOC-BE-010
```

O frontend pode construir o editor e a pre-visualizacao com estado local durante
DOC-BE-001 a DOC-BE-004. Persistencia compartilhada exige DOC-BE-003/005;
exportacao reproduzivel exige DOC-BE-006 a DOC-BE-008.
