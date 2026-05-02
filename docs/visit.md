## Site Visit Day Picker

- When adding or editing a site visit, simplify date selection to a button for each day of the trip.
- A single site visit no longer spans multiple days. Repeated attendance should be represented by multiple site visits.
- Optional start and end times remain supported for now.

## Locked Decisions

1. **Times stay optional**
   - Choosing a trip day does not replace optional `planned_start` / `planned_end`.

2. **Multiple site visits without times**
   - If several visits land on the same day with no explicit times, keep a simple fallback ordering for now.
   - Existing stable ordering such as site code / object ordering is acceptable in the first pass.

3. **Duplicate same-site same-day visits are allowed**
   - A user may leave a site and return later the same day.

4. **Day buttons should use actual dates**
   - Use actual trip dates in the UI.
   - A combined label like `Day 1 · Mon 12 May` is acceptable if it reads well in the interface.

## Clarification On Reassigning A Visit

The current question about moving a site visit between trips is probably too broad for this feature.

For this pass, the relevant change is:

- moving a site visit to a different **day within the same trip**

Assigned jobs should stay attached when that happens.

- No extra confirmation is needed for the first pass unless implementation exposes a concrete risk.
- This is a scheduling move within the same trip, not a reassignment of the jobs themselves.


-> YES ASSIGNED JOBS SHOULD STAY ATTACHED
## Recommended First-Pass Scope

- Replace the current free-form cross-day scheduling input with explicit trip-day selection.
- Keep site visits site-specific.
- Keep optional times.
- Treat each site visit as belonging to one day of one trip.
- Let users create multiple site visits when they need repeated attendance across multiple days.

## Deferred For Later

- Sequence-only daily ordering instead of time
- Automatic route planning
- Generic travel / itinerary stops beyond site visits
