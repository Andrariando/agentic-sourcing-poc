import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select, func
from backend.persistence.database import get_engine
from backend.persistence.models import CaseState, SupplierPerformance, DocumentRecord
from backend.rag.vector_store import get_vector_store

def verify():
    engine = get_engine()
    with Session(engine) as session:
        cases = session.exec(select(func.count(CaseState.id))).one()
        suppliers = session.exec(select(func.count(SupplierPerformance.id))).one()
        print(f"Verified DB: Cases={cases}, SupplierPerf={suppliers}")

    try:
        vs = get_vector_store()
        count = vs.count()
        print(f"Verified Chroma: Documents/Chunks={count}")
    except Exception as e:
        print(f"Chroma Verification Failed: {e}")

if __name__ == "__main__":
    verify()
