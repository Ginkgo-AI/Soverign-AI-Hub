"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchCollections,
  createCollection,
  deleteCollection,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  searchDocuments,
  type Collection,
  type Document,
  type SearchResult,
} from "@/lib/collections";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selected, setSelected] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newClassification, setNewClassification] = useState("UNCLASSIFIED");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const loadCollections = useCallback(async () => {
    try {
      const data = await fetchCollections();
      setCollections(data.collections);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  const loadDocuments = useCallback(async (col: Collection) => {
    try {
      const data = await fetchDocuments(col.id);
      setDocuments(data.documents);
    } catch {
      /* empty */
    }
  }, []);

  const handleSelect = (col: Collection) => {
    setSelected(col);
    setSearchResults([]);
    setSearchQuery("");
    loadDocuments(col);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createCollection({
        name: newName,
        description: newDesc,
        classification_level: newClassification,
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      loadCollections();
    } catch {
      alert("Failed to create collection");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this collection and all its documents?")) return;
    try {
      await deleteCollection(id);
      if (selected?.id === id) {
        setSelected(null);
        setDocuments([]);
      }
      loadCollections();
    } catch {
      alert("Failed to delete collection");
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || !selected) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(selected.id, file);
      }
      loadDocuments(selected);
      loadCollections();
    } catch {
      alert("Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selected) return;
    try {
      await deleteDocument(selected.id, docId);
      loadDocuments(selected);
      loadCollections();
    } catch {
      alert("Failed to delete document");
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !searchQuery.trim()) return;
    setSearching(true);
    try {
      const data = await searchDocuments(selected.id, searchQuery);
      setSearchResults(data.results);
    } catch {
      alert("Search failed");
    } finally {
      setSearching(false);
    }
  };

  const classColors: Record<string, string> = {
    UNCLASSIFIED: "bg-green-500/20 text-green-400",
    CUI: "bg-yellow-500/20 text-yellow-400",
    SECRET: "bg-red-500/20 text-red-400",
    TOP_SECRET: "bg-amber-500/20 text-amber-300",
  };

  const statusColors: Record<string, string> = {
    ready: "text-green-400",
    processing: "text-yellow-400",
    pending: "text-[var(--color-text-muted)]",
    error: "text-red-400",
  };

  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <div className="flex h-full">
      {/* Left panel: Collection list */}
      <div className="w-72 border-r border-[var(--color-border)] flex flex-col shrink-0">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h2 className="text-lg font-semibold">Collections</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="px-2.5 py-1 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
          >
            + New
          </button>
        </div>

        {showCreate && (
          <form
            onSubmit={handleCreate}
            className="p-3 border-b border-[var(--color-border)] space-y-2"
          >
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Collection name"
              required
              className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
            />
            <input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
            />
            <select
              value={newClassification}
              onChange={(e) => setNewClassification(e.target.value)}
              className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
            >
              <option value="UNCLASSIFIED">UNCLASSIFIED</option>
              <option value="CUI">CUI</option>
              <option value="SECRET">SECRET</option>
            </select>
            <div className="flex gap-2">
              <button
                type="submit"
                className="flex-1 py-1.5 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="flex-1 py-1.5 text-xs border border-[var(--color-border)] rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <p className="text-sm text-[var(--color-text-muted)] p-3">
              Loading...
            </p>
          ) : collections.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)] p-3">
              No collections yet. Create one to get started.
            </p>
          ) : (
            collections.map((col) => (
              <div
                key={col.id}
                onClick={() => handleSelect(col)}
                className={`p-3 rounded-md cursor-pointer transition-colors group ${
                  selected?.id === col.id
                    ? "bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30"
                    : "hover:bg-[var(--color-surface-hover)] border border-transparent"
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-sm font-medium truncate">
                    {col.name}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(col.id);
                    }}
                    className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Delete
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${classColors[col.classification_level] || "bg-gray-500/20 text-gray-400"}`}
                  >
                    {col.classification_level}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {col.document_count} docs &middot; {col.chunk_count} chunks
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right panel: Documents + Search */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-[var(--color-text-muted)]">
            <p>Select a collection to view documents</p>
          </div>
        ) : (
          <>
            <div className="p-4 border-b border-[var(--color-border)]">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-lg font-semibold">{selected.name}</h3>
                  {selected.description && (
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {selected.description}
                    </p>
                  )}
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${classColors[selected.classification_level] || "bg-gray-500/20 text-gray-400"}`}
                >
                  {selected.classification_level}
                </span>
              </div>

              {/* Search bar */}
              <form onSubmit={handleSearch} className="flex gap-2">
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search documents in this collection..."
                  className="flex-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
                />
                <button
                  type="submit"
                  disabled={searching}
                  className="px-4 py-2 text-sm bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50 text-white rounded-md transition-colors"
                >
                  {searching ? "..." : "Search"}
                </button>
              </form>
            </div>

            {/* Search results */}
            {searchResults.length > 0 && (
              <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-accent)]/5">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium">
                    Search Results ({searchResults.length})
                  </h4>
                  <button
                    onClick={() => setSearchResults([])}
                    className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  >
                    Clear
                  </button>
                </div>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {searchResults.map((r, i) => (
                    <div
                      key={i}
                      className="p-3 bg-[var(--color-surface)] rounded-md border border-[var(--color-border)]"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium">
                          {r.filename}
                        </span>
                        <span className="text-[10px] text-[var(--color-accent)]">
                          Score: {(r.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-xs text-[var(--color-text-muted)] line-clamp-3">
                        {r.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upload dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                handleUpload(e.dataTransfer.files);
              }}
              className={`mx-4 mt-4 p-4 border-2 border-dashed rounded-lg text-center text-sm transition-colors ${
                dragOver
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)]"
              }`}
            >
              {uploading ? (
                <p>Uploading...</p>
              ) : (
                <>
                  <p>
                    Drag & drop files here or{" "}
                    <label className="text-[var(--color-accent)] cursor-pointer hover:underline">
                      browse
                      <input
                        type="file"
                        multiple
                        className="hidden"
                        onChange={(e) => handleUpload(e.target.files)}
                      />
                    </label>
                  </p>
                  <p className="text-[10px] mt-1">
                    PDF, TXT, MD, DOCX, CSV, JSON
                  </p>
                </>
              )}
            </div>

            {/* Documents table */}
            <div className="flex-1 overflow-y-auto p-4">
              {documents.length === 0 ? (
                <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                  No documents yet. Upload files to get started.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[var(--color-text-muted)] text-xs border-b border-[var(--color-border)]">
                      <th className="pb-2 font-medium">Filename</th>
                      <th className="pb-2 font-medium">Type</th>
                      <th className="pb-2 font-medium">Size</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Chunks</th>
                      <th className="pb-2 font-medium w-16"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-[var(--color-surface-hover)]">
                        <td className="py-2.5 font-medium truncate max-w-[200px]">
                          {doc.filename}
                        </td>
                        <td className="py-2.5 text-[var(--color-text-muted)]">
                          {doc.content_type.split("/").pop()}
                        </td>
                        <td className="py-2.5 text-[var(--color-text-muted)]">
                          {formatBytes(doc.size_bytes)}
                        </td>
                        <td className="py-2.5">
                          <span className={statusColors[doc.status]}>
                            {doc.status}
                          </span>
                        </td>
                        <td className="py-2.5 text-[var(--color-text-muted)]">
                          {doc.chunk_count}
                        </td>
                        <td className="py-2.5">
                          <button
                            onClick={() => handleDeleteDoc(doc.id)}
                            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
