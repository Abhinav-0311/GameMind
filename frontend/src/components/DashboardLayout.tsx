"use client";

import React, { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, getActiveProjectId, setActiveProjectId, subscribeToProjectChange, type GameProject } from "@/lib/api";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

interface NavigationItem {
  name: string;
  href: string;
  section: "Build" | "Test";
  icon: React.ReactNode;
}

interface CommandItem {
  id: string;
  name: string;
  category: string;
  shortcut: string;
  action: () => void;
}

interface CommandNavigationItem {
  name: string;
  href: string;
  category: "Build" | "Test" | "Support";
  shortcut: string;
  icon: React.ReactNode;
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

const IconDecisions = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M8 5.5h9.5M8 10.5h9.5M8 15.5h5.5M4.5 5.5h.01M4.5 10.5h.01M4.5 15.5h.01" />
  </svg>
);

const IconSearch = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M20 20l-4.5-4.5M17.5 10.75a6.75 6.75 0 11-13.5 0 6.75 6.75 0 0113.5 0z" />
  </svg>
);

const IconPlay = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M10 8.5v7l6-3.5-6-3.5z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const IconPeople = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M8.5 11a3 3 0 100-6 3 3 0 000 6zM15.5 10a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3.5 19.5c.7-3 2.4-4.5 5-4.5s4.3 1.5 5 4.5M13.2 15.2c2.8-.2 4.8 1.2 5.5 4.3" />
  </svg>
);

const IconChart = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 19.5V5.5M4 19.5h16M8 16v-4M12 16V8M16 16v-7" />
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

const IconMoon = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M20 15.5A8.5 8.5 0 018.5 4 7 7 0 1020 15.5z" />
  </svg>
);

const IconSun = () => (
  <svg className={iconClassName} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4V2.5M12 21.5V20M4 12H2.5M21.5 12H20M17.66 6.34l1.06-1.06M5.28 18.72l1.06-1.06M6.34 6.34 5.28 5.28M18.72 18.72l-1.06-1.06M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
  </svg>
);

const navigationItems: NavigationItem[] = [
  { name: "Home", href: "/", section: "Build", icon: <IconGrid /> },
  { name: "Sources", href: "/knowledge", section: "Build", icon: <IconArchive /> },
  { name: "Decisions", href: "/decisions", section: "Build", icon: <IconDecisions /> },
  { name: "Blueprints", href: "/blueprints", section: "Build", icon: <IconBlueprint /> },
  { name: "Lore Search", href: "/query", section: "Test", icon: <IconSearch /> },
  { name: "Runtime Test", href: "/vertical-slice", section: "Test", icon: <IconPlay /> },
];

const commandNavigationItems: CommandNavigationItem[] = [
  ...navigationItems.map((item) => ({
    name: item.name,
    href: item.href,
    category: item.section,
    shortcut: item.name === "Home" ? "G H" : `G ${item.name[0]}`,
    icon: item.icon,
  })),
  { name: "NPC Studio", href: "/npcs", category: "Support", shortcut: "G N", icon: <IconPeople /> },
  { name: "Hint Studio", href: "/hints", category: "Support", shortcut: "G I", icon: <IconPlay /> },
  { name: "Diagnostics", href: "/analytics", category: "Support", shortcut: "G D", icon: <IconChart /> },
];

const sections: NavigationItem["section"][] = ["Build", "Test"];
const themeStorageKey = "gamemind-theme";
const themeChangeEvent = "gamemind-theme-change";

function getStoredTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.localStorage.getItem(themeStorageKey) === "dark" ? "dark" : "light";
}

function subscribeToThemeChange(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(themeChangeEvent, callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(themeChangeEvent, callback);
  };
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const theme = useSyncExternalStore(subscribeToThemeChange, getStoredTheme, () => "light");
  const activeProjectId = useSyncExternalStore(subscribeToProjectChange, getActiveProjectId, () => "default_project");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [projects, setProjects] = useState<GameProject[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);

  const currentPage = useMemo(
    () => navigationItems.find((item) => isRouteActive(pathname, item.href)) ?? navigationItems[0],
    [pathname]
  );
  const pageTitle =
    pathname === "/hints"
      ? "Hint Studio"
      : pathname === "/analytics"
        ? "Diagnostics"
        : pathname === "/npcs"
          ? "NPC Studio"
          : currentPage.name;

  const commands: CommandItem[] = useMemo(
    () =>
      commandNavigationItems.map((item) => ({
        id: item.href,
        name: item.name,
        category: item.category,
        shortcut: item.shortcut,
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
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    let active = true;

    api
      .getProjects()
      .then((loadedProjects) => {
        if (!active) return;
        setProjects(loadedProjects);
        if (!loadedProjects.some((project) => project.id === activeProjectId)) {
          setActiveProjectId("default_project");
        }
      })
      .catch((error: unknown) => {
        if (active) setProjectError(error instanceof Error ? error.message : "Could not load workspaces.");
      })
      .finally(() => {
        if (active) setProjectsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activeProjectId]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    window.localStorage.setItem(themeStorageKey, nextTheme);
    window.dispatchEvent(new Event(themeChangeEvent));
  };

  const selectProject = (projectId: string) => {
    setActiveProjectId(projectId);
    setProjectError(null);
  };

  const createProject = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newProjectName.trim();
    if (!name) return;

    setCreatingProject(true);
    setProjectError(null);
    try {
      const project = await api.createProject(name);
      setProjects((current) => [...current, project]);
      setActiveProjectId(project.id);
      setNewProjectName("");
      setProjectDialogOpen(false);
    } catch (error: unknown) {
      setProjectError(error instanceof Error ? error.message : "Could not create workspace.");
    } finally {
      setCreatingProject(false);
    }
  };

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
    <div className="min-h-dvh bg-[var(--background)] text-[var(--foreground)] antialiased">
      <div className="flex min-h-dvh">
        <Sidebar pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--background)]/88 px-4 backdrop-blur-xl sm:px-5 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] lg:hidden"
              >
                <IconMenu />
              </button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold leading-none text-[var(--foreground)]">{pageTitle}</p>
                <p className="mt-1 hidden text-xs text-[var(--text-secondary)] sm:block">Zero-cost local game builder</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 lg:flex">
                <label className="sr-only" htmlFor="active-project">
                  Active workspace
                </label>
                <select
                  id="active-project"
                  value={activeProjectId}
                  onChange={(event) => selectProject(event.target.value)}
                  disabled={projectsLoading || projects.length === 0}
                  className="h-10 max-w-44 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-xs font-semibold text-[var(--foreground)] outline-none transition hover:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
                  title={projectError || "Active workspace"}
                >
                  {projectsLoading ? <option>Loading workspace</option> : null}
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setProjectDialogOpen(true)}
                  className="btn-secondary h-10 whitespace-nowrap px-3 text-xs"
                >
                  New project
                </button>
              </div>
              <button
                type="button"
                onClick={() => setPaletteOpen(true)}
                className="hidden h-10 w-72 items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-left text-xs text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] xl:flex"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconSearch />
                  <span className="truncate">Search pages</span>
                </span>
                <kbd className="rounded-lg border border-[var(--border)] bg-[var(--card-muted)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-secondary)]">
                  Ctrl K
                </kbd>
              </button>
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                className="inline-flex h-10 min-w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                <span className="sm:hidden">{theme === "dark" ? <IconSun /> : <IconMoon />}</span>
                <span className="hidden items-center gap-2 sm:flex">
                  {theme === "dark" ? <IconSun /> : <IconMoon />}
                  {theme === "dark" ? "Light" : "Dark"}
                </span>
              </button>
              <div className="hidden items-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--green)_28%,transparent)] bg-[color-mix(in_srgb,var(--green)_12%,transparent)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground)] sm:flex">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--green)]" />
                Connected
              </div>
            </div>
          </header>

          <main key={activeProjectId} className="flex-1 px-4 py-8 sm:px-6 lg:px-10">{children}</main>
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
          <div className="relative h-full w-[min(22rem,88vw)] border-r border-[var(--border)] bg-[var(--sidebar)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <Brand />
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--text-secondary)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                <IconClose />
              </button>
            </div>
            <div className="border-b border-[var(--border)] px-5 py-4">
              <label className="page-kicker" htmlFor="mobile-active-project">Active workspace</label>
              <select
                id="mobile-active-project"
                value={activeProjectId}
                onChange={(event) => selectProject(event.target.value)}
                disabled={projectsLoading || projects.length === 0}
                className="mt-2 h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm font-semibold text-[var(--foreground)] outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {projectsLoading ? <option>Loading workspace</option> : null}
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  setMobileNavOpen(false);
                  setProjectDialogOpen(true);
                }}
                className="btn-secondary mt-3 w-full"
              >
                New project
              </button>
            </div>
            <Navigation pathname={pathname} onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      {paletteOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/40 px-4 pt-20 backdrop-blur-sm sm:pt-24">
          <div className="flex max-h-[28rem] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
            <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <span className="text-[var(--text-secondary)]">
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
                className="h-10 flex-1 bg-transparent text-sm text-[var(--foreground)] outline-none placeholder:text-[var(--text-tertiary)]"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setPaletteOpen(false)}
                aria-label="Close command palette"
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-[var(--text-secondary)] transition hover:bg-[var(--card-muted)] hover:text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                <IconClose />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {filteredCommands.length === 0 ? (
                <div className="py-12 text-center">
                  <p className="text-sm font-semibold text-[var(--foreground)]">No matching page</p>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">&quot;{searchQuery}&quot; is not in the workspace.</p>
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
                        className={`flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
                          isActive
                            ? "bg-[var(--accent-soft)] text-[var(--foreground)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--card-muted)] hover:text-[var(--foreground)]"
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-3">
                          <span className="text-[var(--text-secondary)]">
                          {commandNavigationItems.find((item) => item.href === cmd.id)?.icon}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate font-semibold">{cmd.name}</span>
                            <span className="block text-xs text-[var(--text-tertiary)]">{cmd.category}</span>
                          </span>
                        </span>
                        <span className="rounded-lg border border-[var(--border)] bg-[var(--card-muted)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-secondary)]">
                          {cmd.shortcut}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-[var(--border)] bg-[var(--card-muted)] px-3 py-2 text-[10px] font-medium text-[var(--text-secondary)]">
              <span>Arrow keys to move</span>
              <span>Esc to close</span>
            </div>
          </div>
        </div>
      )}

      {projectDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm" role="presentation">
          <button
            type="button"
            aria-label="Close new project dialog"
            onClick={() => !creatingProject && setProjectDialogOpen(false)}
            className="absolute inset-0"
          />
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-project-title"
            className="relative w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl"
          >
            <p className="page-kicker">New workspace</p>
            <h2 id="new-project-title" className="mt-3 text-2xl font-semibold text-[var(--foreground)]">
              Name your game project.
            </h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              Sources, blueprints, searches, and runtime data will stay separate from your other projects.
            </p>
            <form className="mt-6" onSubmit={createProject}>
              <label htmlFor="new-project-name" className="mb-2 block text-sm font-semibold text-[var(--foreground)]">
                Project name
              </label>
              <input
                id="new-project-name"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                maxLength={100}
                minLength={2}
                required
                autoFocus
                placeholder="e.g. Moonlit Citadel"
                className="h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--foreground)] outline-none placeholder:text-[var(--text-tertiary)] focus:ring-2 focus:ring-[var(--accent)]"
              />
              {projectError && <p className="mt-3 text-sm text-rose-700" role="alert">{projectError}</p>}
              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setProjectDialogOpen(false)}
                  disabled={creatingProject}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </button>
                <button type="submit" disabled={creatingProject || newProjectName.trim().length < 2} className="btn-primary disabled:cursor-not-allowed disabled:opacity-50">
                  {creatingProject ? "Creating" : "Create project"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

function Sidebar({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  return (
    <aside className="sticky top-0 hidden h-dvh w-[220px] shrink-0 border-r border-[var(--border)] bg-[var(--sidebar)] lg:flex lg:flex-col">
      <div className="border-b border-[var(--border)] px-5 py-5">
        <Brand />
      </div>
      <Navigation pathname={pathname} onNavigate={onNavigate} />
    </aside>
  );
}

function Brand() {
  return (
    <Link href="/" className="group flex items-center gap-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-[var(--accent)]">
      <Image
        src="/brand/gamemind-icon.svg"
        alt=""
        aria-hidden="true"
        width={40}
        height={40}
        className="h-10 w-10 rounded-[0.7rem]"
      />
        <div>
          <p className="text-[1.05rem] font-semibold leading-none tracking-normal text-[var(--foreground)] transition">GameMind</p>
          <p className="mt-1.5 font-mono text-[10px] font-semibold uppercase tracking-normal text-[var(--text-secondary)]">
            Guided game builder
          </p>
        </div>
    </Link>
  );
}

function Navigation({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  return (
    <nav className="flex-1 overflow-y-auto px-3 py-5">
      {sections.map((section) => (
        <div key={section} className="mb-7 last:mb-0">
          <p className="px-3 font-mono text-[10px] font-semibold uppercase tracking-normal text-[var(--text-tertiary)]">{section}</p>
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
                    className={`group flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
                      active
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--card-muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    <span className={active ? "text-[var(--accent)]" : "text-[var(--text-tertiary)] group-hover:text-[var(--text-secondary)]"}>
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
