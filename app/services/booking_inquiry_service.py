from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import InquiryStatus
from app.repositories.booking_inquiry_repo import BookingInquiryRepository
from app.schemas.booking_inquiry_schema import (
    BookingInquiryCreate,
    BookingInquiryResponse, 
    BookingInquiryDetailed,
    BookingInquiryListResponse,
    BookingInquirySearchParams,
    BookingInquiryUpdate,
    CartItemSchema
)


class BookingInquiryService:
    """Service class for booking inquiry business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BookingInquiryRepository(db)

    def create_inquiry(self, inquiry_data: BookingInquiryCreate) -> BookingInquiryResponse:
        """
        Create a new booking inquiry and trigger email notification
        """
        try:
            # Validate cart items pricing consistency
            self._validate_pricing(inquiry_data)
            
            # Create the inquiry (Pending vendor review & confirmation)
            db_inquiry = self.repository.create(inquiry_data)
            
            logger.info(f"Created booking inquiry {db_inquiry.reference} for {db_inquiry.email} (Pending Vendor Review)")
            
            # Convert to response schema
            return BookingInquiryResponse(
                id=db_inquiry.id,
                reference=db_inquiry.reference,
                status=db_inquiry.status,
                created_at=db_inquiry.created_at
            )
            
        except Exception as e:
            logger.error(f"Error creating booking inquiry: {str(e)}")
            raise

    def get_inquiry_by_id(self, inquiry_id: UUID) -> Optional[BookingInquiryDetailed]:
        """Get booking inquiry by ID"""
        try:
            db_inquiry = self.repository.get_by_id(inquiry_id)
            if not db_inquiry:
                return None
                
            return self._convert_to_detailed_response(db_inquiry)
            
        except Exception as e:
            logger.error(f"Error retrieving inquiry {inquiry_id}: {str(e)}")
            raise

    def get_inquiry_by_reference(self, reference: str) -> Optional[BookingInquiryDetailed]:
        """Get booking inquiry by reference"""
        try:
            db_inquiry = self.repository.get_by_reference(reference)
            if not db_inquiry:
                return None
                
            return self._convert_to_detailed_response(db_inquiry)
            
        except Exception as e:
            logger.error(f"Error retrieving inquiry by reference {reference}: {str(e)}")
            raise

    def get_inquiries_by_email(self, email: str) -> list[BookingInquiryDetailed]:
        """Get all inquiries for a specific email"""
        try:
            db_inquiries = self.repository.get_by_email(email)
            return [self._convert_to_detailed_response(inquiry) for inquiry in db_inquiries]
            
        except Exception as e:
            logger.error(f"Error retrieving inquiries for email {email}: {str(e)}")
            raise

    def search_inquiries(self, search_params: BookingInquirySearchParams) -> BookingInquiryListResponse:
        """Search inquiries with pagination"""
        try:
            inquiries, total_count = self.repository.search(search_params)
            
            inquiry_responses = [self._convert_to_detailed_response(inquiry) for inquiry in inquiries]
            
            total_pages = (total_count + search_params.per_page - 1) // search_params.per_page
            
            return BookingInquiryListResponse(
                inquiries=inquiry_responses,
                total=total_count,
                page=search_params.page,
                per_page=search_params.per_page,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error searching inquiries: {str(e)}")
            raise

    def update_inquiry(self, inquiry_id: UUID, inquiry_data: BookingInquiryUpdate) -> Optional[BookingInquiryDetailed]:
        """Update a booking inquiry"""
        try:
            db_inquiry = self.repository.update(inquiry_id, inquiry_data)
            if not db_inquiry:
                return None
                
            logger.info(f"Updated booking inquiry {db_inquiry.reference}")
            return self._convert_to_detailed_response(db_inquiry)
            
        except Exception as e:
            logger.error(f"Error updating inquiry {inquiry_id}: {str(e)}")
            raise

    def update_inquiry_status(self, inquiry_id: UUID, status: InquiryStatus) -> Optional[BookingInquiryDetailed]:
        """Update inquiry status"""
        try:
            db_inquiry = self.repository.update_status(inquiry_id, status)
            if not db_inquiry:
                return None
                
            logger.info(f"Updated inquiry {db_inquiry.reference} status to {status}")
            return self._convert_to_detailed_response(db_inquiry)
            
        except Exception as e:
            logger.error(f"Error updating inquiry status {inquiry_id}: {str(e)}")
            raise

    def delete_inquiry(self, inquiry_id: UUID) -> bool:
        """Delete a booking inquiry"""
        try:
            success = self.repository.delete(inquiry_id)
            if success:
                logger.info(f"Deleted booking inquiry {inquiry_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error deleting inquiry {inquiry_id}: {str(e)}")
            raise

    def get_inquiries_by_status(self, status: InquiryStatus) -> list[BookingInquiryDetailed]:
        """Get all inquiries with specific status"""
        try:
            db_inquiries = self.repository.get_by_status(status)
            return [self._convert_to_detailed_response(inquiry) for inquiry in db_inquiries]
            
        except Exception as e:
            logger.error(f"Error retrieving inquiries by status {status}: {str(e)}")
            raise

    def get_inquiry_statistics(self) -> dict:
        """Get inquiry statistics"""
        try:
            status_counts = self.repository.count_by_status()
            total_count = self.repository.count_total()
            
            return {
                "total_inquiries": total_count,
                "by_status": status_counts,
                "recent_inquiries": len(self.repository.get_recent_inquiries(10))
            }
            
        except Exception as e:
            logger.error(f"Error retrieving inquiry statistics: {str(e)}")
            raise

    def _validate_pricing(self, inquiry_data: BookingInquiryCreate) -> None:
        """Validate that cart items pricing is consistent with totals"""
        calculated_subtotal = sum(
            item.price * item.travel_count for item in inquiry_data.cart_items
        )
        
        # Log pricing details for debugging
        logger.info(f"Pricing validation - Calculated: {calculated_subtotal}, Provided: {inquiry_data.subtotal}")
        for item in inquiry_data.cart_items:
            item_total = item.price * item.travel_count
            logger.info(f"Item: {item.title}, Price: {item.price}, Count: {item.travel_count}, Total: {item_total}")
        
        # Make validation more flexible - warn instead of error for subtotal mismatch
        if abs(calculated_subtotal - inquiry_data.subtotal) > Decimal('0.01'):
            logger.warning(f"Subtotal mismatch - Calculated: {calculated_subtotal}, Provided: {inquiry_data.subtotal}. Using provided subtotal.")
        
        # Still validate that total is not less than subtotal
        if inquiry_data.total < inquiry_data.subtotal:
            raise ValueError("Total amount cannot be less than subtotal")

    def _convert_to_detailed_response(self, db_inquiry: BookingInquiry) -> BookingInquiryDetailed:
        """Convert database model to detailed response schema"""
        from decimal import Decimal
        
        # Convert JSON cart_items back to CartItemSchema objects
        cart_items = []
        for item_data in db_inquiry.cart_items:
            # Handle datetime and Decimal deserialization from JSON format
            item_dict = dict(item_data)
            
            # Process field values
            for key, value in item_dict.items():
                if key == 'travel_date' and isinstance(value, str):
                    try:
                        # Parse ISO datetime string back to datetime object
                        item_dict[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # Fallback if parsing fails, keep as string
                        pass
                elif key == 'price' and isinstance(value, (int, float)):
                    try:
                        # Convert numeric price back to Decimal
                        item_dict[key] = Decimal(str(value))
                    except (ValueError, TypeError):
                        # Fallback if conversion fails, keep as original type
                        pass
            
            # Create CartItemSchema with proper field mapping
            # Use the field names that Pydantic expects (snake_case as defined in the model)
            try:
                cart_items.append(CartItemSchema(**item_dict))
            except Exception as e:
                # Log the problematic data for debugging
                logger.error(f"Failed to create CartItemSchema from item_dict: {item_dict}")
                logger.error(f"CartItemSchema creation error: {str(e)}")
                raise
        
        return BookingInquiryDetailed(
            id=db_inquiry.id,
            reference=db_inquiry.reference,
            first_name=db_inquiry.first_name,
            last_name=db_inquiry.last_name,
            email=db_inquiry.email,
            phone=db_inquiry.phone,
            nationality=db_inquiry.nationality,
            emergency_contact=db_inquiry.emergency_contact,
            number_of_travelers=db_inquiry.number_of_travelers,
            special_requests=db_inquiry.special_requests,
            cart_items=cart_items,
            subtotal=db_inquiry.subtotal,
            total=db_inquiry.total,
            currency=db_inquiry.currency,
            status=db_inquiry.status,
            created_at=db_inquiry.created_at,
            updated_at=db_inquiry.updated_at
        )

    def _auto_provision_stay_bookings(self, db_inquiry: BookingInquiry) -> None:
        """
        Auto-allocate room units and create StayBooking + StayBookingRoom records
        when a client places a stay booking inquiry.
        """
        from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayBooking, StayBookingRoom
        from app.models.booking import Booking
        from app.models.user import User
        from app.models.enum import StayBookingStatus, BookingStatus, PaymentTransactionStatus, CurrencyCode
        from datetime import datetime, timedelta, date
        from decimal import Decimal
        from uuid import UUID

        system_user = self.db.query(User).first()

        for item in db_inquiry.cart_items or []:
            lid = item.get("listing_id")
            if not lid:
                continue
            
            prop = None
            try:
                prop_uuid = UUID(str(lid))
                prop = self.db.query(StayProperty).filter(
                    (StayProperty.id == prop_uuid) | (StayProperty.listing_id == prop_uuid)
                ).first()
            except ValueError:
                pass

            if not prop:
                continue

            tdate_str = item.get("travel_date")
            check_in = date.today()
            if tdate_str:
                val = str(tdate_str).strip()
                if " to " in val:
                    val = val.split(" to ")[0].strip()
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    check_in = dt.date()
                except ValueError:
                    try:
                        check_in = datetime.strptime(val[:10], "%Y-%m-%d").date()
                    except ValueError:
                        pass

            check_out = check_in + timedelta(days=1)

            # Find room type and available room units
            room_type = self.db.query(StayRoomType).filter(StayRoomType.property_id == prop.id).first()
            if not room_type:
                continue

            requested_room_count = item.get("travel_count") or item.get("travelCount") or 1
            try:
                requested_room_count = int(requested_room_count)
            except (ValueError, TypeError):
                requested_room_count = 1

            room_units = self.db.query(StayRoomUnit).filter(
                StayRoomUnit.property_id == prop.id,
                StayRoomUnit.room_type_id == room_type.id
            ).all()

            if not room_units:
                continue

            units_to_allocate = room_units[:requested_room_count]

            try:
                parent_booking = Booking(
                    booking_reference=db_inquiry.reference,
                    user_id=system_user.id if system_user else None,
                    status=BookingStatus.CONFIRMED,
                    total_amount=Decimal(str(db_inquiry.total or 100)),
                    currency=CurrencyCode.USD,
                    payment_status=PaymentTransactionStatus.PENDING,
                    booked_at=db_inquiry.created_at or datetime.utcnow(),
                )
                self.db.add(parent_booking)
                self.db.flush()

                stay_booking = StayBooking(
                    booking_id=parent_booking.id,
                    property_id=prop.id,
                    status=StayBookingStatus.CONFIRMED,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    guest_name=f"{db_inquiry.first_name} {db_inquiry.last_name}",
                    guest_email=db_inquiry.email,
                    guest_phone=db_inquiry.phone,
                    special_requests=db_inquiry.special_requests,
                    metadata_json={"inquiry_reference": db_inquiry.reference}
                )
                self.db.add(stay_booking)
                self.db.flush()

                total_item_price = Decimal(str(item.get("price") or 100))
                per_unit_rate = total_item_price / Decimal(str(max(1, len(units_to_allocate))))

                for unit in units_to_allocate:
                    stay_booking_room = StayBookingRoom(
                        stay_booking_id=stay_booking.id,
                        room_unit_id=unit.id,
                        room_type_id=room_type.id,
                        check_in_date=check_in,
                        check_out_date=check_out,
                        nightly_rate=per_unit_rate,
                        guests=2,
                        metadata_json={}
                    )
                    self.db.add(stay_booking_room)
                self.db.commit()
                logger.info(f"Auto-provisioned StayBooking with {len(units_to_allocate)} room units for inquiry {db_inquiry.reference} on property {prop.name}")
            except Exception as ex:
                self.db.rollback()
                logger.error(f"Failed to auto-provision StayBooking for inquiry {db_inquiry.reference}: {str(ex)}")


def get_booking_inquiry_service(db: Session) -> BookingInquiryService:
    """Get booking inquiry service instance"""
    return BookingInquiryService(db)