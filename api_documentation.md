# Fixel Backend API Documentation

This document outlines the API endpoints for the Fixel Backend.

## Base URL
`/api/funcs/`

## User Functions

### Register User
**Endpoint:** `user.register`
**Method:** `POST`
**Description:** Registers a new user.
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password",
  "name": "User Name",
  "mob_no": "1234567890",
  "address": "User Address"
}
```
**Response:** User, Session, and Profile objects.

### Login User
**Endpoint:** `user.login`
**Method:** `POST`
**Description:** Logs in an existing user.
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password"
}
```
**Response:** User, Session, and Profile objects.

### View Services
**Endpoint:** `service.viewServices`
**Method:** `POST`
**Description:** Returns a list of available services and their sub-services.
**Request Body:** `None` (Empty JSON `{}`)
**Response:** List of Service objects.

### Book Service
**Endpoint:** `service.bookService`
**Method:** `POST`
**Description:** Books a service for a user.
**Request Body:**
```json
{
  "service_id": 1,
  "user_id": "uuid",
  "scheduled_at": "ISO-8601 DateTime String",
  "sub_service_ids": [1, 2] 
}
```
**Response:**
```json
{
    "booking": { ... }
}
```

### View Booked Services
**Endpoint:** `user.viewBookedServices`
**Method:** `POST`
**Description:** Returns a list of bookings made by the authenticated user.
**Request Body:** `None` (Empty JSON `{}`). Requires Auth Token.
**Response:** List of Booking objects (with nested Service and BookingItems).

### View Booking Details
**Endpoint:** `user.viewBooking`
**Method:** `POST`
**Description:** Returns details of a specific booking.
**Request Body:**
```json
{
    "user_id": "uuid",
    "booking_id": 1
}
```
**Response:** Booking object.

### Cancel Booking
**Endpoint:** `user.cancelBooking`
**Method:** `POST`
**Description:** Cancels a specific booking.
**Request Body:**
```json
{
    "user_id": "uuid",
    "booking_id": 1
}
```

### View Notifications
**Endpoint:** `notification.viewNotifications`
**Method:** `POST`
**Description:** Returns notifications for the authenticated user.
**Request Body:** `None`. Requires Auth Token.
**Response:** List of Notification objects.

---

## Technician Functions

### Register Technician
**Endpoint:** `technician.register`
**Method:** `POST`
**Description:** Registers a new technician.
**Request Body:**
```json
{
  "email": "tech@example.com",
  "password": "password",
  "name": "Tech Name",
  "phone": "1234567890",
  "provider_role_id": "role_id"
}
```

### Login Technician
**Endpoint:** `technician.login`
**Method:** `POST`
**Description:** Logs in a technician.
**Request Body:**
```json
{
  "email": "tech@example.com",
  "password": "password"
}
```

### View Profile
**Endpoint:** `technician.viewProfile`
**Method:** `POST`
**Description:** Returns the technician's profile.
**Request Body:** `None`. Requires Auth Token.

### View Assignment Requests
**Endpoint:** `technician.viewAssignmentRequests`
**Method:** `POST`
**Description:** Returns pending assignment requests for the technician.
**Request Body:** `None`. Requires Auth Token.
**Response:** List of **AssignmentRequest** objects.

### Accept Assignment
**Endpoint:** `technician.acceptAssignment`
**Method:** `POST`
**Description:** Accepts a pending assignment request.
**Request Body:**
```json
{
    "request_id": 1
}
```
**Response:** 
```json
{
    "message": "Assignment accepted",
    "assignment": { ... }
}
```

### Reject Assignment
**Endpoint:** `technician.rejectAssignment`
**Method:** `POST`
**Description:** Rejects a pending assignment request.
**Request Body:**
```json
{
    "request_id": 1
}
```

### View Assigned Bookings (Active)
**Endpoint:** `technician.viewAssignedBookings`
**Method:** `POST`
**Description:** Returns active assignments for the technician.
**Request Body:** `None`. Requires Auth Token.
**Response:** List of Assignment objects (with nested Service and Booking).

### View Booking History
**Endpoint:** `technician.viewBookingHistory`
**Method:** `POST`
**Description:** Returns all assignments (history) for the technician.
**Request Body:** `None`. Requires Auth Token.

### Update Service/Assignment Status
**Endpoint:** `service.updateStatus`
**Method:** `POST`
**Description:** Updates the status of an assignment and its corresponding booking.
**Request Body:**
```json
{
    "assignment_id": 1,
    "status": "completed" 
}
```
**Status Options:** `started`, `completed`, `in_progress`, etc.
