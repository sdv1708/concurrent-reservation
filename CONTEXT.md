# Concurrent Reservation

A hotel booking platform. Hotel managers list rooms, and guests claim rooms for a stay and pay for them.

## Hotels

**Room type**:
A kind of room in one hotel, with a number of identical rooms of that kind. A guest claims one or more rooms of one room type.
_Avoid_: Room (for the kind), room category

## Stays and inventory

**Stay**:
The nights a guest occupies, from the check-in date up to, but not including, the check-out date. A stay from 2026-08-05 to 2026-08-07 is 2 nights.
_Avoid_: Date range, booking period

**Night**:
One calendar date on which a guest occupies a room. The check-out date is never a night of the stay.
_Avoid_: Day

**Hold**:
A temporary claim on rooms for a stay, placed before payment. A hold ends when payment confirms it or when its payment window runs out.
_Avoid_: Reservation, temporary reservation

**Booked**:
The state of rooms that a guest paid for. Booked rooms stay claimed until the booking is cancelled.
_Avoid_: Confirmed rooms, reserved

**Available**:
The rooms of a room type on a night that are not closed, not held, and not booked.
_Avoid_: Free, open

**Closed**:
A night on which a manager stops new holds for a room type. Holds and booked rooms that exist before the close stay valid.
_Avoid_: Blocked, unavailable
