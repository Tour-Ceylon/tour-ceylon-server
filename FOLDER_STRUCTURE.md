# Tour Ceylon Server - Folder Structure

## Project Overview
Tour Ceylon Server is a comprehensive tour booking and management system for Sri Lanka, built with Python (FastAPI) and featuring AI-powered recommendations and itinerary optimization.

## Root Directory Structure

```
tour-ceylon-server/
├── .env                          # Environment variables configuration
├── README.md                     # Project documentation
├── README copy.md                # Backup/alternate documentation
├── requirements.txt              # Python dependencies
├── app/                          # Main application directory
├── docker/                       # Docker configuration files
└── FOLDER_STRUCTURE.md           # This documentation file
```

## Core Application Structure (`/app`)

### Main Application Files
```
app/
├── main.py                       # FastAPI application entry point
```

### API Layer (`/app/api`)
**Purpose**: RESTful API endpoints and routing logic
```
app/api/
├── deps.py                       # Dependency injection and common dependencies
├── router.py                     # Main API router configuration
└── v1/                          # API version 1 endpoints
    ├── admin.py                 # Admin management endpoints
    ├── auth.py                  # Authentication & authorization endpoints
    ├── bookings.py              # Tour booking management endpoints
    ├── emergency.py             # Emergency services and contacts endpoints
    ├── guides.py                # Tour guide management endpoints
    ├── itinerary.py             # Itinerary planning and management endpoints
    ├── payments.py              # Payment processing endpoints
    ├── reviews.py               # Review and rating system endpoints
    ├── support.py               # Customer support endpoints
    ├── tours.py                 # Tour package management endpoints
    ├── transport.py             # Transportation booking endpoints
    └── users.py                 # User profile management endpoints
```

### AI & Machine Learning (`/app/ai`)
**Purpose**: AI-powered features for tour optimization and recommendations
```
app/ai/
├── itinerary_optimizer.py       # AI-based itinerary optimization algorithms
└── recommendation_engine.py     # Tour recommendation system
```

### Configuration (`/app/config`)
**Purpose**: Application configuration and settings management
```
app/config/
├── database.py                  # Database connection and ORM configuration
├── payment_config.py            # Payment gateway configurations
├── security.py                 # Security settings and authentication config
└── settings.py                 # General application settings
```

### Core Utilities (`/app/core`)
**Purpose**: Core application utilities and common functionality
```
app/core/
├── exceptions.py                # Custom exception classes and error handling
├── logging.py                   # Logging configuration and utilities
├── middleware.py                # FastAPI middleware components
└── utils.py                     # Common utility functions and helpers
```

### External Integrations (`/app/integrations`)
**Purpose**: Third-party service integrations and API wrappers
```
app/integrations/
├── currency_api.py              # Currency exchange rate API integration
├── email_provider.py            # Email service provider integration
├── google_maps.py               # Google Maps API for location services
├── paypal.py                    # PayPal payment gateway integration
├── sms_provider.py              # SMS service provider integration
└── stripe.py                    # Stripe payment gateway integration
```

### Data Models (`/app/models`)
**Purpose**: Database models and data structures (SQLAlchemy/ORM models)
```
app/models/
├── booking.py                   # Booking and reservation data models
├── guide.py                     # Tour guide profile and availability models
├── itinerary.py                 # Itinerary and travel plan models
├── payment.py                   # Payment transaction and billing models
├── review.py                    # Review and rating data models
├── tour.py                      # Tour package and destination models
├── transport.py                 # Transportation and vehicle models
└── user.py                      # User account and profile models
```

### Data Access Layer (`/app/repositories`)
**Purpose**: Data access patterns and database interaction logic
```
app/repositories/
├── booking_repo.py              # Booking data access operations
├── guide_repo.py                # Guide data access operations
├── payment_repo.py              # Payment data access operations
├── tour_repo.py                 # Tour data access operations
└── user_repo.py                 # User data access operations
```

### API Schemas (`/app/schemas`)
**Purpose**: Pydantic schemas for API request/response validation
```
app/schemas/
├── auth_schema.py               # Authentication request/response schemas
├── booking_schema.py            # Booking API schemas
├── guide_schema.py              # Guide API schemas
├── itinerary_schema.py          # Itinerary API schemas
├── payment_schema.py            # Payment API schemas
├── review_schema.py             # Review API schemas
├── tour_schema.py               # Tour API schemas
├── transport_schema.py          # Transport API schemas
└── user_schema.py               # User API schemas
```

### Business Logic Layer (`/app/services`)
**Purpose**: Business logic and service orchestration
```
app/services/
├── auth_service.py              # Authentication and authorization logic
├── booking_service.py           # Booking management business logic
├── currency_service.py          # Currency conversion and pricing logic
├── email_service.py             # Email notification and communication logic
├── itinerary_service.py         # Itinerary planning and optimization logic
├── notification_service.py      # General notification system logic
├── payment_service.py           # Payment processing business logic
├── safari_service.py            # Safari tour specific logic
└── visa_service.py              # Visa assistance and processing logic
```

### Testing Suite (`/app/tests`)
**Purpose**: Unit and integration tests
```
app/tests/
├── test_auth.py                 # Authentication system tests
├── test_booking.py              # Booking functionality tests
├── test_itinerary.py            # Itinerary planning tests
└── test_payment.py              # Payment processing tests
```

## Docker Configuration (`/docker`)
**Purpose**: Containerization and deployment configuration
```
docker/
├── docker-compose.yml           # Docker Compose services configuration
└── Dockerfile                   # Docker image build instructions
```

## Architecture Overview

### Clean Architecture Layers
1. **API Layer** (`/api`): HTTP endpoints and request handling
2. **Service Layer** (`/services`): Business logic and orchestration
3. **Repository Layer** (`/repositories`): Data access abstraction
4. **Model Layer** (`/models`): Data structures and domain entities
5. **Schema Layer** (`/schemas`): API contract definitions

### Key Features
- **Multi-payment Support**: PayPal and Stripe integrations
- **AI-Powered**: Recommendation engine and itinerary optimization
- **Comprehensive Booking**: Tours, guides, transport, and accommodations
- **Multi-channel Communication**: Email and SMS notifications
- **Location Services**: Google Maps integration
- **Currency Support**: Multi-currency handling
- **Review System**: Customer feedback and ratings
- **Emergency Services**: Safety and support features
- **Visa Assistance**: Travel documentation support

### Technology Stack
- **Backend Framework**: FastAPI (Python)
- **Database**: SQLAlchemy ORM (database agnostic)
- **API Documentation**: Automatic OpenAPI/Swagger generation
- **Containerization**: Docker and Docker Compose
- **Testing**: Pytest framework
- **External APIs**: Google Maps, Payment gateways, Currency services

This structure follows clean architecture principles, ensuring maintainability, testability, and scalability for the tour booking platform.


