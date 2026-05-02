## Dashboard Rewrite
- Add a PIE chart for Jobs by status
- Add a list of upcoming trips in a one month view
- Add a space for site sync or access warnings that need attention
- The dashboard should drive workflows or work that needs to be done. It should be a shortcut into deeper tools and open filtered views directly where possible.

### Agreed shape

- Build the dashboard around actionable sections rather than generic summary cards
- The three main sections should be:
  - Work Overview
  - Upcoming Field Work
  - Data Attention

### Work Overview

- Show Jobs by status in a chart
- The chart should be clickable so each status can take the user into a filtered Jobs view
- Hover can show:
  - status name
  - count
  - a subtle hover animation or pop-out
- Keep the first implementation restrained. It should be useful before it is decorative.

### Upcoming Field Work

- Show trips starting between today and the next 30 days
- Order by start date
- Columns:
  - Trip Name
  - Leader
  - Date
- Prefer non-terminal trips only. Completed and cancelled trips should not clutter an upcoming list unless there is a strong reason later.

### Data Attention

- Show site sync or access warning information
- Prefer grouped actionable summary rows over dumping raw warning text
- Example shape:
  - sites with access warnings
  - stale synced sites
- These should link into the relevant deeper view when practical

### Clarifications and limits

- Do not invent a trip approval workflow just to satisfy the dashboard
- If trip approval becomes a real domain concept later, it can earn its own dashboard section then
- Do not add a people availability or staffing view as part of this dashboard rewrite
- People availability likely belongs in a future staffing or scheduling surface, potentially with external calendar integration

### Deferred ideas

- trips waiting for approval
- people who are free or not assigned to trips
- gantt-like staffing or calendar views
