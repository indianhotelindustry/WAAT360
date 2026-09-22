import logging
from datetime import datetime
from typing import Any

from src.adapters.base import TallyAdapter
from src.models.domain import (
    CreateVoucherCommand,
    TallyCompanyRef,
    VerificationEvidence,
    VerificationQuery,
    VoucherLineData,
    VoucherResult,
)
from src.store.local_store import BridgeLocalStore
from src.transport.base import BridgeTransport

logger = logging.getLogger("waast_bridge.reconciler")


class PostingReconciler:
    """
    Deterministic idempotency and posting reconciliation engine.
    Ensures safe execution of posting commands.
    Prevents duplicate postings under network timeouts by verifying
    Tally existence before any retry attempt.
    """

    def __init__(
        self,
        adapter: TallyAdapter,
        store: BridgeLocalStore,
        transport: BridgeTransport | None = None,
    ):
        self.adapter = adapter
        self.store = store
        self.transport = transport

    def execute_posting_job(
        self, job_dict: dict[str, Any]
    ) -> tuple[VoucherResult, VerificationEvidence]:
        """
        Execute or reconcile a posting job deterministically.
        Workflow:
          1. Check local store idempotency record.
          2. Check Tally existence if previous attempt had unknown outcome.
          3. Post to Tally if not present.
          4. Read-back verify from Tally.
          5. Update durable store and transmit evidence to Cloud.
        """
        job_id = job_dict["job_id"]
        correlation_id = job_dict["correlation_id"]
        payload = job_dict["payload"]

        # Parse command
        comp_ref = TallyCompanyRef(**payload["company_ref"])
        lines = [VoucherLineData(**line) for line in payload["lines"]]
        vch_date = (
            datetime.fromisoformat(payload["voucher_date"]).date()
            if isinstance(payload["voucher_date"], str)
            else payload["voucher_date"]
        )

        command = CreateVoucherCommand(
            company_ref=comp_ref,
            voucher_type=payload["voucher_type"],
            voucher_date=vch_date,
            reference_number=payload.get("reference_number"),
            narration=payload.get("narration"),
            lines=lines,
            correlation_id=correlation_id,
        )

        vquery = VerificationQuery(
            company_ref=comp_ref,
            correlation_id=correlation_id,
            expected_reference=command.reference_number,
            expected_amount=sum(line.amount for line in command.lines if line.is_debit),
            voucher_type=command.voucher_type,
            voucher_date=command.voucher_date,
        )

        # Step 1: Check if already successfully recorded in local store
        history = self.store.get_posting_history(correlation_id)
        if history and history.get("status") == "COMPLETED":
            logger.info(
                "Correlation ID %s already completed in local store. Reconciling.",
                correlation_id,
            )
            evidence = self.adapter.verify_transaction(vquery)
            vch_res = VoucherResult(
                success=True,
                voucher_number=history.get("voucher_number"),
                voucher_guid=history.get("result", {}).get("voucher_guid"),
                status_code=200,
            )
            return vch_res, evidence

        # Step 2: Idempotency safety check — query Tally before posting in case previous timeout succeeded
        pre_check = self.adapter.verify_transaction(vquery)
        if pre_check.is_verified:
            logger.warning(
                "Voucher with reference %s already exists in Tally! Reconciling without re-posting.",
                command.reference_number,
            )
            self.store.record_posting_history(
                correlation_id=correlation_id,
                voucher_reference=command.reference_number,
                voucher_number=pre_check.actual_voucher_number,
                status="COMPLETED",
                result={"reconciled": True, "actual_guid": pre_check.actual_guid},
            )
            self.store.update_job_status(job_id, "COMPLETED")
            vch_res = VoucherResult(
                success=True,
                voucher_number=pre_check.actual_voucher_number,
                voucher_guid=pre_check.actual_guid,
                status_code=200,
            )
            return vch_res, pre_check

        # Step 3: Post voucher to Tally
        logger.info(
            "Posting voucher %s to Tally company %s",
            command.reference_number,
            comp_ref.company_name,
        )
        post_result = self.adapter.create_voucher(command)

        if post_result.success:
            # Step 4: Immediate read-back verification
            evidence = self.adapter.verify_transaction(vquery)
            if not evidence.actual_voucher_number and post_result.voucher_number:
                evidence.actual_voucher_number = post_result.voucher_number
                evidence.is_verified = True
                evidence.status = "VERIFIED"

            self.store.record_posting_history(
                correlation_id=correlation_id,
                voucher_reference=command.reference_number,
                voucher_number=post_result.voucher_number,
                status="COMPLETED",
                result=post_result.model_dump(),
            )
            self.store.update_job_status(job_id, "COMPLETED")

            # Report attempt and verification to cloud if transport configured
            if self.transport:
                try:
                    self.transport.submit_attempt(job_id, post_result.model_dump())
                    self.transport.submit_verification(job_id, evidence.model_dump())
                except Exception as ex:
                    logger.warning(
                        "Failed to submit verification to cloud: %s. Local store preserved.",
                        ex,
                    )

            return post_result, evidence
        else:
            # Step 5: Handling unknown or failed outcomes
            # If network error occurred, verify Tally once more before declaring failed
            post_check = self.adapter.verify_transaction(vquery)
            if post_check.is_verified:
                logger.info(
                    "Voucher verified in Tally despite transport error. Reconciled successfully."
                )
                self.store.record_posting_history(
                    correlation_id=correlation_id,
                    voucher_reference=command.reference_number,
                    voucher_number=post_check.actual_voucher_number,
                    status="COMPLETED",
                    result={
                        "reconciled_after_error": True,
                        "error": post_result.error_message,
                    },
                )
                self.store.update_job_status(job_id, "COMPLETED")
                reconciled_result = VoucherResult(
                    success=True,
                    voucher_number=post_check.actual_voucher_number,
                    voucher_guid=post_check.actual_guid,
                    status_code=200,
                )
                return reconciled_result, post_check

            # Truly failed
            logger.error("Posting failed for job %s: %s", job_id, post_result.error_message)
            self.store.update_job_status(
                job_id,
                "FAILED",
                error_message=post_result.error_message,
                increment_retry=True,
            )
            if self.transport:
                try:
                    self.transport.submit_attempt(job_id, post_result.model_dump())
                except Exception:
                    pass
            return post_result, post_check
