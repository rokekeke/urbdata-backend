"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import {
  listCatalogIndicators,
  type CatalogIndicator,
} from "../api/listCatalogIndicators";

export function useCatalogIndicators() {
  return useQuery<CatalogIndicator[], AppError>({
    queryKey: queryKeys.catalog.indicators,
    queryFn: ({ signal }) => listCatalogIndicators(signal),
    staleTime: 5 * 60 * 1000,
  });
}
