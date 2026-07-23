"use client";

import { useQuery } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { listProjects, type Project } from "../api/listProjects";

export function useProjects() {
  const query = useQuery<Project[], AppError>({
    queryKey: queryKeys.projects.list(),
    queryFn: ({ signal }) => listProjects(signal),
  });

  return {
    ...query,
    isEmpty: query.isSuccess && query.data.length === 0,
  };
}
