import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";
import vm from "node:vm";
import { createRequire } from "node:module";
import React from "react";
import { runInNewContext } from "node:vm";
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

async function loadCorrectionComponent(name, locals = {}) {
  const code = await readFile(new URL(`../src/components/${name}.tsx`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const loaded = { exports: {} };
  const nativeRequire = createRequire(import.meta.url);
  vm.runInNewContext(compiled, { module: loaded, exports: loaded.exports, require: (id) => locals[id] ?? nativeRequire(id) });
  return loaded.exports;
}

test("correction chooser exposes only allowed text leaves and their dependent effects", async () => {
  const modal = await loadCorrectionComponent("ModalDialog");
  const component = await loadCorrectionComponent("FieldCorrectionDialog", { "./ModalDialog": modal });
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
  const component = await loadCorrectionComponent("FieldCorrectionDialog", { "./ModalDialog": await loadCorrectionComponent("ModalDialog") });
  const fields = [0, 1, 2].map((i) => ({ path: `field-${i}`, value: `Value ${i}`, effect: "Derived only" }));
  const html = renderToStaticMarkup(React.createElement(component.CorrectionFieldChoices,
    { fields, selected: ["field-0", "field-1"], disabled: false, onChange: () => {} }));
  assert.equal((html.match(/disabled=""/g) || []).length, 1);
  assert.equal((html.match(/checked=""/g) || []).length, 2);
});

const gateSource = await readFile(new URL("../src/lib/design-review-gate.ts", import.meta.url), "utf8");
const gateCode = ts.transpileModule(gateSource, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { deriveReviewGate } = await import(`data:text/javascript;base64,${Buffer.from(gateCode).toString("base64")}`);
const advisory = { id: "exact-check", check: "quest_label_mismatch", severity: "medium",
  paths: ["/npc_archetypes/content/npcs/0/dialogue_triggers/0/situation"],
  message: "Review both fields; neither is assumed correct.", values: { situation: "Quest 0", quest_id: "quest_1" } };
const moreAdvisories = [
  { ...advisory, id: "empty-hook", check: "empty_quest_dialogue", severity: "low",
    paths: ["/quest_hooks/content/quests/0/dialogue_hooks"], values: { objective: "Mine 5 ore.", dialogue_hooks: [] } },
  { ...advisory, id: "note-label", check: "quest_label_in_assumptions",
    values: { note: "Associated with Quest 0", quest_id: "quest_1" } },
  { ...advisory, id: "runtime-value", check: "runtime_value_without_support",
    paths: ["/unity_runtime_preview/content/primary_input"],
    values: { value: "<Keyboard and Mouse>", evidence_ids: ["source-1"], decision_ids: ["decision-1"] } },
];

async function loadComponent(name) {
  const componentSource = await readFile(new URL(`../src/components/${name}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(componentSource, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  const compiled = { exports: {} };
  runInNewContext("(function(require,module,exports){" + code + "})")(
    createRequire(import.meta.url), compiled, compiled.exports);
  return compiled.exports.default;
}

for (const [provider, expected, absent] of [
  ["gemini", [/Google&#x27;s Gemini API/, /free tier/, /improve its products/, /demo or non-confidential/, /Mock mode.*sends nothing/], /This run is offline/],
  ["mock", [/This run is offline/, /sends nothing/, /deterministic extraction/], /may be sent/],
  ["nvidia", [/hosted provider/, /nvidia/, /source text may be sent/, /until you confirm/], /Google/],
]) {
  test(`shared consent describes the effective ${provider} provider honestly`, async () => {
    const Consent = await loadComponent("DesignReviewConsent");
    const html = renderToStaticMarkup(Consent({ provider }));
    for (const pattern of expected) assert.match(html, pattern);
    assert.doesNotMatch(html, absent);
  });
}

test("critique-only consent preserves recovery scope and data-use warning", async () => {
  const Consent = await loadComponent("DesignReviewConsent");
  const html = renderToStaticMarkup(Consent({ provider: "gemini", critiqueOnly: true }));
  assert.match(html, /saved draft and its frozen source text/);
  assert.match(html, /Planning, retrieval and generation will not repeat/);
  assert.match(html, /free tier/);
});

test("advisories cannot set needsRevision or disable approval, including on blocked runs", () => {
  const run = { status: "awaiting_review", provider_name: "gemini", degraded: false,
    current_artifact: { id: "draft" }, critique: { id: "critique", artifact_id: "draft",
      content: { verdict: "ready_for_review", findings: [] } } };
  const inputs = { activeRun: run, artifactId: "draft", critiqueIsCurrent: true, critiqueFindings: [],
    findingReview: { critique_blocked: false }, preApprovalScorecard: { passed: true, unresolved_assumptions: [] },
    selectedProposals: [], findingBusy: false, degradedAcknowledged: false };
  assert.deepEqual(deriveReviewGate(inputs), { needsRevision: false, confirmationReady: false, approvalBlocked: false });
  for (const variant of [run, { ...run, degraded: true }, { ...run, approval_blocked_reason: "Recorded rejection" }]) {
    const before = deriveReviewGate({ ...inputs, activeRun: variant });
    const after = deriveReviewGate({ ...inputs, activeRun: { ...variant,
      draft_evaluation: { artifact_id: "draft", advisories: [advisory, ...moreAdvisories] } } });
    assert.deepEqual(after, before);
  }
  assert.equal(deriveReviewGate({ ...inputs, findingReview: { critique_blocked: true } }).needsRevision, true);
});

test("advisory panel is separate, non-interactive, escaped, and has an honest empty state", async () => {
  const Panel = await loadComponent("DraftQualityAdvisories");
  const html = renderToStaticMarkup(Panel({ evaluation: { artifact_id: "draft", advisories: [
    { ...advisory, message: "<script>not executable</script>" }] } }));
  assert.match(html, /Advisories \(non-blocking\)/);
  assert.match(html, /medium/);
  assert.match(html, /dialogue_triggers\/0\/situation/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /exact-ch/);
  assert.match(html, /Quest 0/);
  assert.match(html, /quest_1/);
  assert.doesNotMatch(html, /<(button|input|form|select|script)\b/);
  assert.match(renderToStaticMarkup(Panel({ evaluation: { artifact_id: "draft", advisories: [] } })), /not a quality guarantee/);
  assert.equal(renderToStaticMarkup(Panel({ evaluation: null })), "");
});

test("advisory comparison renders objective text and misplaced rule without executing markup", async () => {
  const Panel = await loadComponent("DraftQualityAdvisories");
  const html = renderToStaticMarkup(Panel({ evaluation: { artifact_id: "draft", advisories: [
    { ...advisory, id: "objective-id", check: "objective_text_copied_as_dialogue",
      values: { dialogue: "Mine five ore.", objectives: [{ path: "/objective", value: "Mine FIVE ore!" }] } },
    { ...advisory, id: "warning-id", check: "warning_in_rules", severity: "low", values: { rule: "WARNING: <script>not assessed</script>" } },
  ] } }));
  for (const text of [/Dialogue/, /Matching objective/, /Mine five ore\./, /Mine FIVE ore!/, /Rule text/, /WARNING: &lt;script&gt;/]) assert.match(html, text);
  assert.doesNotMatch(html, /<(button|input|form|select|script)\b/);
});

test("new advisories show their exact comparisons without controls or executable markup", async () => {
  const Panel = await loadComponent("DraftQualityAdvisories");
  const html = renderToStaticMarkup(Panel({ evaluation: { artifact_id: "draft", advisories: moreAdvisories } }));
  for (const pattern of [/Mine 5 ore\./, /Dialogue hooks/, /\[\]/, /Associated with Quest 0/, /Linked quest ID/,
    /quest_1/, /Runtime value/, /&lt;Keyboard and Mouse&gt;/, /source-1/, /decision-1/, /#runtime-/]) assert.match(html, pattern);
  assert.doesNotMatch(html, /<(button|input|form|select|script)\b/);
});

test("Home uses the effective provider, not the legacy mode or NVIDIA wording", async () => {
  const home = await readFile(new URL("../src/app/page.tsx", import.meta.url), "utf8");
  assert.match(home, /health\?\.llm_provider/);
  assert.doesNotMatch(home, /health\?\.ai_mode/);
  assert.match(home, /AI review is an explicit, governed choice\./);
  assert.doesNotMatch(home, /NVIDIA review/);
});

test("absent human evaluation makes no request", async (context) => {
  context.mock.method(globalThis, "fetch", () => { throw new Error("Unexpected evaluation request"); });
  assert.equal(await api.getDesignAgentEvaluation("run", false), null);
});

test("present human evaluation still loads normally", async (context) => {
  context.mock.method(globalThis, "fetch", async () => Response.json({ id: "human-review", overall_score: 0.8 }));
  assert.equal((await api.getDesignAgentEvaluation("run", true)).id, "human-review");
});

for (const status of [401, 403, 404, 500]) {
  test(`unexpected human-evaluation ${status} is not hidden as absence`, async (context) => {
    context.mock.method(globalThis, "fetch", async () => Response.json({ detail: "Evaluation unavailable" }, { status }));
    await assert.rejects(api.getDesignAgentEvaluation("run", true),
      error => error instanceof ApiRequestError && error.status === status);
  });
}
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

test("run API retains advisory paths and exact compared values separately from critique", async (context) => {
  const evaluation = { artifact_id: "draft", advisories: [advisory] };
  context.mock.method(globalThis, "fetch", async () => Response.json({
    id: "run", draft_evaluation: evaluation, critique: { content: { findings: [], verdict: "ready_for_review" } },
  }));
  const run = await api.getDesignAgentRun("run");
  assert.deepEqual(run.draft_evaluation, evaluation);
  assert.deepEqual(run.critique.content.findings, []);
  assert.equal(run.critique.content.verdict, "ready_for_review");
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
