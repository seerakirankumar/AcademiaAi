# Working CSV datasets

The working CSV files in this directory were generated from the supplied `final dataset.xlsx` workbook. The workbook contained 500 students and multiple subject/activity/skill/feedback records per student. To fit the current analytics API, detailed records are aggregated into one row per student for each feature file. The original worksheet data is retained as CSV snapshots in `source_sheets/` for traceability; **the top-level CSV files are the live source of truth** and are the files updated by the admin CRUD API.

## Working files

- `students.csv`: student ID, name, department, year, section, enrollment year, email.
- `academics.csv`: cumulative GPA, backlogs, average internal marks, average marks.
- `attendance.csv`: mean subject attendance and number of subjects below 75% attendance.
- `lms.csv`: LMS logins, assignment completion, weekly learning hours converted from minutes in the last 30 days.
- `engagement.csv`: event/workshop/participation counts, competition count, club participation and volunteer hours. If a student has no engagement rows in the source workbook, zero recorded activity is used for this snapshot.
- `placements.csv`: aptitude, coding, communication/interview score, resume score and mapped placement status.
- `skills.csv`: average technical/professional skill assessment scores and evidence counts.
- `feedback.csv`: average student/faculty ratings, support indicator and most frequent topic.
- `interventions.csv`: starts empty; intervention create/update operations persist here.
- `users.json`: generated on first startup from `.env`; stores password hashes and roles, never plaintext passwords.

## Important mapping notes

- Student IDs use the `STU` prefix.
- No gender field was supplied, so it is not part of the working schema.
- The source workbook does not have a standalone mock-interview score; the communication/interview score is used as the closest available placement readiness measure.
- `projects_count` and `certifications_count` are evidence proxies derived from skill rows, not counts of a separate project/certificate registry.
- The 0–100 success score and support indicators are rule-based prototype outputs. They are not probabilities and should be reviewed by staff before any real-world use.
- This application uses CSV files for student and intervention persistence and JSON for local user accounts. It does not require MySQL, SQLite, or another database.
