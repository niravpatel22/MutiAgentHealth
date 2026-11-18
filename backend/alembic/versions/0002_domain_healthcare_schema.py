"""0002_domain_healthcare_schema

Revision ID: 0002_domain_healthcare
Revises: 0001_initial_app
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_domain_healthcare"
down_revision: str | None = "0001_initial_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.String(length=32), nullable=False),
        sa.Column("patient_name", sa.String(length=200), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("age_band", sa.String(length=16), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("phone_masked", sa.String(length=16), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("registration_month", sa.String(length=7), nullable=False),
        sa.Column("insurance_provider", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_patients_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "patient_id", name="pk_patients"),
    )
    op.create_index("ix_patients_dataset_age_band", "patients", ["dataset_id", "age_band"])
    op.create_index("ix_patients_dataset_city", "patients", ["dataset_id", "city"])
    op.create_index(
        "ix_patients_dataset_insurance", "patients", ["dataset_id", "insurance_provider"]
    )
    op.create_index("ix_patients_dataset_month", "patients", ["dataset_id", "registration_month"])

    op.create_table(
        "doctors",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.String(length=32), nullable=False),
        sa.Column("primary_department", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_doctors_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "doctor_id", name="pk_doctors"),
    )

    op.create_table(
        "suppliers",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_suppliers_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "supplier_id", name="pk_suppliers"),
    )

    op.create_table(
        "vendors",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_vendors_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "vendor_name", name="pk_vendors"),
    )

    op.create_table(
        "appointments",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.String(length=32), nullable=False),
        sa.Column("patient_id", sa.String(length=32), nullable=False),
        sa.Column("doctor_id", sa.String(length=32), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("appointment_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("wait_time_minutes", sa.Integer(), nullable=False),
        sa.Column("consultation_fee", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_appointments_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "doctor_id"],
            ["doctors.dataset_id", "doctors.doctor_id"],
            name="fk_appointments_doctor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "patient_id"],
            ["patients.dataset_id", "patients.patient_id"],
            name="fk_appointments_patient",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "appointment_id", name="pk_appointments"),
    )
    op.create_index("ix_appointments_dataset_dept", "appointments", ["dataset_id", "department"])
    op.create_index("ix_appointments_dataset_doctor", "appointments", ["dataset_id", "doctor_id"])
    op.create_index("ix_appointments_dataset_month", "appointments", ["dataset_id", "month"])
    op.create_index("ix_appointments_dataset_patient", "appointments", ["dataset_id", "patient_id"])
    op.create_index("ix_appointments_dataset_status", "appointments", ["dataset_id", "status"])

    op.create_table(
        "invoices",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.String(length=32), nullable=False),
        sa.Column("patient_id", sa.String(length=32), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("payment_status", sa.String(length=30), nullable=False),
        sa.Column("payment_mode", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_invoices_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "patient_id"],
            ["patients.dataset_id", "patients.patient_id"],
            name="fk_invoices_patient",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "invoice_id", name="pk_invoices"),
    )
    op.create_index("ix_invoices_dataset_month", "invoices", ["dataset_id", "month"])
    op.create_index("ix_invoices_dataset_patient", "invoices", ["dataset_id", "patient_id"])
    op.create_index(
        "ix_invoices_dataset_payment_status", "invoices", ["dataset_id", "payment_status"]
    )
    op.create_index("ix_invoices_dataset_service_type", "invoices", ["dataset_id", "service_type"])

    op.create_table(
        "medicine_items",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("medicine_name", sa.String(length=150), nullable=False),
        sa.Column("batch_no", sa.String(length=50), nullable=False),
        sa.Column("is_duplicate_batch", sa.Boolean(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("stock_on_hand", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_medicine_items_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "supplier_id"],
            ["suppliers.dataset_id", "suppliers.supplier_id"],
            name="fk_medicine_items_supplier",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "item_id", name="pk_medicine_items"),
    )
    op.create_index(
        "ix_medicine_items_dataset_category", "medicine_items", ["dataset_id", "category"]
    )
    op.create_index(
        "ix_medicine_items_dataset_expiry", "medicine_items", ["dataset_id", "expiry_date"]
    )
    op.create_index(
        "ix_medicine_items_dataset_supplier", "medicine_items", ["dataset_id", "supplier_id"]
    )

    op.create_table(
        "expenses",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.String(length=32), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("approval_status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_expenses_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "vendor"],
            ["vendors.dataset_id", "vendors.vendor_name"],
            name="fk_expenses_vendor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "expense_id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_dataset_approval", "expenses", ["dataset_id", "approval_status"])
    op.create_index("ix_expenses_dataset_category", "expenses", ["dataset_id", "category"])
    op.create_index("ix_expenses_dataset_dept", "expenses", ["dataset_id", "department"])
    op.create_index("ix_expenses_dataset_month", "expenses", ["dataset_id", "month"])
    op.create_index("ix_expenses_dataset_vendor", "expenses", ["dataset_id", "vendor"])


def downgrade() -> None:
    op.drop_table("expenses")
    op.drop_table("medicine_items")
    op.drop_table("invoices")
    op.drop_table("appointments")
    op.drop_table("vendors")
    op.drop_table("suppliers")
    op.drop_table("doctors")
    op.drop_table("patients")
