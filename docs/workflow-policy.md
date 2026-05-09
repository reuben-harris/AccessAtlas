# Workflow Policy

## Workflow Overview

```mermaid
flowchart TD
    ActiveJob["Active job"] --> RequirementsEditable["Requirements editable and confirmable"]
    ActiveJob --> UnassignedJob["Unassigned job"]
    ActiveJob --> AssignedJob["Job assigned to active trip"]

    UnassignedJob --> DirectOutcome["Can be completed or cancelled from job editing"]
    AssignedJob --> MetadataEditable["Normal metadata editable without resetting trip approval"]
    AssignedJob --> OutcomeFieldsLocked["Site, status, and closeout note disabled in job editing"]
    AssignedJob --> TripCloseout["Trip closeout sets assigned job outcomes"]

    DirectOutcome --> CompletedJob["Completed job"]
    DirectOutcome --> CancelledJob["Cancelled job"]
    TripCloseout --> CompletedJob
    TripCloseout --> CancelledJob
    TripCloseout --> ReturnedJob["Returned to unassigned"]

    CompletedJob --> RequirementsFrozen["Requirements frozen"]
    CancelledJob --> RequirementsFrozen

    ActiveTrip["Active trip"] --> CompletedTrip["Completed trip"]
    ActiveTrip --> CancelledTrip["Cancelled trip"]
    CompletedTrip --> TripFrozen["Trip editing, visits, assignments, and requirements frozen"]
    CancelledTrip --> TripFrozen
    CompletedTrip --> CloseoutCorrection["Closeout correction for still-linked jobs and site visits"]
    CloseoutCorrection --> CompletedTrip
    ReturnedJob --> CorrectionLimitation["Not included in closeout correction"]
```

## Jobs

Jobs can be planned and edited while active. A job assigned to an active trip can
still have normal metadata updated without resetting trip approval, but its site
assignment and outcome fields are owned by the trip workflow:

- `site`, `status`, and `closeout_note` are visible but disabled in normal job
  editing while the job is assigned to a trip.
- unassigned jobs can be completed or cancelled directly from normal job editing.
- completed jobs may have a closeout note, but do not require one.
- cancelled jobs require a closeout note.
- jobs assigned to completed or cancelled trips cannot be edited through normal
  job editing.

## Requirements

Requirements describe what is needed to complete a job.

- active jobs can have requirements added, edited, deleted, and confirmed.
- completed and cancelled jobs freeze requirement structure and confirmation.

## Trips

Trips are planning containers for site visits and assigned jobs.

- active trips can be edited according to the normal approval reset rules.
- completed and cancelled trips freeze normal trip editing, site visit editing,
  job assignment changes, and requirement changes.
- trip cancellation returns active assigned jobs to unassigned and marks planned
  site visits as skipped.
- trip closeout resolves site visits and sets assigned job outcomes to completed,
  cancelled, or returned to unassigned.

## Closeout Correction

Completed trips can use closeout correction to amend closeout outcomes with an
explicit correction reason. The correction workflow reuses the closeout form for
still-linked site visits and jobs, then writes clear history entries.

Known limitation: jobs that were returned to unassigned during closeout are no
longer linked to the trip, so they do not appear in closeout correction. Restoring
or correcting returned jobs is not currently a supported feature.

Cancelled-trip correction is also not currently supported because cancellation returns
active assigned jobs and removes their trip assignment.
