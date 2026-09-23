# Vacancy Scoring

There are TWO different metrics.

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