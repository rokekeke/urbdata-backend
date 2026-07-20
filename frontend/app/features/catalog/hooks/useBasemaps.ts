"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listBasemaps, type Basemap } from "../api/listBasemaps";

export function useBasemaps() {
  return useQuery<Basemap[], AppError>({
    queryKey: queryKeys.catalog.basemaps,
    queryFn: ({ signal }) => listBasemaps(signal),
    staleTime: 5 * 60 * 1000,
  });
}
