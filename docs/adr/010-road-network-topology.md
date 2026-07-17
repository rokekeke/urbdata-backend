# ADR 010 - Topologia da rede viaria

- Status: aceito para a primeira fatia do Epico 9
- Data: 2026-07-17
- Aprovador de dominio: responsavel urbanista (diretrizes registradas nesta ADR)

## Decisao

A rede usa uma camada GeoJSON explicitamente enviada de eixos viarios
(`sistema_viario`, LineString/MultiLineString). O eixo e a fonte de verdade;
nao sera extraido automaticamente do poligono territorial da via.

Cada feicao pode mapear `road_status` para `existente` ou `proposta`. Valores
desconhecidos permanecem nulos e geram aviso - nunca sao adivinhados.

O grafo e um `networkx.MultiGraph` nao direcionado no MVP. Antes da construcao:

1. a camada e reprojetada para o CRS metrico da execucao;
2. MultiLineStrings sao explodidas apenas na representacao temporaria;
3. extremidades dentro da tolerancia configurada sao consolidadas;
4. intersecoes geometricas recebem noding;
5. as linhas sao subdivididas entre nos;
6. cada aresta preserva feicao de origem, status, geometria temporaria e comprimento.

Nenhuma dessas operacoes altera a geometria persistida.

## Unlinks

Cruzamentos em planta que nao sao conexoes reais (viadutos, tuneis e passagens
desniveladas) usam uma camada de pontos `desconexoes_viarias`. A semantica segue
o *unlink* da sintaxe espacial: um ponto valido identifica exatamente duas linhas
e impede que o cruzamento entre elas se transforme em no. Pontos ambiguos ou
isolados geram aviso e nao sao aplicados silenciosamente.

## Rede externa e rede proposta

Vias existentes fora do perimetro permanecem no grafo. Elas sao necessarias para
avaliar onde a malha proposta se conecta ao sistema urbano real. Um componente
com arestas propostas e nenhuma aresta existente gera aviso explicito.

A densidade de intersecoes e a excecao espacial: seu denominador e a area bruta
do projeto, portanto somente intersecoes dentro ou sobre o perimetro entram no
numerador. As vias externas continuam influenciando os demais indicadores de
conectividade.

## Parametro inicial

A tolerancia de snapping inicial e 2 m (`road_snapping_tolerance_m`). O valor
efetivo e copiado para a configuracao e para o resultado de cada execucao.

## Fora desta fatia

- classificacao qualitativa por benchmark;
- hierarquia local/coletora/arterial e larguras;
- grafo direcionado e regras de mao unica;
- integracao e choice da sintaxe espacial;
- roteamento e cobertura de equipamentos por distancia de rede.
