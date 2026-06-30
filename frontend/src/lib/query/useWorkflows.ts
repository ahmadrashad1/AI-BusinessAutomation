"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { workflowsApi } from "@/lib/api/workflows";
import type { WorkflowGraph } from "@/types/workflow";

export const workflowKeys = {
  all: ["workflows"] as const,
  detail: (id: string) => ["workflows", id] as const,
  versions: (id: string) => ["workflows", id, "versions"] as const,
};

export function useWorkflows() {
  return useQuery({
    queryKey: workflowKeys.all,
    queryFn: () => workflowsApi.list().then((r) => r.data),
  });
}

export function useWorkflow(id: string) {
  return useQuery({
    queryKey: workflowKeys.detail(id),
    queryFn: () => workflowsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useWorkflowVersions(id: string) {
  return useQuery({
    queryKey: workflowKeys.versions(id),
    queryFn: () => workflowsApi.listVersions(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      workflowsApi.create(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useUpdateWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string; description?: string; definition?: WorkflowGraph }) =>
      workflowsApi.update(id, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKeys.detail(id) });
    },
  });
}

export function usePublishWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (definition?: WorkflowGraph) =>
      workflowsApi.publish(id, definition).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKeys.detail(id) });
      qc.invalidateQueries({ queryKey: workflowKeys.versions(id) });
      qc.invalidateQueries({ queryKey: workflowKeys.all });
    },
  });
}

export function useRevertWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionNumber: number) =>
      workflowsApi.revert(id, versionNumber).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKeys.detail(id) });
      qc.invalidateQueries({ queryKey: workflowKeys.versions(id) });
    },
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useDuplicateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      workflowsApi.duplicate(id, name).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useArchiveWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowsApi.archive(id).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}
