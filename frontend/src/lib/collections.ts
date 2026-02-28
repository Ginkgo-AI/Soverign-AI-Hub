/**
 * Collections (RAG Knowledge Base) API helpers
 */

import { apiFetch, apiJson } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Collection {
  id: string;
  name: string;
  description: string;
  classification_level: string;
  document_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionListResponse {
  collections: Collection[];
  total: number;
}

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "pending" | "processing" | "ready" | "error";
  chunk_count: number;
  created_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  collection_id: string;
}

// ---------------------------------------------------------------------------
// Collections API
// ---------------------------------------------------------------------------

export async function fetchCollections(): Promise<CollectionListResponse> {
  return apiJson<CollectionListResponse>("/api/collections");
}

export async function createCollection(data: {
  name: string;
  description?: string;
  classification_level?: string;
}): Promise<Collection> {
  return apiJson<Collection>("/api/collections", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getCollection(
  collectionId: string
): Promise<Collection> {
  return apiJson<Collection>(`/api/collections/${collectionId}`);
}

export async function deleteCollection(
  collectionId: string
): Promise<void> {
  await apiFetch(`/api/collections/${collectionId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Documents API
// ---------------------------------------------------------------------------

export async function fetchDocuments(
  collectionId: string
): Promise<DocumentListResponse> {
  return apiJson<DocumentListResponse>(
    `/api/collections/${collectionId}/documents`
  );
}

export async function uploadDocument(
  collectionId: string,
  file: File
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(
    `/api/collections/${collectionId}/documents`,
    {
      method: "POST",
      body: formData,
      headers: {},
    }
  );
  return response.json();
}

export async function deleteDocument(
  collectionId: string,
  documentId: string
): Promise<void> {
  await apiFetch(
    `/api/collections/${collectionId}/documents/${documentId}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Search API
// ---------------------------------------------------------------------------

export async function searchDocuments(
  collectionId: string,
  query: string,
  topK = 5
): Promise<SearchResponse> {
  return apiJson<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      collection_id: collectionId,
      query,
      top_k: topK,
    }),
  });
}
