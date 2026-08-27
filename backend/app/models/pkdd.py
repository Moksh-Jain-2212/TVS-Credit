"""SQLAlchemy models for cleaned PKDD source tables."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    account_open_date: Mapped[date] = mapped_column(Date, nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
    loans: Mapped[list["Loan"]] = relationship(back_populates="account")
    dispositions: Mapped[list["Disposition"]] = relationship(back_populates="account")
    standing_orders: Mapped[list["StandingOrder"]] = relationship(back_populates="account")


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    birth_number: Mapped[str] = mapped_column(String(16), nullable=False)
    district_id: Mapped[int] = mapped_column(Integer, nullable=False)

    dispositions: Mapped[list["Disposition"]] = relationship(back_populates="client")


class Disposition(Base):
    __tablename__ = "dispositions"

    disp_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.client_id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)

    client: Mapped[Client] = relationship(back_populates="dispositions")
    account: Mapped[Account] = relationship(back_populates="dispositions")


class Loan(Base):
    __tablename__ = "loans"

    loan_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    loan_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    payments: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False)

    account: Mapped[Account] = relationship(back_populates="loans")


class StandingOrder(Base):
    __tablename__ = "standing_orders"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    bank_to: Mapped[str] = mapped_column(String(16), nullable=False)
    account_to: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    k_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)

    account: Mapped[Account] = relationship(back_populates="standing_orders")


class Transaction(Base):
    __tablename__ = "transactions"

    trans_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.account_id"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    k_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bank: Mapped[str | None] = mapped_column(String(16), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column("account", String(32), nullable=True)

    account: Mapped[Account] = relationship(back_populates="transactions")
