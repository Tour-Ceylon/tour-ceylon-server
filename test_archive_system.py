#!/usr/bin/env python3
"""
Test script for the stay archive system functionality.

This script tests:
1. Archive impact analysis
2. Stay property archiving with cascade logic
3. Stay property restoration
4. Data integrity and rollback capabilities
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.stay import StayProperty
from app.models.listing import Listing
from app.models.user import User
from app.models.enum import StayStatus, ListingStatus, UserRole
from app.services.admin.stay_archive_service import StayArchiveService
from app.config.database import get_db_engine

class ArchiveSystemTester:
    """Test the stay archive system functionality"""
    
    def __init__(self):
        # Setup test database connection
        self.engine = get_db_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionLocal()
        self.archive_service = StayArchiveService(self.db)
        
        # Test data
        self.test_vendor_id = None
        self.test_admin_id = None
        self.test_stay_id = None
        self.test_listing_id = None

    def setup_test_data(self):
        """Create test data for testing"""
        print("📝 Setting up test data...")
        
        try:
            # Create test vendor
            test_vendor = User(
                id=uuid4(),
                email=f"test_vendor_{datetime.now().microsecond}@example.com",
                password_hash="dummy_hash",
                first_name="Test",
                last_name="Vendor",
                company_name="Test Vendor Co",
                role=UserRole.VENDOR,
                is_active=True
            )
            self.db.add(test_vendor)
            self.test_vendor_id = test_vendor.id
            
            # Create test admin
            test_admin = User(
                id=uuid4(),
                email=f"test_admin_{datetime.now().microsecond}@example.com",
                password_hash="dummy_hash",
                first_name="Test",
                last_name="Admin",
                role=UserRole.ADMIN,
                is_active=True
            )
            self.db.add(test_admin)
            self.test_admin_id = test_admin.id
            
            # Create test stay property
            test_stay = StayProperty(
                id=uuid4(),
                vendor_id=self.test_vendor_id,
                name="Test Beach Resort",
                property_type="resort",
                description="A beautiful beachfront resort for testing",
                address="123 Beach Road",
                city="Colombo",
                district="Western Province",
                status=StayStatus.APPROVED,
                contact={"phone": "+94123456789", "email": "info@testresort.com"},
                policies={"checkInTime": "14:00", "checkOutTime": "11:00"},
                media=[{"url": "https://example.com/image1.jpg", "role": "cover"}],
                is_active=True
            )
            self.db.add(test_stay)
            self.test_stay_id = test_stay.id
            
            # Create linked marketplace listing
            test_listing = Listing(
                id=uuid4(),
                destination_id=uuid4(),  # Mock destination
                listing_type="hotel",
                title="Test Beach Resort - Marketplace",
                description="Marketplace listing for test resort",
                status=ListingStatus.PUBLISHED,
                is_active=True
            )
            self.db.add(test_listing)
            self.test_listing_id = test_listing.id
            
            # Link stay to listing
            test_stay.listing_id = test_listing.id
            
            self.db.commit()
            print("✅ Test data created successfully")
            print(f"   - Vendor ID: {self.test_vendor_id}")
            print(f"   - Admin ID: {self.test_admin_id}")
            print(f"   - Stay ID: {self.test_stay_id}")
            print(f"   - Listing ID: {self.test_listing_id}")
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Failed to create test data: {str(e)}")
            raise

    def test_archive_impact_analysis(self):
        """Test the archive impact analysis functionality"""
        print("\n🔍 Testing archive impact analysis...")
        
        try:
            analysis = self.archive_service.get_archive_impact_analysis(self.test_stay_id)
            
            # Verify analysis structure
            assert 'stay_property' in analysis, "Analysis missing stay_property"
            assert 'linked_listing' in analysis, "Analysis missing linked_listing"
            assert 'active_bookings' in analysis, "Analysis missing active_bookings"
            assert 'warnings' in analysis, "Analysis missing warnings"
            assert 'blocking_issues' in analysis, "Analysis missing blocking_issues"
            
            # Verify stay property info
            stay_info = analysis['stay_property']
            assert stay_info['id'] == str(self.test_stay_id), "Incorrect stay ID in analysis"
            assert stay_info['name'] == "Test Beach Resort", "Incorrect stay name in analysis"
            assert stay_info['current_status'] == 'approved', "Incorrect stay status in analysis"
            assert stay_info['can_be_archived'] == True, "Stay should be archivable"
            
            # Verify linked listing info
            listing_info = analysis['linked_listing']
            assert listing_info is not None, "Linked listing info should be present"
            assert listing_info['id'] == str(self.test_listing_id), "Incorrect listing ID in analysis"
            assert listing_info['status'] == 'published', "Incorrect listing status in analysis"
            assert listing_info['will_be_archived'] == True, "Listing should be marked for archiving"
            
            print("✅ Archive impact analysis working correctly")
            print(f"   - Stay can be archived: {stay_info['can_be_archived']}")
            print(f"   - Linked listing will be archived: {listing_info['will_be_archived']}")
            print(f"   - Active bookings: {len(analysis['active_bookings'])}")
            print(f"   - Warnings: {len(analysis['warnings'])}")
            print(f"   - Blocking issues: {len(analysis['blocking_issues'])}")
            
        except Exception as e:
            print(f"❌ Archive impact analysis test failed: {str(e)}")
            raise

    def test_stay_archiving(self):
        """Test the stay archiving functionality with cascade logic"""
        print("\n📦 Testing stay archiving with cascade logic...")
        
        try:
            # Archive the stay property
            result = self.archive_service.archive_stay(
                property_id=self.test_stay_id,
                archived_by_id=self.test_admin_id,
                archive_reason="Testing archive functionality"
            )
            
            # Verify archive result
            assert 'archived_stay_id' in result, "Archive result missing stay ID"
            assert result['archived_stay_id'] == str(self.test_stay_id), "Incorrect archived stay ID"
            assert 'archived_at' in result, "Archive result missing timestamp"
            assert 'cascade_operations' in result, "Archive result missing cascade operations"
            assert result['can_be_restored'] == True, "Stay should be restorable"
            
            # Verify stay property was archived
            stay = self.db.query(StayProperty).filter(StayProperty.id == self.test_stay_id).first()
            assert stay is not None, "Stay property not found"
            assert stay.status == StayStatus.ARCHIVED, f"Stay status should be ARCHIVED, got {stay.status}"
            assert stay.archived_at is not None, "Archived timestamp should be set"
            assert stay.archived_by_id == self.test_admin_id, "Archived by ID should be set"
            assert stay.archive_reason == "Testing archive functionality", "Archive reason should be set"
            assert stay.is_active == False, "Stay should be marked as inactive"
            
            # Verify linked listing was also archived (cascade)
            listing = self.db.query(Listing).filter(Listing.id == self.test_listing_id).first()
            assert listing is not None, "Linked listing not found"
            assert listing.status == ListingStatus.ARCHIVED, f"Listing status should be ARCHIVED, got {listing.status}"
            assert listing.is_active == False, "Listing should be marked as inactive"
            
            print("✅ Stay archiving working correctly")
            print(f"   - Stay archived at: {stay.archived_at}")
            print(f"   - Archived by admin: {stay.archived_by_id}")
            print(f"   - Archive reason: {stay.archive_reason}")
            print(f"   - Cascade operations: {len(result['cascade_operations'])}")
            
        except Exception as e:
            print(f"❌ Stay archiving test failed: {str(e)}")
            raise

    def test_stay_restoration(self):
        """Test the stay restoration functionality"""
        print("\n🔄 Testing stay restoration...")
        
        try:
            # Restore the archived stay property
            result = self.archive_service.restore_stay(
                property_id=self.test_stay_id,
                restored_by_id=self.test_admin_id
            )
            
            # Verify restoration result
            assert 'restored_stay_id' in result, "Restoration result missing stay ID"
            assert result['restored_stay_id'] == str(self.test_stay_id), "Incorrect restored stay ID"
            assert 'restored_to_status' in result, "Restoration result missing status"
            assert result['restored_to_status'] == 'approved', "Should restore to approved status"
            assert 'listing_requires_manual_restore' in result, "Result missing listing restore info"
            assert result['listing_requires_manual_restore'] == True, "Should indicate manual listing restore needed"
            
            # Verify stay property was restored
            stay = self.db.query(StayProperty).filter(StayProperty.id == self.test_stay_id).first()
            assert stay is not None, "Stay property not found"
            assert stay.status == StayStatus.APPROVED, f"Stay status should be APPROVED, got {stay.status}"
            assert stay.archived_at is None, "Archived timestamp should be cleared"
            assert stay.archived_by_id is None, "Archived by ID should be cleared"
            assert stay.archive_reason is None, "Archive reason should be cleared"
            assert stay.is_active == True, "Stay should be marked as active"
            
            # Verify linked listing remains archived (intentional - requires manual restore)
            listing = self.db.query(Listing).filter(Listing.id == self.test_listing_id).first()
            assert listing is not None, "Linked listing not found"
            assert listing.status == ListingStatus.ARCHIVED, f"Listing should remain ARCHIVED, got {listing.status}"
            
            print("✅ Stay restoration working correctly")
            print(f"   - Stay restored to status: {stay.status.value}")
            print(f"   - Archive fields cleared: ✅")
            print(f"   - Listing remains archived (manual restore required): ✅")
            
        except Exception as e:
            print(f"❌ Stay restoration test failed: {str(e)}")
            raise

    def test_archived_stays_listing(self):
        """Test listing archived stays functionality"""
        print("\n📋 Testing archived stays listing...")
        
        try:
            # First archive the stay again
            self.archive_service.archive_stay(
                property_id=self.test_stay_id,
                archived_by_id=self.test_admin_id,
                archive_reason="Testing listing functionality"
            )
            
            # List archived stays
            archived_stays = self.archive_service.list_archived_stays()
            
            # Verify results
            assert len(archived_stays) > 0, "Should have at least one archived stay"
            
            # Find our test stay in the results
            test_stay_found = False
            for stay in archived_stays:
                if stay['id'] == str(self.test_stay_id):
                    test_stay_found = True
                    assert stay['name'] == "Test Beach Resort", "Incorrect stay name in listing"
                    assert stay['archived_reason'] == "Testing listing functionality", "Incorrect archive reason"
                    assert stay['had_linked_listing'] == True, "Should indicate linked listing presence"
                    assert stay['can_be_restored'] == True, "Stay should be restorable"
                    break
            
            assert test_stay_found, "Test stay not found in archived stays list"
            
            print("✅ Archived stays listing working correctly")
            print(f"   - Total archived stays: {len(archived_stays)}")
            print(f"   - Test stay found in results: ✅")
            
        except Exception as e:
            print(f"❌ Archived stays listing test failed: {str(e)}")
            raise

    def test_data_integrity(self):
        """Test data integrity and constraints"""
        print("\n🛡️ Testing data integrity...")
        
        try:
            # Test archiving non-existent stay
            try:
                fake_id = uuid4()
                self.archive_service.archive_stay(fake_id, self.test_admin_id)
                assert False, "Should have raised error for non-existent stay"
            except ValueError as e:
                assert "Stay property not found" in str(e), "Correct error message for non-existent stay"
            
            # Test archiving already archived stay
            try:
                self.archive_service.archive_stay(self.test_stay_id, self.test_admin_id)
                assert False, "Should have raised error for already archived stay"
            except ValueError as e:
                assert "already archived" in str(e), "Correct error message for already archived stay"
            
            # Test restoring non-archived stay
            try:
                # First restore the stay
                self.archive_service.restore_stay(self.test_stay_id, self.test_admin_id)
                # Then try to restore again
                self.archive_service.restore_stay(self.test_stay_id, self.test_admin_id)
                assert False, "Should have raised error for non-archived stay"
            except ValueError as e:
                assert "not archived" in str(e), "Correct error message for non-archived stay"
            
            print("✅ Data integrity checks working correctly")
            print("   - Non-existent stay handling: ✅")
            print("   - Already archived stay handling: ✅")
            print("   - Non-archived stay restore handling: ✅")
            
        except Exception as e:
            print(f"❌ Data integrity test failed: {str(e)}")
            raise

    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        try:
            # Delete test records
            if self.test_stay_id:
                self.db.query(StayProperty).filter(StayProperty.id == self.test_stay_id).delete()
            if self.test_listing_id:
                self.db.query(Listing).filter(Listing.id == self.test_listing_id).delete()
            if self.test_vendor_id:
                self.db.query(User).filter(User.id == self.test_vendor_id).delete()
            if self.test_admin_id:
                self.db.query(User).filter(User.id == self.test_admin_id).delete()
            
            self.db.commit()
            print("✅ Test data cleaned up successfully")
            
        except Exception as e:
            self.db.rollback()
            print(f"⚠️ Failed to clean up test data: {str(e)}")

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Stay Archive System Tests")
        print("=" * 50)
        
        try:
            self.setup_test_data()
            self.test_archive_impact_analysis()
            self.test_stay_archiving()
            self.test_stay_restoration()
            self.test_archived_stays_listing()
            self.test_data_integrity()
            
            print("\n" + "=" * 50)
            print("🎉 All tests passed successfully!")
            print("✅ Stay archive system is working correctly")
            
        except Exception as e:
            print(f"\n❌ Tests failed: {str(e)}")
            return False
            
        finally:
            self.cleanup_test_data()
            self.db.close()
        
        return True

if __name__ == "__main__":
    tester = ArchiveSystemTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)