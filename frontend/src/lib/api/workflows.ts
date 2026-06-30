import apiClient from "./client";
import type {
  Workflow,
  WorkflowGraph,
  PaginatedWorkflows,
  PaginatedVersions,
  WorkflowVersion,
  PublishResult,
} from "@/types/workflow";

export const workflowsApi = {
  list: () =>
    apiClient.get<PaginatedWorkflows>("/workflows"),

  get: (id: string) =>
    apiClient.get<Workflow>(`/workflows/${id}`),

  create: (data: { name: string; description?: string }) =>
    apiClient.post<Workflow>("/workflows", data),

  update: (id: string, data: { name?: string; description?: string; definition?: WorkflowGraph }) =>
    apiClient.patch<Workflow>(`/workflows/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/workflows/${id}`),

  publish: (id: string, definition?: WorkflowGraph) =>
    apiClient.post<PublishResult>(`/workflows/${id}/publish`, definition ? { definition } : {}),

  listVersions: (id: string) =>
    apiClient.get<PaginatedVersions>(`/workflows/${id}/versions`),

  getVersion: (id: string, versionNumber: number) =>
    apiClient.get<WorkflowVersion>(`/workflows/${id}/versions/${versionNumber}`),

  revert: (id: string, versionNumber: number) =>
    apiClient.post<PublishResult>(`/workflows/${id}/revert/${versionNumber}`),

  duplicate: (id: string, name: string) =>
    apiClient.post<Workflow>(`/workflows/${id}/duplicate`, { name }),

  archive: (id: string) =>
    apiClient.post<Workflow>(`/workflows/${id}/archive`),
};
