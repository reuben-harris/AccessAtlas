## Global Search

* Job template label needs fixing on the global search page
* At the top it should tell you the number of results returned across the whole website
* Expand search to newly added models (access records and what not)

## Notes / concerns to lock down before implementation

### Global search result count

Good idea. I recommend the page show:

- total result count across all models
- per-model group counts if the page is grouped by object type

That makes the search page much easier to scan.

### Expanding model coverage

I would be deliberate about what gets included.

My recommendation for next additions:

- Access Records
- Access Record Versions only if there is a strong reason -> lets not add these
- maybe Site Visits if they are considered meaningful search destinations -> lets add these

I would avoid flooding the search page with too many low-signal object types too quickly.

### Ranking / grouping question

Before coding, decide whether results should be:

1. grouped by object type -> yes to this
2. merged into one ranked list

My recommendation:

- keep grouped-by-type results

Reason:

- this is an operational internal app
- grouped results are easier to scan than opaque ranking

### Job template label fix

This sounds small, but it suggests the search result presentation logic is already a little inconsistent. I would treat that as a signal to:

- define one result-label helper per object type
- keep search display text standardized

-> yes to this

### Open questions I would want answered before coding

1. Do you actually want separate client-side search inputs on the existing list pages, or would improving the current server-side search be better?
   - My recommendation: improve the existing search pattern rather than introducing a second one.

-> lets just focus on improving the global search function. The other search feature idea is legacy and we should not implement it anymore

2. Which additional models should be in global search first?
   - My recommendation: Access Records first. -> lets add this and site visits

3. Should search match notes/description fields aggressively, or stay narrower?
   - My recommendation: stay narrower first to keep result quality high. -> lets stay narrowed for now

## Agreed implementation scope

Implement only the global search improvements:

1. fix inconsistent labels on the search page
2. show total results across the whole website
3. show grouped results with per-group counts
4. expand global search to:
   - Access Records
   - Site Visits
5. keep matching relatively narrow and operationally useful

Out of scope:

- separate client-side search inputs on list pages
- aggressive full-text style matching across every notes field
- Access Record Version search
