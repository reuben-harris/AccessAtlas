## - v2
Special view
Mermaid js view of domain structure
Gnatt view of trips
##

## - v2 needs some thought
Trip editing status. Maybe ditch that entirely. Have a button thats submit for approval. And the close of statuses are apart of the close of workflow.
need to think about the approval workflow. I want to avoid having to have permissions so maybe its as simple as someone else other than the leader needs to approve the trip.

Currently you can set the status of a completely or cancelled job back to planned or draft which then lets you make changes which would otherwise be locked away. I guess I have to make the decision if I want to lock things down and be rigid or let people break things and do weird workflows. Im inclined to let people do what they want but I really need to test it and see if there is any reason to let people move a trip back to an ealier status.

One feature which might help is a Copy from exisitng trip on creation. That way someone is less inclinded to go edit an exisitng trip. I can see if they do a trip and do half the work they might go and reuse it instead of making a new one as it will have the jobs assinged to it already (or will it because onces its cancelled uncompleted jobs get sent back to unassiged) and update it if they are allowed to. Were we want to keep that history. Becuase of that I think its best to lock it down then and just make it easy to create a new trip from an exisitng trip.
##

## - v2 usability
The dashboard needs some work.
* Maybe it should show YOUR trips and not all trips. I don't think active templates is working having a widget for.
* For MY planned trips it should be of a more gnatt style layout or at least you should be able to see the dates of the tip. 
* The status isn't very important but maybe the trip name can have the background badge color of the trip status so the information is there but its combined with the trip name.
##

## v4 scope - Warning Intergrations
Windy.com intergration. Shows weather on the trips page.
Maybe there could be a notifications feature that tells you if the weather is bad were the trip is going to be.
Extend this to nzta intergration roud closures. 
These should all be togglable features in the settings for the website. Maybe need to think about allowing people to write plugins, that way they can intergrate with their own local services? Plugins can be later, for now just ingegrate directly.
##

## v3 - journey planning
Need to implement the journey planning. Where are we staying what not. Windy feature requires this a little, it answers were is this trip planned.
Route planning
Add "site road end" coordiantes to site sync spec
Add "access notes" maybe intiailly before building it out. This could be in the print out of the trip summary.
Contacts for relevant contacts. Part of the sync spec.
##

## v2
need some way to link jobs to an external ticketing system. For us github tickets. But need to think about the generic implementation and what level of the domain model to implement this at
##

## V2- feature
be able to print out a trip summary
need to be able to see the job requiremets summary. Maybe even a todo style checklist to make sure you have everything. It might even be nice if its like SIM cards stack.
##

## v2 simplish? - Job Templates
ability to link into a SOP for a job. How to configure an alloy etc
needs to support more than one link as could be one hwo to configure and one for how to install
##

## v69 Job requirements tweaks
What about action steps like call gehard, this doesn't have a quantity. Its not an enforced field but it feels slightly jarring. Not a major.
I am not sure if I like the term "Default Requirements". But its also ok on some level
##

## v6 - Booking reminder feature
Helicopter access?
Trigger to make sure helicopter gets book
Accomdation gets book and store the booking reference?
Flights get book?
4wd gets book
Eco portal gets done
jsea?
Some of these are high level trip tasks which happen each time. 
The vehicle booking thing is a trip dependent thing. Maybe when you create the trip you can select from a drop down. And then based on that you have to upload certain file or complete certain tasks.
##

## V1 Global search
seems a little borken, cant serach by user
Job is Job_Templates in the UI
Its not very clear that there is a search result
Add a count for return entries
Make a more clear distinction between the header and the results. Currently they look identical.
##

#####
For the Jobs assigned drop down and site selector in the site trip view. The user should be able to type and essentially search in there. IF there are a lot of sites or jobs this will help filter down.

There should be away in the jobs view to see jobs that are assigned and what trip they are assigned to in the columns
On the job page too when viewing a specific job you should be able to tell and click on what assigned site visit or trip its on

rewrite readme

Site visit edit is obscure, can be fixed with editing overhaul

## - v1 needed for gns deployment
The login screen should have the background of a global spinning. There is no dark mode on the login page.

Users on the website should get a circle avatar. These should be random and unique. I like this idea of this being something unique about the website. The main purpose being usability, oh thats Dave without have to read his name. Need to think about overall auth engine. Maybe the auth service can provide this profile.
##

## !!! v2 - decent feature
Need filters like netbox with a default filter on trips to hide completed trips.

There should  also be a way to select rows like netbox and do a bulk delete or bulk edit.

You should also be able to click the Jobs colum number and it should take you to the jobs page with a filter based on that site visit.


Things need to be done holistically acorss the website.
##

## v1 - deployment
Need to think about and test how someone connects to the db from the docker image
Also it being a webserver how does the docker image even work. I want something you can just deploy to ecs and then wire up the envs.
##

I would like columns in the tables to be sortable. Mainly so grouping can happen such as being able to sort by priority or job status. What are your thoughts on this?

I would like to add filters the same way netbox has them. You should be able to sort by status = planning. Or check a box and get status != planning. What are your thougths on this? We have already started to add this with the layers in the map view. I really like how easy they are to toggle on and off. The netbox ones are powerful but slow and heavy to use. I want to keep this lightweight functionality while extending it and being consistent across the site.

I either need to add a delete to the jobs page or a bulk edit so you can bulk edit and mark jobs as cancelled. I like the idea of the bulk edit. I need that feature anyway. When you need to bulk edit after a bad import you can just specify cancellation reason as failed import. If one really wants to purge they can go edit the db.

AI help me improve my roadmap plan. ALso refactor whole app.

Sumbit for approval workflow... Ditching trip manual set statuses
Training plugin... Just an idea. There should be a feature for teaching you how to use the website. You can define you company specific workflows. Basically interactive documentation. I always thought a tool like netbox needs this were its a white canvas and you really have to define how features should be used in your company. A plugin that steps you through things.



Map view. Need to be able to filter by job type.

Should it remember what view you were on last. When I load jobs do a I want it to go straight to maps if I was on maps view last? 

If I create a job it takes me into that job. There is no way other than to use the left navigation to open the jobs list up. This feels slightly jarring? I think in netbox in the main part of the website there is a folder like navigation and you can click back to the main jobs list when you are in a selected job. It goes like [Job](clickable link) > The Name Of The Current Job You Are In

##
The job requirements needs a refactor to be useful. Maybe a view of a todo list. Its just not very usable in its current state ticking things off. Its also a bit slow to specify requriements and I have just not used it enough really.

On the trips page when you open a trip there should be a added view for requirements. It should also maybe group the requriements so you get totals making it more of a summary. This is makes me wonder if requirements you should be able to make an object instead of free text. Include this in the requirements refactor.
##

Regarding adding filters everywhere. The histroy you should be able to filter by at least user. So you can see what changes a user did. And maybe a date range too.

Team members tick boxes when making a trip def needs a refactor. Good enough for now though. I like the Clickup style for a drop down list but you can select more than one option. They get added as tags when you click them and then there is an x agaisnt there name which removes then and adds them back into the dropdown.

Currently profile takes email for initials. It should only be display name but I need to ebtter understand auth providors and if they offer this or its just email.

Dockerfile looks like it could be simplified a little