import { mkdir, writeFile } from "node:fs/promises";

const DEFAULT_OPENAPI_URL = "http://localhost:8000/openapi.json";
const sourceUrl = process.env.URBDATA_OPENAPI_URL?.trim() || DEFAULT_OPENAPI_URL;
const contractDirectory = new URL("../contracts/", import.meta.url);
const contractFile = new URL("openapi.json", contractDirectory);

let response;
try {
  response = await fetch(sourceUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
} catch (error) {
  const reason = error instanceof Error ? error.message : String(error);
  throw new Error(
    `Não foi possível acessar o OpenAPI em ${sourceUrl}. Confirme que o backend está ativo. ${reason}`,
  );
}

if (!response.ok) {
  throw new Error(`O OpenAPI respondeu HTTP ${response.status} em ${sourceUrl}.`);
}

const contract = await response.json();
if (
  !contract ||
  typeof contract !== "object" ||
  typeof contract.openapi !== "string" ||
  !contract.info ||
  !contract.paths
) {
  throw new Error("A resposta recebida não possui a estrutura mínima de um documento OpenAPI.");
}

await mkdir(contractDirectory, { recursive: true });
await writeFile(contractFile, `${JSON.stringify(contract, null, 2)}\n`, "utf8");

console.log(
  `OpenAPI ${contract.info.title ?? "sem título"} ${contract.info.version ?? "sem versão"} salvo em contracts/openapi.json.`,
);
