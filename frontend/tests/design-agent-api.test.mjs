import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { api, ApiRequestError } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

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
