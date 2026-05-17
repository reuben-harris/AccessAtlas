# Imports

Access Atlas supports CSV import workflows for Jobs and Job Templates.

## Job Imports

Job import examples:

- [Job test import](../examples/job-test-import.csv)

Job imports identify sites by site code, can optionally use Job Templates, and
can include status fields for historical or pre-existing work.

Cancelled imported Jobs require a closeout note. Completed imported Jobs require
a completed date.

## Job Template Imports

Job Template import examples:

- [Job Template test import](../examples/job-template-test-import.csv)

Job Template imports create reusable templates that can later be used to create
Jobs with default priority, estimated duration, and description.
