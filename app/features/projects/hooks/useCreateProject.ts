"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type AppError } from "../../../lib/errors";
import { queryKeys } from "../../../lib/query";
import { createProject, type ProjectCreateInput } from "../api/createProject";
import type { Project } from "../api/listProjects";

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation<Project, AppError, ProjectCreateInput>({
    mutationFn: (payload) => createProject(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}
