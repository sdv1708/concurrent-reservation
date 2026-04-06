# Concurrent Reservation API

An enterprise-grade hotel reservation and booking API built with FastAPI. This project serves a dual purpose: it demonstrates the capacity to construct complex, scalable backend systems using AI-assisted engineering workflows, while also functioning as an educational resource for students and engineers studying software architecture.

## Overview

The Concurrent Reservation project simulates the backend processing of an AirBnB-style platform. It handles user authentication, role-based access control, hotel management, dynamic inventory generation, and robust booking transactions with integrated Stripe payments. 

The primary challenge this system addresses is concurrency—handling simultaneous booking attempts on limited inventory using pessimistic locking strategies.

## The AI-Assisted Engineering Methodology

This codebase was developed through an AI-assisted engineering methodology, iterating through progressive phases. The process simulated a senior-to-junior handoff: high-level architecture documents and specific test suites served as the ground truth, while AI generation was leveraged to rapidly prototype, refine, and implement the application logic layer by layer. 

The transition from granular, tutorial-style instructions to standard, production-ready code documentation reflects the maturation of an AI-assisted pipeline into a professional software artifact.

## Architectural Patterns and Design Decisions

The application adheres to industry-standard backend design principles, ensuring maintainability, separation of concerns, and robust data integrity.

### 1. Service Layer Architecture
The application strictly enforces a separation between routing and business logic. 
- **Routers** (`app/routers/`): Thin endpoints responsible only for dependency injection, input validation (via Pydantic), and HTTP response formatting.
- **Services** (`app/services/`): Pure Python modules where all business logic, authorization checks, and complex orchestrations reside. This decoupling ensures the core logic is highly testable and agnostic to the HTTP framework.

### 2. Concurrency Control via Pessimistic Locking
The core of the reservation system relies on strict data consistency. When a booking is initiated, the system executes a `SELECT FOR UPDATE` query against the database.
- Inventory rows are locked at the database layer during the transaction.
- This prevents race conditions where two simultaneous transactions might attempt to book the last available room, effectively neutralizing the risk of double-booking.

### 3. State Machine Booking Flow
Bookings transition through a strict state machine (`RESERVED` -> `PAYMENTS_PENDING` -> `CONFIRMED` or `CANCELLED`).
This decoupled flow separates the immediate holding of inventory (the reservation) from asynchronous payment confirmations.

### 4. Integration via Webhooks
Payment finalization is entirely asynchronous. The system integrates with Stripe and utilizes a secure webhook listener to confirm payments. The webhook handler inherently verifies cryptographic signatures and uses pessimistic locking to safely finalize database states, rendering the endpoint safe for concurrent webhook deliveries.

### 5. Role-Based Access Control (RBAC)
Authentication is stateless and implemented via JWT (JSON Web Tokens). Dual-channel delivery is used to maximize security:
- Short-lived Access Tokens are passed via the Authorization header.
- Long-lived Refresh Tokens are stored in HttpOnly, secure cookies to mitigate Cross-Site Scripting (XSS) vulnerabilities.
Endpoints are aggressively guarded based on user roles (`GUEST` vs `HOTEL_MANAGER`).

## Educational Guide

For students and junior engineers, this codebase is structured to serve as a comprehensive study guide for modern web development in Python:

1. **Database Modeling**: Review `app/models/` to understand SQLAlchemy ORM relationships (one-to-many, many-to-many) and cascading deletes.
2. **Schema Validation**: Examine `app/schemas/` to see how Pydantic enforces strict input validation and response serialization.
3. **Dependency Injection**: Explore how FastAPI's `Depends` is used in the routers to inject database sessions and authenticate users on a per-request basis.
4. **Integration Testing**: Review the `tests/` directory to see how `pytest` fixtures, database rollbacks, and mock webhooks are orchestrated to validate complex state transitions.

## Future Roadmap

The system is currently configured to run seamlessly with an SQLite database for rapid local development and automated testing. 

Future updates to this repository will include a complete migration to **Supabase** (PostgreSQL). The foundational configuration (`DATABASE_URL`, connection pooling logic) is already present in the environment variables and database engine setup. This migration will serve as a showcase for staging the application in a production-tier managed database environment, highlighting migrations, connection pooling, and advanced PostgreSQL features.

## Local Setup Instructions

1. Ensure Python 3.10+ is installed.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on `app/config.py` definitions (assigning `jwt_secret_key` and Stripe keys).
5. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Access the interactive Swagger UI documentation at `http://localhost:8000/swagger-ui.html`.
