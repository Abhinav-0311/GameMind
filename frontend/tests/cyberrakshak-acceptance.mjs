// Opt-in LIVE acceptance: creates only a new isolated workspace; may call NVIDIA.
// Run with CYBER_ACCEPTANCE_DIR pointing to a new evidence-output directory.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { randomUUID } from "node:crypto";

const mode = process.argv[2] || "capture";
const output = process.env.CYBER_ACCEPTANCE_DIR;
assert.ok(output, "Set CYBER_ACCEPTANCE_DIR explicitly; live acceptance is opt-in.");
const base = process.env.CYBER_ACCEPTANCE_URL || "http://localhost:8000";
assert.ok(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Only the local backend is supported.");
const save = async (name, value) => writeFile(join(output, name), JSON.stringify(value, null, 2) + "\n");
let metadata;
async function request(path, { method = "GET", body, scoped = true } = {}) {
  const headers = {};
  if (scoped) { assert.ok(metadata?.project?.id); headers["X-Game-Project-ID"] = metadata.project.id; }
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const started = performance.now();
  const response = await fetch(base + path, { method, headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(900_000), redirect: "error" });
  const content = await response.text();
  let value; try { value = JSON.parse(content); } catch { value = { text: content }; }
  return { status: response.status, milliseconds: Math.round(performance.now() - started), value };
}
async function capture(label) {
  const runs = await request("/api/v1/design-agent/runs");
  assert.equal(runs.status, 200); await save(`${label}-runs.json`, runs.value);
  const run = runs.value.find((item) => item.id === metadata.run_id) || runs.value[0];
  if (!run) return;
  metadata.run_id = run.id; await save("metadata.json", metadata);
  await save(`${label}-run.json`, run);
  const trace = await request(`/api/v1/design-agent/runs/${run.id}/trace`);
  assert.equal(trace.status, 200); await save(`${label}-trace.json`, trace.value);
  const exports = {};
  for (const format of ["technical-brief", "runtime"]) {
    const result = await request(`/api/v1/design-agent/runs/${run.id}/exports/${format}`);
    exports[format] = result;
  }
  await save(`${label}-exports.json`, exports);
  console.log(JSON.stringify({ stage: label, workspace: metadata.project.id, run: run.id,
    status: run.status, degraded: run.degraded, revision: run.revision_count,
    quality: run.critique?.content?.quality_scorecard,
    nodes: trace.value.items.map((item) => ({ node: item.node_name, status: item.status,
      provider: item.provider_name, model: item.model_name, milliseconds: item.latency_ms,
      metadata: item.details, error: item.error })) }));
}
if (mode === "start") {
  assert.equal(process.env.CYBER_ACCEPTANCE_HOSTED_CONSENT, "yes", "Explicit NVIDIA consent is required.");
  await mkdir(output, { recursive: false });
  const name = `QA CyberRakshak ${new Date().toISOString().slice(0, 10)} ${randomUUID().slice(0, 8)}`;
  const created = await request("/api/v1/projects/", { method: "POST", body: { name }, scoped: false });
  assert.equal(created.status, 201);
  metadata = { project: created.value, started_at: new Date().toISOString(), source_ids: [], hosted_consent: true };
  await save("metadata.json", metadata); console.log(`Created isolated workspace: ${metadata.project.id}`);
  for (const name of ["cyberrakshak_gdd.md"]) {
    const source = await readFile(resolve("../docs/demo", name));
    const form = new FormData(); form.append("file", new Blob([source], { type: "text/markdown" }), name); form.append("source_kind", "gdd");
    const uploaded = await request("/api/v1/documents/upload", { method: "POST", body: form });
    assert.equal(uploaded.status, 201); metadata.source_ids.push(uploaded.value.id);
    await save("metadata.json", metadata); await save(`source-${uploaded.value.id}.json`, (await request(`/api/v1/documents/${uploaded.value.id}`)).value);
    console.log(`Indexed ${name}: ${uploaded.value.chunks_count} chunks; ${uploaded.milliseconds}ms`);
  }
  const payload = { objective: "Create a grounded developer-ready CyberRakshak design draft. Prioritize PATCH's short funny warning-based dialogue and early Training Sandbox or Password Vault quests. Provide ordered objectives, failure states, source-supported dependencies and rewards, and concrete integration steps. Do not invent engine IDs or numerical rewards. Mark creative dialogue and unsupported quest details as proposals requiring approval. Preserve Jay's early supervisor role and the Level 9 reveal followed by Level 10 Hunt Jay.", document_ids: metadata.source_ids, max_revisions: 2 };
  const denied = await request("/api/v1/design-agent/runs", { method: "POST", body: payload });
  assert.equal(denied.status, 409); assert.match(denied.value.detail, /Explicit consent/);
  await save("consent-denied.json", denied); console.log("Verified: missing hosted consent blocks generation.");
  console.log("Starting live NVIDIA generation and critique; no approval or materialization will occur automatically.");
  const result = await request("/api/v1/design-agent/runs", { method: "POST", body: { ...payload, hosted_provider_consent: true } });
  await save("start-response.json", result);
  if (result.value.id) metadata.run_id = result.value.id;
  await save("metadata.json", metadata); await capture("initial");
  assert.equal(result.status, 201, "Live workflow did not produce a reviewable artifact; inspect the saved trace.");
} else {
  metadata = JSON.parse(await readFile(join(output, "metadata.json"), "utf8"));
  assert.ok(metadata.project.id.startsWith("qa-cyberrakshak-"), "Refusing to mutate a non-QA workspace.");
  if (mode === "preview") {
    const observed = await request("/api/v1/design-agent/runs");
    assert.equal(observed.status, 200);
    const observedRun = observed.value.find((item) => item.id === metadata.run_id);
    assert.ok(["failed", "awaiting_review"].includes(observedRun?.status), "Only failed or review-paused runs are supported.");
    const observedTrace = await request(`/api/v1/design-agent/runs/${metadata.run_id}/trace`);
    assert.equal(observedTrace.status, 200);
    const latestFailure = observedTrace.value.items.filter((item) => item.status === "failed").at(-1);
    if (observedRun.status === "failed") assert.ok(latestFailure?.error, "A failed run must expose a diagnostic trace.");
    else {
      assert.ok(observedRun.current_artifact && observedRun.critique);
      assert.equal(observedRun.degraded, false);
      assert.equal(observedRun.critique.content.quality_scorecard.passed, false, "This check expects a blocked draft, not approved content.");
    }
    const browserLabel = observedRun.status === "failed" ? `failed-attempt-${latestFailure.attempt}` : `draft-v${observedRun.current_artifact.version}`;
    const { chromium } = await import("playwright");
    const browser = await chromium.launch({ headless: true, args: ["--disable-logging"] });
    const checks = [];
    try {
      for (const [width, theme] of [[1440, "light"], [768, "light"], [375, "dark"]]) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage(); const violations = [], crashes = [];
        page.on("pageerror", (error) => crashes.push(error.message));
        await context.addInitScript(({ workspace, theme }) => {
          localStorage.setItem("gamemind-active-project", workspace);
          localStorage.setItem("gamemind-theme", theme);
        }, { workspace: metadata.project.id, theme });
        await context.route("**/*", async (route) => {
          const request = route.request(); const url = new URL(request.url());
          if (url.origin === "https://fonts.googleapis.com" && url.pathname === "/css2") return route.fulfill({ status: 200, contentType: "text/css", body: "" });
          if (!["http://localhost:3000", new URL(base).origin].includes(url.origin) || !["GET", "OPTIONS"].includes(request.method())) {
            violations.push(`${request.method()} ${url.origin}${url.pathname}`); return route.abort();
          }
          if (url.pathname.startsWith("/api/v1/") && !url.pathname.startsWith("/api/v1/auth/") && url.pathname !== "/api/v1/projects/"
            && request.headers()["x-game-project-id"] !== metadata.project.id) violations.push(`Wrong workspace: ${url.pathname}`);
          return route.continue();
        });
        await page.goto("http://localhost:3000/design-agent");
        if (observedRun.status === "failed") {
          await page.getByText("Review failed", { exact: true }).waitFor({ state: "visible" });
          assert.equal(await page.getByRole("button", { name: /^(Approve run|Approval blocked|Finalizing…)$/ }).count(), 0);
        } else {
          const blocked = page.getByRole("button", { name: "Approval blocked", exact: true });
          await blocked.waitFor({ state: "visible" }); assert.equal(await blocked.isDisabled(), true);
          await page.getByRole("button", { name: "Request revision", exact: true }).waitFor({ state: "visible" });
          await page.getByRole("region", { name: "Pre-approval quality scorecard" }).waitFor({ state: "visible" });
        }
        if (observedRun.current_artifact) {
          await page.getByRole("tab", { name: "NPCs", exact: true }).click();
          for (const npc of observedRun.current_artifact.content.npc_archetypes.content.npcs) await page.getByText(npc.name, { exact: true }).waitFor({ state: "visible" });
          await page.getByRole("tab", { name: "Quests", exact: true }).click();
          for (const quest of observedRun.current_artifact.content.quest_hooks.content.quests) await page.getByText(quest.title, { exact: true }).waitFor({ state: "visible" });
        }
        assert.equal(await page.getByRole("button", { name: "Download runtime JSON", exact: true }).count(), 0);
        await page.locator("summary").filter({ hasText: "Workflow trace" }).click();
        if (observedRun.status === "failed") await page.getByText(latestFailure.error, { exact: true }).first().waitFor({ state: "visible" });
        if (observedRun.current_artifact) await page.getByText(/openai\/gpt-oss-20b/).first().waitFor({ state: "visible" });
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: join(output, `live-${browserLabel}-${theme}-${width}.png`), fullPage: true });
        await page.goto("http://localhost:3000/knowledge");
        for (const [start, end] of [[1, 6], [7, 12], [13, 17]]) {
          await page.getByText(`Chunks ${start}–${end} of 17`, { exact: true }).waitFor({ state: "visible" });
          assert.equal(await page.locator('[id^="source-chunk-"]').count(), end - start + 1);
          if (end < 17) await page.getByRole("button", { name: "Next chunks", exact: true }).click();
        }
        assert.deepEqual(violations, []); assert.deepEqual(crashes, []);
        checks.push({ width, theme, actual_backend: true, source_chunks_reachable: 17, status: observedRun.status,
          approval_unavailable: true, latest_failure: observedRun.status === "failed" ? latestFailure.error : null, writes: 0 });
        await context.close();
      }
    } finally { await browser.close(); }
    await save(`live-browser-${browserLabel}.json`, checks); console.log(JSON.stringify({ live_browser: checks }));
  } else if (mode === "revise") {
    assert.equal(process.env.CYBER_ACCEPTANCE_HOSTED_CONSENT, "yes");
    const reasonPath = process.argv[3]; assert.ok(reasonPath, "Provide an explicit review-reason file.");
    const target_sections = process.argv.slice(4);
    assert.ok(target_sections.length > 0, "Provide explicit blueprint section IDs after the reason file.");
    const reason = (await readFile(reasonPath, "utf8")).trim(); assert.ok(reason.length > 0);
    const result = await request(`/api/v1/design-agent/runs/${metadata.run_id}/review`, { method: "POST", body: { decision: "reject", reason, target_sections } });
    await save("revision-response.json", result); await capture("revised");
    assert.equal(result.status, 200, "Revision failed; inspect the saved trace.");
  } else { assert.equal(mode, "capture"); await capture(process.env.CYBER_ACCEPTANCE_LABEL || "current"); }
}
