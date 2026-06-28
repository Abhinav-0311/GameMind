"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

interface CommandItem {
  id: string;
  name: string;
  category: string;
  shortcut: string;
  action: () => void;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  
  // Command Palette State
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const workspaceItems = [
    { name: "Workspace", href: "/", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    )},
    { name: "Knowledge Base", href: "/knowledge", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    )},
    { name: "Query Studio", href: "/query", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    )},
    { name: "NPC Studio", href: "/npcs", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )},
    { name: "Observability", href: "/analytics", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    )},
    { name: "Hint Studio", href: "/hints", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )},
    { name: "Blueprint Studio", href: "/blueprints", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )},
    { name: "Narrative Simulator", href: "/vertical-slice", icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )},
  ];

  const futureItems = [
    { name: "Quest Studio", label: "R3" },
    { name: "Settings", label: "R4" },
  ];

  // Command palette actions
  const commands: CommandItem[] = [
    { id: "g-workspace", name: "Go to Workspace Overview", category: "Navigation", shortcut: "G W", action: () => router.push("/") },
    { id: "g-knowledge", name: "Go to Knowledge Base", category: "Navigation", shortcut: "G K", action: () => router.push("/knowledge") },
    { id: "g-query", name: "Go to Query Studio", category: "Navigation", shortcut: "G Q", action: () => router.push("/query") },
    { id: "g-npcs", name: "Go to NPC Studio", category: "Navigation", shortcut: "G N", action: () => router.push("/npcs") },
    { id: "g-observability", name: "Go to Observability Dashboard", category: "Navigation", shortcut: "G O", action: () => router.push("/analytics") },
    { id: "g-hints", name: "Go to Hint Studio", category: "Navigation", shortcut: "G H", action: () => router.push("/hints") },
    { id: "g-blueprints", name: "Go to Blueprint Studio", category: "Navigation", shortcut: "G B", action: () => router.push("/blueprints") },
    { id: "g-simulator", name: "Go to Narrative Simulator", category: "Navigation", shortcut: "G S", action: () => router.push("/vertical-slice") },
  ];

  const filteredCommands = commands.filter((cmd) =>
    cmd.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
        setSearchQuery("");
        setActiveIndex(0);
      }
      
      if (e.key === "Escape" && paletteOpen) {
        setPaletteOpen(false);
      }

      if (paletteOpen && filteredCommands.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setActiveIndex((prev) => (prev + 1) % filteredCommands.length);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setActiveIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
        } else if (e.key === "Enter") {
          e.preventDefault();
          if (filteredCommands[activeIndex]) {
            filteredCommands[activeIndex].action();
            setPaletteOpen(false);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [paletteOpen, activeIndex, filteredCommands]);

  const executeCommand = (index: number) => {
    if (filteredCommands[index]) {
      filteredCommands[index].action();
      setPaletteOpen(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-[#fafafa] font-sans antialiased overflow-hidden">
      {/* Sidebar - Linear Style */}
      <aside className="w-60 border-r border-[#262626] bg-[#111111] flex flex-col justify-between select-none z-25">
        <div className="flex-1 flex flex-col min-h-0">
          {/* Header branding */}
          <div className="h-14 border-b border-[#262626] px-4 flex items-center justify-between">
            <div className="flex flex-col justify-center">
              <span className="font-bold text-sm text-[#fafafa] tracking-tight leading-none">
                GameMind
              </span>
              <span className="text-[9px] font-mono text-[#a1a1aa] block mt-1 uppercase tracking-wider font-semibold">
                AI Narrative Platform
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-500 font-bold border border-[#262626] bg-[#0a0a0a] px-1.5 py-0.5 rounded">
              v1.0.0
            </span>
          </div>

          {/* Navigation Links */}
          <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
            {/* Workspace section */}
            <div className="space-y-1">
              <span className="px-3 text-[10px] font-mono font-bold text-[#a1a1aa] tracking-widest uppercase block mb-2">
                Workspace
              </span>
              {workspaceItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`flex items-center justify-between px-3 py-1.5 rounded-md text-xs font-medium transition duration-150 ${
                      isActive
                        ? "bg-[#171717] text-[#fafafa] font-semibold border border-[#262626]"
                        : "text-[#a1a1aa] hover:text-[#fafafa] hover:bg-[#171717]/50 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <span className={isActive ? "text-[#fafafa]" : "text-[#a1a1aa]"}>
                        {item.icon}
                      </span>
                      <span>{item.name}</span>
                    </div>
                    {isActive && (
                      <span className="h-1 w-1 rounded-full bg-[#b9ff66]" />
                    )}
                  </Link>
                );
              })}
            </div>

            {/* Studios (Future Releases Placeholder) */}
            <div className="space-y-1">
              <span className="px-3 text-[10px] font-mono font-bold text-[#a1a1aa] tracking-widest uppercase block mb-2">
                Studios
              </span>
              {futureItems.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between px-3 py-1.5 rounded-md text-xs text-slate-600 border border-transparent select-none cursor-not-allowed"
                >
                  <span>{item.name}</span>
                  <span className="text-[8px] font-mono bg-[#171717] px-1 rounded border border-[#262626] text-slate-500">
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Flat Bottom Health Status */}
        <div className="p-3 border-t border-[#262626] space-y-2 bg-[#0d0d0d]">
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
            <span>DATABASE STATE</span>
            <div className="flex items-center gap-1.5 font-sans">
              <span className="text-emerald-400 text-[10px]">●</span>
              <span className="text-[#fafafa] font-mono text-[9px] uppercase tracking-wide">connected</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Viewport */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Command Bar */}
        <header className="h-14 border-b border-[#262626] bg-[#111111] flex items-center justify-between px-6 z-10 select-none">
          {/* Vercel/Linear style Command Search Bar */}
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center justify-between w-96 px-3 py-1.5 rounded-md border border-[#262626] bg-[#0a0a0a] hover:border-slate-800 transition text-xs text-[#a1a1aa] font-sans"
          >
            <div className="flex items-center gap-2">
              <svg className="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Search lore, documents, commands...</span>
            </div>
            <kbd className="bg-[#171717] border border-[#262626] rounded px-1.5 py-0.5 text-[9px] font-mono text-[#fafafa] select-none">
              Ctrl K
            </kbd>
          </button>
          
          <div className="flex items-center gap-2 text-[10px] font-mono text-[#a1a1aa]">
            <span className="text-emerald-500">●</span>
            <span className="text-[#fafafa]">Connected</span>
          </div>
        </header>

        {/* Content Panel Scrollable */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#0a0a0a]">{children}</main>
      </div>

      {/* Raycast-style Command Palette Modal */}
      {paletteOpen && (
        <div className="fixed inset-0 z-50 bg-[#000000]/70 flex items-start justify-center pt-28 px-4 backdrop-blur-[1px]">
          <div className="w-full max-w-lg bg-[#171717] border border-[#262626] rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[380px]">
            {/* Search Input */}
            <div className="p-3 border-b border-[#262626] flex items-center gap-2">
              <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search workspaces, documents, or execute actions..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setActiveIndex(0);
                }}
                className="flex-1 bg-transparent text-sm text-[#fafafa] placeholder-slate-500 outline-none border-none py-1"
                autoFocus
              />
            </div>

            {/* List of actions */}
            <div className="flex-1 overflow-y-auto p-2">
              {filteredCommands.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-xs font-mono">
                  No commands matching &quot;{searchQuery}&quot;
                </div>
              ) : (
                <div className="space-y-1">
                  {filteredCommands.map((cmd, idx) => {
                    const isActive = idx === activeIndex;
                    return (
                      <button
                        key={cmd.id}
                        onClick={() => executeCommand(idx)}
                        onMouseEnter={() => setActiveIndex(idx)}
                        className={`w-full text-left px-3 py-2 rounded-md text-xs transition duration-150 flex items-center justify-between ${
                          isActive
                            ? "bg-[#262626] text-[#fafafa]"
                            : "text-[#a1a1aa] hover:bg-[#262626]/40"
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-[10px] font-mono text-slate-500 uppercase font-bold">
                            {cmd.category}
                          </span>
                          <span>{cmd.name}</span>
                        </div>
                        <span className="bg-[#0a0a0a] border border-[#262626] rounded px-1.5 py-0.5 text-[9px] font-mono text-[#a1a1aa]">
                          {cmd.shortcut}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer tips */}
            <div className="p-2.5 bg-[#111111] border-t border-[#262626] flex items-center justify-between text-[9px] font-mono text-slate-500">
              <div className="flex items-center gap-3">
                <span>↑↓ to navigate</span>
                <span>·</span>
                <span>enter to select</span>
              </div>
              <span>esc to close</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
