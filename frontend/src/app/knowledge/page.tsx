"use client";

import React, { useState, useEffect } from "react";
import { api, DocumentResponse, DocumentDetailResponse } from "@/lib/api";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetailResponse | null>(null);
  
  // Loading & Error States
  const [loadingList, setLoadingList] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  
  // Drag Over state
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    setLoadingList(true);
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
      
      // Select first document automatically if details aren't populated
      if (docs.length > 0 && !selectedDoc) {
        handleViewDetails(docs[0].id);
      }
    } catch (err: any) {
      console.error(err);
      setError("Failed to fetch documents catalog.");
    } finally {
      setLoadingList(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setError(null);
    setSuccessMsg(null);

    // Validate size limit (5 MB)
    if (file.size > MAX_FILE_SIZE) {
      setError(`File "${file.name}" exceeds the maximum allowed size of 5 MB.`);
      return;
    }

    setUploading(true);
    try {
      const newDoc = await api.uploadDocument(file);
      setSuccessMsg(`"${file.name}" processed and embedded successfully!`);
      await fetchDocuments();
      await handleViewDetails(newDoc.id);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to process file. Check backend log and API Key.");
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleViewDetails = async (id: string) => {
    setLoadingDetail(true);
    setError(null);
    try {
      const detail = await api.getDocument(id);
      setSelectedDoc(detail);
    } catch (err: any) {
      console.error(err);
      setError("Failed to retrieve document details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDeleteDoc = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Avoid triggering row selection click
    if (!confirm(`Are you sure you want to delete "${name}"? This deletes PG chunks and ChromaDB vectors.`)) {
      return;
    }
    setError(null);
    setSuccessMsg(null);
    try {
      await api.deleteDocument(id);
      setSuccessMsg(`"${name}" deleted successfully.`);
      if (selectedDoc && selectedDoc.id === id) {
        setSelectedDoc(null);
      }
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      setError("Failed to delete document.");
    }
  };

  // Helper to estimate token counts based on standard characters mapping
  const estimateTokens = (count: number) => {
    return `${((count * 220) / 1000).toFixed(1)}k`;
  };

  // Helper to map world name based on lore document titles
  const getWorldName = (title: string): string => {
    const t = title.toLowerCase();
    if (t.includes("siege") || t.includes("arven") || t.includes("kingdom")) return "Frostpeak";
    if (t.includes("ashen") || t.includes("court")) return "Ashen Court";
    if (t.includes("vulcana") || t.includes("faction")) return "Vulcana";
    return "Universal";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 max-w-7xl mx-auto animate-fade-in pb-12">
      {/* Upload and Table Catalog (3 cols wide on lg) */}
      <div className="lg:col-span-3 space-y-8">
        
        {/* Title Header */}
        <div className="space-y-1.5 border-b border-[#262626] pb-4">
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
            Knowledge Base
          </h2>
          <p className="text-xs text-[#a1a1aa] font-medium leading-relaxed">
            Synchronize raw world-building files with the vector search engine. Supports plain text, markdown, and PDF manuals (maximum size 5 MB).
          </p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-3.5 rounded border border-rose-500/20 bg-rose-500/10 text-rose-400 text-xs flex gap-2.5 items-center font-sans font-medium">
            <svg className="w-4 h-4 flex-shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3.5 rounded border border-emerald-500/20 bg-emerald-500/10 text-emerald-400 text-xs flex gap-2.5 items-center font-sans font-medium">
            <svg className="w-4 h-4 flex-shrink-0 text-emerald-450" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Stripe-style Compact Upload Area */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border rounded p-5 transition-all duration-150 ${
            dragOver ? "border-slate-500 bg-[#111111]/30" : "border-[#262626] bg-[#111111]/10"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-[#fafafa] block">
                {uploading ? "Ingesting document..." : "Upload Lore Document"}
              </span>
              <span className="text-[10px] text-[#a1a1aa] font-mono block">
                Supports TXT, MD, and PDF formats (Maximum size limit 5 MB)
              </span>
            </div>
            
            <label className={`cursor-pointer px-3 py-1.5 rounded text-xs font-bold font-sans transition shadow-sm ${
              uploading 
                ? "bg-[#262626] text-slate-500 cursor-not-allowed" 
                : "bg-[#b9ff66] text-[#0a0a0a] hover:opacity-90 active:opacity-95"
            }`}>
              {uploading ? "Ingesting..." : "Select File"}
              <input 
                type="file" 
                className="hidden" 
                accept=".txt,.md,.pdf" 
                onChange={handleFileChange} 
                disabled={uploading} 
              />
            </label>
          </div>
        </div>

        {/* Vercel-Style Library Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#fafafa]">Ingested Knowledge Library</span>
            <button
              onClick={fetchDocuments}
              className="text-xs font-mono text-[#a1a1aa] hover:text-[#fafafa] flex items-center gap-1 transition"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89H18" />
              </svg>
              REFRESH
            </button>
          </div>

          <div className="border border-[#262626] rounded bg-[#111111]/10 overflow-hidden">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#262626] bg-[#111111] font-mono text-[#a1a1aa] text-[10px] uppercase tracking-wider select-none">
                  <th className="py-2 px-4 font-bold">Document Name</th>
                  <th className="py-2 px-4 font-bold text-center">Chunks</th>
                  <th className="py-2 px-4 font-bold text-center">Tokens</th>
                  <th className="py-2 px-4 font-bold">World</th>
                  <th className="py-2 px-4">Last Indexed</th>
                  <th className="py-2 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]/80 font-sans">
                {loadingList ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500 font-mono text-xs">
                      LOADING FILES CATALOG...
                    </td>
                  </tr>
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center bg-[#111111]/5">
                      <div className="h-8 w-8 rounded bg-[#171717] border border-[#262626] text-slate-500 flex items-center justify-center mx-auto mb-3.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 13h6m-3-3v6m-9 1V4a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                        </svg>
                      </div>
                      <h4 className="font-semibold text-slate-300 text-xs">No Lore Documents Ingested</h4>
                      <p className="text-[10px] text-slate-500 mt-1 max-w-xs mx-auto leading-normal">
                        Upload a game manual or drop `ember_siege.txt` to populate the workspace.
                      </p>
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => {
                    const isSelected = doc.id === selectedDoc?.id;
                    const nameLower = doc.title.toLowerCase();
                    return (
                      <tr
                        key={doc.id}
                        onClick={() => handleViewDetails(doc.id)}
                        className={`cursor-pointer transition duration-150 ${
                          isSelected 
                            ? "bg-[#171717]/80 hover:bg-[#171717]" 
                            : "hover:bg-[#111111]/30"
                        }`}
                      >
                        <td className="py-2.5 px-4 font-semibold text-[#fafafa] font-mono text-[12px] truncate max-w-[150px]">
                          {doc.title}
                        </td>
                        <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center">
                          {doc.chunks_count}
                        </td>
                        <td className="py-2.5 px-4 font-mono text-[#a1a1aa] text-[12px] text-center">
                          {estimateTokens(doc.chunks_count)}
                        </td>
                        <td className="py-2.5 px-4 text-[#fafafa]">{getWorldName(doc.title)}</td>
                        <td className="py-2.5 px-4 text-[#a1a1aa]">{new Date(doc.created_at).toLocaleDateString()}</td>
                        <td className="py-2.5 px-4 text-right">
                          <button
                            onClick={(e) => handleDeleteDoc(doc.id, doc.title, e)}
                            className="text-slate-600 hover:text-rose-450 transition text-[11px] font-mono tracking-wider uppercase font-semibold"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Chunk Inspector Column (1 col wide) */}
      <div className="space-y-6">
        <div className="rounded border border-[#262626] bg-[#111111] p-5 h-[calc(100vh-140px)] flex flex-col justify-between">
          <div className="flex-1 flex flex-col min-h-0">
            <div className="border-b border-[#262626] pb-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-[#fafafa]">Chunk Inspector</span>
              {selectedDoc && (
                <span className="text-[10px] font-mono text-slate-500 uppercase">
                  {selectedDoc.chunks_count} chunks
                </span>
              )}
            </div>

            {loadingDetail ? (
              <div className="flex-1 flex items-center justify-center text-slate-500 font-mono text-xs">
                RETRIEVING CHUNKS...
              </div>
            ) : selectedDoc ? (
              <div className="flex-1 overflow-y-auto space-y-4 pr-1 mt-4">
                <div className="pb-1.5 border-b border-[#262626]/40">
                  <span className="text-[11px] font-semibold text-[#fafafa] block truncate font-mono">
                    {selectedDoc.title}
                  </span>
                  <span className="text-[9px] font-mono text-slate-500 uppercase block">
                    ID: {selectedDoc.id.substring(0, 8)}...
                  </span>
                </div>

                {selectedDoc.chunks.map((chunk, idx) => (
                  <div
                    key={chunk.id}
                    className="p-3 rounded border border-[#262626] bg-[#0a0a0a]/50 space-y-2 hover:border-slate-800 transition duration-150"
                  >
                    <div className="flex items-center justify-between text-[9px] font-mono text-slate-500">
                      <span>INDEX: #{chunk.chunk_index + 1}</span>
                      <span>SIZE: {chunk.content.length} chars</span>
                    </div>
                    <p className="text-xs text-[#a1a1aa] leading-relaxed font-sans select-all">
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-center p-4">
                <p className="text-slate-600 text-xs font-sans">
                  Select a document to inspect its parsed paragraphs.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
