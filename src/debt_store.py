import logging
import math
import os
from collections import defaultdict
from datetime import UTC, datetime

from pymongo import MongoClient

from baml_client.types import Debt


EPSILON = 1e-9
DEFAULT_MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_MONGODB_DB = "overfit_hack_kosice"
DEFAULT_MONGODB_COLLECTION = "debts"

logger = logging.getLogger(__name__)


def has_valid_amount(amount) -> bool:
    return amount is not None and math.isfinite(float(amount)) and float(amount) > EPSILON


def has_valid_currency(currency) -> bool:
    return isinstance(currency, str) and bool(currency.strip())


class DebtStore:
    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        collection_name: str = DEFAULT_MONGODB_COLLECTION,
    ):
        self.client = MongoClient(
            uri or os.getenv("MONGODB_URI", DEFAULT_MONGODB_URI),
            serverSelectionTimeoutMS=3000,
        )
        self.collection = self.client[
            db_name or os.getenv("MONGODB_DB", DEFAULT_MONGODB_DB)
        ][collection_name]
        logger.info(
            "debt store initialized db=%s collection=%s",
            self.collection.database.name,
            self.collection.name,
        )

    def add_debt(self, debt: Debt) -> None:
        if not has_valid_amount(debt.amount) or not has_valid_currency(debt.currency) or debt.debtor == debt.creditor:
            logger.warning(
                "skipping invalid debt debtor=%s creditor=%s amount=%r currency=%r",
                debt.debtor,
                debt.creditor,
                debt.amount,
                debt.currency,
            )
            return

        self.collection.insert_one(
            {
                "debtor": debt.debtor,
                "creditor": debt.creditor,
                "amount": debt.amount,
                "currency": debt.currency,
                "created_at": datetime.now(UTC),
            }
        )
        logger.info(
            "stored debt debtor=%s creditor=%s amount=%s currency=%s",
            debt.debtor,
            debt.creditor,
            debt.amount,
            debt.currency,
        )

    def add_debts(self, debts: list[Debt]) -> None:
        documents = []
        skipped = 0
        for debt in debts:
            if not has_valid_amount(debt.amount) or not has_valid_currency(debt.currency) or debt.debtor == debt.creditor:
                skipped += 1
                logger.warning(
                    "skipping invalid debt debtor=%s creditor=%s amount=%r currency=%r",
                    debt.debtor,
                    debt.creditor,
                    debt.amount,
                    debt.currency,
                )
                continue

            documents.append(
                {
                    "debtor": debt.debtor,
                    "creditor": debt.creditor,
                    "amount": float(debt.amount),
                    "currency": debt.currency,
                    "created_at": datetime.now(UTC),
                }
            )

        if not documents:
            logger.info("no valid debts to store skipped=%s", skipped)
            return

        self.collection.insert_many(documents)
        logger.info("stored debts count=%s skipped=%s", len(documents), skipped)

    def get_simplified_debts(self) -> list[Debt]:
        debts = []
        skipped = 0
        for document in self.collection.find(
            {},
            {"_id": 0, "debtor": 1, "creditor": 1, "amount": 1, "currency": 1},
        ):
            amount = float(document["amount"])
            currency = document.get("currency")
            if not has_valid_amount(amount) or not has_valid_currency(currency) or document["debtor"] == document["creditor"]:
                skipped += 1
                logger.warning("ignoring invalid stored debt document=%s", document)
                continue

            debts.append(
                Debt(
                    debtor=document["debtor"],
                    creditor=document["creditor"],
                    amount=amount,
                    currency=currency,
                )
            )
        logger.info("loaded raw debts count=%s skipped=%s", len(debts), skipped)
        simplified = self._simplify(debts)
        logger.info("simplified debts count=%s", len(simplified))
        return simplified

    @staticmethod
    def _simplify(debts: list[Debt]) -> list[Debt]:
        simplified: list[Debt] = []
        debts_by_currency: dict[str, list[Debt]] = defaultdict(list)

        for debt in debts:
            if not has_valid_currency(debt.currency):
                logger.warning("skipping debt without valid currency during simplify debt=%s", debt)
                continue
            debts_by_currency[debt.currency].append(debt)

        for currency, currency_debts in debts_by_currency.items():
            balances: dict[str, float] = defaultdict(float)
            for debt in currency_debts:
                balances[debt.debtor] -= debt.amount
                balances[debt.creditor] += debt.amount

            debtors: list[list[str | float]] = []
            creditors: list[list[str | float]] = []

            for name, balance in balances.items():
                if balance < -EPSILON:
                    debtors.append([name, -balance])
                elif balance > EPSILON:
                    creditors.append([name, balance])

            debtor_index = 0
            creditor_index = 0

            while debtor_index < len(debtors) and creditor_index < len(creditors):
                debtor_name = str(debtors[debtor_index][0])
                debtor_amount = float(debtors[debtor_index][1])
                creditor_name = str(creditors[creditor_index][0])
                creditor_amount = float(creditors[creditor_index][1])

                if not has_valid_amount(debtor_amount) or not has_valid_amount(creditor_amount):
                    logger.warning(
                        "stopping simplify because of invalid balance currency=%s debtor=%s amount=%r creditor=%s amount=%r",
                        currency,
                        debtor_name,
                        debtor_amount,
                        creditor_name,
                        creditor_amount,
                    )
                    break

                settled = min(debtor_amount, creditor_amount)
                if not has_valid_amount(settled):
                    logger.warning(
                        "stopping simplify because settled amount is invalid currency=%s debtor=%s creditor=%s amount=%r",
                        currency,
                        debtor_name,
                        creditor_name,
                        settled,
                    )
                    break

                simplified.append(
                    Debt(
                        debtor=debtor_name,
                        creditor=creditor_name,
                        amount=settled,
                        currency=currency,
                    )
                )

                debtors[debtor_index][1] = debtor_amount - settled
                creditors[creditor_index][1] = creditor_amount - settled

                if not math.isfinite(float(debtors[debtor_index][1])) or float(debtors[debtor_index][1]) <= EPSILON:
                    debtor_index += 1
                if not math.isfinite(float(creditors[creditor_index][1])) or float(creditors[creditor_index][1]) <= EPSILON:
                    creditor_index += 1

        return simplified

    def close(self) -> None:
        logger.info("closing debt store client")
        self.client.close()
