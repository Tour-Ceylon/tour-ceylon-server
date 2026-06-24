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
    CartItemSchema,
    AdminBookingInquiryItem,
    AdminBookingInquiryCustomer,
    AdminBookingInquiryStatusCounts,
    AdminBookingInquiryMetrics,
    AdminBookingInquiryPaginatedResponse,
    VendorBookingInquiryPaginatedResponse
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
            # Get the old inquiry first for logging
            old_inquiry = self.repository.get_by_id(inquiry_id)
            old_status = old_inquiry.status if old_inquiry else None
            
            db_inquiry = self.repository.update_status(inquiry_id, status)
            if not db_inquiry:
                logger.warning(f"Booking inquiry not found for status update: {inquiry_id}")
                return None
                
            logger.info(f"Booking inquiry status changed", extra={
                "inquiry_id": str(inquiry_id),
                "inquiry_reference": db_inquiry.reference,
                "old_status": old_status.value if old_status else None,
                "new_status": status.value,
                "inquiry_email": db_inquiry.email
            })
            
            # Create client notification for status changes
            try:
                logger.info(f"Creating client notification for inquiry reference={db_inquiry.reference} email={db_inquiry.email}")
                from app.services.notification_service import get_notification_service
                notification_service = get_notification_service(self.db)
                notification = notification_service.create_booking_status_notification(db_inquiry, status.value)
                
                if notification:
                    logger.info(f"Successfully created notification id={notification.id} for inquiry {db_inquiry.reference}")
                else:
                    logger.warning(f"Notification creation returned None for inquiry {db_inquiry.reference} status {status.value}")
                    
            except Exception as e:
                # Don't fail status update if notification creation fails
                logger.error(f"Failed to create notification for inquiry {db_inquiry.reference}: {str(e)}", exc_info=True)
            
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

    def _convert_to_admin_item(self, db_inquiry: BookingInquiry) -> AdminBookingInquiryItem:
        """Convert database model to admin-shaped detailed item schema"""
        listing_ids = []
        for item in db_inquiry.cart_items:
            item_dict = dict(item)
            l_id = item_dict.get('listing_id') or item_dict.get('listingId')
            if l_id:
                listing_ids.append(l_id)
                
        # Query listings
        from app.models.listing import Listing
        from app.models.user import User
        from app.models.enum import ListingType
        
        listings_db = []
        if listing_ids:
            uuid_list = []
            for l_id in listing_ids:
                try:
                    uuid_list.append(UUID(str(l_id)))
                except ValueError:
                    pass
            if uuid_list:
                listings_db = self.db.query(Listing).filter(Listing.id.in_(uuid_list)).all()
                
        listing_map = {str(l.id): l for l in listings_db}
        
        vendor_ids = []
        vendor_names = []
        derived_type = "Booking"
        
        LISTING_TYPE_TO_BOOKING_TYPE = {
            ListingType.HOTEL: "Stay",
            ListingType.TOUR: "Tour",
            ListingType.SAFARI: "Safari",
            ListingType.EXPERIENCE: "Experience",
            ListingType.TRANSFER: "Transfer"
        }
        
        for l_id in listing_ids:
            l_str = str(l_id)
            if l_str in listing_map:
                listing = listing_map[l_str]
                if listing.vendor_id:
                    v_id = listing.vendor_id
                    if v_id not in vendor_ids:
                        vendor_ids.append(v_id)
                        vendor_user = self.db.query(User).filter(User.id == v_id).first()
                        if vendor_user:
                            v_name = vendor_user.company_name or vendor_user.full_name or "Vendor"
                            if v_name not in vendor_names:
                                vendor_names.append(v_name)
                                
                if derived_type == "Booking" and listing.listing_type:
                    derived_type = LISTING_TYPE_TO_BOOKING_TYPE.get(listing.listing_type, "Booking")
                    
        if not vendor_names:
            vendor_names = ["Unassigned"]
            
        first_travel_date = datetime.utcnow()
        if db_inquiry.cart_items:
            first_item = dict(db_inquiry.cart_items[0])
            travel_date_str = first_item.get('travel_date') or first_item.get('travelDate')
            if travel_date_str:
                if isinstance(travel_date_str, datetime):
                    first_travel_date = travel_date_str
                else:
                    try:
                        first_travel_date = datetime.fromisoformat(str(travel_date_str).replace('Z', '+00:00'))
                    except ValueError:
                        pass
                        
        first_title = ""
        if db_inquiry.cart_items:
            first_title = dict(db_inquiry.cart_items[0]).get('title', '')
            
        cart_items_schema = []
        for item in db_inquiry.cart_items:
            item_dict = dict(item)
            t_date = item_dict.get('travel_date') or item_dict.get('travelDate')
            t_count = item_dict.get('travel_count') or item_dict.get('travelCount')
            b_curr = item_dict.get('base_currency') or item_dict.get('baseCurrency') or 'USD'
            l_id = item_dict.get('listing_id') or item_dict.get('listingId')
            
            if isinstance(t_date, str):
                try:
                    t_date = datetime.fromisoformat(t_date.replace('Z', '+00:00'))
                except ValueError:
                    t_date = datetime.utcnow()
            elif not isinstance(t_date, datetime):
                t_date = datetime.utcnow()
                
            cart_items_schema.append(CartItemSchema(
                listingId=str(l_id),
                title=item_dict.get('title', ''),
                travelDate=t_date,
                travelCount=int(t_count) if t_count else 1,
                price=Decimal(str(item_dict.get('price', 0))),
                baseCurrency=b_curr
            ))
            
        customer_name = f"{db_inquiry.first_name} {db_inquiry.last_name}"
        
        return AdminBookingInquiryItem(
            id=db_inquiry.id,
            reference=db_inquiry.reference,
            status=db_inquiry.status,
            customer=AdminBookingInquiryCustomer(
                name=customer_name,
                email=db_inquiry.email,
                phone=db_inquiry.phone,
                nationality=db_inquiry.nationality,
                emergencyContact=db_inquiry.emergency_contact
            ),
            listingSummary=first_title,
            listings=cart_items_schema,
            listingIds=[str(lid) for lid in listing_ids],
            type=derived_type,
            vendorIds=vendor_ids,
            vendorNames=vendor_names,
            travelDate=first_travel_date,
            guests=db_inquiry.number_of_travelers,
            numberOfTravelers=db_inquiry.number_of_travelers,
            subtotal=db_inquiry.subtotal,
            total=db_inquiry.total,
            currency=db_inquiry.currency,
            specialRequests=db_inquiry.special_requests,
            createdAt=db_inquiry.created_at,
            updatedAt=db_inquiry.updated_at
        )

    def list_admin_inquiries(
        self,
        status: Optional[InquiryStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None
    ) -> AdminBookingInquiryPaginatedResponse:
        """Search and list booking inquiries for admins, including metrics and status counts"""
        from sqlalchemy import func
        from app.models.bookingInquiry import BookingInquiry
        
        inquiries, total_count = self.repository.search_admin(
            status=status,
            search=search,
            page=page,
            per_page=per_page,
            created_from=created_from,
            created_to=created_to
        )
        
        items = [self._convert_to_admin_item(inq) for inq in inquiries]
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0
        
        status_counts_db = self.repository.count_by_status()
        all_count = sum(status_counts_db.values())
        
        status_counts = AdminBookingInquiryStatusCounts(
            all=all_count,
            pending_contact=status_counts_db.get(InquiryStatus.PENDING_CONTACT, 0),
            contacted=status_counts_db.get(InquiryStatus.CONTACTED, 0),
            quoted=status_counts_db.get(InquiryStatus.QUOTED, 0),
            converted_to_booking=status_counts_db.get(InquiryStatus.CONVERTED_TO_BOOKING, 0),
            cancelled=status_counts_db.get(InquiryStatus.CANCELLED, 0)
        )
        
        total_value = self.db.query(func.sum(BookingInquiry.total)).scalar() or Decimal('0')
        pending_value = self.db.query(func.sum(BookingInquiry.total)).filter(
            BookingInquiry.status.in_([
                InquiryStatus.PENDING_CONTACT,
                InquiryStatus.CONTACTED,
                InquiryStatus.QUOTED
            ])
        ).scalar() or Decimal('0')
        
        metrics = AdminBookingInquiryMetrics(
            totalValue=total_value,
            pendingValue=pending_value,
            confirmedOrConvertedCount=status_counts_db.get(InquiryStatus.CONVERTED_TO_BOOKING, 0),
            cancelledCount=status_counts_db.get(InquiryStatus.CANCELLED, 0)
        )
        
        return AdminBookingInquiryPaginatedResponse(
            items=items,
            total=total_count,
            page=page,
            perPage=per_page,
            totalPages=total_pages,
            statusCounts=status_counts,
            metrics=metrics
        )

    def list_vendor_inquiries(
        self,
        vendor_id: UUID,
        status: Optional[InquiryStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> VendorBookingInquiryPaginatedResponse:
        """Search and list booking inquiries related to vendor owned listings"""
        inquiries, total_count = self.repository.get_vendor_inquiries(
            vendor_id=vendor_id,
            status=status,
            search=search,
            page=page,
            per_page=per_page
        )
        
        items = [self._convert_to_admin_item(inq) for inq in inquiries]
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0
        
        return VendorBookingInquiryPaginatedResponse(
            items=items,
            total=total_count,
            page=page,
            perPage=per_page,
            totalPages=total_pages
        )


def get_booking_inquiry_service(db: Session) -> BookingInquiryService:
    """Get booking inquiry service instance"""
    return BookingInquiryService(db)
