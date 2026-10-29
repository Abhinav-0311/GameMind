import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
import vm from "node:vm";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { api, ApiRequestError } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("field correction sends action and exact paths bound to the current artifact", async (context) => {
  let sent;
  context.mock.method(globalThis, "fetch", async (_url, options) => {
    sent = JSON.parse(options.body); return Response.json({ status: "awaiting_review" });
  });
  const body = { decision: "request_correction", artifact_id: "draft", reason: "Use spoken dialogue.",
    target_paths: ["/quest_hooks/content/quests/1/dialogue_hooks/0"] };
  await api.reviewDesignAgentRun("run", body);
  assert.deepEqual(sent, body);
});

async function loadComponent(name, locals = {}) {
  const code = await readFile(new URL(`../src/components/${name}.tsx`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const loaded = { exports: {} };
  const nativeRequire = createRequire(import.meta.url);
  vm.runInNewContext(compiled, { module: loaded, exports: loaded.exports, require: (id) => locals[id] ?? nativeRequire(id) });
  return loaded.exports;
}

test("correction chooser exposes only allowed text leaves and their dependent effects", async () => {
  const modal = await loadComponent("ModalDialog");
  const component = await loadComponent("FieldCorrectionDialog", { "./ModalDialog": modal });
  const content = { quest_hooks: { content: { quests: [{ reward: "keep", objectives: ["keep"], dialogue_hooks: ["Current hook"] }] } },
    npc_archetypes: { content: { npcs: [{ dialogue_triggers: [{ situation: "Quest 0 progress", text: "Keep speech", eligibility: { quest_id: "quest_1" } }] }] } },
    unity_runtime_preview: { content: { target_platform: "Windows PC" } } };
  const fields = component.correctionFields(content);
  assert.deepEqual(JSON.parse(JSON.stringify(fields.map((field) => field.path))), [
    "/quest_hooks/content/quests/0/dialogue_hooks/0", "/npc_archetypes/content/npcs/0/dialogue_triggers/0/situation"]);
  const html = renderToStaticMarkup(React.createElement(component.CorrectionFieldChoices,
    { fields, selected: fields.map((field) => field.path), disabled: false, onChange: () => {} }));
  assert.match(html, /Current hook/);
  assert.match(html, /Quest 0 progress/);
  assert.match(html, /manual_test/);
  assert.match(html, /creative proposals/);
  const dialog = renderToStaticMarkup(React.createElement(component.default,
    { content, artifactId: "draft", busy: false, error: "Draft unchanged", onClose: () => {}, onSubmit: () => {} }));
  assert.match(dialog, /This is not a rejection/);
  assert.match(dialog, /still approvable if its other gates allow/);
  assert.match(dialog, /Draft unchanged/);
  assert.match(dialog, /disabled="">Send correction request/);
});

test("chooser disables unselected fields at the two-field limit", async () => {
  const component = await loadComponent("FieldCorrectionDialog", { "./ModalDialog": await loadComponent("ModalDialog") });
  const fields = [0, 1, 2].map((i) => ({ path: `field-${i}`, value: `Value ${i}`, effect: "Derived only" }));
  const html = renderToStaticMarkup(React.createElement(component.CorrectionFieldChoices,
    { fields, selected: ["field-0", "field-1"], disabled: false, onChange: () => {} }));
  assert.equal((html.match(/disabled=""/g) || []).length, 1);
  assert.equal((html.match(/checked=""/g) || []).length, 2);
});

test("review forwards explicit acknowledgement bound to the artifact", async (context) => {
  let sent;
  context.mock.method(globalThis, "fetch", async (_url, options) => {
    sent = JSON.parse(options.body);
    return Response.json({ status: "completed" });
  });
  await api.reviewDesignAgentRun("run", {
    decision: "approve", artifact_id: "reviewed-v2", acknowledge_degraded: true,
  });
  assert.deepEqual(sent, { decision: "approve", artifact_id: "reviewed-v2", acknowledge_degraded: true });
});

for (const status of [502, 503]) {
  test(`start failure ${status} preserves the saved run ID without another request`, async (context) => {
    let calls = 0;
    context.mock.method(globalThis, "fetch", async () => {
      calls += 1;
      return Response.json({ detail: { message: "Saved failure", run_id: "failed-run" } }, { status });
    });
    await assert.rejects(api.createDesignAgentRun({ objective: "Review the GDD", document_ids: ["gdd"] }),
      (error) => error instanceof ApiRequestError && error.status === status && error.runId === "failed-run");
    assert.equal(calls, 1);
  });
}

test("offline unsupported correction preserves the 409 message without retrying", async (context) => {
  let calls = 0;
  const message = "The offline provider cannot make this correction. Use a hosted provider or start a new run.";
  context.mock.method(globalThis, "fetch", async () => {
    calls += 1;
    return Response.json({ detail: message }, { status: 409 });
  });
  await assert.rejects(api.reviewDesignAgentRun("run", { decision: "reject", artifact_id: "draft-v1",
    reason: "Correct the missing systems", target_sections: ["gameplay_systems"] }),
    (error) => error instanceof ApiRequestError && error.status === 409 && error.message === message);
  assert.equal(calls, 1);
});

test("run response exposes the current draft approval blocker unchanged", async (context) => {
  const message = "This draft already has a recorded rejection. Request another correction or start a new isolated run.";
  context.mock.method(globalThis, "fetch", async () => Response.json({
    id: "run", status: "awaiting_review", approval_blocked_reason: message,
    current_artifact: { id: "unchanged-draft" },
  }));
  const run = await api.getDesignAgentRun("run");
  assert.equal(run.approval_blocked_reason, message);
  assert.equal(run.current_artifact.id, "unchanged-draft");
});

test("conflicting approval preserves the 409 explanation and sends no retry", async (context) => {
  let calls = 0;
  const message = "This draft already has a recorded rejection. The correction failed and no revised draft was saved, so this draft cannot currently be approved. Request another correction or start a new isolated run.";
  context.mock.method(globalThis, "fetch", async () => {
    calls += 1;
    return Response.json({ detail: message }, { status: 409 });
  });
  await assert.rejects(api.reviewDesignAgentRun("run", {
    decision: "approve", artifact_id: "unchanged-draft",
  }), (error) => error instanceof ApiRequestError && error.status === 409 && error.message === message);
  assert.equal(calls, 1);
});
