import sys
import os
import json
from uuid import UUID

# Add the server directory to sys.path
sys.path.append(os.getcwd())

from app.config.database import SessionLocal
from app.models.admin_dashboard import Package

def dump_package(package_id_str):
    db = SessionLocal()
    try:
        package_id = UUID(package_id_str)
        package = db.query(Package).filter(Package.id == package_id).first()
        
        if not package:
            print(f"Package {package_id_str} not found.")
            return

        print("--- RAW DATABASE VALUES ---")
        print(f"ID: {package.id}")
        print(f"Name: {package.name}")
        print(f"Summary: {package.summary}")
        print(f"Quick Facts: {json.dumps(package.quick_facts, indent=2)}")
        print(f"Destinations: {json.dumps(package.destinations, indent=2)}")
        print(f"Highlights: {json.dumps(package.highlights, indent=2)}")
        print(f"Exclusions: {json.dumps(package.exclusions, indent=2)}")
        print(f"Structured Itinerary: {json.dumps(package.structured_itinerary, indent=2)}")
        print(f"Listing Refs: {json.dumps(package.listing_refs, indent=2)}")
        print(f"Legacy Itinerary: {json.dumps(package.itinerary, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    target_id = "88888888-8888-8888-8888-888888888808"
    dump_package(target_id)
