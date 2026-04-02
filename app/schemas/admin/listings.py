from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enum import DestinationType, PropertyType, SafariType, TransferLocationType


AdminListingCategory = Literal["stay", "tour", "activity", "transfer"]


class CoordinateMixin(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class DestinationRef(BaseModel):
    id: UUID
    name: str
    destination_type: DestinationType
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminHotelDetail(BaseModel):
    property_type: PropertyType = Field(alias="propertyType")
    star_rating: int = Field(alias="starRating")
    check_in_time: str = Field(alias="checkInTime")
    check_out_time: str = Field(alias="checkOutTime")
    child_policy: str | None = Field(default=None, alias="childPolicy")

    model_config = ConfigDict(populate_by_name=True)


class AdminTourDetail(BaseModel):
    duration_days: int = Field(alias="durationDays")
    route_summary: str = Field(alias="routeSummary")
    meeting_point: str = Field(alias="meetingPoint")

    model_config = ConfigDict(populate_by_name=True)


class AdminSafariDetail(BaseModel):
    national_park: str = Field(alias="nationalPark")
    safari_type: SafariType = Field(alias="safariType")
    duration_minutes: int = Field(alias="durationMinutes")
    guide_included: bool = Field(alias="guideIncluded")
    pickup_supported: bool = Field(default=False, alias="pickupSupported")

    model_config = ConfigDict(populate_by_name=True)


class AdminTransferDetail(BaseModel):
    origin_type: TransferLocationType = Field(alias="originType")
    destination_type: DestinationType = Field(alias="destinationType")
    vehicle_policy: str = Field(alias="vehiclePolicy")

    model_config = ConfigDict(populate_by_name=True)


class AdminListingBase(CoordinateMixin):
    destination_id: UUID = Field(alias="destinationId")
    title: str
    description: str | None = None
    is_active: bool = Field(default=True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class StayListingCreate(AdminListingBase):
    hotel_detail: AdminHotelDetail = Field(alias="hotelDetail")


class StayListingResponse(AdminListingBase):
    id: UUID
    category: Literal["stay"]
    destination: DestinationRef | None = None
    hotel_detail: AdminHotelDetail | None = Field(default=None, alias="hotelDetail")


class TourListingCreate(AdminListingBase):
    tour_detail: AdminTourDetail = Field(alias="tourDetail")


class TourListingResponse(AdminListingBase):
    id: UUID
    category: Literal["tour"]
    destination: DestinationRef | None = None
    tour_detail: AdminTourDetail | None = Field(default=None, alias="tourDetail")


class ActivityListingCreate(AdminListingBase):
    safari_detail: AdminSafariDetail = Field(alias="safariDetail")


class ActivityListingResponse(AdminListingBase):
    id: UUID
    category: Literal["activity"]
    destination: DestinationRef | None = None
    safari_detail: AdminSafariDetail | None = Field(default=None, alias="safariDetail")


class TransferListingCreate(AdminListingBase):
    transfer_detail: AdminTransferDetail = Field(alias="transferDetail")


class TransferListingResponse(AdminListingBase):
    id: UUID
    category: Literal["transfer"]
    destination: DestinationRef | None = None
    transfer_detail: AdminTransferDetail | None = Field(default=None, alias="transferDetail")


class ListingUpdateRequest(CoordinateMixin):
    destination_id: UUID | None = Field(default=None, alias="destinationId")
    title: str | None = None
    description: str | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
    hotel_detail: AdminHotelDetail | None = Field(default=None, alias="hotelDetail")
    tour_detail: AdminTourDetail | None = Field(default=None, alias="tourDetail")
    safari_detail: AdminSafariDetail | None = Field(default=None, alias="safariDetail")
    transfer_detail: AdminTransferDetail | None = Field(default=None, alias="transferDetail")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_single_detail_payload(self):
        populated_details = [
            detail
            for detail in [
                self.hotel_detail,
                self.tour_detail,
                self.safari_detail,
                self.transfer_detail,
            ]
            if detail is not None
        ]
        if len(populated_details) > 1:
            raise ValueError("only one detail payload can be provided")
        return self
