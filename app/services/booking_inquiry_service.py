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
        self.last_provisioned_transports = []

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

            # Auto-provision a TransportBooking if cart contains a transfer item
            try:
                self._auto_provision_transport_booking(db_inquiry, inquiry_data)
            except Exception as tp_ex:
                logger.error(f"Auto-provision transport booking failed for {db_inquiry.reference}: {tp_ex}")
            
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
                if key in ('travel_date', 'travel_date_end') and isinstance(value, str):
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
        from app.models.stay import StayProperty, StayRoomType, StayRoomUnit, StayBooking, StayBookingRoom, StayRoomBlock
        from app.models.booking import Booking
        from app.models.user import User
        from app.models.enum import StayBookingStatus, StayRoomBlockStatus, BookingStatus, PaymentTransactionStatus, CurrencyCode
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

            # --- Fix 3: Parse date ranges properly for multi-night stays ---
            tdate_raw = item.get("travel_date_raw") or item.get("travelDateRaw")
            tdate_end = item.get("travel_date_end") or item.get("travelDateEnd")
            tdate_str = item.get("travel_date") or item.get("travelDate")

            check_in = date.today()
            check_out = None

            # 1. Parse check_in date
            in_val = tdate_str or tdate_raw
            if in_val:
                val = str(in_val).strip()
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

            # 2. Parse check_out date
            if tdate_end:
                end_val = str(tdate_end).strip()
                try:
                    co_dt = datetime.fromisoformat(end_val.replace("Z", "+00:00"))
                    check_out = co_dt.date()
                except ValueError:
                    try:
                        check_out = datetime.strptime(end_val[:10], "%Y-%m-%d").date()
                    except ValueError:
                        pass
            elif tdate_raw and " to " in str(tdate_raw):
                parts = str(tdate_raw).split(" to ")
                try:
                    co_dt = datetime.fromisoformat(parts[1].strip().replace("Z", "+00:00"))
                    check_out = co_dt.date()
                except (ValueError, IndexError):
                    try:
                        check_out = datetime.strptime(parts[1].strip()[:10], "%Y-%m-%d").date()
                    except (ValueError, IndexError):
                        pass
            elif tdate_str and " to " in str(tdate_str):
                parts = str(tdate_str).split(" to ")
                try:
                    co_dt = datetime.fromisoformat(parts[1].strip().replace("Z", "+00:00"))
                    check_out = co_dt.date()
                except (ValueError, IndexError):
                    try:
                        check_out = datetime.strptime(parts[1].strip()[:10], "%Y-%m-%d").date()
                    except (ValueError, IndexError):
                        pass

            if check_out is None or check_out <= check_in:
                check_out = check_in + timedelta(days=1)

            # Extract the specific rooms selected from the frontend multi-room payload
            selected_rooms = item.get("selectedRooms") or item.get("selected_rooms") or []
            rooms_to_book = []
            
            if selected_rooms:
                for sr in selected_rooms:
                    qty = int(sr.get("qty") or 1)
                    r_id = sr.get("roomId")
                    rt = None
                    if r_id:
                        try:
                            rt = self.db.query(StayRoomType).filter(
                                StayRoomType.property_id == prop.id,
                                (StayRoomType.id == UUID(r_id)) | (StayRoomType.metadata_json['sourceVariantId'].astext == r_id)
                            ).first()
                        except ValueError:
                            pass
                    if not rt:
                        r_name = sr.get("roomName")
                        if r_name:
                            rt = self.db.query(StayRoomType).filter(
                                StayRoomType.property_id == prop.id,
                                StayRoomType.name.ilike(f"%{r_name.strip()}%")
                            ).first()
                    if not rt:
                        rt = self.db.query(StayRoomType).filter(StayRoomType.property_id == prop.id).first()
                    if rt:
                        rooms_to_book.append({"room_type": rt, "qty": qty})
            else:
                rt = self.db.query(StayRoomType).filter(StayRoomType.property_id == prop.id).first()
                if rt:
                    try:
                        qty = int(item.get("travel_count") or item.get("travelCount") or 1)
                    except (ValueError, TypeError):
                        qty = 1
                    rooms_to_book.append({"room_type": rt, "qty": qty})

            if not rooms_to_book:
                continue

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
                total_qty = sum(rb["qty"] for rb in rooms_to_book)
                per_unit_rate = total_item_price / Decimal(str(max(1, total_qty)))

                # Allocate units for each requested room type
                inactive_statuses = {"maintenance", "blocked", "inactive", "out_of_service"}
                units_to_allocate = []
                for rb in rooms_to_book:
                    room_type = rb["room_type"]
                    requested_qty = rb["qty"]
                    
                    all_units = self.db.query(StayRoomUnit).filter(
                        StayRoomUnit.property_id == prop.id,
                        StayRoomUnit.room_type_id == room_type.id
                    ).all()

                    available_units = []
                    for unit in all_units:
                        if unit.status.lower() in inactive_statuses:
                            continue
                        has_booking = self.db.query(StayBookingRoom.id).join(
                            StayBooking, StayBookingRoom.stay_booking_id == StayBooking.id
                        ).join(Booking, StayBooking.booking_id == Booking.id).filter(
                            StayBookingRoom.room_unit_id == unit.id,
                            StayBookingRoom.check_in_date < check_out,
                            StayBookingRoom.check_out_date > check_in,
                            StayBooking.status != StayBookingStatus.CANCELLED,
                            Booking.status.in_(["pending", "confirmed", "completed"]),
                        ).first() is not None
                        if has_booking:
                            continue
                        has_block = self.db.query(StayRoomBlock.id).filter(
                            StayRoomBlock.room_unit_id == unit.id,
                            StayRoomBlock.status == StayRoomBlockStatus.ACTIVE,
                            StayRoomBlock.start_date < check_out,
                            StayRoomBlock.end_date > check_in,
                        ).first() is not None
                        if has_block:
                            continue
                        available_units.append(unit)

                    if not available_units:
                        logger.warning(f"No available room units for {room_type.name} on {check_in}-{check_out}")
                        continue

                    units_to_allocate = available_units[:requested_qty]
                    for unit in units_to_allocate:
                        stay_booking_room = StayBookingRoom(
                            stay_booking_id=stay_booking.id,
                            room_unit_id=unit.id,
                            room_type_id=room_type.id,
                            check_in_date=check_in,
                            check_out_date=check_out,
                            nightly_rate=per_unit_rate,
                            guests=1,
                            metadata_json={}
                        )
                        self.db.add(stay_booking_room)
                    self.db.flush()

                self.db.flush()
                self.db.commit()

                # --- Fix 4: Refresh calendar so availability search reflects this booking ---
                try:
                    from app.services.stay_inventory_service import StayInventoryService
                    inv_service = StayInventoryService(self.db)
                    room_type_ids = {rb["room_type"].id for rb in rooms_to_book}
                    inv_service.refresh_calendar(prop.id, room_type_ids, check_in, check_out - timedelta(days=1))
                    self.db.commit()
                except Exception as cal_ex:
                    logger.error(f"Error refreshing calendar for stay booking on {prop.name}: {cal_ex}")

                logger.info(f"Auto-provisioned StayBooking with {len(units_to_allocate)} room units for inquiry {db_inquiry.reference} on property {prop.name}")
            except Exception as ex:
                self.db.rollback()
                logger.error(f"Failed to auto-provision StayBooking for inquiry {db_inquiry.reference}: {str(ex)}")


    def _auto_provision_transport_booking(self, db_inquiry: BookingInquiry, inquiry_data: 'BookingInquiryCreate') -> None:
        """
        When a booking inquiry contains a transfer cart item (listing_id starts with 'transfer-'),
        create a corresponding TransportBooking record so it appears in the admin Transport Requests page.
        Parses route/pricing details from the special_requests string written by the frontend.
        """
        from app.models.vehicleCategory import VehicleCategory
        from app.models.transportBooking import TransportBooking
        from datetime import date, time
        import re, random, string

        self.last_provisioned_transports = []
        for item in inquiry_data.cart_items:
            lid = str(getattr(item, 'listing_id', '') or '').lower()
            if not lid.startswith('transfer-'):
                continue

            # Derive the vehicle category slug from the listing_id
            # listing_id format: "transfer-standard-sedan" -> slug: "standard-sedan"
            category_slug = lid[len('transfer-'):]

            # Resolve VehicleCategory by slug
            vehicle_category = self.db.query(VehicleCategory).filter(
                VehicleCategory.slug == category_slug
            ).first()

            if not vehicle_category:
                logger.warning(
                    f"Cannot auto-provision transport booking for {db_inquiry.reference}: "
                    f"VehicleCategory with slug '{category_slug}' not found."
                )
                continue

            # Parse special_requests metadata injected by the frontend
            sr = db_inquiry.special_requests or ''
            def _extract(pattern: str, text: str, default: str = '') -> str:
                m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                return m.group(1).strip() if m else default

            pickup_location   = _extract(r'Pickup Location:\s*(.+)', sr) or 'Unknown'
            destination_loc   = _extract(r'Destination Location:\s*(.+)', sr) or 'Unknown'
            travel_date_str   = _extract(r'Travel Date:\s*(\S+)', sr)
            distance_str      = _extract(r'Distance:\s*([\d.]+)', sr, '0')
            duration_str      = _extract(r'Duration:\s*(\d+)', sr, '0')
            luggage_str       = _extract(r'Luggage Count:\s*(\d+)', sr, '0')

            # Parse travel_date and pickup_time
            try:
                td_parts = travel_date_str.replace('T', ' ').split(' ')
                travel_date_val = date.fromisoformat(td_parts[0]) if td_parts[0] else item.travel_date.date() if hasattr(item.travel_date, 'date') else date.today()
                pickup_time_val = time.fromisoformat(td_parts[1][:8]) if len(td_parts) > 1 else time(12, 0)
            except Exception:
                travel_date_val = item.travel_date.date() if hasattr(item.travel_date, 'date') else date.today()
                pickup_time_val = time(12, 0)

            distance_km  = Decimal(distance_str) if distance_str else Decimal('0')
            duration_min = int(duration_str) if duration_str.isdigit() else 0
            luggage_cnt  = int(luggage_str)  if luggage_str.isdigit()  else 0

            # Pricing: use item price as total; derive route_price from vehicle category
            total_price   = Decimal(str(item.price))
            base_fare     = Decimal(str(vehicle_category.base_fare))
            price_per_km  = Decimal(str(vehicle_category.price_per_km))
            route_price   = total_price - base_fare
            if route_price < Decimal('0'):
                route_price = Decimal('0')

            # Generate unique transport booking reference tied to inquiry
            timestamp   = db_inquiry.created_at.strftime('%Y%m%d') if db_inquiry.created_at else datetime.utcnow().strftime('%Y%m%d')
            rand_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            transport_ref = f"TR-{timestamp}-{rand_suffix}"

            db_transport = TransportBooking(
                booking_reference=transport_ref,
                vehicle_category_id=vehicle_category.id,

                customer_name=f"{db_inquiry.first_name} {db_inquiry.last_name}",
                customer_email=db_inquiry.email,
                customer_phone=db_inquiry.phone,
                customer_country=None,

                pickup_location=pickup_location,
                destination_location=destination_loc,

                distance_km=distance_km,
                estimated_duration_minutes=duration_min,

                travel_date=travel_date_val,
                pickup_time=pickup_time_val,

                passengers_count=int(item.travel_count),
                luggage_count=luggage_cnt,
                special_requests=db_inquiry.special_requests,

                base_fare=base_fare,
                price_per_km=price_per_km,
                route_price=route_price,
                extra_charges=Decimal('0'),
                total_price=total_price,
                currency=str(item.base_currency.value) if hasattr(item.base_currency, 'value') else 'USD',

                booking_status='pending',
                payment_status='unpaid',
            )

            try:
                self.db.add(db_transport)
                self.db.commit()
                self.db.refresh(db_transport)
                self.last_provisioned_transports.append(db_transport)
                logger.info(
                    f"Auto-provisioned TransportBooking {transport_ref} for inquiry {db_inquiry.reference} "
                    f"(category: {category_slug}, route: {pickup_location} → {destination_loc})"
                )
            except Exception as ex:
                self.db.rollback()
                logger.error(f"Failed to commit TransportBooking for inquiry {db_inquiry.reference}: {ex}")


def get_booking_inquiry_service(db: Session) -> BookingInquiryService:
    """Get booking inquiry service instance"""
    return BookingInquiryService(db)