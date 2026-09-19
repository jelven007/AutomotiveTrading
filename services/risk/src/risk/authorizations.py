import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from risk.models import (
    RiskApproval,
    RiskEvaluationRecord,
    RiskPolicyRecord,
    RiskSnapshotRecord,
)
from risk.policy import OrderRiskInput, RiskDecision, RiskEvaluator, RiskPolicy, RiskSnapshot


class AuthorizationError(RuntimeError):
    pass


class PolicyNotFoundError(LookupError):
    pass


class AuthorizationIssueResult(BaseModel):
    authorization_id: str | None
    approved: bool
    approval_token: str | None
    expires_at: datetime | None
    reasons: list[str]
    decision: RiskDecision


class RiskAuthorizationService:
    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
        token_ttl_seconds: int = 60,
    ) -> None:
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))
        self.token_ttl_seconds = token_ttl_seconds

    def set_policy(self, tenant_id: str, policy: RiskPolicy) -> int:
        current = self.session.scalar(
            select(RiskPolicyRecord)
            .where(
                RiskPolicyRecord.tenant_id == tenant_id,
                RiskPolicyRecord.enabled.is_(True),
            )
            .order_by(RiskPolicyRecord.version.desc())
        )
        if current is not None:
            current.enabled = False
        version = (
            self.session.scalar(
                select(func.max(RiskPolicyRecord.version)).where(
                    RiskPolicyRecord.tenant_id == tenant_id
                )
            )
            or 0
        ) + 1
        self.session.add(
            RiskPolicyRecord(
                tenant_id=tenant_id,
                version=version,
                enabled=True,
                policy_json=policy.model_dump_json(),
            )
        )
        self.session.commit()
        return version

    def get_policy(self, tenant_id: str) -> tuple[int, RiskPolicy]:
        record = self.session.scalar(
            select(RiskPolicyRecord)
            .where(
                RiskPolicyRecord.tenant_id == tenant_id,
                RiskPolicyRecord.enabled.is_(True),
            )
            .order_by(RiskPolicyRecord.version.desc())
        )
        if record is None:
            raise PolicyNotFoundError("active risk policy not found")
        return record.version, RiskPolicy.model_validate_json(record.policy_json)

    def issue(
        self,
        *,
        tenant_id: str,
        account_id: str,
        order_payload: dict[str, object],
        snapshot_payload: dict[str, object],
    ) -> AuthorizationIssueResult:
        policy_version, policy = self.get_policy(tenant_id)
        order = OrderRiskInput.model_validate(order_payload)
        snapshot = RiskSnapshot.model_validate(snapshot_payload)
        decision = RiskEvaluator(clock=self.clock).evaluate(policy, order, snapshot)
        fingerprint = self._fingerprint(order)
        snapshot_as_of = (
            snapshot.as_of.astimezone(UTC).replace(tzinfo=None)
            if snapshot.as_of.tzinfo
            else snapshot.as_of
        )
        self.session.add(
            RiskSnapshotRecord(
                tenant_id=tenant_id,
                account_id=account_id,
                account_scope=order.account_scope.value,
                snapshot_json=snapshot.model_dump_json(),
                as_of=snapshot_as_of,
            )
        )
        evaluation = RiskEvaluationRecord(
            tenant_id=tenant_id,
            account_id=account_id,
            policy_version=policy_version,
            order_fingerprint=fingerprint,
            approved=decision.approved,
            reasons_json=json.dumps(decision.reasons, separators=(",", ":")),
            metrics_json=json.dumps(
                {
                    "order_notional": str(decision.order_notional),
                    "projected_daily_notional": str(decision.projected_daily_notional),
                    "projected_position_notional": str(decision.projected_position_notional),
                },
                separators=(",", ":"),
            ),
        )
        self.session.add(evaluation)
        self.session.flush()
        if not decision.approved:
            self.session.commit()
            return AuthorizationIssueResult(
                authorization_id=None,
                approved=False,
                approval_token=None,
                expires_at=None,
                reasons=decision.reasons,
                decision=decision,
            )

        token = secrets.token_urlsafe(32)
        expires_at = self._now() + timedelta(seconds=self.token_ttl_seconds)
        approval = RiskApproval(
            tenant_id=tenant_id,
            account_id=account_id,
            evaluation_id=evaluation.id,
            token_hash=self._token_hash(token),
            order_fingerprint=fingerprint,
            expires_at=expires_at,
        )
        self.session.add(approval)
        self.session.commit()
        return AuthorizationIssueResult(
            authorization_id=approval.id,
            approved=True,
            approval_token=token,
            expires_at=expires_at.replace(tzinfo=UTC),
            reasons=[],
            decision=decision,
        )

    def verify_and_consume(
        self,
        *,
        tenant_id: str,
        account_id: str,
        order_payload: dict[str, object],
        approval_token: str,
    ) -> bool:
        token_hash = self._token_hash(approval_token)
        approval = self.session.scalar(
            select(RiskApproval).where(RiskApproval.token_hash == token_hash)
        )
        if approval is None:
            raise AuthorizationError("approval token is invalid")
        if not hmac.compare_digest(approval.tenant_id, tenant_id):
            raise AuthorizationError("approval token tenant mismatch")
        if not hmac.compare_digest(approval.account_id, account_id):
            raise AuthorizationError("approval token account mismatch")
        order = OrderRiskInput.model_validate(order_payload)
        if not hmac.compare_digest(approval.order_fingerprint, self._fingerprint(order)):
            raise AuthorizationError("approval token order mismatch")
        if approval.expires_at <= self._now():
            raise AuthorizationError("approval token expired")
        if approval.consumed_at is not None:
            raise AuthorizationError("approval token already consumed")

        result = self.session.execute(
            update(RiskApproval)
            .where(
                RiskApproval.id == approval.id,
                RiskApproval.consumed_at.is_(None),
                RiskApproval.expires_at > self._now(),
            )
            .values(consumed_at=self._now())
        )
        if getattr(result, "rowcount", 0) != 1:
            self.session.rollback()
            raise AuthorizationError("approval token already consumed")
        self.session.commit()
        return True

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _fingerprint(order: OrderRiskInput) -> str:
        payload = json.dumps(
            order.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
