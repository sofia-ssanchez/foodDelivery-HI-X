
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Eligibility = {
  eligibility_status: "eligible" | "ineligible" | "manual_review";
  eligibility_reasons: string[];
  suggested_refund_type: string;
  maximum_refundable_amount: string;
};

type RefundResponse = {
  refunds?: RefundRequest[];
  results?: RefundRequest[];
};

type RefundRequest = {
  id: number;
  order_id: number;
  customer: string;
  restaurant: string;
  order_status: string;
  reason: string;
  reason_code: string;
  details: string;
  requested_amount: string | null;
  status: "pending" | "approved" | "rejected";
  approved_amount: string | null;
  eligibility: Eligibility;
  decision_notes: string;
  created_at: string;
  decided_at: string | null;
  operator: string | null;
};

type Filter = "all" | "pending" | "approved" | "rejected";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-100 text-amber-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
    eligible: "bg-green-100 text-green-800",
    ineligible: "bg-red-100 text-red-800",
    manual_review: "bg-amber-100 text-amber-800",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        styles[status] || "bg-gray-100 text-gray-700"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

function SummaryCard({
  label,
  count,
}: {
  label: string;
  count: number;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-5">
      <p className="text-2xl font-bold text-[var(--color-forest)] sm:text-3xl">
        {count}
      </p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">{label}</p>
    </div>
  );
}

function EligibilityDetails({
  eligibility,
}: {
  eligibility: Eligibility;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-sage-light)] p-4">
      <h3 className="font-semibold text-[var(--color-forest)]">
        Eligibility Assessment
      </h3>

      <div className="mt-3">
        <StatusBadge status={eligibility.eligibility_status} />
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <div>
          <p className="font-medium text-[var(--color-forest)]">
            Suggested review type
          </p>
          <p className="mt-1 text-[var(--color-muted)]">
            {formatStatus(eligibility.suggested_refund_type)}
          </p>
        </div>

        <div>
          <p className="font-medium text-[var(--color-forest)]">
            Maximum refundable amount
          </p>
          <p className="mt-1 text-[var(--color-muted)]">
            ${Number(eligibility.maximum_refundable_amount).toFixed(2)}
          </p>
        </div>

        <div>
          <p className="font-medium text-[var(--color-forest)]">
            Assessment details
          </p>

          {eligibility.eligibility_reasons.length > 0 ? (
            <ul className="mt-2 list-inside list-disc space-y-1 text-[var(--color-muted)]">
              {eligibility.eligibility_reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-[var(--color-muted)]">
              No additional concerns identified.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function OperatorRefundsPage() {
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [filter, setFilter] = useState<Filter>("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [approvedAmounts, setApprovedAmounts] = useState<
    Record<number, string>
  >({});

  const [decisionNotes, setDecisionNotes] = useState<
    Record<number, string>
  >({});

  const [submittingId, setSubmittingId] = useState<number | null>(null);

  const loadRefunds = useCallback(async () => {
  try {
    setLoading(true);
    setError("");

    const response = await apiFetch("/api/pricing/operator/refunds/");
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to load refund requests."
      );
    }

    const requests: RefundRequest[] = Array.isArray(data)
      ? data
      : data.refunds ?? data.results ?? [];

    requests.sort(
      (a, b) =>
        new Date(b.created_at).getTime() -
        new Date(a.created_at).getTime()
    );

    setRefunds(requests);

    const amounts: Record<number, string> = {};

    requests.forEach((refund) => {
      amounts[refund.id] =
        refund.requested_amount ||
        refund.eligibility.maximum_refundable_amount ||
        "";
    });

    setApprovedAmounts(amounts);
  } catch (err) {
    console.error(err);
    setError(
      err instanceof Error
        ? err.message
        : "Unable to load refund requests."
    );
  } finally {
    setLoading(false);
  }
}, []);

  useEffect(() => {
    loadRefunds();
  }, [loadRefunds]);

  const pendingCount = refunds.filter(
    (refund) => refund.status === "pending"
  ).length;

  const approvedCount = refunds.filter(
    (refund) => refund.status === "approved"
  ).length;

  const rejectedCount = refunds.filter(
    (refund) => refund.status === "rejected"
  ).length;

  const filteredRefunds = refunds.filter((refund) => {
    if (filter === "all") return true;
    return refund.status === filter;
  });

  async function submitDecision(
  refund: RefundRequest,
  decision: "approve" | "reject"
) {
  setError("");
  setMessage("");

  const notes = decisionNotes[refund.id] || "";

  if (decision === "reject" && !notes.trim()) {
    setError("Please provide a reason before rejecting a refund.");
    return;
  }

  if (
    decision === "approve" &&
    refund.eligibility.eligibility_status === "ineligible"
  ) {
    setError("This refund request is marked as ineligible.");
    return;
  }

  const amount = Number(approvedAmounts[refund.id]);

  if (decision === "approve") {
    const maximum = Number(
      refund.eligibility.maximum_refundable_amount
    );

    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Enter a valid refund amount greater than zero.");
      return;
    }

    if (amount > maximum) {
      setError(
        `The refund cannot exceed the remaining balance of $${maximum.toFixed(2)}.`
      );
      return;
    }

    if (
      refund.requested_amount &&
      amount > Number(refund.requested_amount)
    ) {
      setError(
        "The approved amount cannot exceed the amount requested by the customer."
      );
      return;
    }

    if (
      refund.eligibility.eligibility_status === "manual_review" &&
      !notes.trim()
    ) {
      setError(
        "Please provide decision notes explaining your manual review."
      );
      return;
    }
  }

  const confirmed = window.confirm(
    decision === "approve"
      ? `Approve a refund of $${amount.toFixed(2)} for order #${refund.order_id}?`
      : `Reject the refund request for order #${refund.order_id}?`
  );

  if (!confirmed) return;

  try {
    setSubmittingId(refund.id);

    const response = await apiFetch(
      `/api/pricing/operator/refunds/${refund.id}/decision/`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          decision,
          approved_amount:
            decision === "approve" ? amount.toFixed(2) : null,
          decision_notes: notes,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to process this refund decision."
      );
    }

    setMessage(
      decision === "approve"
        ? "Refund approved successfully."
        : "Refund request rejected successfully."
    );

    await loadRefunds();

  } catch (err) {
    console.error(err);
    setError(
      err instanceof Error
        ? err.message
        : "Unable to process this refund decision."
    );
  } finally {
    setSubmittingId(null);
  }
}

  return (
    <main className="page-container botanical-background flex w-full flex-col">
    <header className="mb-8 flex w-full items-center justify-between gap-4">
      <div>
        <p className="eyebrow">Operator Dashboard</p>
        <h1 className="page-title">Refund Requests</h1>
        <p className="form-help mt-2">
          Review customer refund requests and make refund decisions.
        </p>
      </div>

      <a
        href="/dashboard/operator"
        className="shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm font-semibold text-[var(--color-forest)] transition hover:bg-[var(--color-sage-light)]"
      >
        ← Back to Overview
      </a>
    </header>

      {/* SUMMARY NUMBERS */}
      <section className="mb-10 flex w-full flex-row items-stretch gap-4">
        <div className="min-w-0 flex-1">
          <SummaryCard label="Pending" count={pendingCount} />
        </div>

        <div className="min-w-0 flex-1">
          <SummaryCard label="Approved" count={approvedCount} />
        </div>

        <div className="min-w-0 flex-1">
          <SummaryCard label="Rejected" count={rejectedCount} />
        </div>
      </section>

      {/* CUSTOMER REQUESTS */}
      <section className="flex w-full flex-col">
        <div className="mb-5">
          <h2 className="section-title">Customer Requests</h2>
          <p className="form-help mt-1">
            Select a request to review its details and make a decision.
          </p>
        </div>

        {/* FILTERS */}
        <div className="mb-6 flex flex-wrap gap-2">
          {(["pending", "approved", "rejected", "all"] as Filter[]).map(
            (value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  filter === value
                    ? "bg-[var(--color-forest)] text-white"
                    : "border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-muted)] hover:bg-[var(--color-sage-light)]"
                }`}
              >
                {value === "all" ? "All Requests" : formatStatus(value)}
              </button>
            )
          )}
        </div>

        {/* FEEDBACK */}
        {error && (
          <div className="message message-error mb-5">
            {error}
          </div>
        )}

        {message && (
          <div className="mb-5 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            {message}
          </div>
        )}

        {/* REQUEST LIST */}
        {loading ? (
          <p className="body-text">Loading refund requests...</p>
        ) : filteredRefunds.length === 0 ? (
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center">
            <h3 className="font-semibold text-[var(--color-forest)]">
              No refund requests found
            </h3>
            <p className="form-help mt-2">
              There are no {filter === "all" ? "" : filter} refund requests.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {filteredRefunds.map((refund) => (
              <article
                key={refund.id}
                className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-sm sm:p-6"
              >
                {/* REQUEST HEADER */}
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="eyebrow">Refund Request #{refund.id}</p>
                    <h3 className="mt-1 text-lg font-semibold text-[var(--color-forest)]">
                      Order #{refund.order_id}
                    </h3>
                  </div>

                  <StatusBadge status={refund.status} />
                </div>

                {/* CUSTOMER AND ORDER INFORMATION */}
                <div className="mb-5 border-t border-[var(--color-border)] pt-5">
                  <h4 className="mb-3 font-semibold text-[var(--color-forest)]">
                    Customer and Order Information
                  </h4>

                  <div className="flex flex-col gap-3 text-sm">
                    <div>
                      <p className="text-[var(--color-muted)]">Customer</p>
                      <p className="font-medium">{refund.customer}</p>
                    </div>

                    <div>
                      <p className="text-[var(--color-muted)]">Restaurant</p>
                      <p className="font-medium">{refund.restaurant}</p>
                    </div>

                    <div>
                      <p className="text-[var(--color-muted)]">Order status</p>
                      <p className="font-medium">
                        {formatStatus(refund.order_status)}
                      </p>
                    </div>

                    <div>
                      <p className="text-[var(--color-muted)]">
                        Requested amount
                      </p>
                      <p className="font-medium">
                        {refund.requested_amount
                          ? `$${Number(refund.requested_amount).toFixed(2)}`
                          : "No amount specified"}
                      </p>
                    </div>

                    <div>
                      <p className="text-[var(--color-muted)]">
                        Request submitted
                      </p>
                      <p className="font-medium">
                        {formatDate(refund.created_at)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* REASON */}
                <div className="mb-5 border-t border-[var(--color-border)] pt-5">
                  <h4 className="mb-3 font-semibold text-[var(--color-forest)]">
                    Customer's Reason
                  </h4>

                  <p className="text-sm font-medium">
                    {refund.reason}
                  </p>

                  {refund.details && (
                    <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--color-muted)]">
                      {refund.details}
                    </p>
                  )}
                </div>

                {/* ELIGIBILITY */}
                <div className="mb-5 border-t border-[var(--color-border)] pt-5">
                  <EligibilityDetails eligibility={refund.eligibility} />
                </div>

                {/* OPERATOR DECISION */}
                {refund.status === "pending" ? (
                  <div className="border-t border-[var(--color-border)] pt-5">
                    <h4 className="mb-4 font-semibold text-[var(--color-forest)]">
                      Operator Decision
                    </h4>

                    <div className="flex flex-col gap-4">
                      <div>
                        <label
                          htmlFor={`amount-${refund.id}`}
                          className="mb-2 block text-sm font-medium"
                        >
                          Approved refund amount ($)
                        </label>

                        <input
                          id={`amount-${refund.id}`}
                          type="number"
                          min="0.01"
                          max={refund.eligibility.maximum_refundable_amount}
                          step="0.01"
                          value={approvedAmounts[refund.id] || ""}
                          onChange={(event) =>
                            setApprovedAmounts((previous) => ({
                              ...previous,
                              [refund.id]: event.target.value,
                            }))
                          }
                          disabled={
                            refund.eligibility.eligibility_status ===
                            "ineligible"
                          }
                          className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-gray-100"
                        />

                        <p className="form-help mt-1">
                          Maximum refundable amount: $
                          {Number(
                            refund.eligibility.maximum_refundable_amount
                          ).toFixed(2)}
                        </p>
                      </div>

                      <div>
                        <label
                          htmlFor={`notes-${refund.id}`}
                          className="mb-2 block text-sm font-medium"
                        >
                          Decision notes
                        </label>

                        <textarea
                          id={`notes-${refund.id}`}
                          rows={3}
                          value={decisionNotes[refund.id] || ""}
                          onChange={(event) =>
                            setDecisionNotes((previous) => ({
                              ...previous,
                              [refund.id]: event.target.value,
                            }))
                          }
                          placeholder="Explain your decision or provide additional review notes..."
                          className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
                        />
                        <p className="form-help mt-1">
                          Required when rejecting a request or approving one
                          that needs manual review.
                        </p>
                      </div>

                      <div className="flex flex-col gap-3">
                        <button
                          type="button"
                          onClick={() =>
                            submitDecision(refund, "approve")
                          }
                          disabled={
                            submittingId === refund.id ||
                            refund.eligibility.eligibility_status ===
                              "ineligible"
                          }
                          className="w-full rounded-lg bg-[var(--color-forest)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {submittingId === refund.id
                            ? "Processing..."
                            : "Approve Refund"}
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            submitDecision(refund, "reject")
                          }
                          disabled={submittingId === refund.id}
                          className="w-full rounded-lg border border-red-300 bg-white px-5 py-3 text-sm font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Reject Request
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* PREVIOUS DECISION */
                  <div className="border-t border-[var(--color-border)] pt-5">
                    <h4 className="mb-3 font-semibold text-[var(--color-forest)]">
                      Decision Details
                    </h4>

                    <div className="flex flex-col gap-3 text-sm">
                      {refund.approved_amount && (
                        <div>
                          <p className="text-[var(--color-muted)]">
                            Approved amount
                          </p>
                          <p className="font-medium">
                            ${Number(refund.approved_amount).toFixed(2)}
                          </p>
                        </div>
                      )}

                      <div>
                        <p className="text-[var(--color-muted)]">
                          Decision notes
                        </p>
                        <p className="whitespace-pre-wrap">
                          {refund.decision_notes || "No notes provided."}
                        </p>
                      </div>

                      <div>
                        <p className="text-[var(--color-muted)]">
                          Decided by
                        </p>
                        <p className="font-medium">
                          {refund.operator || "Unknown"}
                        </p>
                      </div>

                      {refund.decided_at && (
                        <div>
                          <p className="text-[var(--color-muted)]">
                            Decision date
                          </p>
                          <p className="font-medium">
                            {formatDate(refund.decided_at)}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
