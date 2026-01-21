"""Quick diagnostic script to check database state for audit trail debugging."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.persistence.database import get_db_session
from backend.persistence.models import CaseState, ArtifactPack as ArtifactPackModel

def check_database():
    session = get_db_session()
    
    # Check cases and their activity_log
    print("=" * 60)
    print("CASE STATE ANALYSIS")
    print("=" * 60)
    
    cases = session.query(CaseState).limit(5).all()
    for case in cases:
        print(f"\nCase: {case.case_id}")
        print(f"  Name: {case.name}")
        print(f"  activity_log is NULL: {case.activity_log is None}")
        print(f"  activity_log length: {len(case.activity_log) if case.activity_log else 0}")
        if case.activity_log:
            print(f"  activity_log preview: {case.activity_log[:200]}...")
    
    # Check artifact packs
    print("\n" + "=" * 60)
    print("ARTIFACT PACKS ANALYSIS")
    print("=" * 60)
    
    packs = session.query(ArtifactPackModel).limit(5).all()
    if not packs:
        print("NO ARTIFACT PACKS FOUND IN DATABASE!")
    else:
        for pack in packs:
            print(f"\nPack: {pack.pack_id}")
            print(f"  Case: {pack.case_id}")
            print(f"  Agent: {pack.agent_name}")
            print(f"  Has execution_metadata: {pack.execution_metadata_json is not None}")
    
    session.close()
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    check_database()
