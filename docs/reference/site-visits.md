# Site Visits

Site Visits are planned attendance at one Site during a Trip.

## Key Fields

- Trip
- Site
- Planned day
- Planned start and planned end
- Status
- Notes

The model owns schedule validation. The form mirrors part of that validation so
browser input problems surface as clear field errors.

## Statuses

- Planned
- Skipped
- Completed

## Job Assignments

Jobs are assigned to Site Visits through a Site Visit Job relationship. The Job
site must match the Site Visit site.

Jobs cannot be assigned to Site Visits on completed or cancelled Trips.
