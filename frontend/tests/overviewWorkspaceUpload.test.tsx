import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, within } from "@testing-library/react";

import OverviewWorkspace from "../app/components/OverviewWorkspace";

// f1.3 (nota 53/54): the split-profile toggle inside each UploadSlot must
// gate submission on its own fields, without disturbing the existing
// combined-profile behavior or the other slots' independent state.

function renderOverview() {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <OverviewWorkspace
        projects={[
          {
            id: "project-1",
            name: "Projeto teste",
            municipality: null,
            state: null,
            typology: null,
            approx_area_m2: null,
            description: null,
            team: null,
            created_at: "2026-07-21T12:00:00Z",
          },
        ]}
        projectsLoading={false}
        projectsError={null}
        activeProjectId="project-1"
        activeVersionId="version-1"
        projectLayers={[]}
        onSelectProject={() => {}}
        onOpenData={() => {}}
      />
    </QueryClientProvider>,
  );
}

// Ordem de NAMED_SLOTS em OverviewWorkspace.tsx: Matrícula, Projeto, Eixos das vias.
function uploadSlots(): HTMLElement[] {
  return Array.from(document.querySelectorAll(".overview-upload-slot"));
}

function projetoSlotElement(): HTMLElement {
  return uploadSlots()[1]!;
}

describe("OverviewWorkspace - alternador combined/split (f1.3)", () => {
  afterEach(() => cleanup());

  it("mantem o envio combined inalterado: um arquivo basta para habilitar o botao", () => {
    renderOverview();
    const slotElement = projetoSlotElement();
    const slot = within(slotElement);
    const submit = slot.getByRole("button", { name: /enviar/i });
    expect(submit).toBeDisabled();

    const fileInputs = slotElement.querySelectorAll('input[type="file"]');
    fireEvent.change(fileInputs[0]!, {
      target: { files: [new File(["{}"], "t.geojson", { type: "application/geo+json" })] },
    });

    expect(submit).toBeEnabled();
  });

  it("revela os campos de split e mantem o botao desabilitado ate arquivo+chave estarem prontos", () => {
    renderOverview();
    const slotElement = projetoSlotElement();
    const slot = within(slotElement);

    fireEvent.change(slotElement.querySelectorAll('input[type="file"]')[0]!, {
      target: { files: [new File(["{}"], "t.geojson", { type: "application/geo+json" })] },
    });
    const submit = slot.getByRole("button", { name: /enviar/i });
    expect(submit).toBeEnabled();

    fireEvent.click(slot.getByRole("checkbox"));
    expect(slot.getByText("Tabela de atributos (CSV)")).toBeInTheDocument();
    expect(submit).toBeDisabled(); // CSV e chave ainda faltam

    fireEvent.change(slotElement.querySelectorAll('input[type="file"]')[1]!, {
      target: { files: [new File(["Name;Area\nL01;100\n"], "a.csv", { type: "text/csv" })] },
    });
    expect(submit).toBeDisabled(); // falta a chave

    fireEvent.change(slot.getByPlaceholderText("Ex.: Name"), { target: { value: "Name" } });
    expect(submit).toBeEnabled();
  });

  it("nao afeta o estado dos outros slots (Matricula/Eixos das vias)", () => {
    renderOverview();
    fireEvent.click(within(projetoSlotElement()).getByRole("checkbox"));

    const matriculaSlot = within(uploadSlots()[0]!);
    expect(matriculaSlot.queryByText("Tabela de atributos (CSV)")).not.toBeInTheDocument();
  });
});

describe("OverviewWorkspace - resumo de validacao pos-envio (f2.2)", () => {
  // getApiClient() (app/lib/api/client.ts) is a module-level singleton that
  // binds to whatever `fetch` is live the first time it's constructed - a
  // second test that re-stubs `fetch` without a fresh module registry would
  // silently keep hitting the FIRST test's (by then torn-down) stub instead
  // of its own, producing a generic network error instead of the domain
  // one. Reset modules and re-import both the component and react-query
  // fresh per test so the singleton (and the QueryClient context it reads)
  // are rebuilt against this test's own fetch stub.
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  async function renderOverviewFresh() {
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { default: FreshOverviewWorkspace } = await import("../app/components/OverviewWorkspace");
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <FreshOverviewWorkspace
          projects={[
            {
              id: "project-1",
              name: "Projeto teste",
              municipality: null,
              state: null,
              typology: null,
              approx_area_m2: null,
              description: null,
              team: null,
              created_at: "2026-07-21T12:00:00Z",
            },
          ]}
          projectsLoading={false}
          projectsError={null}
          activeProjectId="project-1"
          activeVersionId="version-1"
          projectLayers={[]}
          onSelectProject={() => {}}
          onOpenData={() => {}}
        />
      </QueryClientProvider>,
    );
  }

  function submitSplitUpload(slotElement: HTMLElement) {
    const slot = within(slotElement);
    fireEvent.change(slotElement.querySelectorAll('input[type="file"]')[0]!, {
      target: { files: [new File(["{}"], "t.geojson", { type: "application/geo+json" })] },
    });
    fireEvent.click(slot.getByRole("checkbox"));
    fireEvent.change(slotElement.querySelectorAll('input[type="file"]')[1]!, {
      target: { files: [new File(["Name;Area\nL01;100\n"], "a.csv", { type: "text/csv" })] },
    });
    fireEvent.change(slot.getByPlaceholderText("Ex.: Name"), { target: { value: "Name" } });
    fireEvent.click(slot.getByRole("button", { name: /enviar/i }));
    return slot;
  }

  it("mostra as contagens do join_summary apos um envio split bem-sucedido", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "layer-1",
            project_version_id: "version-1",
            layer_type: "territorio",
            source_filename: "t.geojson",
            geometry_type: "Polygon",
            feature_count: 1,
            status: "uploaded",
            uploaded_at: "2026-07-21T12:00:00Z",
            import_profile: "split",
            attributes_filename: "a.csv",
            attributes_join_key: "Name",
            geometry_join_key: null,
            join_summary: { geometry_count: 1, attribute_count: 1, matched: 1 },
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    await renderOverviewFresh();
    const slot = submitSplitUpload(projetoSlotElement());

    expect(await slot.findByText(/1 de 1 geometrias combinadas com 1/i)).toBeInTheDocument();
  });

  it("lista as chaves problematicas do context quando o envio split falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              error: "attribute_join_mismatch",
              message: "A junção entre geometria e atributos falhou.",
              context: {
                duplicate_geometry_keys: ["L01"],
                missing_attribute_keys: ["L02"],
              },
            },
          }),
          { status: 400, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    await renderOverviewFresh();
    const slot = submitSplitUpload(projetoSlotElement());

    const duplicateItem = (await slot.findByText(/Chaves duplicadas na geometria/i)).closest("li");
    expect(duplicateItem).toHaveTextContent("L01");
    const missingItem = slot
      .getByText(/Chaves da geometria sem linha correspondente no CSV/i)
      .closest("li");
    expect(missingItem).toHaveTextContent("L02");
  });

  it("mostra a mensagem certa para um CSV malformado (f6.2) - nao so que a requisicao falhou", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              error: "csv_malformed",
              message: "Arquivo CSV esta vazio.",
              context: {},
            },
          }),
          { status: 400, headers: { "content-type": "application/json" } },
        ),
      ),
    );

    await renderOverviewFresh();
    const slot = submitSplitUpload(projetoSlotElement());

    expect(await slot.findByText("Arquivo CSV esta vazio.")).toBeInTheDocument();
  });
});
