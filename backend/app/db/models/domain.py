"""Healthcare domain tables, isolated per uploaded dataset via composite keys."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

Money = Numeric(14, 2)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_id", "patient_id", name="pk_patients"),
        Index("ix_patients_dataset_month", "dataset_id", "registration_month"),
        Index("ix_patients_dataset_city", "dataset_id", "city"),
        Index("ix_patients_dataset_insurance", "dataset_id", "insurance_provider"),
        Index("ix_patients_dataset_age_band", "dataset_id", "age_band"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # Stored for audit completeness, never returned by any API or sent to the LLM.
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    age_band: Mapped[str] = mapped_column(String(16), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    # Masked-ready:******1234 (only last 4 digits are ever exposed).
    phone_masked: Mapped[str] = mapped_column(String(16), nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    registration_month: Mapped[str] = mapped_column(String(7), nullable=False)
    insurance_provider: Mapped[str] = mapped_column(String(100), nullable=False)


class Doctor(Base):
    """Derived dimension table from Appointments.doctor_id (no invented names)."""

    __tablename__ = "doctors"
    __table_args__ = (PrimaryKeyConstraint("dataset_id", "doctor_id", name="pk_doctors"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_department: Mapped[str] = mapped_column(String(100), nullable=False)


class Supplier(Base):
    """Derived dimension table from Medicine_Inventory.supplier_id."""

    __tablename__ = "suppliers"
    __table_args__ = (PrimaryKeyConstraint("dataset_id", "supplier_id", name="pk_suppliers"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[str] = mapped_column(String(32), nullable=False)


class Vendor(Base):
    """Derived dimension table from Expenses.vendor."""

    __tablename__ = "vendors"
    __table_args__ = (PrimaryKeyConstraint("dataset_id", "vendor_name", name="pk_vendors"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    vendor_name: Mapped[str] = mapped_column(String(100), nullable=False)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_id", "appointment_id", name="pk_appointments"),
        ForeignKeyConstraint(
            ["dataset_id", "patient_id"],
            ["patients.dataset_id", "patients.patient_id"],
            name="fk_appointments_patient",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["dataset_id", "doctor_id"],
            ["doctors.dataset_id", "doctors.doctor_id"],
            name="fk_appointments_doctor",
            ondelete="CASCADE",
        ),
        Index("ix_appointments_dataset_month", "dataset_id", "month"),
        Index("ix_appointments_dataset_status", "dataset_id", "status"),
        Index("ix_appointments_dataset_dept", "dataset_id", "department"),
        Index("ix_appointments_dataset_patient", "dataset_id", "patient_id"),
        Index("ix_appointments_dataset_doctor", "dataset_id", "doctor_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(32), nullable=False)
    doctor_id: Mapped[str] = mapped_column(String(32), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    appointment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    wait_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Informational only: never added to revenue (avoids double-counting Billing).
    consultation_fee: Mapped[Decimal] = mapped_column(Money, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_id", "invoice_id", name="pk_invoices"),
        ForeignKeyConstraint(
            ["dataset_id", "patient_id"],
            ["patients.dataset_id", "patients.patient_id"],
            name="fk_invoices_patient",
            ondelete="CASCADE",
        ),
        Index("ix_invoices_dataset_month", "dataset_id", "month"),
        Index("ix_invoices_dataset_payment_status", "dataset_id", "payment_status"),
        Index("ix_invoices_dataset_service_type", "dataset_id", "service_type"),
        Index("ix_invoices_dataset_patient", "dataset_id", "patient_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(30), nullable=False)


class MedicineItem(Base):
    __tablename__ = "medicine_items"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_id", "item_id", name="pk_medicine_items"),
        ForeignKeyConstraint(
            ["dataset_id", "supplier_id"],
            ["suppliers.dataset_id", "suppliers.supplier_id"],
            name="fk_medicine_items_supplier",
            ondelete="CASCADE",
        ),
        Index("ix_medicine_items_dataset_category", "dataset_id", "category"),
        Index("ix_medicine_items_dataset_expiry", "dataset_id", "expiry_date"),
        Index("ix_medicine_items_dataset_supplier", "dataset_id", "supplier_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    medicine_name: Mapped[str] = mapped_column(String(150), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    is_duplicate_batch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    stock_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(32), nullable=False)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        PrimaryKeyConstraint("dataset_id", "expense_id", name="pk_expenses"),
        ForeignKeyConstraint(
            ["dataset_id", "vendor"],
            ["vendors.dataset_id", "vendors.vendor_name"],
            name="fk_expenses_vendor",
            ondelete="CASCADE",
        ),
        Index("ix_expenses_dataset_month", "dataset_id", "month"),
        Index("ix_expenses_dataset_approval", "dataset_id", "approval_status"),
        Index("ix_expenses_dataset_dept", "dataset_id", "department"),
        Index("ix_expenses_dataset_category", "dataset_id", "category"),
        Index("ix_expenses_dataset_vendor", "dataset_id", "vendor"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[str] = mapped_column(String(32), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False)
