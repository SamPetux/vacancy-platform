# Product Design System

## Product type

This is an operational admin application.

It is NOT a marketing landing page.

Prioritize:

- speed
- clarity
- information density
- operational visibility
- fast moderation

---

# UI stack

React
TypeScript
Tailwind CSS
shadcn/ui

Use shadcn/ui components whenever a suitable component exists.

Avoid implementing custom primitives unnecessarily.

---

# Layout

Desktop-first admin interface.

Main sidebar:

Dashboard

Vacancies

Moderation

Sources

Cities

Companies

Scoring

Analytics

System

Settings

---

# Dashboard

Must answer immediately:

Is the system working?

How many items arrived?

How many vacancies were detected?

How many duplicates?

How many passed scoring?

How many are waiting for moderation?

Are any sources broken?

---

# UI principles

Prefer:

tables
cards
badges
filters
compact charts
drawers
dialogs

Avoid:

huge hero sections
marketing-style design
excessive gradients
decorative animations
large empty spaces

---

# Status colors

Use semantic component variants.

SUCCESS
WARNING
ERROR
NEUTRAL

Do not hardcode random colors across components.

---

# Tables

Every major table should support where useful:

filtering
sorting
pagination
search
status indicators

---

# Vacancy details

Vacancy detail page must show:

original source data

parsed values

score

score breakdown

penalties

flags

source

moderation history

---

# Responsiveness

Desktop is primary.

Tablet should remain usable.

Mobile does not need full feature parity during MVP.