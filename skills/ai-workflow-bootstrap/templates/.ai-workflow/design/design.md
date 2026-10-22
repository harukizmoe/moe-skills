# Design

Only for tasks whose shape is not obvious. If a competent developer could pick
the modules from the spec, skip this file.

## Modules and boundaries

What owns what. Name the seam where each module can be replaced or tested alone.

## Data model

Entities, identity, and what makes two records the same or different.

## Failure behavior

What happens on bad input, partial writes, retries, and concurrent updates.

## Task breakdown

The `depends_on` graph belongs in `tasks/tasks.json`; this file explains why the
split is where it is.
