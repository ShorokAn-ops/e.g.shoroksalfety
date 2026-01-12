from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Invoice(Base):
    __tablename__ = "invoices"

    InvoiceId = Column(String, primary_key=True)
    VendorName = Column(String)
    InvoiceDate = Column(String)
    BillingAddressRecipient = Column(String)
    ShippingAddress = Column(String)
    SubTotal = Column(Float)
    ShippingCost = Column(Float)
    InvoiceTotal = Column(Float)

    confidences = relationship(
        "Confidence",
        back_populates="invoice",
        cascade="all, delete-orphan",
        uselist=False,  # one-to-one
    )
    items = relationship(
        "Item",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


class Confidence(Base):
    __tablename__ = "confidences"

    InvoiceId = Column(String, ForeignKey("invoices.InvoiceId"), primary_key=True)
    VendorName = Column(Float)
    InvoiceDate = Column(Float)
    BillingAddressRecipient = Column(Float)
    ShippingAddress = Column(Float)
    SubTotal = Column(Float)
    ShippingCost = Column(Float)
    InvoiceTotal = Column(Float)

    invoice = relationship("Invoice", back_populates="confidences")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    InvoiceId = Column(String, ForeignKey("invoices.InvoiceId"))
    Description = Column(String)
    Name = Column(String)
    Quantity = Column(Float)
    UnitPrice = Column(Float)
    Amount = Column(Float)

    invoice = relationship("Invoice", back_populates="items")
