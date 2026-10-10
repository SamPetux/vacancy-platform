# Vacancy Scoring

There are THREE different metrics.

Never merge them.

---

# VQS

Vacancy Quality Score answers:

"How good and transparent is this vacancy for a potential candidate?"

Range:

0–100

Initial components:

SalaryScore          0–25

WorkloadScore        0–15

FlexibilityScore     0–10

CompanyScore         0–15

ExperienceValue      0–15

AccessibilityScore   0–10

TransparencyScore    0–10

---

# Important scoring principles

Missing information does not always mean zero.

Scores must be explainable.

Every score component must provide:

value

reason

signals used

penalties

---

# FeedScore

FeedScore answers:

"How useful is it to show this vacancy in the media feed right now?"

Possible factors:

VQS

freshness

novelty

category diversity

company diversity

duplicate probability

recent feed composition

---

# AudienceInterestScore

AudienceInterestScore answers:

"How interesting is this vacancy for a career-media audience, including people not actively job-hunting?"

It must not simply duplicate VQS.

Initial components (weights configurable):

novelty_role

employer_pull

conditions_edge

experience_value

career_potential

accessibility

task_interest

shareability

CreativeContext interprets scores into an editorial marker and visual family.
It does not change VQS or FeedScore.

Public cards show editorial markers (e.g. КАРЬЕРНЫЙ ШАГ), not letter grades.
Letter grades A+/A/B+/B remain internal for moderators and analytics.

ABOVE_MARKET requires city+category cohort percentile (own DB sample ≥ 15),
never a large salary figure alone.

---

# Example

Vacancy:

Courier

VQS:
88

But there were already six courier vacancies today.

FeedScore may therefore be:

61

---

# LLM

An LLM must never return an unexplained final VQS.

The LLM may extract semantic information.

Final score should be calculated by application code.

---

# Configuration

Weights and thresholds must be stored in configuration/database.

Do not scatter numeric weights through source code.

---

# Evaluation

Whenever scoring logic changes:

run the new algorithm on historical vacancies.

Compare:

score distribution

top vacancies

bottom vacancies

moderator approval rate

category distribution

previous vs new score

Do not deploy major scoring changes without reviewing these results.