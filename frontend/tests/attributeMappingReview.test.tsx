import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import DataWorkspace from "../app/components/DataWorkspace";
import type { LayerAttributes } from "../app/features/layers/api/getLayerAttributes";
import type { LayerStyleConfig } from "../app/lib/types";

// f5 (nota 53/54): the mapping review is new UI, from scratch - there was no
// consumer of PATCH /layers/{id}/attributes anywhere before this.

const layer: LayerStyleConfig = {
  id: "layer-1",
  name: "Território",
  shortName: "Território",
  geometry: "polygon",
  visible: true,
  opacity: 0.7,
  color: "#D6B17B",
  secondaryColor: "#3D6F78",
  strokeColor: "#384541",
  strokeWidth: 1,
  lineStyle: "solid",
  representation: "single",
  mode: "single",
  representationOptions: [
    { value: "single", label: "Estilo único", type: "text", source: "source" },
  ],
  featureCount: 102,
};

const attributes: LayerAttributes = {
  layer_id: "layer-1",
  source_fields: ["TIPO DE MACROÁREA", "QUADRA", "Uso do solo"],
  sample_values: { "TIPO DE MACROÁREA": ["Lote", "AVL"] },
  suggested_mapping: { macroarea: "TIPO DE MACROÁREA", quadra_id: "QUADRA" },
  feature_count: 102,
  fields: [],
  compatible_indicators: [],
};

function renderWorkspace() {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <DataWorkspace
        projectId="project-1"
        activeVersion={null}
        layers={[layer]}
        selectedLayer={layer}
        attributes={attributes}
        isLoading={false}
        attributesLoading={false}
        error={null}
        attributesError={null}
        geojsonStateByLayerId={{}}
        onSelectLayer={() => {}}
        onRetryLayer={async () => {}}
        onOpenDocumentation={() => {}}
      />
    </QueryClientProvider>,
  );
}

class CapturedRequest {
  readonly url: string;
  readonly method: string;
  readonly body: BodyInit | null;
  constructor(input: string | URL, init?: RequestInit) {
    this.url = String(input);
    this.method = init?.method ?? "GET";
    this.body = init?.body ?? null;
  }
}

describe("Revisão de mapeamento de atributos (f5)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("mostra o mapeamento sugerido pre-preenchido e permite trocar a coluna de origem", () => {
    renderWorkspace();
    const review = within(screen.getByText("Revisar mapeamento sugerido").closest("details")!);

    const macroareaSelect = review.getByLabelText("macroarea") as unknown as HTMLSelectElement;
    expect(macroareaSelect.value).toBe("TIPO DE MACROÁREA");

    fireEvent.change(macroareaSelect, { target: { value: "QUADRA" } });
    expect(macroareaSelect.value).toBe("QUADRA");
  });

  it("aplica o mapeamento via PATCH e exibe os warnings da resposta", async () => {
    vi.stubGlobal("Request", CapturedRequest);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          layer_id: "layer-1",
          status: "mapped",
          features_updated: 102,
          warnings: [{ feature_id: "feature-9", message: "Area com unidade não reconhecida." }],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace();
    const review = within(screen.getByText("Revisar mapeamento sugerido").closest("details")!);
    fireEvent.click(review.getByRole("button", { name: /aplicar mapeamento/i }));

    const successMessage = await review.findByText(/102 feições atualizadas/i);
    expect(successMessage).toBeInTheDocument();
    expect(review.getByText(/unidade não reconhecida/i)).toBeInTheDocument();

    const [request] = fetchMock.mock.calls[0] as unknown as [CapturedRequest];
    expect(request.method).toBe("PATCH");
    expect(JSON.parse(request.body as string)).toEqual({
      mappings: { macroarea: "TIPO DE MACROÁREA", quadra_id: "QUADRA" },
    });
  });
});
