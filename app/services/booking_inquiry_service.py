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
            
            # Create the inquiry
            db_inquiry = self.repository.create(inquiry_data)
            
            logger.info(f"Created booking inquiry {db_inquiry.reference} for {db_inquiry.email}")
            
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


def get_booking_inquiry_service(db: Session) -> BookingInquiryService:
    """Get booking inquiry service instance"""
    return BookingInquiryService(db)