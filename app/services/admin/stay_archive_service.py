from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.stay import StayProperty
from app.models.listing import Listing
from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.enum import StayStatus, ListingStatus, BookingStatus
from app.repositories.stay_repo import StayRepository
from app.repositories.listing_repo import ListingRepository


class StayArchiveService:
    """Service for archiving stay properties with cascade logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.stay_repo = StayRepository(db)
        self.listing_repo = ListingRepository(db)
    
    def archive_stay(self, property_id: UUID, archived_by_id: UUID, archive_reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Archive a stay property with cascade logic.
        
        This performs a safe archive operation that:
        1. Checks for active bookings
        2. Archives the stay property
        3. Cascades to archive linked marketplace listing
        4. Provides audit trail
        """
        # Load stay property with relationships
        stay_property = self.stay_repo.get_by_id(property_id)
        if not stay_property:
            raise ValueError("Stay property not found")
        
        # Check if already archived
        if stay_property.status == StayStatus.ARCHIVED:
            raise ValueError("Stay property is already archived")
        
        # Check business logic constraints
        self._check_archive_constraints(stay_property)
        
        # Prepare archive data
        archive_timestamp = datetime.utcnow()
        cascade_results = []
        
        try:
            # Archive the stay property
            stay_property.status = StayStatus.ARCHIVED
            stay_property.archived_at = archive_timestamp
            stay_property.archived_by_id = archived_by_id
            stay_property.archive_reason = archive_reason or "Manual archive"
            stay_property.is_active = False  # Soft delete flag
            
            # Cascade archive to linked marketplace listing
            if stay_property.listing_id:
                listing_result = self._cascade_archive_listing(
                    stay_property.listing_id, 
                    archived_by_id, 
                    f"Cascaded from stay property: {stay_property.name}"
                )
                cascade_results.append(listing_result)
            
            self.db.commit()
            
            return {
                "archived_stay_id": str(property_id),
                "archived_at": archive_timestamp.isoformat(),
                "archived_by_id": str(archived_by_id),
                "archive_reason": archive_reason,
                "cascade_operations": cascade_results,
                "can_be_restored": True
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to archive stay property: {str(e)}")
    
    def restore_stay(self, property_id: UUID, restored_by_id: UUID) -> Dict[str, Any]:
        """
        Restore an archived stay property.
        
        This restores the stay but does NOT automatically restore the linked listing
        to prevent accidental publishing of content that may need re-review.
        """
        stay_property = self.stay_repo.get_by_id(property_id)
        if not stay_property:
            raise ValueError("Stay property not found")
        
        if stay_property.status != StayStatus.ARCHIVED:
            raise ValueError("Stay property is not archived")
        
        try:
            # Restore stay property to its previous state or draft
            # We determine the appropriate status based on whether it was approved
            if stay_property.listing_id:
                # Was approved before, restore to approved status
                stay_property.status = StayStatus.APPROVED
            else:
                # Was not approved, restore to draft
                stay_property.status = StayStatus.DRAFT
            
            stay_property.archived_at = None
            stay_property.archived_by_id = None
            stay_property.archive_reason = None
            stay_property.is_active = True
            
            self.db.commit()
            
            return {
                "restored_stay_id": str(property_id),
                "restored_to_status": stay_property.status.value,
                "restored_at": datetime.utcnow().isoformat(),
                "restored_by_id": str(restored_by_id),
                "listing_requires_manual_restore": stay_property.listing_id is not None
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to restore stay property: {str(e)}")
    
    def get_archive_impact_analysis(self, property_id: UUID) -> Dict[str, Any]:
        """
        Analyze the impact of archiving a stay property before performing the operation.
        
        This provides a preview of what will happen when the archive operation is performed.
        """
        stay_property = self.stay_repo.get_by_id(property_id)
        if not stay_property:
            raise ValueError("Stay property not found")
        
        analysis = {
            "stay_property": {
                "id": str(stay_property.id),
                "name": stay_property.name,
                "current_status": stay_property.status.value,
                "can_be_archived": stay_property.status != StayStatus.ARCHIVED
            },
            "linked_listing": None,
            "active_bookings": [],
            "warnings": [],
            "blocking_issues": []
        }
        
        # Check linked listing
        if stay_property.listing_id:
            listing = self.listing_repo.get_by_id(stay_property.listing_id)
            if listing:
                analysis["linked_listing"] = {
                    "id": str(listing.id),
                    "title": listing.title,
                    "status": listing.status.value,
                    "will_be_archived": listing.status != ListingStatus.ARCHIVED
                }
        
        # Check for active bookings
        active_bookings = self._get_active_bookings_for_stay(property_id)
        analysis["active_bookings"] = [
            {
                "booking_id": str(booking.id),
                "status": booking.status.value,
                "guest_name": f"{booking.first_name} {booking.last_name}",
                "check_in_date": booking.check_in_date.isoformat() if booking.check_in_date else None,
                "check_out_date": booking.check_out_date.isoformat() if booking.check_out_date else None
            }
            for booking in active_bookings
        ]
        
        # Generate warnings and blocking issues
        if active_bookings:
            analysis["warnings"].append(
                f"This stay has {len(active_bookings)} active booking(s). "
                "Archiving will prevent new bookings but existing bookings will remain valid."
            )
        
        if stay_property.listing_id and analysis["linked_listing"]:
            if analysis["linked_listing"]["status"] == "published":
                analysis["warnings"].append(
                    "This will also archive the published marketplace listing, "
                    "making it unavailable to customers."
                )
        
        return analysis
    
    def _check_archive_constraints(self, stay_property: StayProperty) -> None:
        """Check business constraints before archiving"""
        
        # Check for revenue-generating bookings with future dates
        future_bookings = self._get_future_bookings_for_stay(stay_property.id)
        if future_bookings:
            # This is a warning, not a blocker - let admins decide
            pass
        
        # Add any other business logic constraints here
        # For example: check if stay has pending payments, etc.
    
    def _cascade_archive_listing(self, listing_id: UUID, archived_by_id: UUID, reason: str) -> Dict[str, Any]:
        """Archive the linked marketplace listing"""
        listing = self.listing_repo.get_by_id(listing_id)
        if not listing:
            return {"error": "Linked listing not found"}
        
        if listing.status == ListingStatus.ARCHIVED:
            return {"message": "Listing was already archived", "listing_id": str(listing_id)}
        
        # Archive the listing
        listing.status = ListingStatus.ARCHIVED
        listing.is_active = False
        
        return {
            "archived_listing_id": str(listing_id),
            "previous_status": "published" if listing.status == ListingStatus.PUBLISHED else "draft",
            "archive_reason": reason
        }
    
    def _get_active_bookings_for_stay(self, property_id: UUID) -> List[Booking]:
        """Get active bookings for a stay property"""
        return self.db.query(Booking).join(BookingItem).filter(
            and_(
                BookingItem.listing_id.in_(
                    # Get listing IDs linked to this stay
                    self.db.query(StayProperty.listing_id).filter(
                        and_(
                            StayProperty.id == property_id,
                            StayProperty.listing_id.isnot(None)
                        )
                    ).subquery()
                ),
                Booking.status.in_([
                    BookingStatus.PENDING,
                    BookingStatus.CONFIRMED
                ])
            )
        ).all()
    
    def _get_future_bookings_for_stay(self, property_id: UUID) -> List[Booking]:
        """Get bookings with future check-in dates"""
        today = datetime.utcnow().date()
        return self.db.query(Booking).join(BookingItem).filter(
            and_(
                BookingItem.listing_id.in_(
                    self.db.query(StayProperty.listing_id).filter(
                        and_(
                            StayProperty.id == property_id,
                            StayProperty.listing_id.isnot(None)
                        )
                    ).subquery()
                ),
                Booking.status.in_([
                    BookingStatus.PENDING,
                    BookingStatus.CONFIRMED
                ]),
                Booking.check_in_date >= today
            )
        ).all()
    
    def list_archived_stays(self, archived_by_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """List archived stay properties with restore options"""
        query = self.db.query(StayProperty).filter(
            StayProperty.status == StayStatus.ARCHIVED
        )
        
        if archived_by_id:
            query = query.filter(StayProperty.archived_by_id == archived_by_id)
        
        archived_stays = query.order_by(StayProperty.archived_at.desc()).all()
        
        return [
            {
                "id": str(stay.id),
                "name": stay.name,
                "property_type": stay.property_type,
                "vendor_name": stay.vendor.company_name if stay.vendor else "Unknown",
                "archived_at": stay.archived_at.isoformat() if stay.archived_at else None,
                "archived_by": stay.archived_by.first_name if stay.archived_by else "System",
                "archive_reason": stay.archive_reason,
                "had_linked_listing": stay.listing_id is not None,
                "can_be_restored": True
            }
            for stay in archived_stays
        ]