"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

interface NavigationItem {
  name: string;
  href: string;
  section: "Build" | "Runtime";
  icon: React.ReactNode;
}

interface CommandItem {
  id: string;
  name: string;
  category: string;
  shortcut: string;
  action: () => void;
}

const iconClassName = "h-4 w-4";

const IconGrid = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 5.5A1.5 1.5 0 015.5 4h4A1.5 1.5 0 0111 5.5v4A1.5 1.5 0 019.5 11h-4A1.5 1.5 0 014 9.5v-4zM13 5.5A1.5 1.5 0 0114.5 4h4A1.5 1.5 0 0120 5.5v4a1.5 1.5 0 01-1.5 1.5h-4A1.5 1.5 0 0113 9.5v-4zM4 14.5A1.5 1.5 0 015.5 13h4a1.5 1.5 0 011.5 1.5v4A1.5 1.5 0 019.5 20h-4A1.5 1.5 0 014 18.5v-4zM13 14.5a1.5 1.5 0 011.5-1.5h4a1.5 1.5 0 011.5 1.5v4a1.5 1.5 0 01-1.5 1.5h-4a1.5 1.5 0 01-1.5-1.5v-4z" />
  </svg>
);

const IconArchive = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 8h16M6 8v10.5A1.5 1.5 0 007.5 20h9a1.5 1.5 0 001.5-1.5V8M8 8V5.5A1.5 1.5 0 019.5 4h5A1.5 1.5 0 0116 5.5V8M10 12h4" />
  </svg>
);

const IconBlueprint = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 4h6l4 4v12H7V4zM13 4v4h4M9.5 12h5M9.5 15h5" />
  </svg>
);

const IconSearch = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M20 20l-4.5-4.5M17.5 10.75a6.75 6.75 0 11-13.5 0 6.75 6.75 0 0113.5 0z" />
  </svg>
);

const IconPeople = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9.5 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM4 20a5.5 5.5 0 0111 0M16 11a3 3 0 100-6M17 15a5 5 0 013 5" />
  </svg>
);

const IconPlay = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M10 8.5v7l6-3.5-6-3.5z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const IconHint = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9.3 9a3 3 0 115.1 2.1c-.8.7-1.4 1.1-1.4 2.4M12 17h.01" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const IconChart = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M5 19V9M12 19V5M19 19v-7" />
  </svg>
);

const IconMenu = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

const IconClose = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M6 6l12 12M18 6L6 18" />
  </svg>
);

const navigationItems: NavigationItem[] = [
  { name: "Home", href: "/", section: "Build", icon: <IconGrid /> },
  { name: "Knowledge", href: "/knowledge", section: "Build", icon: <IconArchive /> },
  { name: "Blueprints", href: "/blueprints", section: "Build", icon: <IconBlueprint /> },
  { name: "Query", href: "/query", section: "Build", icon: <IconSearch /> },
  { name: "NPCs", href: "/npcs", section: "Runtime", icon: <IconPeople /> },
  { name: "Simulator", href: "/vertical-slice", section: "Runtime", icon: <IconPlay /> },
  { name: "Hints", href: "/hints", section: "Runtime", icon: <IconHint /> },
  { name: "Observability", href: "/analytics", section: "Runtime", icon: <IconChart /> },
];

const sections: NavigationItem["section"][] = ["Build", "Runtime"];

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const currentPage = useMemo(
    () => navigationItems.find((item) => isRouteActive(pathname, item.href)) ?? navigationItems[0],
    [pathname]
  );

  const commands: CommandItem[] = useMemo(
    () =>
      navigationItems.map((item) => ({
        id: item.href,
        name: item.name,
        category: item.section,
        shortcut: item.name === "Home" ? "G H" : `G ${item.name[0]}`,
        action: () => {
          router.push(item.href);
          setMobileNavOpen(false);
        },
      })),
    [router]
  );

  const filteredCommands = useMemo(
    () => commands.filter((cmd) => cmd.name.toLowerCase().includes(searchQuery.toLowerCase())),
    [commands, searchQuery]
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((prev) => !prev);
        setSearchQuery("");
        setActiveIndex(0);
        return;
      }

      if (event.key === "Escape") {
        setPaletteOpen(false);
        setMobileNavOpen(false);
        return;
      }

      if (!paletteOpen || filteredCommands.length === 0) return;

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((prev) => (prev + 1) % filteredCommands.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (event.key === "Enter") {
        event.preventDefault();
        filteredCommands[activeIndex]?.action();
        setPaletteOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeIndex, filteredCommands, paletteOpen]);

  const executeCommand = (index: number) => {
    filteredCommands[index]?.action();
    setPaletteOpen(false);
  };

  return (
    <div className="min-h-dvh bg-[#090b0e] text-[#f7f8fa] antialiased">
      <div className="flex min-h-dvh">
        <Sidebar pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b border-[#202832] bg-[#0d1116]/95 px-4 backdrop-blur sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-[#25303b] text-[#a5afbd] transition hover:border-[#3a4654] hover:text-[#f7f8fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] lg:hidden"
              >
                <IconMenu />
              </button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-[#f7f8fa]">{currentPage.name}</p>
                <p className="mt-0.5 hidden text-xs text-[#7c8794] sm:block">
                  Local-first AI game builder, running at zero model cost.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPaletteOpen(true)}
                className="hidden h-10 w-72 items-center justify-between rounded-md border border-[#25303b] bg-[#0a0e12] px-3 text-left text-xs text-[#8b96a5] transition hover:border-[#3a4654] hover:text-[#f7f8fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0] md:flex"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconSearch />
                  <span className="truncate">Search pages</span>
                </span>
                <kbd className="rounded border border-[#25303b] bg-[#111820] px-1.5 py-0.5 text-[10px] font-semibold text-[#c3cad4]">
                  Ctrl K
                </kbd>
              </button>
              <div className="hidden items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 sm:flex">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
                Connected
              </div>
            </div>
          </header>

          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            onClick={() => setMobileNavOpen(false)}
            className="absolute inset-0 bg-black/70"
          />
          <div className="relative h-full w-[min(22rem,88vw)] border-r border-[#202832] bg-[#0d1116] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#202832] px-5 py-4">
              <Brand />
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
                className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-[#25303b] text-[#a5afbd] transition hover:border-[#3a4654] hover:text-[#f7f8fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
              >
                <IconClose />
              </button>
            </div>
            <Navigation pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      {paletteOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 px-4 pt-20 backdrop-blur-sm sm:pt-24">
          <div className="flex max-h-[28rem] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-[#27303a] bg-[#10161d] shadow-2xl">
            <div className="flex items-center gap-3 border-b border-[#27303a] px-4 py-3">
              <span className="text-[#7c8794]">
                <IconSearch />
              </span>
              <input
                type="text"
                placeholder="Search pages..."
                value={searchQuery}
                onChange={(event) => {
                  setSearchQuery(event.target.value);
                  setActiveIndex(0);
                }}
                className="h-10 flex-1 bg-transparent text-sm text-[#f7f8fa] outline-none placeholder:text-[#6f7a87]"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setPaletteOpen(false)}
                aria-label="Close command palette"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md text-[#7c8794] transition hover:bg-[#18212b] hover:text-[#f7f8fa] focus:outline-none focus:ring-2 focus:ring-[#8bdff0]"
              >
                <IconClose />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {filteredCommands.length === 0 ? (
                <div className="py-12 text-center">
                  <p className="text-sm font-semibold text-[#f7f8fa]">No matching page</p>
                  <p className="mt-1 text-xs text-[#7c8794]">&quot;{searchQuery}&quot; is not in the workspace.</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {filteredCommands.map((cmd, index) => {
                    const isActive = index === activeIndex;

                    return (
                      <button
                        key={cmd.id}
                        type="button"
                        onClick={() => executeCommand(index)}
                        onMouseEnter={() => setActiveIndex(index)}
                        className={`flex min-h-11 w-full items-center justify-between rounded-md px-3 text-left text-sm transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0] ${
                          isActive
                            ? "bg-[#1a242e] text-[#f7f8fa]"
                            : "text-[#a5afbd] hover:bg-[#151d25] hover:text-[#f7f8fa]"
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-3">
                          <span className="text-[#7c8794]">
                            {navigationItems.find((item) => item.href === cmd.id)?.icon}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate font-semibold">{cmd.name}</span>
                            <span className="block text-xs text-[#6f7a87]">{cmd.category}</span>
                          </span>
                        </span>
                        <span className="rounded border border-[#27303a] bg-[#0b1015] px-1.5 py-0.5 text-[10px] font-semibold text-[#8b96a5]">
                          {cmd.shortcut}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-[#27303a] bg-[#0b1015] px-3 py-2 text-[10px] font-medium text-[#7c8794]">
              <span>Arrow keys to move</span>
              <span>Esc to close</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Sidebar({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-[#202832] bg-[#0d1116] lg:flex lg:flex-col">
      <div className="border-b border-[#202832] px-5 py-5">
        <Brand />
      </div>
      <Navigation pathname={pathname} onNavigate={onNavigate} />
      <div className="border-t border-[#202832] px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6f7a87]">Mode</p>
        <div className="mt-3 rounded-md border border-[#25303b] bg-[#0a0e12] p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-semibold text-[#f7f8fa]">Local demo</span>
            <span className="rounded-full bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold text-emerald-300">
              $0
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-[#7c8794]">Chroma retrieval and deterministic generation.</p>
        </div>
      </div>
    </aside>
  );
}

function Brand() {
  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#25303b] bg-[#101820] text-sm font-semibold text-[#f7f8fa]">
          G
        </span>
        <div>
          <p className="text-sm font-semibold leading-none text-[#f7f8fa]">GameMind</p>
          <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#7c8794]">
            AI game builder
          </p>
        </div>
      </div>
    </div>
  );
}

function Navigation({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  return (
    <nav className="flex-1 overflow-y-auto px-3 py-5">
      {sections.map((section) => (
        <div key={section} className="mb-7 last:mb-0">
          <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#647080]">{section}</p>
          <div className="mt-3 space-y-1">
            {navigationItems
              .filter((item) => item.section === section)
              .map((item) => {
                const active = isRouteActive(pathname, item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={`group flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[#8bdff0] ${
                      active
                        ? "bg-[#151d25] text-[#f7f8fa]"
                        : "text-[#8b96a5] hover:bg-[#121922] hover:text-[#f7f8fa]"
                    }`}
                  >
                    <span className={active ? "text-[#8bdff0]" : "text-[#647080] group-hover:text-[#a5afbd]"}>
                      {item.icon}
                    </span>
                    <span>{item.name}</span>
                  </Link>
                );
              })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function isRouteActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
