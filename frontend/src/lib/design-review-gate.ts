import type { DesignAgentRun, DesignAgentCritiqueFinding, DesignAgentQualityScorecard,
  DesignAgentProposalConfirmation, DesignFindingReview } from "./api";

// Kept separate from advisory rendering: only the existing review policy can block approval.
export function deriveReviewGate({ activeRun, artifactId, critiqueIsCurrent, critiqueFindings,
  findingReview, preApprovalScorecard, selectedProposals, findingBusy, degradedAcknowledged }: {
  activeRun: DesignAgentRun | null;
  artifactId?: string;
  critiqueIsCurrent: boolean;
  critiqueFindings: DesignAgentCritiqueFinding[];
  findingReview: DesignFindingReview | null;
  preApprovalScorecard?: DesignAgentQualityScorecard;
  selectedProposals: DesignAgentProposalConfirmation[];
  findingBusy: boolean;
  degradedAcknowledged: boolean;
}) {
  const pendingProposals = preApprovalScorecard?.unresolved_assumptions ?? [];
  const rawCritiqueBlocked = activeRun?.critique?.content.verdict === "needs_revision"
    || critiqueFindings.some((finding) => finding.severity === "high")
    || (["nvidia", "gemini"].includes(activeRun?.provider_name ?? "") && (activeRun?.critique?.content.verdict !== "ready_for_review"
      || activeRun?.critique?.artifact_id !== artifactId || !preApprovalScorecard));
  const needsRevision = Boolean(activeRun?.critique && !critiqueIsCurrent)
    || (activeRun?.status === "awaiting_review" && Boolean(activeRun.critique?.id) && !findingReview)
    || (["nvidia", "gemini"].includes(activeRun?.provider_name ?? "") && (!preApprovalScorecard || activeRun?.critique?.artifact_id !== artifactId))
    || (findingReview ? findingReview.critique_blocked : rawCritiqueBlocked);
  const confirmationReady = Boolean(preApprovalScorecard && !preApprovalScorecard.passed
    && preApprovalScorecard.blockers.length === 1 && preApprovalScorecard.blockers[0] === "Integration readiness"
    && ["grounding", "completeness", "consistency"].every((key) => preApprovalScorecard.metrics.some((metric) => metric.key === key && metric.passed))
    && preApprovalScorecard.metrics.filter((metric) => metric.key !== "integration_readiness").every((metric) => metric.passed)
    && !preApprovalScorecard.unsupported_sections?.length && !preApprovalScorecard.incomplete_sections?.length
    && !preApprovalScorecard.quest_integration_gaps?.length
    && !preApprovalScorecard.recovered_sections?.length && pendingProposals.length > 0
    && pendingProposals.length <= 64 && selectedProposals.length === pendingProposals.length && !needsRevision);
  const approvalBlocked = Boolean(activeRun?.approval_blocked_reason)
    || findingBusy || needsRevision || (pendingProposals.length > 0 && !confirmationReady)
    || (activeRun?.degraded === true && !degradedAcknowledged)
    || Boolean(preApprovalScorecard && !preApprovalScorecard.passed && !confirmationReady);
  return { needsRevision, confirmationReady, approvalBlocked };
}
