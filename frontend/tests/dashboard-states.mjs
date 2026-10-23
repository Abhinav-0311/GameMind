// Run against an existing dashboard: node tests/dashboard-states.mjs
// All backend requests are intercepted; no game data or provider calls are made.
import assert from "node:assert/strict";
import { join } from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.DASHBOARD_TEST_URL || "http://localhost:3000";
const now = "2026-10-03T10:00:00Z";
const document = {
  id: "fixture-source", title: "Fixture GDD", content_type: "text/plain", source_kind: "gdd",
  revision_number: 1, created_at: now, updated_at: now, chunks_count: 3,
};
const health = { status: "healthy", database: "healthy", chromadb: "healthy", ai_mode: "local_demo" };
const overview = {
  total_cost_usd: 0, total_requests: 7, avg_latency_ms: 123,
  total_input_tokens: 20, total_output_tokens: 10, safety_blocked_count: 0,
  error_count: 0, breakdown_by_action: [], breakdown_by_model: [],
};
const memory = { active_memories: 4, archived_memories: 0, promoted_memories: 0, average_importance_score: 0.5, failed_chroma_indexing_count: 0 };
const failedScore = { metrics: [], overall_score: 0.56, passed: false, blockers: ["citation_gap"], unresolved_assumptions: [] };
const passedScore = { ...failedScore, overall_score: 1, passed: true, blockers: [] };
const defaults = {
  "/health": health,
  "/api/v1/auth/session": { auth_required: false, user: null },
  "/api/v1/projects/": [{ id: "fixture-project", name: "Fixture workspace", created_at: now }],
  "/api/v1/documents/": [document],
  "/api/v1/documents/fixture-source": { ...document, chunks: [] },
  "/api/v1/blueprints/": [],
  "/api/v1/decisions/": [],
  "/api/v1/decisions/coverage": { items: [], summary: { source_backed: 0, needs_source_evidence: 0, decision_open: 0, evidence_attached: 0 } },
  "/api/v1/analytics/overview": overview,
  "/api/v1/analytics/costs": [],
  "/api/v1/analytics/memory": memory,
  "/api/v1/analytics/logs": { logs: [], total: 0 },
  "/api/v1/design-agent/runs": [],
  "/api/v1/npcs": [{ id: "fixture-npc", slug: "fixture-guide", name: "Fixture guide", title: "Guide", personality_summary: "A patient guide who knows the village", dialogue_style: "Brief and practical", faction_alignment: "Village", created_at: now, updated_at: now }],
};

function runFixture(status, scorecard = passedScore) {
  return {
    id: "fixture-run", game_project_id: "fixture-project", objective: "Review the fixture design with cited evidence",
    document_ids: [document.id], status, provider_name: "mock", degraded: false,
    retrieval_revision: 1, revision_count: 0, max_revisions: 2, created_at: now, updated_at: now,
    current_artifact: { id: "artifact", version: 1, immutable: status === "completed", created_at: now,
      content: { summary: { content: { premise: "Fixture premise" }, confidence: "Low", citations: [], warnings: [] } } },
    critique: { artifact_id: "artifact", content: { verdict: scorecard.passed ? "ready_for_review" : "needs_revision", findings: [], summary: "Fixture critique", quality_scorecard: scorecard } },
  };
}

const browser = await chromium.launch({ headless: true, args: ["--disable-logging"] });
let passed = 0;
async function check(name, path, fixtures, verify, viewport = { width: 1440, height: 1000 }) {
  if (process.env.DASHBOARD_TEST_FILTER && !name.includes(process.env.DASHBOARD_TEST_FILTER)) return;
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  const unexpected = [];
  const crashes = [];
  page.on("pageerror", (error) => crashes.push(error.message));
  const responses = { ...defaults, ...fixtures };
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    // Keep the existing hosted font import offline; verify with the OS fallback font.
    if (url.origin === "https://fonts.googleapis.com" && url.pathname === "/css2") {
      return route.fulfill({ status: 200, contentType: "text/css", body: "" });
    }
    if (url.pathname !== "/health" && !url.pathname.startsWith("/api/")) {
      // Only the dashboard assets may reach the network.
      if (url.origin === new URL(baseUrl).origin) return route.continue();
      unexpected.push(`External request: ${url.origin}${url.pathname}`);
      return route.abort();
    }
    const headers = {
      "access-control-allow-origin": new URL(baseUrl).origin,
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "content-type,x-game-project-id",
      "access-control-allow-methods": "GET,POST,OPTIONS",
    };
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    // FastAPI's list routes include a slash. Do not mask redirect-dependent
    // client calls with successful fixtures at URLs the backend does not serve.
    if (request.method() === "GET" && ["/api/v1/documents", "/api/v1/blueprints", "/api/v1/decisions"].includes(url.pathname)) {
      unexpected.push(`Noncanonical list request: ${url.pathname}`);
      return route.abort();
    }
    const fixtureKey = request.method() === "GET" ? url.pathname : `${request.method()} ${url.pathname}`;
    // Only explicit, local account/review fixture actions may simulate a POST.
    const stubbedActions = new Set([
      "/api/v1/auth/password-reset/request", "/api/v1/auth/password-reset/confirm",
      "/api/v1/auth/email-verification/request", "/api/v1/auth/email-verification/confirm",
      "/api/v1/projects/invitations/accept", "/api/v1/decisions/sync",
      "/api/v1/design-agent/runs/fixture-run/review",
      "/api/v1/design-agent/runs/fixture-run/retry-critique",
      "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/finding-resolutions",
      "/api/v1/design-agent/runs",
    ]);
    if (request.method() !== "GET" && !(request.method() === "POST" && stubbedActions.has(url.pathname) && Object.hasOwn(fixtures, fixtureKey))) {
      unexpected.push(`Mutation attempted: ${request.method()} ${url.pathname}`);
      return route.abort();
    }
    if (url.pathname !== "/health" && !url.pathname.startsWith("/api/v1/auth/") && url.pathname !== "/api/v1/projects/" && url.pathname !== "/api/v1/projects/invitations/accept"
      && request.headers()["x-game-project-id"] !== "fixture-project") {
      unexpected.push(`Missing workspace scope: ${url.pathname}`);
    }
    let response = responses[fixtureKey];
    if (typeof response === "function") response = await response(request);
    if (url.pathname === "/api/v1/design-agent/runs/fixture-run" && response === undefined) response = responses["/api/v1/design-agent/runs"][0];
    if (url.pathname.endsWith("/fixture-run/trace") && response === undefined) response = { run_id: "fixture-run", items: [] };
    if (url.pathname.endsWith("/fixture-run/evaluation")) response = { httpError: 404 };
    if (response === undefined) {
      unexpected.push(`Missing fixture: ${url.pathname}`);
      response = { httpError: 500 };
    }
    if (response === "abort") return route.abort("failed");
    return route.fulfill({ status: response.httpError || 200, headers,
      contentType: "application/json", body: JSON.stringify(response.httpError ? { detail: response.detail ?? "Fixture failure" } : response) });
  });
  try {
    await page.goto(`${baseUrl}${path}`);
    // Initial SSR markup can be actionable before client handlers hydrate.
    // All API fixtures settle before interactions; no pending POST exists yet.
    await page.waitForLoadState("networkidle");
    await verify(page, responses);
    assert.deepEqual(unexpected, [], "Unexpected API or network traffic");
    assert.deepEqual(crashes, [], "Browser runtime errors");
    passed += 1;
    console.log(`PASS ${name}`);
  } finally {
    await context.close();
  }
}
async function visible(page, text) {
  await page.getByText(text, { exact: true }).first().waitFor({ state: "visible" });
}
async function absent(page, text) {
  assert.equal(await page.getByText(text, { exact: true }).count(), 0, `Unexpected claim: ${text}`);
}

async function trappedFocus(page, dialog) {
  await dialog.waitFor({ state: "visible" });
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, "Initial focus belongs in the modal");
  assert.equal(await page.locator('dialog[open]').evaluate((element) => element.matches(":modal")), true, "Background must be natively inert");
  for (const key of ["Tab", "Shift+Tab"]) {
    for (let index = 0; index < 16; index += 1) {
      await page.keyboard.press(key);
      assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, `${key} escaped the modal`);
    }
  }
}

async function contrast(locator) {
  return locator.evaluate((element) => {
    const canvas = document.createElement("canvas"); canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const rgba = (color) => {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1);
      return Array.from(ctx.getImageData(0, 0, 1, 1).data);
    };
    const blend = (foreground, background) => background.map((value, index) => foreground[index] * (foreground[3] / 255) + value * (1 - foreground[3] / 255));
    let background = [255, 255, 255];
    const ancestors = []; for (let node = element; node; node = node.parentElement) ancestors.unshift(node);
    for (const node of ancestors) background = blend(rgba(getComputedStyle(node).backgroundColor), background);
    const foreground = blend(rgba(getComputedStyle(element).color), background);
    const luminance = (rgb) => rgb.map((value) => { const s = value / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
    const a = luminance(foreground), b = luminance(background);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
}
async function readable(locator) {
  await locator.waitFor({ state: "visible" });
  const ratio = await contrast(locator);
  const style = await locator.evaluate((element) => ({ color: getComputedStyle(element).color, accent: getComputedStyle(element).getPropertyValue("--accent"), theme: document.documentElement.dataset.theme }));
  assert.ok(ratio >= 4.5, `${await locator.innerText()}: ${ratio.toFixed(2)}:1 contrast ${JSON.stringify(style)}`);
  return ratio;
}
async function setTheme(page, theme) {
  await page.evaluate((value) => {
    localStorage.setItem("gamemind-theme", value);
    window.dispatchEvent(new Event("gamemind-theme-change"));
  }, theme);
  await page.waitForFunction((value) => document.documentElement.dataset.theme === value, theme);
}

try {
  for (const width of [1440, 375]) {
    let current = { ...runFixture("failed"), provider_name: "nvidia", current_node: "critique", critique: null };
    let failureId = "failed-1";
    const requests = [];
    await check(`Retry critique retains draft and consent: ${width}px`, "/design-agent", {
      "/api/v1/design-agent/runs": () => [current],
      "/api/v1/design-agent/runs/fixture-run": () => current,
      "/api/v1/design-agent/runs/fixture-run/trace": () => ({ run_id: "fixture-run", items: [
        { id: failureId, node_name: "critique", attempt: requests.length + 1, status: "failed", latency_ms: 1,
          input_tokens: 0, output_tokens: 0, cost_usd: 0, details: {}, error: "Provider unavailable" },
      ] }),
      "POST /api/v1/design-agent/runs/fixture-run/retry-critique": (request) => {
        const body = request.postDataJSON();
        assert.deepEqual(body, { artifact_id: "artifact", failed_execution_id: failureId, hosted_provider_consent: true });
        requests.push(body);
        if (requests.length === 1) { failureId = "failed-2"; return { httpError: 503, detail: { message: "Critique retry failed; saved draft unchanged.", run_id: "fixture-run" } }; }
        current = { ...current, status: "review_queued" };
        return current;
      },
    }, async (page) => {
      const retry = page.getByRole("button", { name: "Retry critique", exact: true });
      await retry.click();
      const dialog = page.getByRole("dialog");
      await trappedFocus(page, dialog);
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(requests.length, 0);
      await retry.click();
      await dialog.getByRole("button", { name: "Retry saved draft review", exact: true }).click();
      await page.getByRole("alert").getByText(/saved draft unchanged/).waitFor();
      await retry.click();
      await dialog.getByRole("button", { name: "Retry saved draft review", exact: true }).click();
      await page.getByText("Critique retry queued. The saved draft is unchanged.", { exact: true }).waitFor();
      assert.equal(requests.length, 2);
      await page.reload();
      await page.getByText("Fixture premise", { exact: true }).waitFor();
      assert.equal(await retry.count(), 0);
      assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Download technical brief", exact: true }).count(), 0);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }, { width, height: 1000 });
  }
  for (const width of [1440, 768, 375]) {
    const run = runFixture("awaiting_review", passedScore);
    run.critique.id = "critic";
    run.critique.artifact_id = "artifact";
    const original = JSON.stringify(run.critique.content);
    const endpoint = "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/finding-resolutions";
    let unavailable = true;
    const findings = [
      { severity: "high", section: "npc_archetypes", issue: "Progress dialogue lacks the active-attempt condition.", recommendation: "Restrict the progress situation to active attempts." },
      { severity: "high", section: "quest_hooks", issue: "Restart requires the player's confirmation action.", recommendation: "Name the confirmation in the restart event." },
    ];
    await check(`Current system checks preserve saved critique: ${width}px`, "/design-agent", {
      "/api/v1/design-agent/runs": [run],
      [endpoint]: () => unavailable ? { httpError: 503 } : {
        artifact_id: "artifact", critique_id: "critic", evidence_snapshot_id: "snapshot",
        artifact_sha256: "a".repeat(64), critique_sha256: "c".repeat(64), evidence_sha256: "e".repeat(64),
        findings: [], resolutions: [], can_record: false, critique_blocked: true,
        system_checks: { verdict: "needs_revision", findings, quality_scorecard: { ...failedScore, blockers: ["Consistency"] } },
      },
    }, async (page) => {
      const reviews = page.getByRole("region", { name: "Finding reviews", exact: true });
      await reviews.getByRole("alert").waitFor();
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      unavailable = false;
      await reviews.getByRole("button", { name: "Reload finding reviews", exact: true }).click();
      const checks = page.getByRole("region", { name: "Pre-approval quality scorecard" });
      await checks.getByText("Current system checks", { exact: true }).waitFor();
      for (const finding of findings) await checks.getByText(finding.issue, { exact: true }).waitFor();
      assert.equal(await checks.getByRole("button", { name: "Review finding", exact: true }).count(), 0, "System blockers are not dismissible model findings");
      const suggestedFix = checks.locator("summary").first();
      await suggestedFix.focus();
      await suggestedFix.press("Enter");
      await checks.getByText(findings[0].recommendation, { exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      assert.equal(JSON.stringify(run.critique.content), original);
      await page.reload();
      await checks.getByText("Current system checks", { exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      for (const theme of ["light", "dark"]) {
        await setTheme(page, theme);
        await readable(checks.getByText(findings[0].issue, { exact: true }));
      }
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width);
    }, { width, height: 1000 });
  }
  for (const { width, reference } of [
    ...[1440, 768, 375].map((width) => ({ width, reference: null })),
    { width: 375, reference: "scalar" }, { width: 1440, reference: "object" },
  ]) {
    const run = runFixture("awaiting_review", passedScore);
    run.critique.id = "critic";
    run.critique.artifact_id = "artifact";
    run.critique.content.verdict = "needs_revision";
    run.critique.content.findings = [{ severity: "high", section: "npc_archetypes.content.npcs[0].dialogue_style", issue: "Comma differs from and.", recommendation: "Use and." }];
    run.current_artifact.content.npc_archetypes = { content: { npcs: [{ name: "Mira", dialogue_style: "formal, slow" }] }, citations: ["frozen-1"], confidence: "High", warnings: [] };
    const expectedPath = "/npc_archetypes/content/npcs/0" + (reference === "object" ? "" : "/dialogue_style");
    const expectedValue = reference === "object" ? run.current_artifact.content.npc_archetypes.content.npcs[0] : "formal, slow";
    if (reference) run.critique.content.findings[0].reference = { artifact_path: expectedPath, artifact_value: expectedValue,
      evidence_chunk_id: "frozen-1", evidence_quote: "Mira speaks in a formal and slow manner." };
    const originalCritique = JSON.stringify(run.critique.content);
    const endpoint = "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/finding-resolutions";
    const catalog = { artifact_id: "artifact", critique_id: "critic", evidence_snapshot_id: "snapshot", artifact_sha256: "a".repeat(64),
      critique_sha256: "c".repeat(64), evidence_sha256: "e".repeat(64), can_record: true, critique_blocked: true,
      findings: [{ finding_id: "f".repeat(64), index: 0, finding: run.critique.content.findings[0], origin: "model", can_resolve: true, resolution_applies: false,
        status_message: "Compare the exact draft field with frozen evidence before recording your judgment." }], resolutions: [], approval_effect: "none" };
    let posts = 0;
    let approvals = 0;
    await check(`Finding review records nested-path human judgment without approving: ${reference || "legacy"} ${width}px`, "/design-agent", {
      "/api/v1/design-agent/runs": [run], [endpoint]: () => catalog,
      "/api/v1/auth/session": { auth_required: true, user: { id: "reviewer", email: "reviewer@example.test", created_at: now } },
      [`POST ${endpoint}`]: (request) => {
        posts += 1;
        const payload = request.postDataJSON();
        assert.equal(payload.artifact_path, expectedPath);
        assert.equal(payload.evidence_quote, "Mira speaks in a formal and slow manner.");
        assert.equal(payload.finding_id, catalog.findings[0].finding_id);
        assert.equal(payload.artifact_sha256, catalog.artifact_sha256);
        assert.equal(Object.hasOwn(payload, "reviewer_user_id"), false);
        const record = { ...payload, id: "resolution", finding_index: 0, finding_content: catalog.findings[0].finding,
          artifact_id: "artifact", artifact_version: 1, artifact_value: expectedValue, reviewer_label: "reviewer@example.test", created_at: now };
        catalog.resolutions = [record];
        catalog.critique_blocked = false;
        catalog.findings[0] = { ...catalog.findings[0], can_resolve: false, resolution_applies: true,
          status_message: "Human-reviewed, not AI-verified. Applies only to this exact draft and frozen evidence." };
        return record;
      },
      "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/evidence": { artifact_id: "artifact", snapshot_id: "snapshot", revision: 1,
        items: [{ chunk_id: "frozen-1", title: "Frozen GDD", content: "Mira speaks in a formal and slow manner.", chunk_index: 0, document_id: document.id }] },
      "POST /api/v1/design-agent/runs/fixture-run/review": () => { approvals += 1; return runFixture("completed"); },
    }, async (page) => {
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      await page.getByText("AI feedback is advisory, not verified correctness.", { exact: false }).waitFor({ state: "visible" });
      await page.getByRole("button", { name: "Review finding", exact: true }).click();
      const form = page.getByRole("form", { name: "Review finding 1" });
      const field = form.getByLabel("Draft field", { exact: true });
      if (reference) {
        assert.equal(await field.inputValue(), expectedPath);
        assert.equal(await field.getAttribute("readonly"), "");
        assert.equal(await field.evaluate((element) => element === document.activeElement), true);
        await visible(page, "This finding fixes the draft field. Review its value against the frozen evidence below.");
        if (reference === "object") assert.ok((await form.locator("pre").innerText()).includes('"dialogue_style": "formal, slow"'));
      } else await field.selectOption(expectedPath);
      if (reference !== "object") await visible(page, "formal, slow");
      await form.getByLabel("Exact supporting quote", { exact: true }).fill("Invented supporting quote");
      await form.getByLabel("Why is this not a defect?", { exact: true }).fill("Both descriptions preserve the same voice traits; punctuation does not change their meaning.");
      assert.equal(await form.getByRole("button", { name: "Record human review", exact: true }).isDisabled(), true);
      await form.getByLabel("Exact supporting quote", { exact: true }).fill("Mira speaks in a formal and slow manner.");
      for (const theme of ["light", "dark"]) {
        await setTheme(page, theme);
        for (const text of ["Draft field", "Exact supporting quote", "Why is this not a defect?"]) await readable(form.getByText(text, { exact: true }));
        if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) await page.getByRole("region", { name: "Finding reviews", exact: true }).screenshot({
          path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `finding-form-${theme}-${width}.png`),
        });
      }
      await form.getByRole("button", { name: "Record human review", exact: true }).click();
      await visible(page, "Human-reviewed, not AI-verified");
      assert.equal(posts, 1);
      assert.equal(approvals, 0, "Recording must never approve or generate");
      assert.equal(JSON.stringify(run.critique.content), originalCritique, "Original critic text and nested section must remain unchanged");
      assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).isEnabled(), true);
      await visible(page, "Comma differs from and.");
      await visible(page, "Changes recommended"); // Raw AI verdict remains visible.
      await page.reload();
      await visible(page, "Human-reviewed, not AI-verified");
      assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).isEnabled(), true);
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width, "Finding review must not overflow");
      if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `finding-reviewed-${width}.png`), fullPage: true });
      await page.getByRole("button", { name: "Approve run", exact: true }).click();
      await visible(page, "Review complete");
      assert.equal(approvals, 1);
    }, { width, height: 1000 });
  }
  for (const scenario of ["viewer", "anonymous", "legacy", "server", "stale", "service", "post-conflict", "proposal", "wrong-evidence", "unknown-section", "malformed-path", "empty-section", "missing-reference", "malformed-reference"]) {
    const run = runFixture("awaiting_review", passedScore);
    run.critique.id = "critic";
    run.critique.artifact_id = "artifact";
    run.critique.content.verdict = "needs_revision";
    run.critique.content.findings = [{ severity: "high", section: "npc_archetypes", issue: "Review this voice.", recommendation: "Compare with the source." }];
    run.current_artifact.content.npc_archetypes = { content: { npcs: [{ name: "Mira", dialogue_style: "formal, slow" }] }, citations: ["frozen-1"], confidence: "High", warnings: [] };
    if (scenario === "unknown-section") run.critique.content.findings[0].section = "unknown_section.content.npcs[0].dialogue_style";
    if (scenario === "malformed-path") run.critique.content.findings[0].section = "npc_archetypes.content.npcs[0].dialogue_style;unknown";
    if (scenario === "empty-section") run.current_artifact.content.npc_archetypes.content = {};
    if (["missing-reference", "malformed-reference"].includes(scenario)) run.critique.content.findings[0].reference = {
      artifact_path: scenario === "missing-reference" ? "/npc_archetypes/content/missing" : "/npc_archetypes/content/npcs/00/dialogue_style",
      artifact_value: "unavailable", evidence_chunk_id: "frozen-1", evidence_quote: "Mira speaks in a formal and slow manner." };
    const endpoint = "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/finding-resolutions";
    const catalog = { artifact_id: scenario === "stale" ? "other-draft" : "artifact", critique_id: "critic", evidence_snapshot_id: "snapshot",
      artifact_sha256: "a".repeat(64), critique_sha256: "c".repeat(64), evidence_sha256: "e".repeat(64),
      can_record: !["viewer", "anonymous"].includes(scenario), critique_blocked: scenario !== "proposal",
      findings: [{ finding_id: "f".repeat(64), index: 0, finding: run.critique.content.findings[0],
        origin: scenario === "legacy" ? "unknown" : scenario === "server" ? "server" : "model",
        can_resolve: !["legacy", "server", "proposal"].includes(scenario), resolution_applies: scenario === "proposal",
        status_message: scenario === "legacy" ? "Finding origin is unknown. A new critique is needed."
          : scenario === "server" ? "System check. A human resolution cannot remove this blocker." : "Compare with frozen evidence." }], resolutions: [] };
    if (scenario === "proposal") run.critique.content.quality_scorecard = { ...passedScore, passed: false, blockers: ["Integration readiness"],
      metrics: ["grounding", "completeness", "consistency", "integration_readiness"].map((key) => ({ key, label: key, value: key === "integration_readiness" ? 0 : 1, passed: key !== "integration_readiness", detail: "Fixture check" })),
      unresolved_assumptions: [{ section: "npc_archetypes", record_id: "Mira", record: "Mira", assumption: "Proposed dialogue trigger; not runtime-tested." }] };
    let reads = 0;
    let posts = 0;
    let serviceUnavailable = true;
    await check(`Finding review safe boundary: ${scenario}`, "/design-agent", {
      "/api/v1/design-agent/runs": [run],
      [endpoint]: async () => {
        reads += 1;
        if (scenario === "service" && serviceUnavailable) return { httpError: 503 };
        return catalog;
      },
      [`POST ${endpoint}`]: () => { posts += 1; return { httpError: 409 }; },
      "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/evidence": { artifact_id: "artifact", snapshot_id: scenario === "wrong-evidence" ? "other-snapshot" : "snapshot", revision: 1,
        items: [{ chunk_id: "frozen-1", title: "Frozen GDD", content: "Mira speaks in a formal and slow manner.", chunk_index: 0, document_id: document.id }] },
    }, async (page) => {
      const panel = page.getByRole("region", { name: "Finding reviews", exact: true });
      if (["viewer", "anonymous", "legacy", "server"].includes(scenario)) {
        assert.equal(await panel.getByRole("button", { name: "Review finding", exact: true }).count(), 0);
        await visible(page, scenario === "legacy" ? "Finding origin is unknown. A new critique is needed."
          : scenario === "server" ? "System check. A human resolution cannot remove this blocker."
            : "Read-only. Recording requires a signed-in workspace owner or editor and the current review checkpoint.");
      } else if (["stale", "service"].includes(scenario)) {
        await panel.getByRole("alert").waitFor();
        assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
        if (scenario === "service") {
          serviceUnavailable = false;
          await panel.getByRole("button", { name: "Reload finding reviews", exact: true }).click();
          await panel.getByRole("button", { name: "Review finding", exact: true }).waitFor();
          assert.ok(reads >= 2);
        }
      } else if (scenario === "proposal") {
        await visible(page, "Human-reviewed, not AI-verified");
        assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
        await page.getByRole("checkbox").check();
        assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).isEnabled(), true);
        await visible(page, "Your proposal choices are unsaved. The server will recheck this exact draft before recording approval.");
      } else {
        const opener = panel.getByRole("button", { name: "Review finding", exact: true });
        await opener.focus(); await opener.press("Enter");
        const form = panel.getByRole("form", { name: "Review finding 1" });
        const initialFocus = ["unknown-section", "malformed-path", "empty-section", "missing-reference", "malformed-reference"].includes(scenario)
          ? form.getByRole("button", { name: "Cancel", exact: true }) : form.getByLabel("Draft field", { exact: true });
        assert.equal(await initialFocus.evaluate((element) => element === document.activeElement), true);
        if (["unknown-section", "malformed-path", "empty-section", "missing-reference", "malformed-reference"].includes(scenario)) {
          await visible(page, "No reviewable draft fields match this finding. Recording is blocked; request a corrected critique or draft.");
          assert.equal(await form.getByLabel("Draft field", { exact: true }).isDisabled(), true);
          assert.equal(await form.getByRole("button", { name: "Record human review", exact: true }).isDisabled(), true);
          await form.getByRole("button", { name: "Cancel", exact: true }).click();
          await page.waitForFunction((id) => document.activeElement?.id === id, await opener.getAttribute("id"));
          assert.equal(await opener.evaluate((element) => element === document.activeElement), true);
        } else if (scenario === "wrong-evidence") {
          await visible(page, "Frozen evidence does not match this draft. Reload finding reviews before recording.");
          assert.equal(await form.getByRole("button", { name: "Record human review", exact: true }).isDisabled(), true);
          await form.getByLabel("Draft field", { exact: true }).press("Escape");
          await page.waitForFunction((id) => document.activeElement?.id === id, await opener.getAttribute("id"));
          assert.equal(await opener.evaluate((element) => element === document.activeElement), true);
        } else {
          await form.getByLabel("Draft field", { exact: true }).selectOption("/npc_archetypes/content/npcs/0/dialogue_style");
          await form.getByLabel("Exact supporting quote", { exact: true }).fill("Mira speaks in a formal and slow manner.");
          await form.getByLabel("Why is this not a defect?", { exact: true }).fill("The draft and cited source describe the same voice; this is only a punctuation difference.");
          await form.getByRole("button", { name: "Record human review", exact: true }).click();
          await visible(page, "The draft or review changed. Reload finding reviews before trying again; nothing was approved.");
          assert.equal(posts, 1);
        }
      }
      if (scenario !== "proposal") assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      assert.equal(posts, scenario === "post-conflict" ? 1 : 0);
    });
  }
  for (const width of [375, 1440]) {
    let submitted = null;
    await check(`Phase 3 generation direction and consent: ${width}px`, "/design-agent", {
      "POST /api/v1/design-agent/runs": (request) => {
        submitted = request.postDataJSON();
        return runFixture("queued");
      },
    }, async (page) => {
      const policy = "Once per object per mission attempt; reset ONLY on mission restart, never on scanner use.";
      const fresh = page.getByRole("checkbox", { name: "Generate fresh dialogue", exact: true });
      const deferred = page.getByRole("checkbox", { name: "Design only — defer runtime integration", exact: true });
      const memoryScope = page.getByRole("checkbox", { name: "Allow NPC memory to remain unspecified for this run", exact: true });
      assert.equal(await memoryScope.isChecked(), false);
      await memoryScope.focus();
      await page.keyboard.press("Space");
      assert.equal(await memoryScope.isChecked(), true);
      assert.equal(await deferred.isChecked(), false);
      await deferred.focus();
      await page.keyboard.press("Space");
      assert.equal(await deferred.isChecked(), true);
      assert.equal(await fresh.isChecked(), false);
      await fresh.focus();
      await page.keyboard.press("Space");
      assert.equal(await fresh.isChecked(), true);
      const input = page.getByLabel("Fixed repeat/reset policy (optional)");
      assert.equal(await input.getAttribute("maxlength"), "240");
      await input.fill("short");
      await page.getByRole("button", { name: "Start design run", exact: true }).click();
      await visible(page, "Describe the repeat/reset policy in at least 10 characters, or leave it blank.");
      assert.equal(submitted, null);
      await input.fill(policy);
      await page.getByRole("button", { name: "Start design run", exact: true }).click();
      await page.getByRole("dialog").waitFor({ state: "visible" });
      assert.equal(submitted, null, "Opening consent must not start generation");
      await page.getByRole("button", { name: "Start governed review", exact: true }).click();
      await visible(page, "Run queued. A worker is preparing the draft.");
      assert.equal(submitted.fresh_dialogue, true);
      assert.equal(submitted.defer_runtime, true);
      assert.equal(submitted.allow_unspecified_memory, true);
      assert.equal(submitted.dialogue_policy, policy);
      assert.equal(submitted.hosted_provider_consent, true);
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width, "Generation setup overflows");
      await page.getByRole("button", { name: "New run", exact: true }).click();
      assert.equal(await memoryScope.isChecked(), false, "A new run must start without a memory exemption");
    }, { width, height: 1000 });
  }
  await check("Completed design-only run cannot export runtime", "/design-agent", {
    "/api/v1/design-agent/runs": [{ ...runFixture("completed"), defer_runtime: true,
      critique: { ...runFixture("completed").critique, artifact_id: "reviewed-draft-before-final-snapshot" } }],
  }, async (page) => {
    await visible(page, "Design-only review · Runtime integration deferred. Design approval does not enable runtime export or materialization.");
    assert.equal(await page.getByRole("button", { name: "Download runtime JSON", exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "Download technical brief", exact: true }).isDisabled(), false);
    await visible(page, "Previous draft critique");
    assert.equal(await page.getByText(/needs its own independent review before approval/).count(), 0);
  });
  for (const width of [375, 1440]) {
    for (const entry of ["/design-agent", "/decisions"]) {
      let posts = 0;
      const failed = { ...runFixture("failed"), current_node: "plan", current_artifact: null, critique: null };
      await check(`Failed start recovers saved run: ${entry} ${width}px`, entry, {
        "POST /api/v1/decisions/sync": [],
        "POST /api/v1/design-agent/runs": () => {
          posts += 1;
          return { httpError: 503, detail: { message: "Workflow could not start. Inspect the saved trace.", run_id: failed.id } };
        },
        "/api/v1/design-agent/runs/fixture-run/trace": { run_id: failed.id, items: [{
          id: "failed-plan", node_name: "plan", attempt: 1, status: "failed", provider_name: "nvidia",
          latency_ms: 272119, input_tokens: 0, output_tokens: 0, details: { token_usage_scope: "unavailable" },
          error: "Planner unavailable", started_at: now,
        }] },
      }, async (page, responses) => {
        if (entry === "/decisions") await page.getByRole("button", { name: "Review GDD", exact: true }).click();
        else await page.getByRole("button", { name: "Start design run", exact: true }).click();
        responses["/api/v1/design-agent/runs"] = [failed];
        await page.getByRole("button", { name: "Start governed review", exact: true }).click();
        await page.getByRole("dialog").waitFor({ state: "hidden" });
        await visible(page, "Workflow could not start. Inspect the saved trace.");
        if (entry === "/decisions") await page.getByRole("link", { name: "View review trace", exact: true }).click();
        else assert.equal(await page.locator("#design-run-error").evaluate(el => el === document.activeElement), true);
        await visible(page, "Run failed");
        await visible(page, "No draft was generated. Inspect the failed step in the workflow trace.");
        await visible(page, "Planner unavailable");
        assert.ok(new URL(page.url()).searchParams.get("run") === failed.id);
        await absent(page, "No runs yet");
        await absent(page, "0 tokens");
        await visible(page, "Token usage unknown");
        await page.reload();
        await visible(page, "Run failed");
        assert.equal(posts, 1, "Recovery/reload must never retry generation");
        assert.equal(await page.getByRole("button", { name: "Download technical brief", exact: true }).count(), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth));
        if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `failed-start-${entry.slice(1)}-${width}.png`), fullPage: true });
      }, { width, height: 1000 });
    }
  }
  for (const saved of [false, true]) {
    let posts = 0;
    await check(`Failed start preserves setup when ${saved ? "saved run cannot reload" : "no run was created"}`, "/design-agent", {
      "POST /api/v1/design-agent/runs": () => {
        posts += 1;
        return { httpError: saved ? 503 : 409, detail: saved ? { message: "Workflow failed", run_id: "fixture-run" } : "Source is not indexed" };
      },
      "/api/v1/design-agent/runs/fixture-run": { httpError: 503 },
    }, async (page) => {
      const objective = page.getByLabel(/Design objective/);
      await objective.fill("Keep this custom objective after an unavailable request.");
      await page.getByRole("button", { name: "Start design run", exact: true }).click();
      await page.getByRole("button", { name: "Start governed review", exact: true }).click();
      await page.getByRole("dialog").waitFor({ state: "hidden" });
      await visible(page, saved ? "Workflow failed The failed run was saved, but could not be loaded. Reload this page to recover it." : "Source is not indexed");
      assert.equal(await objective.inputValue(), "Keep this custom objective after an unavailable request.");
      assert.equal(new URL(page.url()).searchParams.has("run"), saved);
      assert.equal(posts, 1);
    });
  }
  for (const scope of ["unavailable", "completed_responses_only", "measured_zero"]) {
    const label = scope === "unavailable" ? "Token usage unknown" : scope === "completed_responses_only" ? "25 reported tokens (total may be incomplete)" : "0 tokens";
    await check(`Trace usage honest: ${scope}`, "/design-agent", {
      "/api/v1/design-agent/runs": [{ ...runFixture("failed"), current_artifact: null, critique: null }],
      "/api/v1/design-agent/runs/fixture-run/trace": { run_id: "fixture-run", items: [{
        id: "trace", node_name: "plan", attempt: 1, status: scope === "measured_zero" ? "completed" : "failed",
        latency_ms: 100, input_tokens: scope === "completed_responses_only" ? 20 : 0,
        output_tokens: scope === "completed_responses_only" ? 5 : 0,
        details: scope === "measured_zero" ? {} : { token_usage_scope: scope }, started_at: now,
      }] },
    }, async (page) => {
      await visible(page, label);
      assert.ok((await page.locator("summary").filter({ hasText: "Workflow trace" }).innerText()).includes(label));
      if (scope !== "measured_zero") await absent(page, "0 tokens");
    });
  }
  await check("Normal GDD review sends explicit design-only scope only after consent", "/decisions", {
    "POST /api/v1/decisions/sync": [],
    "POST /api/v1/design-agent/runs": (request) => {
      assert.equal(request.postDataJSON().defer_runtime, true);
      assert.equal(request.postDataJSON().allow_unspecified_memory, true);
      assert.equal(request.postDataJSON().hosted_provider_consent, true);
      return { ...runFixture("queued"), defer_runtime: true };
    },
  }, async (page) => {
    await page.getByRole("button", { name: "Review GDD", exact: true }).click();
    const checkbox = page.getByRole("checkbox", { name: "Design only — defer runtime integration", exact: true });
    await checkbox.waitFor({ state: "visible" });
    assert.equal(await checkbox.isChecked(), false);
    await checkbox.check();
    const memoryScope = page.getByRole("checkbox", { name: "Allow NPC memory to remain unspecified for this run", exact: true });
    assert.equal(await memoryScope.isChecked(), false);
    await memoryScope.check();
    await page.getByRole("button", { name: "Start governed review", exact: true }).click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
  });
  for (const width of [375, 1440]) {
    const run = { ...runFixture("completed", { ...passedScore, unspecified_sections: ["npc_memory_design"],
      assessed_sections: ["summary", "npc_archetypes", "quest_hooks"] }), allow_unspecified_memory: true };
    run.current_artifact.content.npc_memory_design = { content: { memory_nodes: [] }, citations: [], confidence: "Low",
      warnings: ["NPC memory is unspecified."] };
    await check(`Unspecified memory disclosure at ${width}px`, "/design-agent", { "/api/v1/design-agent/runs": [run] }, async (page) => {
      await visible(page, "Pre-approval quality · assessed scope");
      await visible(page, "NPC memory: Unspecified—not assessed. This is not a complete memory design or proof of source absence.");
      await page.getByRole("tab", { name: "Memory", exact: true }).click();
      await visible(page, "Unspecified—not assessed");
      assert.equal(await page.getByRole("checkbox", { name: "Allow NPC memory to remain unspecified for this run", exact: true }).count(), 0);
      if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
        await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `memory-light-${width}.png`), fullPage: true });
        await page.getByRole("button", { name: "Switch to dark mode", exact: true }).click();
        await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `memory-dark-${width}.png`), fullPage: true });
      }
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width, "Memory disclosure overflows");
    }, { width, height: 1000 });
  }
  const deferredBlueprint = { id: "fixture-blueprint", title: "Reviewed design", document_id: document.id,
    source_document_ids: [document.id], game_project_id: "fixture-project", status: "approved",
    materialization_manifest: null, created_at: now, updated_at: now,
    ...Object.fromEntries(["summary", "narrative_direction", "art_style_direction", "npc_archetypes",
      "npc_memory_design", "level_design_suggestions", "gameplay_systems", "quest_hooks", "unity_runtime_preview"]
      .map((key) => [key, { content: {}, citations: [], confidence: "Low", warnings: [] }])),
  };
  await check("Deferred blueprint blocks runtime actions", "/blueprints", {
    "/api/v1/blueprints/": [deferredBlueprint],
    "/api/v1/blueprints/fixture-blueprint/provenance": { blueprint_id: "fixture-blueprint", sections: [] },
    "/api/v1/blueprints/fixture-blueprint/readiness": { status: "runtime_deferred", can_approve: true,
      can_materialize: false, can_serve_runtime: false, runtime_release_reason: "runtime_deferred",
      runtime_release_blockers: ["Runtime integration explicitly deferred."], missing_required: [], blockers: [], advisories: [] },
  }, async (page) => {
    await visible(page, "Design approved");
    assert.equal(await page.getByRole("button", { name: "Runtime deferred", exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "Export JSON", exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "Export brief", exact: true }).isDisabled(), false);
  });
  const dialogueBlueprint = { ...deferredBlueprint,
    npc_archetypes: { content: { npcs: [
      { name: "Mira", archetype: "Mentor", dialogue_style: "Brief warnings",
        dialogue_hooks: ["Your work at the pass is not yet finished."],
        dialogue_triggers: [null, [], {
          trigger: "incomplete_progress", situation: "At least one objective remains incomplete.",
          text: "Your work at the pass is not yet finished.",
          eligibility: { stage: "progress", quest_id: "reclaim_ash_pass", lifecycle: "active", progress: "incomplete" },
          repeat_policy: "Once per attempt; reset only on mission restart.",
          manual_test: "Setup: one objective incomplete. Action: interact. Expect: the incomplete reminder; suppress after completion.",
        }, { trigger: "first_greeting", situation: "First encounter.", text: "Welcome to the pass.",
          eligibility: { stage: "greeting", quest_id: null, lifecycle: null, progress: "any" },
          repeat_policy: "Once per attempt.", manual_test: "Interact once; expect greeting. Repeat; expect suppression.",
        }, { trigger: "legacy_warning", situation: "An approaching threat.", text: "Take cover.",
          repeat_policy: "Once per encounter.", manual_test: "Confirm the intended encounter boundary.",
        }], implementation_notes: ["Run each manual_test before client integration."], assumptions: [] },
      { name: "Legacy guide", dialogue_style: "Patient", dialogue_hooks: ["Follow the northern trail."], dialogue_triggers: [] },
    ] }, citations: [], confidence: "Low", warnings: [] },
  };
  for (const width of [375, 768, 1440]) {
    for (const theme of ["light", "dark"]) {
      await check(`Blueprint dialogue conditions ${theme} ${width}`, "/blueprints", {
        "/api/v1/blueprints/": [dialogueBlueprint],
        "/api/v1/blueprints/fixture-blueprint/provenance": { blueprint_id: "fixture-blueprint", sections: [] },
        "/api/v1/blueprints/fixture-blueprint/readiness": { status: "runtime_deferred", can_approve: true,
          can_materialize: false, can_serve_runtime: false, runtime_release_reason: "runtime_deferred",
          runtime_release_blockers: [], missing_required: [], blockers: [], advisories: [] },
      }, async (page) => {
        await page.getByRole("button", { name: "NPCs", exact: true }).click();
        await setTheme(page, theme);
        await page.getByText("Your work at the pass is not yet finished.", { exact: true }).first().waitFor({ state: "visible" });
        await visible(page, "Follow the northern trail.");
        await visible(page, "Design proposals, not active game bindings.");
        const summary = page.locator("summary").filter({ hasText: "Trigger: incomplete_progress" });
        const detail = page.locator("details").filter({ has: summary });
        assert.equal(await detail.evaluate((element) => element.open), false);
        await summary.focus();
        await page.keyboard.press("Enter");
        await detail.locator("dd").first().waitFor({ state: "visible" });
        assert.match(await detail.innerText(), /Stage: progress; quest: reclaim_ash_pass; attempt: active; progress: incomplete/);
        assert.match(await detail.innerText(), /Spoken line\s+Your work at the pass is not yet finished\./);
        await visible(page, "Setup: one objective incomplete. Action: interact. Expect: the incomplete reminder; suppress after completion.");
        await visible(page, "Once per attempt; reset only on mission restart.");
        await readable(detail.locator("dd").first());
        await readable(summary);
        await page.keyboard.press("Space");
        assert.equal(await detail.evaluate((element) => element.open), false);
        await page.locator("summary").filter({ hasText: "Trigger: first_greeting" }).click();
        await visible(page, "Stage: greeting; quest: not quest-scoped; attempt: not quest-scoped; progress: any.");
        await page.locator("summary").filter({ hasText: "Trigger: legacy_warning" }).click();
        await visible(page, "Not supplied in this legacy draft; confirm eligibility before integration.");
        const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
        assert.ok(dimensions.scroll <= dimensions.width, "Dialogue conditions must not overflow");
        if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
          await summary.click();
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `dialogue-conditions-${theme}-${width}.png`), fullPage: true });
        }
      }, { width, height: 1000 });
    }
  }
  await check("Header rejects failed health and retries without reload", "/", { "/health": "abort" }, async (page, responses) => {
    await visible(page, "API unavailable");
    await visible(page, "Needs attention");
    await absent(page, "Workspace is connected");
    await absent(page, "Begin with a document you can defend.");
    responses["/health"] = health;
    await page.getByRole("button", { name: "API unavailable", exact: true }).click();
    await visible(page, "API connected");
    await visible(page, "Workspace is connected");
  });
  await check("Workspace access failure does not claim connected", "/", { "/api/v1/projects/": { httpError: 403 } }, async (page, responses) => {
    await visible(page, "We could not confirm your workspace.");
    await visible(page, "Workspace unavailable");
    await absent(page, "API connected");
    responses["/api/v1/projects/"] = defaults["/api/v1/projects/"];
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await visible(page, "API connected");
    await visible(page, "Start a reviewed design run");
  });
  await check("Home preserves successful sources when blueprints fail", "/", { "/api/v1/blueprints/": { httpError: 500 } }, async (page, responses) => {
    await visible(page, "Workspace status unavailable");
    assert.match(await page.locator('.metric-tile').filter({ hasText: /^Documents/ }).innerText(), /1/);
    assert.match(await page.locator('.metric-tile').filter({ hasText: /^Chunks/ }).innerText(), /3/);
    assert.match(await page.locator('.metric-tile').filter({ hasText: /^Blueprints/ }).innerText(), /Unavailable/);
    await absent(page, "Add your first source document");
    responses["/api/v1/blueprints/"] = [];
    await page.getByRole("button", { name: "Retry workspace" }).click();
    await visible(page, "Start a reviewed design run");
  });
  await check("Home does not invent zero sources", "/", { "/api/v1/documents/": "abort" }, async (page) => {
    await visible(page, "Workspace status unavailable");
    assert.match(await page.locator('.metric-tile').filter({ hasText: /^Documents/ }).innerText(), /Unavailable/);
    await absent(page, "Begin with a document you can defend.");
  });
  await check("Unknown runtime readiness does not recommend materialization", "/", {
    "/api/v1/blueprints/": [{ id: "fixture-blueprint", status: "approved", materialization_manifest: { npcs: ["npc"] } }],
    "/api/v1/blueprints/fixture-blueprint/readiness": { httpError: 500 },
  }, async (page) => {
    await visible(page, "Workspace status unavailable");
    assert.match(await page.locator('.metric-tile').filter({ hasText: /^Runtime ready/ }).innerText(), /Unavailable/);
    await absent(page, "Materialize reviewed runtime data");
  });
  await check("Successful empty home retains onboarding", "/", { "/api/v1/documents/": [] }, async (page) => {
    await visible(page, "Begin with a document you can defend.");
    await absent(page, "Workspace status unavailable");
  });

  for (const failure of [401, 403, 500, "abort"]) {
    const reason = failure === "abort" ? failure : { httpError: failure };
    await check(`Diagnostics ${failure} is unavailable, not healthy or free`, "/analytics", {
      "/api/v1/analytics/overview": reason, "/api/v1/analytics/memory": reason, "/api/v1/analytics/logs": reason,
    }, async (page, responses) => {
      await visible(page, "Activity unavailable");
      await absent(page, "Healthy");
      await absent(page, "Clean");
      await absent(page, "$0");
      await absent(page, "0ms");
      if (failure === 500 && process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
        await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, "chunk4-diagnostics-desktop.png"), fullPage: true });
      }
      const alert = await page.getByRole("alert").filter({ hasText: "Some diagnostics" }).innerText();
      assert.match(alert, failure === 401 ? /Sign in again/ : failure === 403 ? /does not have access/ : /API connection/);
      await page.getByText("Inspect recent trace log", { exact: true }).click();
      await visible(page, "Trace log unavailable");
      await absent(page, "No traces found");
      responses["/api/v1/analytics/overview"] = overview;
      responses["/api/v1/analytics/memory"] = memory;
      responses["/api/v1/analytics/logs"] = defaults["/api/v1/analytics/logs"];
      await page.getByRole("button", { name: "Retry diagnostics" }).click();
      await visible(page, "Healthy");
      await visible(page, "123ms");
      await page.getByText("Inspect recent trace log", { exact: true }).click();
      await visible(page, "No traces found");
    });
  }
  await check("Diagnostics partial success keeps measured latency", "/analytics", { "/api/v1/analytics/memory": { httpError: 500 } }, async (page) => {
    await visible(page, "123ms");
    await absent(page, "Healthy");
    assert.match(await page.getByText("Memory store", { exact: true }).locator('..').innerText(), /Unavailable/);
  });
  await check("Successful zero diagnostics remain real zero", "/analytics", { "/api/v1/analytics/overview": { ...overview, total_requests: 0, avg_latency_ms: 0, total_input_tokens: 0, total_output_tokens: 0 } }, async (page) => {
    await visible(page, "Healthy");
    await visible(page, "$0");
    await visible(page, "0ms");
    await visible(page, "No activity yet");
  });

  const libraryCases = [
    ["Sources", "/knowledge", "Source library unavailable", "No source documents yet.", "Retry sources"],
    ["Blueprints", "/blueprints", "Blueprint workspace unavailable", "No documents yet", "Retry blueprints"],
    ["Decisions", "/decisions", "Decision workspace unavailable", "Add a source before making decisions.", "Retry decisions"],
    ["Design agent", "/design-agent", "Design-agent workspace unavailable", "No runs yet", "Retry design agent"],
  ];
  for (const [name, path, errorTitle, emptyTitle, retryLabel] of libraryCases) {
    await check(`${name} failed source load is not an empty library`, path, { "/api/v1/documents/": { httpError: 500 } }, async (page, responses) => {
      await visible(page, errorTitle);
      await absent(page, emptyTitle);
      responses["/api/v1/documents/"] = [];
      await page.getByRole("button", { name: retryLabel, exact: true }).click();
      await visible(page, emptyTitle);
    });
  }
  await check("Source detail failure does not show a stale source and can retry", "/knowledge", { "/api/v1/documents/fixture-source": { httpError: 500 } }, async (page, responses) => {
    await visible(page, "Retry selected source");
    await absent(page, "Generate blueprint");
    responses["/api/v1/documents/fixture-source"] = defaults["/api/v1/documents/fixture-source"];
    await page.getByRole("button", { name: "Retry selected source" }).click();
    await visible(page, "Generate blueprint");
  });
  await check("Failed decision request is not zero decisions", "/decisions", { "/api/v1/decisions/": { httpError: 500 } }, async (page, responses) => {
    await visible(page, "Decision workspace unavailable");
    await visible(page, "Decision count unavailable");
    await absent(page, "No decision records");
    responses["/api/v1/decisions/"] = [];
    await page.getByRole("button", { name: "Retry decisions" }).click();
    await visible(page, "No decision records");
  });
  await check("Resolved status is independent of decision severity", "/decisions", {
    "/api/v1/decisions/": [
      { id: "resolved", title: "Resolved scope", status: "resolved", severity: "missing", priority: "high", decision: "Chosen scope" },
      { id: "conflict", title: "Open conflict", status: "open", severity: "conflict", priority: "medium", decision: "" },
    ],
  }, async (page) => {
    await visible(page, "resolved decision · high priority");
    await visible(page, "open decision · medium priority · scope conflict");
    await visible(page, "1 open decision");
  });
  for (const [status, title] of [
    ["created", "Review in progress"], ["queued", "Review queued"], ["running", "Review in progress"],
    ["review_queued", "Review queued"], ["approved", "Finalizing approved review"],
    ["revision_requested", "Revision in progress"], ["awaiting_review", "Ready for your judgment"],
    ["completed", "Review complete"], ["failed", "Review failed"],
  ]) {
    await check(`Run lifecycle: ${status}`, "/design-agent", { "/api/v1/design-agent/runs": [runFixture(status)] }, async (page) => {
      const gate = page.locator('section[aria-label="Approval status"]');
      await gate.getByText(title, { exact: true }).waitFor({ state: "visible" });
      await absent(page, "Review checkpoint pending");
      const approve = page.getByRole("button", { name: "Approve run", exact: true });
      assert.equal(await approve.count(), status === "awaiting_review" ? 1 : 0);
    });
  }
  for (const width of [1440, 768, 375]) {
    const run = runFixture("awaiting_review");
    run.current_artifact = { ...run.current_artifact, id: "artifact-v2", version: 2 };
    const original = JSON.stringify(run.critique.content);
    await check(`Critique version identity: ${width}px`, "/design-agent", { "/api/v1/design-agent/runs": [run] }, async (page) => {
      await visible(page, "Critique not linked to current draft");
      await visible(page, "Draft version 2 needs its own independent review before approval. The critique below is not linked to this version; its findings are retained for reference only.");
      await visible(page, "Fixture critique");
      await absent(page, "Ready for your judgment");
      await absent(page, "Pre-approval quality");
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      delete run.critique.artifact_id;
      await page.reload();
      await visible(page, "Critique not linked to current draft");
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      run.critique.artifact_id = "artifact-v2";
      await page.reload();
      await visible(page, "Ready for your judgment");
      await absent(page, "Critique not linked to current draft");
      await visible(page, "Pre-approval quality");
      assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).isEnabled(), true);
      assert.equal(JSON.stringify(run.critique.content), original);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    }, { width, height: 900 });
  }
  for (const width of [1440, 768, 375]) {
    const run = runFixture("awaiting_review", failedScore);
    run.current_artifact.content.summary.citations = ["frozen-1", "missing-reference"];
    run.current_artifact.content.npc_archetypes = { content: { npcs: [] }, confidence: "Low", citations: [], warnings: [] };
    let evidenceReads = 0;
    const frozenText = "Original source excerpt. <script>window.evidenceExecuted = true</script>";
    run.objective = "Review the source-supported character, quest objectives, rewards and proposed integration steps. ".repeat(16)
      + "Preserve this final requirement exactly: " + "unbroken-token-".repeat(24);
    await check(`Awaiting review keeps quality blockers and compact objective: ${width}px`, "/design-agent", {
      "/api/v1/design-agent/runs": [run],
      "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/evidence": () => {
        evidenceReads += 1;
        return { artifact_id: "artifact", snapshot_id: "snapshot", revision: 1,
          items: [{ chunk_id: "frozen-1", document_id: document.id, title: "Frozen GDD", content: frozenText, chunk_index: 0 }] };
      },
    }, async (page) => {
      await visible(page, "citation_gap");
      const artifact = page.getByRole("heading", { name: "Summary", exact: true });
      const box = await artifact.boundingBox();
      assert.ok(box && box.y + box.height < 900, `The artifact heading should fit in the initial viewport, not below a full prompt (y=${box?.y})`);
      const disclosure = page.locator("details").filter({ has: page.locator("summary").filter({ hasText: /^Full objective$/ }) });
      const objective = disclosure.locator("p");
      assert.equal(await objective.isVisible(), false, "Full objective starts collapsed");
      const trigger = disclosure.locator("summary");
      await trigger.focus();
      await trigger.press("Enter");
      await objective.waitFor({ state: "visible" });
      assert.equal(await objective.textContent(), run.objective, "No objective text may be shortened or rewritten");
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width, "Expanded unbroken objective must wrap without horizontal overflow");
      await trigger.press("Space");
      await objective.waitFor({ state: "hidden" });
      await trigger.click();
      await objective.waitFor({ state: "visible" });
      const approve = page.getByRole("button", { name: "Approval blocked", exact: true });
      assert.equal(await approve.isDisabled(), true);
      assert.equal(evidenceReads, 0, "Evidence loads only on demand");
      const sources = page.locator("details").filter({ has: page.locator("summary").filter({ hasText: /^Source evidence$/ }) });
      await sources.locator("summary").focus();
      await sources.locator("summary").press("Enter");
      await visible(page, "Frozen GDD");
      assert.equal(await sources.locator("blockquote").textContent(), frozenText);
      assert.equal(await page.evaluate(() => window.evidenceExecuted), undefined, "Source text is never executable HTML");
      await sources.getByText("Unavailable in this frozen snapshot: missing-reference", { exact: true }).waitFor();
      assert.equal(evidenceReads, 1);
      await page.getByRole("tab", { name: "NPCs", exact: true }).click();
      await sources.getByText("No evidence references were recorded for this section.", { exact: true }).waitFor();
      assert.equal(await sources.locator("blockquote").count(), 0, "Uncited evidence must not carry into another section");
      await page.getByRole("tab", { name: "Summary", exact: true }).click();
      assert.equal(evidenceReads, 1, "Tab switches reuse only this artifact's frozen snapshot");
    }, { width, height: 900 });
  }
  for (const firstFault of [404, "wrong-artifact"]) {
    const run = runFixture("awaiting_review", failedScore);
    run.current_artifact.content.summary.citations = ["source-1"];
    let attempts = 0;
    await check(`Frozen evidence failure can retry without changing the draft: ${firstFault}`, "/design-agent", {
      "/api/v1/design-agent/runs": [run],
      "/api/v1/design-agent/runs/fixture-run/artifacts/artifact/evidence": async () => {
        attempts += 1;
        await new Promise((resolve) => setTimeout(resolve, 350));
        if (attempts === 1) return firstFault === 404 ? { httpError: 404 }
          : { artifact_id: "wrong-artifact", snapshot_id: "snapshot", revision: 1, items: [] };
        return { artifact_id: "artifact", snapshot_id: "snapshot", revision: 1, items: [] };
      },
    }, async (page) => {
      const sources = page.locator("details").filter({ has: page.locator("summary").filter({ hasText: /^Source evidence$/ }) });
      await sources.locator("summary").click();
      await sources.getByRole("status").waitFor();
      await sources.getByRole("alert").waitFor();
      await sources.getByRole("button", { name: "Retry evidence" }).click();
      await sources.getByText("Unavailable in this frozen snapshot: source-1", { exact: true }).waitFor();
      assert.equal(attempts, 2);
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
    });
  }
  for (const width of [1440, 375]) {
    const proposals = [
      { section: "npc_archetypes", record_id: "PATCH", record: "PATCH", assumption: "Proposed warning trigger; not runtime-tested." },
      { section: "quest_hooks", record_id: "training", record: "Training Sandbox", assumption: "Proposed training completion event; not a GDD fact." },
    ];
    const score = { ...passedScore, passed: false, overall_score: 0.75, blockers: ["Integration readiness"],
      metrics: ["grounding", "completeness", "consistency", "integration_readiness"].map((key) => ({
        key, label: key, value: key === "integration_readiness" ? 0 : 1,
        passed: key !== "integration_readiness", detail: "Fixture check",
      })), unresolved_assumptions: proposals, unsupported_sections: [], incomplete_sections: [], recovered_sections: [] };
    const run = runFixture("awaiting_review", score);
    run.provider_name = "nvidia";
    run.critique.artifact_id = run.current_artifact.id;
    run.critique.content.verdict = "ready_for_review";
    let submitted;
    await check(`Proposal confirmation is explicit and version-bound ${width}`, "/design-agent", {
      "/api/v1/design-agent/runs": [run],
      "POST /api/v1/design-agent/runs/fixture-run/review": (request) => {
        submitted = request.postDataJSON();
        return { httpError: 409 };
      },
    }, async (page, responses) => {
      if (width === 375) await setTheme(page, "dark");
      const choices = page.getByRole("group", { name: "Proposals to review" }).getByRole("checkbox");
      assert.equal(await choices.count(), 2);
      for (const choice of await choices.all()) assert.equal(await choice.isChecked(), false);
      await visible(page, "Selections are unsaved until you submit approval. They do not verify GDD facts or runtime behaviour.");
      await choices.nth(0).focus(); await page.keyboard.press("Space");
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      await choices.nth(1).check();
      await visible(page, "Ready to submit for approval");
      await absent(page, "System checks are clear. Review the cited draft, then approve only when you agree with it.");
      await readable(page.getByText(proposals[0].assumption, { exact: true }));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
        await page.getByRole("group", { name: "Proposals to review" }).screenshot({
          path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `proposal-confirmation-${width}.png`),
        });
      }
      await page.getByRole("button", { name: "Approve run", exact: true }).click();
      await page.getByRole("alert").filter({ hasText: "Fixture failure" }).waitFor({ state: "visible" });
      assert.deepEqual(submitted, { decision: "approve", artifact_id: "artifact", confirmed_proposals:
        proposals.map(({ section, record_id, assumption }) => ({ section, record_id, assumption })) });
      for (const choice of await choices.all()) assert.equal(await choice.isChecked(), false, "409 clears unsaved acceptance");
      await choices.nth(0).check(); await choices.nth(1).check();
      responses["/api/v1/design-agent/runs"][0] = { ...run,
        current_artifact: { ...run.current_artifact, id: "artifact-v2", version: 2 },
        critique: { ...run.critique, artifact_id: "artifact-v2" } };
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.waitForLoadState("networkidle");
      await visible(page, "Run state refreshed.");
      for (const choice of await choices.all()) assert.equal(await choice.isChecked(), false, "New versions start unchecked");
      // Other quality failures and an independent critique still block every selection.
      const refreshed = structuredClone(responses["/api/v1/design-agent/runs"][0]);
      for (const fault of ["quality", "quest_checks", "critique", "stale_critique", "missing_metrics", "high_finding", "legacy"]) {
        const next = structuredClone(refreshed);
        if (fault === "quality") next.critique.content.quality_scorecard.blockers.push("Completeness");
        if (fault === "quest_checks") next.critique.content.quality_scorecard.quest_integration_gaps = [
          { record_id: "training", record: "Training Sandbox", objectives: ["Unlock the training gate"] },
        ];
        if (fault === "critique") next.critique.content.verdict = "needs_revision";
        if (fault === "stale_critique") next.critique.artifact_id = "artifact";
        if (fault === "missing_metrics") next.critique.content.quality_scorecard.metrics = [];
        if (fault === "high_finding") next.critique.content.findings = [{ severity: "high", section: "quest_hooks", issue: "Unresolved issue", recommendation: "Revise the quest" }];
        if (fault === "legacy") next.critique.content.quality_scorecard.unresolved_assumptions.forEach((item) => { delete item.section; delete item.record_id; });
        responses["/api/v1/design-agent/runs"][0] = next;
        await page.getByRole("button", { name: "Refresh", exact: true }).click();
        await page.waitForLoadState("networkidle");
        await visible(page, "Run state refreshed.");
        if (fault === "stale_critique") {
          await visible(page, "Critique not linked to current draft");
          assert.equal(await choices.count(), 0, "Stale review proposals must not apply to this draft");
        } else {
          await choices.first().waitFor({ state: "visible" });
          for (const choice of await choices.all()) if (await choice.isEnabled()) await choice.check();
        }
        assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      }
      responses["/api/v1/design-agent/runs"][0] = refreshed;
      responses["POST /api/v1/design-agent/runs/fixture-run/review"] = (request) => {
        submitted = request.postDataJSON();
        return { ...refreshed, status: "completed", current_artifact: { ...refreshed.current_artifact, immutable: true } };
      };
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.waitForLoadState("networkidle");
      await choices.nth(0).check(); await choices.nth(1).check();
      await page.getByRole("button", { name: "Approve run", exact: true }).click();
      await visible(page, "Blueprint approved and final artifact locked.");
      assert.deepEqual(submitted, { decision: "approve", artifact_id: "artifact-v2", confirmed_proposals:
        proposals.map(({ section, record_id, assumption }) => ({ section, record_id, assumption })) });
      assert.equal(await choices.count(), 0, "Completed drafts have no editable confirmations");
      assert.equal(await page.getByRole("button", { name: "Approve run", exact: true }).count(), 0);
    }, { width, height: 1000 });
  }
  for (const [width, used, maximum] of [[1440, 1, 1], [768, 2, 2], [375, 3, 2]]) {
    await check(`Revision budget exhausted ${width}`, "/design-agent", {
      "/api/v1/design-agent/runs": [{ ...runFixture("awaiting_review", failedScore), revision_count: used, max_revisions: maximum }],
    }, async (page) => {
      if (width === 375) await page.getByRole("button", { name: "Switch to dark mode" }).click();
      const request = page.getByRole("button", { name: "Request revision", exact: true });
      await request.waitFor({ state: "visible" });
      assert.equal(await request.isDisabled(), true);
      await visible(page, `Revisions used: ${used}/${maximum}`);
      await visible(page, "Revision budget exhausted. Start a new run with a clearer objective and fresh provider consent. This draft stays unchanged.");
      assert.equal(await page.getByRole("button", { name: "Approval blocked", exact: true }).isDisabled(), true);
      assert.equal(await page.getByRole("button", { name: "Send revision request", exact: true }).count(), 0);
      await page.getByRole("button", { name: "New run", exact: true }).click();
      await visible(page, "Set the source of truth");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }, { width, height: 1000 });
  }
  await check("Revision budget exhausted still permits clear approval", "/design-agent", {
    "/api/v1/design-agent/runs": [{ ...runFixture("awaiting_review"), revision_count: 2, max_revisions: 2 }],
  }, async (page) => {
    const approve = page.getByRole("button", { name: "Approve run", exact: true });
    await approve.waitFor({ state: "visible" });
    assert.equal(await approve.isEnabled(), true);
    assert.equal(await page.getByRole("button", { name: "Request revision", exact: true }).isDisabled(), true);
  });
  await check("Revision budget exhausted closes a stale revision form on refresh", "/design-agent", {
    "/api/v1/design-agent/runs": [{ ...runFixture("awaiting_review", failedScore), revision_count: 1 }],
  }, async (page, responses) => {
    await page.getByRole("button", { name: "Request revision", exact: true }).click();
    await page.getByLabel("What must change?", { exact: true }).fill("Improve the warnings.");
    assert.equal(await page.getByRole("button", { name: "Send revision request", exact: true }).isEnabled(), true);
    responses["/api/v1/design-agent/runs"][0].revision_count = 2;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await visible(page, "Revisions used: 2/2");
    assert.equal(await page.getByRole("button", { name: "Send revision request", exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "Request revision", exact: true }).isDisabled(), true);
  });
  await check("Revision budget exhausted historical run is not in progress", "/design-agent", {
    "/api/v1/design-agent/runs": [{ ...runFixture("revision_limit_reached", failedScore), revision_count: 2 }],
  }, async (page) => {
    await visible(page, "This historical run cannot continue. Its draft and trace are preserved. Start a new run with fresh provider consent.");
    await absent(page, "Review in progress");
    await absent(page, "Approve run");
    assert.equal(await page.getByRole("button", { name: "Request revision", exact: true }).count(), 0);
  });
  for (const width of [1440, 375]) {
    for (const linked of [false, true]) {
    let submitted;
    await check(`Explicit revision scope ${linked ? "linked" : "single"} ${width}`, "/design-agent", {
      "/api/v1/design-agent/runs": [runFixture("awaiting_review", failedScore)],
      "POST /api/v1/design-agent/runs/fixture-run/review": (request) => {
        submitted = request.postDataJSON();
        return runFixture("awaiting_review", failedScore);
      },
    }, async (page, responses) => {
      if (width === 375) await page.getByRole("button", { name: "Switch to dark mode" }).click();
      await page.getByRole("tab", { name: "NPCs", exact: true }).click();
      await page.getByRole("button", { name: "Request revision", exact: true }).click();
      const scope = page.getByRole("group", { name: "Sections to revise", exact: true });
      const npc = scope.getByRole("checkbox", { name: "NPCs", exact: true });
      const quest = scope.getByRole("checkbox", { name: "Quests", exact: true });
      assert.equal(await npc.isChecked(), true);
      assert.equal(await scope.getByRole("checkbox", { checked: true }).count(), 1);
      await visible(page, "Only selected sections may change. Other sections stay unchanged, even if mentioned below.");
      const send = page.getByRole("button", { name: "Send revision request", exact: true });
      assert.equal(await send.isDisabled(), true);
      const reason = linked ? "Remove rejected NPC and quest scene notes; preserve dialogue and rewards."
        : "Improve PATCH warnings. Do not change quests or story.";
      await page.getByLabel("What must change?", { exact: true }).fill(reason);
      await npc.uncheck();
      await visible(page, "Select at least one section.");
      assert.equal(await send.isDisabled(), true, "A reason alone cannot authorize an empty scope");
      assert.equal(submitted, undefined);
      await npc.focus(); await page.keyboard.press("Space");
      assert.equal(await npc.isChecked(), true, "Keyboard selection must work");
      if (linked) {
        await quest.check();
        await visible(page, "2 sections selected.");
        if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
          await scope.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `revision-scope-linked-${width}-20261012.png`) });
        }
      }
      await send.click();
      await visible(page, "Revision and critique are ready for another review.");
      assert.deepEqual(submitted, { decision: "reject", reason,
        artifact_id: "artifact", target_sections: linked ? ["npc_archetypes", "quest_hooks"] : ["npc_archetypes"] });
      await page.getByRole("button", { name: "Request revision", exact: true }).click();
      assert.equal(await scope.getByRole("checkbox", { checked: true }).count(), 1, "Reopening must not reuse a broader scope");
      assert.equal(await npc.isChecked(), true);
      if (!linked) {
        let rejected = 0;
        responses["POST /api/v1/design-agent/runs/fixture-run/review"] = () => {
          rejected += 1;
          responses["/api/v1/design-agent/runs"][0] = { ...runFixture("awaiting_review", failedScore),
            revision_count: rejected, max_revisions: 2 };
          return { httpError: 409, detail: "Revision rejected; previous draft retained." };
        };
        await page.getByLabel("What must change?", { exact: true }).fill(reason);
        await send.click();
        await visible(page, "Revision rejected; previous draft retained.");
        await visible(page, "Revisions used: 1/2");
        assert.equal(await page.getByLabel("What must change?", { exact: true }).inputValue(), reason);
        await absent(page, "Revision and critique are ready for another review.");
        await send.click();
        await visible(page, "Revisions used: 2/2");
        assert.equal(await page.getByRole("button", { name: "Request revision", exact: true }).isDisabled(), true);
        assert.equal(await send.count(), 0);
        assert.equal(rejected, 2, "Rejections never auto-retry");
      }
      const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert.ok(dimensions.scroll <= dimensions.width);
    }, { width, height: 1000 });
    }
  }
  await check("Completed historical review keeps its failed 56 percent score", "/design-agent", { "/api/v1/design-agent/runs": [runFixture("completed", failedScore)] }, async (page) => {
    await visible(page, "Review complete");
    await visible(page, "56%");
    await absent(page, "Review checkpoint pending");
    await absent(page, "Approve run");
  });
  await check("Failure states fit mobile and dark mode", "/analytics", { "/api/v1/analytics/overview": { httpError: 500 } }, async (page) => {
    await visible(page, "Activity unavailable");
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    assert.ok(dimensions.scroll <= dimensions.width, `Horizontal overflow: ${JSON.stringify(dimensions)}`);
    if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, "chunk4-diagnostics-mobile-dark.png"), fullPage: true });
    }
  }, { width: 390, height: 844 });
  const chunks = Array.from({ length: 17 }, (_, index) => ({ id: `chunk-${index + 1}`, chunk_index: index, content: `Evidence for chunk ${index + 1}. `.repeat(32) + `Complete ending ${index + 1}.` }));
  const evidenceFixtures = {
    "/api/v1/documents/": [{ ...document, chunks_count: 17 }],
    "/api/v1/documents/fixture-source": { ...document, chunks_count: 17, chunks },
  };
  for (const keyboard of [false, true]) {
    await check(`All 17 evidence chunks reachable by ${keyboard ? "keyboard" : "pointer"}`, "/knowledge", evidenceFixtures, async (page) => {
      for (let index = 0; index < 3; index += 1) {
        const start = index * 6 + 1, end = Math.min(start + 5, 17);
        await visible(page, `Chunks ${start}–${end} of 17`);
        assert.equal(await page.locator('[id^="source-chunk-"]').count(), end - start + 1);
        for (let number = start; number <= end; number += 1) {
          const chunk = page.getByRole("article", { name: `Chunk ${number}`, exact: true });
          const full = chunk.getByText(chunks[number - 1].content, { exact: true });
          assert.equal(await full.isVisible(), false, "Long evidence starts collapsed");
          const summary = chunk.locator("summary");
          if (keyboard) { await summary.focus(); await page.keyboard.press("Enter"); } else await summary.click();
          await full.waitFor({ state: "visible" });
        }
        if (index < 2) {
          const next = page.getByRole("button", { name: "Next chunks", exact: true });
          if (keyboard) { await next.focus(); await page.keyboard.press("Enter"); } else await next.click();
        }
      }
      assert.equal(await page.getByRole("button", { name: "Next chunks", exact: true }).isDisabled(), true);
      await page.getByRole("button", { name: "Previous chunks", exact: true }).click();
      await visible(page, "Chunks 7–12 of 17");
    });
  }
  await check("Chunk 12 deep link survives a late initial response", "/knowledge?document=fixture-source&chunk=chunk-12", {
    ...evidenceFixtures,
    "/api/v1/documents/fixture-source": (() => { let requests = 0; return async () => {
      requests += 1;
      if (requests === 1) await new Promise((resolve) => setTimeout(resolve, 200));
      return { ...document, chunks_count: 17, chunks };
    }; })(),
  }, async (page) => {
    await visible(page, "Chunks 7–12 of 17");
    const target = page.getByRole("article", { name: "Chunk 12", exact: true });
    await target.getByText(chunks[11].content, { exact: true }).waitFor({ state: "visible" });
    assert.match(await target.getAttribute("class"), /accent-soft/);
    assert.equal(await target.evaluate((element) => document.activeElement === element), true);
    await page.getByRole("button", { name: "Next chunks" }).click();
    await visible(page, "Chunks 13–17 of 17");
  });

  for (const width of [375, 1440]) {
    await check(`New-project modal focus at ${width}px`, "/", {}, async (page) => {
      await visible(page, "Start a reviewed design run");
      let trigger = page.getByRole("button", { name: "New project", exact: true }).first();
      if (width < 1024) {
        const navTrigger = page.getByRole("button", { name: "Open navigation" });
        await navTrigger.focus(); await page.keyboard.press("Enter");
        const drawer = page.getByRole("dialog", { name: "Workspace navigation" });
        await trappedFocus(page, drawer);
        trigger = drawer.getByRole("button", { name: "New project" });
      }
      await trigger.focus(); await page.keyboard.press("Enter");
      const dialog = page.getByRole("dialog", { name: "Name your game project." });
      await trappedFocus(page, dialog);
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "hidden" });
      const expected = width < 1024 ? page.getByRole("button", { name: "Open navigation" }) : trigger;
      assert.equal(await expected.evaluate((element) => element === document.activeElement), true);
      assert.equal(await page.evaluate(() => document.body.style.overflow), "");
    }, { width, height: 900 });
    await check(`Command palette focus and real shortcuts at ${width}px`, "/", {}, async (page) => {
      await visible(page, "Start a reviewed design run");
      const trigger = page.getByRole("button", { name: width < 1024 ? "Open navigation" : "Switch to dark mode" });
      await trigger.focus(); await page.keyboard.press("Control+k");
      const dialog = page.getByRole("dialog", { name: "Search pages", exact: true });
      await trappedFocus(page, dialog);
      assert.equal(await dialog.getByText(/^G [A-Z]$/).count(), 0, "Fake shortcuts must not be shown");
      await dialog.getByRole("textbox", { name: "Search pages" }).fill("nothing matches");
      await visible(page, "No matching page");
      await trappedFocus(page, dialog);
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "hidden" });
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
      await page.keyboard.press("Control+k");
      const search = page.getByRole("textbox", { name: "Search pages" });
      await search.fill("Sources"); await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter");
      await visible(page, "Start with source truth.");
    }, { width, height: 900 });
  }
  await check("Mobile drawer traps focus and restores its trigger", "/", {}, async (page) => {
    await visible(page, "Start a reviewed design run");
    const trigger = page.getByRole("button", { name: "Open navigation" });
    await trigger.focus(); await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Workspace navigation" });
    await trappedFocus(page, dialog);
    await page.keyboard.press("Escape"); await dialog.waitFor({ state: "hidden" });
    assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
  }, { width: 375, height: 844 });
  await check("Design-agent consent is keyboard-safe without provider calls", "/design-agent", {}, async (page) => {
    const trigger = page.getByRole("button", { name: "Start design run", exact: true });
    await trigger.waitFor({ state: "visible" }); await trigger.focus(); await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Start a cited review?" });
    await trappedFocus(page, dialog);
    await page.keyboard.press("Escape"); await dialog.waitFor({ state: "hidden" });
    assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
  });
  await check("Local GDD review consent is keyboard-safe without provider calls", "/decisions", { "POST /api/v1/decisions/sync": [] }, async (page) => {
    await visible(page, "No decision records");
    const trigger = page.getByRole("button", { name: "Review GDD", exact: true });
    await trigger.focus(); await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Add a cited AI review to this GDD?" });
    await trappedFocus(page, dialog);
    await page.keyboard.press("Escape"); await dialog.waitFor({ state: "hidden" });
    assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
  });
  for (const [name, triggerName, dialogName] of [
    ["create", "Create NPC", "Add an NPC to the runtime roster."],
    ["edit", "Edit selected", "Refine this NPC profile."],
    ["delete confirmation", "Delete", "Delete Fixture guide?"],
  ]) {
    await check(`NPC ${name} modal is keyboard-safe`, "/npcs", {}, async (page) => {
      await visible(page, "fixture-guide");
      const trigger = page.getByRole("button", { name: triggerName, exact: true }).first();
      await trigger.focus(); await page.keyboard.press("Enter");
      const dialog = page.getByRole("dialog", { name: dialogName });
      await trappedFocus(page, dialog);
      await page.keyboard.press("Escape"); await dialog.waitFor({ state: "hidden" });
      assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
    });
  }

  for (const [path, button, guidance] of [
    ["/reset-password", "Update password", "This reset link is incomplete."],
    ["/verify-email", "Verify email", "This verification link is incomplete."],
    ["/accept-invitation", "Accept invitation", "This invitation link is missing its token."],
  ]) {
    await check(`Missing-token recovery: ${path}`, path, {}, async (page) => {
      await page.getByText(guidance, { exact: false }).waitFor({ state: "visible" });
      assert.equal(await page.getByRole("button", { name: button, exact: true }).isDisabled(), true);
      assert.ok(await page.getByRole("link", { name: /Sign in|reset link/ }).count() > 0);
    });
  }
  for (const [name, path, endpoint, actionName, field, success] of [
    ["reset request", "/forgot-password", "/api/v1/auth/password-reset/request", "Send reset link", "Email address", "If an account exists for this email, a reset link is on its way."],
    ["password reset", "/reset-password?token=fixture-token", "/api/v1/auth/password-reset/confirm", "Update password", "New password", "Password updated. Sign in with your new password."],
    ["email verification", "/verify-email?token=fixture-token", "/api/v1/auth/email-verification/confirm", "Verify email", null, "Email verified. You can sign in."],
    ["invitation", "/accept-invitation?token=fixture-token", "/api/v1/projects/invitations/accept", "Accept invitation", null, "Joined Fixture workspace. You can now open the workspace."],
  ]) {
    let calls = 0, release, signalStarted;
    const pending = new Promise((resolve) => { release = resolve; });
    const started = new Promise((resolve) => { signalStarted = resolve; });
    await check(`Account ${name}: labels, busy guard, and success`, path, {
      [`POST ${endpoint}`]: async () => { calls += 1; signalStarted(); await pending; return defaults["/api/v1/projects/"][0]; },
    }, async (page) => {
      if (field) await page.getByLabel(field, { exact: true }).fill(field === "New password" ? "fixture-password-only" : "fixture@example.test");
      await page.getByRole("button", { name: actionName, exact: true }).click();
      await page.waitForFunction(() => document.querySelector('[aria-busy="true"]'));
      if (field) await page.locator("form").dispatchEvent("submit");
      else await page.locator("button").first().evaluate((button) => button.click());
      await page.waitForFunction(() => document.querySelector('button:disabled'));
      await started;
      assert.equal(calls, 1);
      release();
      await visible(page, success);
      assert.equal(calls, 1);
      if (name === "password reset") assert.equal(await page.getByLabel("New password").inputValue(), "");
    });
  }
  for (const [name, path, endpoint, button] of [
    ["password reset", "/reset-password?token=expired", "/api/v1/auth/password-reset/confirm", "Update password"],
    ["verification", "/verify-email?token=expired", "/api/v1/auth/email-verification/confirm", "Verify email"],
    ["invitation", "/accept-invitation?token=expired", "/api/v1/projects/invitations/accept", "Accept invitation"],
  ]) {
    await check(`Expired ${name} shows an alert and recovery`, path, { [`POST ${endpoint}`]: { httpError: 400 } }, async (page) => {
      if (name === "password reset") await page.getByLabel("New password").fill("fixture-password-only");
      await page.getByRole("button", { name: button, exact: true }).click();
      await page.getByRole("alert").filter({ hasText: "Fixture failure" }).waitFor({ state: "visible" });
      if (name === "password reset") await page.getByRole("link", { name: "Request a new reset link" }).waitFor({ state: "visible" });
      if (name === "verification") await page.getByRole("button", { name: "Request a new verification link" }).waitFor({ state: "visible" });
      if (name === "invitation") await page.getByText(/Ask the workspace owner for a new invitation/).waitFor({ state: "visible" });
    });
  }
  await check("Incomplete verification can request a new link without enumeration", "/verify-email", { "POST /api/v1/auth/email-verification/request": {} }, async (page) => {
    await page.getByLabel("Email address").fill("fixture@example.test");
    await page.getByRole("button", { name: "Request a new verification link" }).click();
    await visible(page, "If this account needs verification, a new link is on its way.");
  });
  await check("Failed verification-link request is an alert, not success", "/verify-email", { "POST /api/v1/auth/email-verification/request": { httpError: 500 } }, async (page) => {
    await page.getByLabel("Email address").fill("fixture@example.test");
    await page.getByRole("button", { name: "Request a new verification link" }).click();
    await page.getByRole("alert").filter({ hasText: "Could not request a new link" }).waitFor({ state: "visible" });
  });
  const traceLog = { conversation_id: "fixture", action_type: "dialogue", npc_slug: "fixture-guide", model_used: "mock", llm_provider: "mock", latency_ms: 123, input_tokens: 10, output_tokens: 10, estimated_cost_usd: 0, safety_blocked: false, created_at: now };
  let minimumContrast = Infinity;
  for (const width of [375, 768, 1440]) {
    for (const theme of ["light", "dark"]) {
      await check(`Semantic text contrast and layout: ${theme}, ${width}px`, "/analytics", {
        "/api/v1/analytics/costs": { httpError: 500 },
        "/api/v1/analytics/logs": { logs: [{ ...traceLog, id: "success" }, { ...traceLog, id: "warning", error: "Fixture warning" }], total: 2 },
        "/api/v1/design-agent/runs": [runFixture("awaiting_review", failedScore)],
      }, async (page) => {
        await visible(page, "No activity yet"); await setTheme(page, theme);
        minimumContrast = Math.min(minimumContrast, await readable(page.getByRole("alert").filter({ hasText: "Some diagnostics" }).locator("p")));
        await page.getByText("Inspect recent trace log", { exact: true }).click();
        for (const text of ["Success", "Review", "Fixture warning"]) minimumContrast = Math.min(minimumContrast, await readable(page.getByText(text, { exact: true })));
        if (process.env.DASHBOARD_TEST_SCREENSHOT_DIR) {
          // Full-page captures should not pin the sticky header midway down the image.
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          await page.screenshot({ path: join(process.env.DASHBOARD_TEST_SCREENSHOT_DIR, `chunk5-diagnostics-${theme}-${width}.png`), fullPage: true });
        }
        await page.goto(`${baseUrl}/design-agent`);
        await visible(page, "Approval is blocked");
        minimumContrast = Math.min(minimumContrast, await readable(page.getByRole("tab", { name: "Summary", exact: true })));
        minimumContrast = Math.min(minimumContrast, await readable(page.getByText("Review needed", { exact: true }).first()));
        minimumContrast = Math.min(minimumContrast, await readable(page.getByText("Request a revision or resolve the review items before this draft can become runtime intent.", { exact: true })));
        await page.goto(`${baseUrl}/reset-password`);
        minimumContrast = Math.min(minimumContrast, await readable(page.getByText(/This reset link is incomplete/)));
        minimumContrast = Math.min(minimumContrast, await readable(page.getByRole("link", { name: "Request a new reset link" })));
        const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
        assert.ok(dimensions.scroll <= dimensions.width, "Recovery layout overflow");
      }, { width, height: 900 });
    }
  }
  if (Number.isFinite(minimumContrast)) {
    console.log(`Minimum measured semantic-text contrast: ${minimumContrast.toFixed(2)}:1.`);
  }
  console.log(`\n${passed} dashboard state checks passed; real backend mutations and hosted calls: 0.`);
} finally {
  await browser.close();
}
