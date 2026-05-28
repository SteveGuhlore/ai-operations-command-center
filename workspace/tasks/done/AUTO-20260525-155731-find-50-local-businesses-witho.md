---
task_id: AUTO-20260525-155731-find-50-local-businesses-witho
assigned_agent: outreach_worker
status: done
priority: normal
pod: local_outreach_pod
task_type: prospect_research
created_at: 20260525-155731
---

# Find 50 Local Businesses Without Websites for Outreach Pitch

# Goal

Generate a list of 50 local service businesses that do not have a website. This list will be used for the next outreach sequence for easysimplesites.org.

# Deliverables

A single CSV file named `prospects.csv` in `workspace/output/` with the following columns:
- `business_name`
- `business_type` (e.g., plumber, roofer, electrician)
- `city`
- `state`
- `phone_number`
- `source_url` (The Google Maps URL, Yelp page, etc., where you found the business)

# Instructions

1.  **Targeting**: Focus on local service-based businesses (plumbers, electricians, landscapers, cleaning services, etc.) in major US metro areas (e.g., Dallas, Phoenix, Atlanta).
2.  **Verification**: You MUST verify that the business does not have a website. Check their Google Maps listing, Yelp page, and do a direct Google search for their business name. If a website exists, they are not a valid prospect.
3.  **Data Collection**: Collect the required information for 50 valid prospects.
4.  **Formatting**: Format the data into a CSV file as specified above and save it to the output directory.


## Agent Output


