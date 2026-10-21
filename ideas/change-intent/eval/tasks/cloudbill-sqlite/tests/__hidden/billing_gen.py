"""Deterministic generator of cloud billing exports for the cloudbill tasks.

    python billing_gen.py sample OUTDIR      # the two sample exports shipped in the seed's sample/

Never copied into a seed. ``scripts/build_tasks.py`` writes the seed's ``sample/`` by running it; the
hidden tests build small exports with ``Item`` and ``Export`` and one large export with
``write_large()``. Expected answers come from the oracle functions at the bottom, computed
from the generator's own records, never by parsing the CSV, so a parsing bug cannot be shared between
the oracle and the tool under test.

The oracle encodes only what the brief states:
  * a row is rejected when it cannot be read: wrong number of fields, no line item id, no usage start,
    a cost that is not a number, a line item type other than usage, tax, fee, credit and refund, or a
    currency other than USD; formatting a person would read the same way (case, surrounding whitespace,
    thousands separators) is not a reason to reject;
  * a restated line item (same id, later ``last_updated``) replaces the earlier version, whatever the
    file order;
  * a line belongs to the UTC date its usage starts on; accounts are account ids; services are the same
    service whatever their case; a tag that is blank or whose column is absent is untagged;
  * charges are usage, tax and fee lines; credits are credit and refund lines; net is their sum.
"""

from __future__ import annotations

import csv
import io
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=-7))  # the billing account's local time; a distractor, never the day
Q4 = Decimal("0.0001")

COLUMNS = [
    "line_item_id", "billing_period", "account_id", "account_name", "service", "region", "usage_type",
    "resource_id", "usage_start", "usage_end", "usage_start_local", "usage_amount", "usage_unit",
    "unblended_cost", "currency", "line_item_type", "last_updated", "tag:team", "tag:env", "tag:cost-center",
    "description",
]
CHARGE_TYPES = ("usage", "tax", "fee")
CREDIT_TYPES = ("credit", "refund")


def ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local(dt: datetime) -> str:
    return dt.astimezone(LOCAL).strftime("%Y-%m-%d %H:%M:%S %z")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Q4)


_ids = {"n": 0}


def new_id(prefix: str = "") -> str:
    """Line item ids look like the vendor's: 20 lowercase hex digits. Deterministic per process."""
    _ids["n"] += 1
    return f"{prefix}{(_ids['n'] * 0x9E3779B97F4A7C15) & ((1 << 80) - 1):020x}"


@dataclass
class Item:
    line_item_id: str
    account_id: str
    service: str
    start: datetime
    cost: Decimal
    line_item_type: str = "Usage"
    end: datetime | None = None
    account_name: str = ""
    region: str = "us-west-2"
    usage_type: str = ""
    resource_id: str = ""
    usage_amount: str = "1"
    usage_unit: str = "Hrs"
    currency: str = "USD"
    last_updated: datetime | None = None
    tags: dict = field(default_factory=dict)
    description: str = ""
    billing_period: str | None = None
    cost_text: str | None = None  # literal text for unblended_cost (thousands separators, padding)
    bad: str | None = None  # short | long | cost | start | id | kind: how the row is broken; None = readable

    def __post_init__(self) -> None:
        self.cost = money(self.cost)
        if self.end is None:
            self.end = self.start + timedelta(days=1)
        if self.last_updated is None:
            self.last_updated = self.end + timedelta(hours=4)

    @property
    def rejected(self) -> bool:
        return self.bad is not None or self.currency.strip().upper() != "USD"

    def values(self) -> dict[str, str]:
        v = {
            "line_item_id": self.line_item_id,
            "billing_period": self.billing_period or self.start.strftime("%Y-%m"),
            "account_id": self.account_id,
            "account_name": self.account_name,
            "service": self.service,
            "region": self.region,
            "usage_type": self.usage_type,
            "resource_id": self.resource_id,
            "usage_start": iso(self.start),
            "usage_end": iso(self.end),
            "usage_start_local": local(self.start),
            "usage_amount": self.usage_amount,
            "usage_unit": self.usage_unit,
            "unblended_cost": self.cost_text if self.cost_text is not None else f"{self.cost:.4f}",
            "currency": self.currency,
            "line_item_type": self.line_item_type,
            "last_updated": iso(self.last_updated),
            "description": self.description,
        }
        for key, value in self.tags.items():
            v[f"tag:{key}"] = value
        if self.bad == "cost":
            v["unblended_cost"] = "#VALUE!"
        elif self.bad == "start":
            v["usage_start"] = ""
        elif self.bad == "id":
            v["line_item_id"] = ""
        elif self.bad == "kind":  # a line item type the brief does not know
            v["line_item_type"] = "Discount"
        return v

    def render(self, columns: list[str]) -> list[str]:
        v = self.values()
        row = [v.get(c, "") for c in columns]
        if self.bad == "short":
            row = row[:-2]
        elif self.bad == "long":  # an unquoted comma in the description: one field too many
            i = columns.index("description")
            head, _, tail = (self.description or "see notes, attached").partition(",")
            row[i:i + 1] = [head, tail or " attached"]
        return row


@dataclass
class Export:
    items: list[Item]
    columns: list[str] = field(default_factory=lambda: list(COLUMNS))
    bom: bool = False
    newline: str = "\n"
    lines: list[int] = field(default_factory=list)  # physical start line of each item, set by text()

    def text(self) -> str:
        parts, self.lines = [], []
        line = 1
        for row in [self.columns] + [it.render(self.columns) for it in self.items]:
            buf = io.StringIO()
            csv.writer(buf, lineterminator=self.newline).writerow(row)
            s = buf.getvalue()
            if parts:
                self.lines.append(line)
            parts.append(s)
            line += s.count("\n")
        return "".join(parts)

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((("﻿" if self.bom else "") + self.text()).encode("utf-8"))
        return path


# ---- the seed sample ---------------------------------------------------------------------------

ACCOUNTS = {
    "payments": ("012345678901", "payments-prod"),
    "data": ("123456789012", "data-platform"),
    "analytics": ("234567890123", "analytics-sandbox"),
    "shared": ("098765432109", "shared-services "),
}

# (account, service as exported, usage_type, unit, resource_id, region, tags, low, high, description)
DAILY = [
    ("payments", "Compute Engine", "BoxUsage:m6.large", "Hrs", "vm-payments-api-01", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "2.3040", "2.3040", "$0.096 per On Demand Linux m6.large Instance Hour"),
    ("payments", "Compute Engine", "BoxUsage:m6.large", "Hrs", "vm-payments-api-02", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "2.3040", "2.3040", "$0.096 per On Demand Linux m6.large Instance Hour"),
    ("payments", "Compute Engine", "BoxUsage:m6.xlarge", "Hrs", "vm-payments-worker-01", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "4.6080", "4.6080", "$0.192 per On Demand Linux m6.xlarge Instance Hour"),
    ("payments", "Compute Engine", "BoxUsage:m6.large", "Hrs", "vm-payments-batch-01", "us-west-2",
     {"team": "", "env": "prod", "cost-center": ""}, "0.4800", "2.3040", "$0.096 per On Demand Linux m6.large Instance Hour"),
    ("payments", "Managed Database", "InstanceUsage:db.r6.large", "Hrs", "db-payments-primary", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "5.7600", "5.7600", "Managed Database, db.r6.large, Multi-AZ"),
    ("payments", "Object Storage", "TimedStorage-GB-Month", "GB-Mo", "bucket-payments-receipts", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "1.1800", "1.4100", "Standard storage, first 50 TB / month"),
    ("payments", "Load Balancing", "LCUUsage", "LCU-Hrs", "lb-payments-public", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "0.6000", "0.9200", "Application load balancer capacity units"),
    ("data", "Managed Database", "InstanceUsage:db.r6.16xlarge", "Hrs", "db-warehouse-primary", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": "CC-2001"}, "1100.0000", "1650.0000", "Managed Database, db.r6.16xlarge, Multi-AZ"),
    ("data", "Managed Database", "InstanceUsage:db.r6.8xlarge", "Hrs", "db-warehouse-replica", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": "CC-2001"}, "550.0000", "800.0000", "Managed Database, db.r6.8xlarge, read replica"),
    ("data", "Kubernetes", "ClusterHours", "Hrs", "k8s-data-pipelines", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": "CC-2001"}, "2.4000", "2.4000", "Managed Kubernetes control plane"),
    ("data", "Compute Engine", "BoxUsage:c6.4xlarge", "Hrs", "vm-spark-01", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": ""}, "16.3200", "16.3200", "$0.68 per On Demand Linux c6.4xlarge Instance Hour"),
    ("data", "Compute Engine", "BoxUsage:c6.4xlarge", "Hrs", "vm-spark-02", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": ""}, "16.3200", "16.3200", "$0.68 per On Demand Linux c6.4xlarge Instance Hour"),
    ("data", "Compute Engine", "BoxUsage:c6.4xlarge", "Hrs", "vm-spark-03", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": ""}, "8.1600", "16.3200", "$0.68 per On Demand Linux c6.4xlarge Instance Hour"),
    ("data", "Object Storage", "TimedStorage-GB-Month", "GB-Mo", "bucket-data-lake", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": "CC-2001"}, "380.0000", "420.0000", "Standard storage, next 450 TB / month"),
    ("data", "Data Transfer", "DataTransfer-Regional-Bytes", "GB", "bucket-data-lake", "us-east-1",
     {"team": "data", "env": "prod", "cost-center": "CC-2001"}, "20.0000", "60.0000", "Data transfer, inter-region"),
    ("analytics", "compute engine", "BoxUsage:t3.medium", "Hrs", "vm-notebook-01", "us-west-2",
     {"team": "analytics", "env": "dev", "cost-center": "CC-3100"}, "0.9984", "0.9984", "$0.0416 per On Demand Linux t3.medium Instance Hour"),
    ("analytics", "compute engine", "BoxUsage:t3.medium", "Hrs", "vm-notebook-02", "us-west-2",
     {"team": "analytics", "env": "dev", "cost-center": "CC-3100"}, "0.9984", "0.9984", "$0.0416 per On Demand Linux t3.medium Instance Hour"),
    ("analytics", "compute engine", "BoxUsage:t3.xlarge", "Hrs", "vm-scratch-01", "us-west-2",
     {}, "1.2000", "3.9936", "$0.1664 per On Demand Linux t3.xlarge Instance Hour"),
    ("analytics", "object storage", "TimedStorage-GB-Month", "GB-Mo", "bucket-analytics-scratch", "us-west-2",
     {"team": "analytics", "env": "dev", "cost-center": ""}, "0.3000", "0.5000", "Standard storage, first 50 TB / month"),
    ("analytics", "Managed Database", "InstanceUsage:db.t3.large", "Hrs", "db-analytics-sandbox", "us-west-2",
     {"team": "analytics", "env": "dev", "cost-center": "CC-3100"}, "3.1200", "3.1200", "Managed Database, db.t3.large, Single-AZ"),
    ("shared", "Kubernetes ", "ClusterHours", "Hrs", "k8s-shared-platform", "eu-west-1",
     {"team": "platform ", "env": "prod", "cost-center": "CC-0100"}, "2.4000", "2.4000", "Managed Kubernetes control plane – eu-west-1 (Dublin)"),
    ("shared", "Compute Engine", "BoxUsage:m6.large", "Hrs", "vm-ci-runner-01", "eu-west-1",
     {"team": "platform", "env": "ci", "cost-center": "CC-0100"}, "2.3040", "2.3040", "$0.096 per On Demand Linux m6.large Instance Hour"),
    ("shared", "Compute Engine", "BoxUsage:m6.large", "Hrs", "vm-ci-runner-02", "eu-west-1",
     {"team": "platform", "env": "ci", "cost-center": "CC-0100"}, "2.3040", "2.3040", "$0.096 per On Demand Linux m6.large Instance Hour"),
    ("shared", "Monitoring", "MetricsIngested", "Metrics", "monitoring-shared", "eu-west-1",
     {"team": "platform", "env": "prod", "cost-center": "CC-0100"}, "0.0000", "0.0000", "Free tier: first 10,000 metrics"),
    ("shared", "Load Balancing", "LCUUsage", "LCU-Hrs", "lb-shared-internal", "eu-west-1",
     {"team": "platform", "env": "prod", "cost-center": "CC-0100"}, "0.5500", "0.6000", "Network load balancer capacity units"),
    ("shared", "Object Storage", "TimedStorage-GB-Month", "GB-Mo", "bucket-shared-artifacts", "eu-west-1",
     {"team": "platform", "env": "", "cost-center": "CC-0100"}, "2.1000", "2.6000", "Standard storage, first 50 TB / month"),
]
HOURLY = [
    ("payments", "Data Transfer", "DataTransfer-Out-Bytes", "GB", "lb-payments-public", "us-west-2",
     {"team": "payments", "env": "prod", "cost-center": "CC-1042"}, "0.0200", "0.3500", "$0.09 per GB - data transfer out to the internet"),
    ("shared", "Data Transfer", "DataTransfer-Out-Bytes", "GB", "lb-shared-internal", "eu-west-1",
     {"team": "platform", "env": "prod", "cost-center": "CC-0100"}, "0.0100", "0.1200", "$0.09 per GB - data transfer out to the internet"),
]


def _draw(rng: random.Random, low: str, high: str) -> Decimal:
    lo, hi = int(Decimal(low) * 10000), int(Decimal(high) * 10000)
    return Decimal(rng.randint(lo, hi)) / 10000


def _cost_text(account: str, cost: Decimal) -> str | None:
    return f"{cost:,.4f}" if account == "data" else None  # this account's rows went through a spreadsheet


def build_sample(seed: int = 20260918) -> list[tuple[str, Export]]:
    """August 2026 (closed: tax, fees, credits, restatements) and September 2026 up to the 17th."""
    rng = random.Random(seed)
    _ids["n"] = seed
    aug: list[Item] = []
    sep: list[Item] = []
    restate_aug: list[Item] = []
    charges_by_account: dict[str, Decimal] = {}
    first, aug_end, sep_last = date(2026, 8, 1), date(2026, 9, 1), date(2026, 9, 17)
    day = first
    while day <= sep_last:
        target = aug if day < aug_end else sep
        start_of_day = datetime(day.year, day.month, day.day, tzinfo=UTC)
        for acct, service, utype, unit, res, region, tags, lo, hi, desc in DAILY:
            acct_id, name = ACCOUNTS[acct]
            if acct == "analytics" and day >= date(2026, 9, 8):
                name = "analytics-dev"  # renamed mid-month; still the same account
            if acct == "data" and day >= aug_end and service == "Managed Database":
                service = "Managed database"  # the new export pipeline spells it differently
            cost = _draw(rng, lo, hi)
            hours = Decimal(24)
            item = Item(new_id(), acct_id, service, start_of_day, cost, account_name=name, region=region,
                        usage_type=utype, resource_id=res, usage_amount=str(hours) if unit == "Hrs" else f"{cost * 3:.4f}",
                        usage_unit=unit, tags=dict(tags), description=desc, cost_text=_cost_text(acct, cost))
            target.append(item)
            if day < aug_end:
                charges_by_account[acct] = charges_by_account.get(acct, Decimal(0)) + cost
            if acct == "payments" and res == "vm-payments-api-01" and date(2026, 8, 10) <= day <= date(2026, 8, 14):
                restate_aug.append(Item(item.line_item_id, acct_id, service, start_of_day, "2.1120", account_name=name,
                                        region=region, usage_type=utype, resource_id=res, usage_amount="24", usage_unit=unit,
                                        tags=dict(tags), description=desc + " (rate correction)",
                                        last_updated=ts("2026-09-02T10:30:00Z")))
            if acct == "shared" and res == "vm-ci-runner-02" and date(2026, 8, 20) <= day <= date(2026, 8, 22):
                restate_aug.append(Item(item.line_item_id, acct_id, service, start_of_day, "1.1520", account_name=name,
                                        region=region, usage_type=utype, resource_id=res, usage_amount="12", usage_unit=unit,
                                        tags=dict(tags), description=desc + " (runner stopped at noon)",
                                        last_updated=ts("2026-09-02T10:30:00Z")))
        for acct, service, utype, unit, res, region, tags, lo, hi, desc in HOURLY:
            acct_id, name = ACCOUNTS[acct]
            for hour in range(24):
                cost = _draw(rng, lo, hi)
                start = start_of_day + timedelta(hours=hour)
                target.append(Item(new_id(), acct_id, service, start, cost, end=start + timedelta(hours=1),
                                   account_name=name, region=region, usage_type=utype, resource_id=res,
                                   usage_amount=f"{cost / Decimal('0.09'):.4f}", usage_unit=unit, tags=dict(tags),
                                   description=desc))
        day += timedelta(days=1)

    # Bad rows, where a person reading the file would also say "that row is broken".
    aug.insert(412, Item(new_id(), ACCOUNTS["analytics"][0], "object storage", datetime(2026, 8, 6, tzinfo=UTC), "0.4100",
                         account_name="analytics-sandbox", resource_id="bucket-analytics-scratch", usage_unit="GB-Mo",
                         description="Scratch bucket, analytics team", bad="long"))
    aug.insert(1530, Item(new_id(), ACCOUNTS["data"][0], "Data Transfer", datetime(2026, 8, 19, tzinfo=UTC), "41.2000",
                          account_name="data-platform", resource_id="bucket-data-lake", usage_unit="GB",
                          description="Data transfer, inter-region", bad="cost"))
    aug.insert(2100, Item(new_id(), ACCOUNTS["payments"][0], "Load Balancing", datetime(2026, 8, 27, tzinfo=UTC), "0.7000",
                          account_name="payments-prod", resource_id="lb-payments-public", usage_unit="LCU-Hrs",
                          description="Application load balancer capacity units", bad="short"))

    # Month close for August: tax, support fees, credits, a refund, then the restated lines.
    month_start, month_end, closed = ts("2026-08-01T00:00:00Z"), ts("2026-09-01T00:00:00Z"), ts("2026-09-01T06:00:00Z")

    def monthly(acct: str, service: str, kind: str, cost, desc: str, usage_type: str = "") -> Item:
        acct_id, name = ACCOUNTS[acct]
        cost = money(cost)
        return Item(new_id(), acct_id, service, month_start, cost, line_item_type=kind, end=month_end, account_name=name,
                    region="", usage_type=usage_type, usage_amount="", usage_unit="", last_updated=closed,
                    description=desc, cost_text=_cost_text(acct, cost))

    for acct in ("payments", "data", "analytics", "shared"):
        tax = (charges_by_account[acct] * Decimal("0.065")).quantize(Q4)
        aug.append(monthly(acct, "Tax", "Tax", tax, "Sales tax", "Tax"))
    aug.append(monthly("data", "Support", "Fee", "1250.0000", "Business support plan, monthly", "Support"))
    aug.append(monthly("payments", "Support", "Fee", "100.0000", "Developer support plan, monthly", "Support"))
    aug.append(monthly("analytics", "compute engine", "Credit", "-250.0000", 'Promotional credit "Analytics Q3 pilot"'))
    aug.append(monthly("data", "Managed Database", "Credit", "-1500.0000", "Committed use discount, 1-year term, Managed Database"))
    aug.append(monthly("payments", "Managed Database", "Refund", "-312.4400",
                       "Refund for incident INC-4821:\nManaged Database unavailable 2026-08-12 03:10-05:40 UTC,\nper SLA section 4.2"))
    aug.extend(restate_aug)

    # September: a correction to an August line arrives in the September export.
    last_hour = next(i for i in reversed(aug) if i.resource_id == "lb-payments-public" and i.usage_unit == "GB")
    sep.insert(30, Item(last_hour.line_item_id, last_hour.account_id, last_hour.service, last_hour.start, "0.9000",
                        end=last_hour.end, account_name=last_hour.account_name, region=last_hour.region,
                        usage_type=last_hour.usage_type, resource_id=last_hour.resource_id, usage_amount="10.0000",
                        usage_unit="GB", tags=dict(last_hour.tags), billing_period="2026-08",
                        description=last_hour.description + " (metering correction)", last_updated=ts("2026-09-05T12:00:00Z")))
    sep.insert(200, Item(new_id(), ACCOUNTS["shared"][0], "Marketplace", ts("2026-09-01T00:00:00Z"), "49.0000",
                         end=ts("2026-10-01T00:00:00Z"), account_name="shared-services", region="", usage_type="Subscription",
                         resource_id="log-analytics-pro", usage_amount="1", usage_unit="Seat", currency="EUR",
                         tags={"team": "platform", "env": "prod"}, description="Marketplace: LogScope Pro, monthly seat"))
    tail = sep[-1]
    sep.append(Item(new_id(), tail.account_id, "Compute Engine", ts("2026-09-17T00:00:00Z"), "2.3040",
                    account_name=tail.account_name, region="eu-west-1", usage_type="BoxUsage:m6.large", resource_id="vm-ci-runner-03",
                    usage_amount="24", tags={"team": "platform", "env": "ci"},
                    description="$0.096 per On Demand Linux m6.large Instance Hour", bad="short"))

    sep_columns = [c for c in COLUMNS if c not in ("tag:cost-center", "description")]
    sep_columns.insert(sep_columns.index("tag:team"), "description")
    return [
        ("export-2026-08.csv", Export(aug, bom=True, newline="\r\n")),
        ("export-2026-09.csv", Export(sep, columns=sep_columns)),
    ]


def write_sample(directory: Path, seed: int = 20260918) -> list[tuple[Path, Export]]:
    return [(ex.write(Path(directory) / name), ex) for name, ex in build_sample(seed)]


# ---- one large export, streamed, with its expected answers ------------------------------------

def _e4(n: int) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    return f"{sign}{n // 10000}.{n % 10000:04d}"


def write_large(path: Path, rows: int = 600_000, seed: int = 7) -> dict:
    """An hourly export with ``rows`` usage lines (plus credits, restatements and broken rows), written
    without holding it in memory. Returns the expected answers for ``costs --by service`` and ``daily``."""
    rng = random.Random(seed)
    services = ["Compute Engine", "Object Storage", "Managed Database", "Data Transfer", "Kubernetes",
                "Load Balancing", "Monitoring", "Queueing", "Serverless Functions", "Cache"]
    accounts = [f"{rng.randrange(10 ** 12):012d}" for _ in range(25)]
    resources = []
    for a in accounts:
        for r in range(20):
            svc = services[(r + int(a[-2:])) % len(services)]
            team = "" if r % 7 == 0 else f"team-{int(a[-3:]) % 9}"
            resources.append((a, svc, f"res-{a[-4:]}-{r:02d}", team, rng.randint(50, 90000)))
    by_service: dict[str, list[int]] = {s.lower(): [0, 0] for s in services}  # [charges, credits] in 1e-4
    daily: dict[str, int] = {}
    rejected = 0
    restated: list[tuple[list[str], int, int]] = []  # (row, old cost, new cost)
    hours_needed = rows // len(resources) + 1
    t0 = datetime(2026, 8, 1, tzinfo=UTC)
    # Corrections are stamped after the last row's own last_updated (start + 5 h), whatever the row
    # count, so the later version is always the corrected one and the oracle below holds at any size.
    corrected_at = iso(t0 + timedelta(hours=hours_needed + 5, days=7))
    restated_at = iso(t0 + timedelta(hours=hours_needed + 5, days=8))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for a in accounts:  # one credit line per account, on the first day
            amount = -rng.randint(10000, 5000000)
            w.writerow([new_id("c"), "2026-08", a, f"acct-{a[-4:]}", "Compute Engine", "", "", "", iso(t0),
                        iso(t0 + timedelta(days=31)), local(t0), "", "", _e4(amount), "USD", "Credit",
                        "2026-09-01T06:00:00Z", "", "", "", "Committed use discount"])
            by_service["compute engine"][1] += amount
            daily["2026-08-01"] = daily.get("2026-08-01", 0) + amount
        written = 0
        for h in range(hours_needed):
            start = t0 + timedelta(hours=h)
            s_iso, e_iso, s_local = iso(start), iso(start + timedelta(hours=1)), local(start)
            upd = iso(start + timedelta(hours=5))
            day = s_iso[:10]
            period = s_iso[:7]
            for a, svc, res, team, scale in resources:
                if written >= rows:
                    break
                written += 1
                cost = rng.randint(0, scale)
                lid = f"{written * 0x9E3779B97F4A7C15 & ((1 << 80) - 1):020x}"
                row = [lid, period, a, f"acct-{a[-4:]}", svc, "us-east-1", "Usage:hourly", res, s_iso, e_iso, s_local,
                       "1.0000", "Hrs", _e4(cost), "USD", "Usage", upd, team, "prod", "", "Hourly usage, metered"]
                if written % 1999 == 3:
                    mode = (written // 1999) % 4
                    if mode == 0:
                        row = row[:-3]
                    elif mode == 1:
                        row = row + ["unexpected"]
                    elif mode == 2:
                        row[13] = "#VALUE!"
                    else:
                        row[14] = "EUR"
                    rejected += 1
                    w.writerow(row)
                    continue
                final = cost
                if written % 4999 == 17:  # the correction appears BEFORE the original in the file
                    new = cost + rng.randint(1, 900)
                    early = list(row)
                    early[13], early[16], early[-1] = _e4(new), corrected_at, "Hourly usage, metered (corrected)"
                    w.writerow(early)
                    final = new
                elif written % 211 == 5:
                    new = max(0, cost - rng.randint(1, max(1, scale // 2)))
                    restated.append((row, cost, new))
                    final = new
                w.writerow(row)
                by_service[svc.lower()][0] += final
                daily[day] = daily.get(day, 0) + final
        for row, _old, new in restated:
            again = list(row)
            again[13], again[16], again[-1] = _e4(new), restated_at, "Hourly usage, metered (restated)"
            w.writerow(again)
    dec = lambda n: Decimal(n) / 10000  # noqa: E731
    charges = sum(v[0] for v in by_service.values())
    credits = sum(v[1] for v in by_service.values())
    return {
        "by_service": {k: {"charges": dec(v[0]), "credits": dec(v[1]), "net": dec(v[0] + v[1])} for k, v in by_service.items()},
        "total": {"charges": dec(charges), "credits": dec(credits), "net": dec(charges + credits)},
        "daily": {k: dec(v) for k, v in daily.items()},
        "rejected": rejected,
        "rows_written": written + len(accounts) + len(restated),
    }


# ---- oracle ------------------------------------------------------------------------------------

def resolved(exports: list[Export]) -> list[tuple[Item, Export]]:
    """Readable rows, one per line item id: the version with the latest last_updated (ties: the later one)."""
    latest: dict[str, tuple[datetime, int, Item, Export]] = {}
    order = 0
    for ex in exports:
        for it in ex.items:
            order += 1
            if it.rejected:
                continue
            key = it.line_item_id.strip()
            cur = latest.get(key)
            if cur is None or (it.last_updated, order) > (cur[0], cur[1]):
                latest[key] = (it.last_updated, order, it, ex)
    return [(it, ex) for _, _, it, ex in sorted(latest.values(), key=lambda v: v[1])]


def usage_day(it: Item) -> date:
    return it.start.astimezone(UTC).date()


def is_credit(it: Item) -> bool:
    return it.line_item_type.strip().lower() in CREDIT_TYPES


def key_of(it: Item, ex: Export, by: str) -> str | None:
    if by == "account":
        return it.account_id.strip()
    if by == "service":
        return it.service.strip().lower()
    if by == "resource":
        return it.resource_id.strip()
    if by.startswith("tag:"):
        if by not in ex.columns:
            return None
        return it.tags.get(by[4:], "").strip() or None
    raise ValueError(by)


def selected(exports, date_from: date | None = None, date_to: date | None = None):
    for it, ex in resolved(exports):
        d = usage_day(it)
        if (date_from is None or d >= date_from) and (date_to is None or d <= date_to):
            yield it, ex


def totals(exports, by: str, date_from=None, date_to=None) -> tuple[dict, dict]:
    groups: dict = {}
    total = {"charges": Decimal(0), "credits": Decimal(0), "net": Decimal(0)}
    for it, ex in selected(exports, date_from, date_to):
        g = groups.setdefault(key_of(it, ex, by), {"charges": Decimal(0), "credits": Decimal(0), "net": Decimal(0)})
        side = "credits" if is_credit(it) else "charges"
        for target in (g, total):
            target[side] += it.cost
            target["net"] += it.cost
    return groups, total


def daily(exports, date_from=None, date_to=None) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for it, _ in selected(exports, date_from, date_to):
        k = usage_day(it).isoformat()
        out[k] = out.get(k, Decimal(0)) + it.cost
    return out


def monthly(exports, by: str | None = None) -> dict[tuple, Decimal]:
    out: dict[tuple, Decimal] = {}
    for it, ex in selected(exports):
        k = (key_of(it, ex, by) if by else None, usage_day(it).strftime("%Y-%m"))
        out[k] = out.get(k, Decimal(0)) + it.cost
    return out


def account_days(exports, date_from=None, date_to=None) -> dict[str, dict[str, Decimal]]:
    out: dict[str, dict[str, Decimal]] = {}
    for it, _ in selected(exports, date_from, date_to):
        days = out.setdefault(it.account_id.strip(), {})
        k = usage_day(it).isoformat()
        days[k] = days.get(k, Decimal(0)) + it.cost
    return out


def untagged(exports, tag: str, date_from=None, date_to=None) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, list[Decimal]] = {}
    for it, ex in selected(exports, date_from, date_to):
        acc = out.setdefault(it.account_id.strip(), [Decimal(0), Decimal(0)])
        if key_of(it, ex, f"tag:{tag}") is None:
            acc[0] += it.cost
        acc[1] += it.cost
    return {k: (v[0], v[1]) for k, v in out.items()}


def credit_split(exports, date_from=None, date_to=None) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, list[Decimal]] = {}
    for it, _ in selected(exports, date_from, date_to):
        kind = it.line_item_type.strip().lower()
        if kind in CREDIT_TYPES:
            acc = out.setdefault(it.account_id.strip(), [Decimal(0), Decimal(0)])
            acc[0 if kind == "credit" else 1] += it.cost
    return {k: (v[0], v[1]) for k, v in out.items()}


def rejected_count(exports) -> int:
    return sum(1 for ex in exports for it in ex.items if it.rejected)


def rejected_lines(exports) -> list[tuple[int, int]]:
    """(export index, physical start line) of every rejected row; call after writing the exports."""
    return [(i, ex.lines[j]) for i, ex in enumerate(exports) for j, it in enumerate(ex.items) if it.rejected]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "sample":
        for path, _ in write_sample(Path(sys.argv[2])):
            print(path)
    else:
        sys.exit("usage: billing_gen.py sample OUTDIR")
