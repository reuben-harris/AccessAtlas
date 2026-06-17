import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

function runDjangoShell(script) {
  const output = execFileSync(
    "uv",
    ["run", "python", "manage.py", "shell", "--no-imports", "-c", script],
    {
      cwd: process.cwd(),
      encoding: "utf8",
      env: process.env,
    },
  );
  return JSON.parse(output.trim().split("\n").at(-1));
}

async function login(page) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  await page.goto("/accounts/login/");
  await page.getByLabel("Email").fill(`playwright-${suffix}@example.com`);
  await page.getByLabel("Display name").fill("Playwright");
  await page.getByRole("button", { name: "Continue with email" }).click();

  await expect(page).toHaveURL("/");
}

function visibleDropdownOptionTexts(page) {
  return page.locator(".ts-dropdown .option").evaluateAll((options) =>
    options
      .filter((option) => option.offsetParent !== null)
      .map((option) => option.textContent.trim()),
  );
}

function fieldStyles(locator) {
  return locator.evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      borderColor: style.borderColor,
      boxShadow: style.boxShadow,
    };
  });
}

test("invalid TomSelect fields keep the validation outline", async ({ page }) => {
  await login(page);

  await page.goto("/jobs/new/");

  const titleField = page.locator("#id_title");
  const siteSelect = page.locator("#id_site");
  const siteWrapper = page.locator("#id_site + .ts-wrapper");

  await expect(siteSelect).not.toHaveClass(/is-invalid/);
  await expect(siteWrapper).not.toHaveClass(/is-invalid/);
  const freshSiteStyles = await fieldStyles(siteWrapper);
  const freshTitleStyles = await fieldStyles(titleField);
  expect(freshSiteStyles.borderColor).toBe(freshTitleStyles.borderColor);
  expect(freshSiteStyles.boxShadow).not.toContain("rgba(214, 57, 57");

  await page.getByRole("button", { name: "Save" }).click();

  await expect(siteSelect).toHaveClass(/is-invalid/);
  await expect(siteWrapper).toHaveClass(/is-invalid/);
  await expect(titleField).toHaveClass(/is-invalid/);

  const invalidSiteStyles = await fieldStyles(siteWrapper);
  const invalidTitleStyles = await fieldStyles(titleField);
  expect(invalidSiteStyles.borderColor).toBe(invalidTitleStyles.borderColor);
  expect(invalidSiteStyles.borderColor).not.toBe(freshSiteStyles.borderColor);
});

test("site visit job assignment hides selected jobs without blocking more choices", async ({
  page,
}) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const seed = runDjangoShell(`
import json
from datetime import date

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job, JobStatus, Priority
from access_atlas.sites.models import Site
from access_atlas.trips.models import SiteVisit, Trip

suffix = ${JSON.stringify(suffix)}
leader, _ = User.objects.update_or_create(
    email=f"playwright-leader-{suffix}@example.com",
    defaults={"display_name": "Playwright Leader"},
)
site, _ = Site.objects.update_or_create(
    source_name="playwright",
    external_id=f"tomselect-{suffix}",
    defaults={
        "code": f"PW-{suffix[:8]}",
        "name": f"Playwright TomSelect {suffix}",
        "description": "",
        "tags": [],
        "latitude": "-41.286500",
        "longitude": "174.776200",
    },
)
trip, _ = Trip.objects.update_or_create(
    name=f"Playwright TomSelect Trip {suffix}",
    defaults={
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 6, 3),
        "trip_leader": leader,
    },
)
site_visit, _ = SiteVisit.objects.update_or_create(
    trip=trip,
    site=site,
    defaults={"planned_day": date(2026, 6, 1)},
)
job_titles = [
    f"Playwright Assignable {suffix} 1",
    f"Playwright Assignable {suffix} 2",
    f"Playwright Assignable {suffix} 3",
]
for title in job_titles:
    Job.objects.update_or_create(
        site=site,
        title=title,
        defaults={
            "description": "",
            "status": JobStatus.UNASSIGNED,
            "priority": Priority.NORMAL,
            "work_programme": None,
        },
    )
print(json.dumps({"siteVisitId": site_visit.pk, "jobTitles": job_titles}))
`);
  const [firstJob, secondJob] = seed.jobTitles;

  await login(page);
  await page.goto(`/trips/site-visits/${seed.siteVisitId}/`);

  const jobsWrapper = page.locator("#id_jobs + .ts-wrapper");
  const jobsInput = jobsWrapper.locator("input");
  const option = (name) => page.locator(".ts-dropdown .option", { hasText: name });

  await jobsInput.click();
  await expect(option(firstJob)).toBeVisible();
  await option(firstJob).click();
  await expect(jobsWrapper.locator("[data-value]", { hasText: firstJob })).toBeVisible();

  await jobsInput.click();
  await jobsInput.press("ArrowDown");
  await expect(option(secondJob)).toBeVisible();

  const visibleOptions = await visibleDropdownOptionTexts(page);
  expect(visibleOptions).not.toContain(firstJob);
  expect(visibleOptions).toContain(secondJob);

  await option(secondJob).click();
  await expect(
    jobsWrapper.locator("[data-value]", { hasText: secondJob }),
  ).toBeVisible();
});
