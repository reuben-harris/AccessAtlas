## Trip Lifecycle And Approval

### Goal

Add a lightweight approval workflow to trips so planning can move through:

* `draft`
* `submitted`
* `approved`
* `completed`
* `cancelled`

This is a trip-level workflow. Approval is not a separate readiness state for
site visits or jobs, but changes to those child objects should still invalidate
trip approval because they materially change the trip plan.

### Locked decisions

* New trips always start as `draft`.
* The trip create form should not expose a status selector.
* Replace the current `planned` status with `submitted` and `approved`.
* Add a `Submit for approval` action on trip pages.
* Add an `Approve` action on trip pages.
* `Approve` is only available when the trip is currently `submitted`.
* Anyone except the trip leader can approve the trip.
* One valid approval is enough to move the trip to `approved`.
* Multiple approvals are still allowed and should be recorded as proof-reading /
  review context.
* Approval cannot be revoked in the first pass.
* Approval history should be visible:
  * who submitted
  * who approved
  * when it happened
* If an approved trip is changed, show a warning before saving:
  * `Making changes to this approved trip will send it back to waiting for approval.`
* If the user confirms the change, the trip returns to `submitted`.
* Approval invalidation should apply to:
  * direct trip edits
  * site visit create, edit, delete, reorder, and job-assignment changes within the trip
  * any persisted edit to a job that is tied to the trip
* `Submit for approval` should only be available from `draft`.
* The trip leader can submit their own trip for approval.
* After the first approval moves a trip to `approved`, additional approvers can
  still be recorded with an `Add approval` action.
* The approval list should appear in a dedicated approval card on the trip
  overview page.

### Recommended first implementation scope

* Default new trips to `draft`
* Add `Submit for approval` action
* Add `Approve` action
* Replace `planned` with `submitted` and `approved`
* Record submitter and approver events
* Show approval history on the trip page / trip history
* On approved trip edits, warn and send the trip back to `submitted`
* Apply the same invalidation rule when relevant site visits or jobs within the
  trip are edited
* Allow additional approvals to be added after the first approval

### UI expectations

* Trip create page:
  * no status selector
* Trip detail page:
  * `Submit for approval` sits with the existing trip actions
  * `Approve` sits with the existing trip actions
  * `Approve` should be disabled when the trip is not `submitted`, using the
    same disabled-action pattern already used elsewhere in the app
* Approval context should be visible without opening the history page, in a
  dedicated approval card

### Implementation notes

* Backwards compatibility is not required here. The database can be recreated if
  that is the simplest path.
* This feature touches workflow rules, forms, action buttons, and history.
* Model/service ownership matters here: the workflow transitions and invalidation
  rules should not live only in templates or forms.
* Child-object invalidation is part of the required first pass, not a stretch
  goal.
* Once a trip is already `submitted`, it should stay in that state until
  approval or another workflow transition. Repeated submit clicks should not
  create new approval rounds.

### Remaining implementation question

* If one child-object invalidation path turns out to be materially harder than
  the others, document the exact gap rather than silently skipping it.

### Deferred or worth deciding later

* Multi-approver thresholds or voting semantics
* Approval revocation
* Richer role-based approval rules
* Broader readiness workflows beyond trip approval
