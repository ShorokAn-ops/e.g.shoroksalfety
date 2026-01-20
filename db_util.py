from db import engine, SessionLocal
from models import Base
import queries


def init_db():
    Base.metadata.create_all(bind=engine)

def clean_db():
    db = SessionLocal()
    try:
        queries.clean_db(db)
    finally:
        db.close()

def DbUnit_save_inv_extraction(result: dict):
    db = SessionLocal()
    try:
        queries.save_inv_extraction(db, result)
    finally:
        db.close()
