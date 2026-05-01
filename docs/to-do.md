# To-Do

This file is a rough thinking space, not a committed roadmap. Items here range from likely features to open questions to loose ideas.

**Bold Bits Are Things I Am Very Keen On**

## Core Workflow

- Explore creating a new trip from an existing trip instead of encouraging heavy reuse of completed trips.

## Jobs And Requirements

- Revisit the job requirements UX. It is still not especially useful in practice.
- Explore a more checklist-like or summary-oriented requirement view.
- Add better requirement summaries at the trip level.
- Consider whether requirements should eventually become first-class reusable objects instead of only free text.
- **Explore linking jobs to external ticketing systems in a generic way.**
- Revisit job templates linking to SOP or instruction material, likely supporting multiple links.

Questions:

- Are requirements better as lightweight free text plus quantity, or as a stronger object model?
- What level should external ticket linkage live at?

Loose thoughts:

- "Default Requirements" may not be the right term.
- Action-style requirements such as "call Gerhard" feel awkward in the current model.

## Synced Site Lifecycle

- Decide how stale synced sites should appear across the website.
- Decide what should happen to jobs attached to stale sites.
- Consider whether stale sites should remain selectable when creating jobs, site visits, or Access Records.
- Consider whether stale sites should be hidden by default once site-wide filtering exists.

Questions:

- Should jobs on stale sites remain active, become blocked, or just show a warning?
- Should unassigned jobs for stale sites stay in the normal job pool?
- Should planned trips/site visits involving stale sites show a stronger warning?
- Should the jobs map include jobs for stale sites if the stale site still has coordinates?
- Should sync status affect future Access Record warnings, or should stale status be treated separately?

Loose thoughts:

- Stale sites should probably remain available for history, so hard deletion is still the wrong default.
- New jobs, site visits, or Access Records against stale sites may need blocking or an explicit warning.
- Global search results should show stale status clearly enough that stale sites are not mistaken for current sites.
- Reports, exports, maps, and future print views need to decide whether stale-site work is included by default.
- Jobs on stale sites may need a visual cue anywhere jobs are listed, not only on the site page.

## Reporting And Printouts

- Add a trip summary print/export flow.
- Include requirement summaries in a printable form.
- Consider whether printed views should emphasise packing/checklist workflows.
- Or discourge this an build an offline app

## Auto Journey Planning

- Add journey planning only when it becomes worth the complexity.

## Integrations

- Weather integration
- Road closure integration
- Ticketing integration
- Possibly training or onboarding guidance later

Questions:

- Should these stay built-in for a while rather than jumping straight to plugins?
- What toggles or settings model would keep integrations manageable?

Loose thoughts:

- Training/workflow guidance as a plugin is still just an idea.

## Technical And Platform

- Revisit deployment ergonomics for database wiring and container runtime expectations.
- Simplify the Dockerfile if there is real cleanup value there.
- Keep validating that the container/deployment path feels straightforward for ECS-style deployment.

# Reubens thoughts for agent to tidy

## Other
* Demo dataset flag? as well as demo auth mode? That would be local but it tells you its in demo and put something in random and it will log you in.
* Bulk edit
* Automatic site sync? How to configure? Is it finally time for a UI settings panel?
* Is there a case to use typescript instead of javascript? Should we implement some js package management and linting?
* You can update a site visit to skipped and the job remains planned. Same issue when the user can control the statuses. is it better to always enforce a workflow?
* Allow the user to save custom views (dropdown option of views to selet from?). This would save column sort order and a specific filter applied. These should be able to be shared.
* Origonally we moved to CARTO beacuse of a tileing issue with OpenStreetMaps. However, this maybe have been fixable after reading [this GH issue.](https://github.com/Leaflet/Leaflet/issues/10156) I prefer the detail of the openstreetmaps one thats all. I do like the simplicty and dark mode of CARTO though.
* have to Think about recording jobs against a finicial plan. So is this a 26-27 job or 27-28. This might be important as the years overlap so we can track if there are jobs getting forgotten about. Example, there are jobs still to do from 26-27 but we import 27-28 and it gets hard to see what to do. Maybe this is were a priority comes in. The workflow for that might be someone updating all the 26-27 jobs to high priority before importing the new batch.
* There are these too warnings on the website now ```Unexpected value calc(100% - 2px) parsing width attribute. history```, ```Unexpected value calc(100% - 2px) parsing height attribute```
* Add Meta description. Give all buttons accessible names. [Main tag on every page](https://dequeuniversity.com/rules/axe/4.11/landmark-one-main). Is the website WCAG compliant.
* Tasks to complete post trip. Upload site photos, update asset management etc. There should also be a way to see a list of all the outstanding to do items. Also should consider if it is past a trip date and the trip has not been closed off. This is another post trip task that could show up in this list. The goal here it to have checks and balances and make sure things are not missed. Also, trying to make it easier for people to be able to see what they tasks they still need to do.
* The + button on the left for jobs is to create a fresh job (no template). I see most people creating jobs from template so do we direct that button to be "From template" or do we add a third button. This would make it: Import Bulk, Create from template, Create fresh. I don't think its getting too wide in the nav menu but it also just seems odd to have one with three buttons and the rest with one for some reason.
* Add the end reset migrations to be one file.
* Are we actually using HTMX anywhere?
* Add a minigame to the website for when I am bored.
* break down the app.css into logical chunks so that a human can work on it.
* add comments to the js files (espically helper code)
* Automatically schedule yearly maintenance jobs for a site
* Sync through site description from source of truth (general notes)
* Sale pitch: Gis and project management in one
* BUG UI: If I click the profile button the glow doesn't go away after I click off. I have to click off again and then the glow goes away.
* move css file into chunks (so human can read with comments)
* general agents file, comments in the right places (and why we are doing it that way)
* css of main content in center doesnt scale well when zooming out. It also has a lot of padding on the left and probably could take up more of the screen.
* Consider putting a direct link on the left nav to Site Visit and Access Records (maybe requirements?)
* rename .js files that relate to map to be consistent (currenlty job_map.js and site_access_map.js). Create subfolder and move three files.

## Access Record Improvements
* Generate starter geojson when not access record is uploaded. It will put the points for access start and the site. [It would be on this page](http://localhost:8000/sites/1/access-records/new/). Maybe instead of specifying a file you can check a box. Automatically generate a v1 or something. Then you are just specifying the arrival method, name and changelog.
* View toggle for map visability is only avaliable on the sites page and not the access record page for that specific record.
* **Feature Idea: Add a view for elevation of a track. https://github.com/Raruto/leaflet-elevation**
* **There should be thought and maybe intergration about getting the KMLs on the devices. Can we auto sync to Garmin? Can we auto sync to phone app?**
* **The map size on the sites page is weird. The page is also overall very long now. I like the jobs map view were it takes up the full page and scales based on window size. Maybe the sites view should move to view style tabs to breakup the content.**
* **Add fullscreen options to access record map (and all maps)**
* Update the readme with specs for the Geojson. Add a whole new section just for that.
* I need to produce an example geojson with all the features in it. This will make testing easier and UI improvements easier to see.
* **Download GPX (instead of KML or keep KML?)** https://www.npmjs.com/package/@dwayneparton/geojson-to-gpx?activeTab=readme or https://github.com/nicholas-fong/GeoJSON-to-gpx or agent finds something better. Not a fan of how small and inactive those repos look. However, maybe its not that complicated. Can always role my own convertor in a serparte repo and swap that out for these opensource ones if they become a liability.
* Export ALL access records (for loading to a device) OR investigate ways we can sync to our phones etc. Needs more investigation into full pipline (from access atlas to using on phone). Also, how does this look once we have a phone app. No more export pipeline as the app could be a free topo offline map too?
* **Add home button to the access records map the centers the map around the access records**
* **Make the access record map bigger somehow. Access record table could collapse?**
* **Open site in google maps could be moved back to normal button spot for consistency**
* **New access record button should persist across menus. Those main buttons should always persist across menus (I think the new access records button is the only one that doesnt in the whole site. Might be to do with were the button is in the code so verify and make sure its consistent with the rest of the codebase)**

### Complex Access Record Feature

GeoJSON download normalization of styles

  It means when users download GeoJSON, Access Atlas would automatically write or refresh map style properties so files are consistent, regardless of what was uploaded.

  Example:

  - For point features, enforce fields like:
      - marker-color
      - marker-size
      - marker-symbol
  - For tracks, enforce:
      - stroke
      - stroke-width
      - stroke-opacity
  - Apply based on Access Atlas rules (access_start, site, gate, note, and track suitability 4wd/luv/walking).

  So the app becomes the owner of default style output, and users don’t have to maintain colors/symbols manually.

## OIDC

* Test fully
* Confirm dispaly name email all working

# Features To Implement

## Team And User Experience

- Refine team member selection when creating or editing trips.
* Use https://github.com/OmenApps/django-tomselect as it does seem what I want

## Site Visit Date Picker

* Remove and simplify with a button for each day
* A single site visit no longer spans multiple days. The user should simply create multiple site visits and assign to multiple days
* Consider how to expand site visit to inlclude, heading to the hotel, airport, lunch etc. This way we build a source of truth of travel desitnation. Maybe site visit gets turned generic. We need a complete picture of travel if there will be a feature were it auto routes your day. zDiscuss with agent.
* Consider instead of a direct time select, the user can just select the sequence order for that day. This way route calcuation can happen automatically. Dicuss with agent.

## Trip Lifecycle And Approval

* Remove the status option being selectable when creating a trip. The default is now draft.
* Next to cancel and close trip add a submit for approval button
* Next to close and cancel add an approve button. Unless the status is not "submitted" we disable the button like we have done in other places
* Replace the planned status with "Submitted" and "Approved"
* For now lets keep it simple and everyone who is not the leader can approve the trip
* Mulitple people can approve a trip. A list adds up with all the approvers
* If a trip is approved and a change is made the user is prompted with a warning "Making changes to this approved trip will send it back to waiting for approval". If the changes are confirmed the trip gets sent back to the submitted status

## Global Search

* Job template label needs fixing on the global search page
* At the top it should tell you the number of results returned across the whole website
* Add a search input on each trips, jobs, job templates and sites. This simply filters the current table (does not refresh the page or load a new page)
* Expand search to newly added model

## Columns

* Add sortable table columns where it improves grouping and scanning.
* These would get saved as a user preference and be remembered across page reload

## Bulk Edit

* Add checkboxes on the far left of tabler views to allow a user to select multiple rows. Do this were there is already a edit button on the row.
* Add a bulk edit button down the bottom right of the tabler view were a user can select multiple entries
* Add checkboxes on the map view under jobs. When you open the tool tip/popup you can select job by job or all jobs

## Filters

* Add filter functionality to Trips, Jobs and Sites Lists
* The filters functionality should sit below the custom views. Currently only jobs has custom views and it would sit below Table and Map buttons.
* I like the quick access of the filters on the map page. I want to somehow keep this easy access while extending the feature
* The job status filter on the maps page should be moved into this site wide filters feature. This would mean these filters apply to now both the table and map view.
* [Have the ability to filter with more advance logic the same as this netbox feature](https://github.com/netbox-community/netbox/issues/7604)
* Filters save to the users preferences so if they leave and revisit the page the filters remain
* Sites page gets a default filter that excludes stale sites

## Dashboard Rewrite
- Add a PIE chart for Jobs by status (assigned, planned etc)
- Add a list of upcoming trips ( A month out view only). All statuses. Columns are, Trip Name, Leader, Date. Order by Start Date
- Add a list of trips waiting for approval
- Add a space for all Site sync warnings (missing coordinates etc)
* The PIE chart you can hover over and the piece of the PIE animates by moving out of the pie slightly. The pie is glowing like the rest of the theme of the website. It also shows you the number of items in the status when you hover over the piece.
* There needs to be a view of the people that are free (not assigned to a trip). This might be better in a different place. I am almost thinking a gnatt view with each row being a person. This could also be were its better to intergrate with something like teams and use the calendar feature. This one will need more thought.
* I want the dashboard to drive workflows or work needed to be done. Its that shortcut into the deeper tools. Opening filters directly in the other views showing you the data you need to see.

## Site photos

* Hook into an s3 backend for storage of files (when in a deployment scenario)
* Display site photos at a site
* Add a new tabe for photos. Investigate if there are any out of the box django or good js viewers like. https://github.com/codingjoe/django-pictures
* Allow filtering by date. Organsie photos by date uploaded (we can assume same date same site visit)
* Build in functionaltiy were users can tag photos and associated them with a site visit
* Photos without a tagged site visit just display the date and unknown site visit were as photos with an assocaited site visit display the site visit and the date.
* I like the photo grouping the google photos uses
* Ask agent if its best to pin the photos to a trip or site visit. I am leaning on trip for simplicity
* How does dev work with s3 backend? I assume I can add to docker compose file?
* Use django storages and update default backend with an env
* env for file path (s3 or local)