# Caso de ouro: square_perimeter

## Como foi gerado

O quadrado foi construído diretamente em `EPSG:32722` (WGS 84 / UTM zone 22S,
o CRS métrico padrão aprovado na ADR 001) com vértices exatos:

```
(500000.0, 7000000.0), (500100.0, 7000000.0),
(500100.0, 7000100.0), (500000.0, 7000100.0)
```

Isso da uma area exata de 100 m x 100 m = **10.000 m2** por construcao, sem
depender de nenhuma funcao do motor.

`input.geojson` contem esse mesmo quadrado reprojetado para `EPSG:4326` (o
GeoJSON exige WGS 84 por especificacao), usando `pyproj.Transformer`. O
calculo e independente do codigo da aplicacao: as coordenadas foram geradas
uma unica vez com PyProj e congeladas no arquivo.

## Verificacao independente

Reprojetar `input.geojson` de volta para `EPSG:32722` com PyProj recupera
`9999.999999950523 m2` — um desvio relativo de ~5e-9 em relacao aos
10.000 m2 exatos, unicamente por arredondamento de ponto flutuante na ida e
volta entre CRS. Isso define a tolerancia abaixo.

## Resultado esperado

CRS metrico esperado para os tres indicadores: `EPSG:32722` (o quadrado esta
inteiramente dentro do fuso 22S, entao o seletor de CRS deve escolher o EPSG
padrao aprovado).

### `territorial.total_area`

- Valor: `10000.0 m2` (100 m x 100 m, por construcao)
- Tolerancia: `0.01 m2` (a margem observada no arredondamento de ida e volta
  entre CRS e de ~5e-5 m2, entao 0.01 m2 e uma tolerancia folgada e segura)

### `territorial.perimeter` (BT-041)

- Valor: `400.0 m` (4 x 100 m, por construcao - `Polygon.length` ja soma os
  aneis da geometria, entao nao existe extracao de fronteira separada)
- Tolerancia: `0.01 m`, pela mesma razao do total_area

### `territorial.compactness` (BT-042)

- Formula: indice isoperimetrico de Polsby-Popper,
  `4 x pi x area / perimetro^2`. Para qualquer quadrado, esse valor e
  exatamente `pi / 4 ~= 0.7853981633974483`, independente do tamanho do
  lado - e uma identidade geometrica, nao depende dos 100 m especificos
  deste caso.
- Valor: `0.7853981633974483`
- Tolerancia: `1e-6` (a compacidade e uma razao de area/perimetro^2; o erro
  de ponto flutuante de ~5e-9 relativo em cada termo nao se acumula o
  suficiente para se aproximar dessa margem)
