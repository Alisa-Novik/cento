admin = User.find_by_login("admin") || User.where(admin: true).first
raise "No admin user exists yet" unless admin

consultant_role = Role.find_or_initialize_by(name: "Career Consultant")
consultant_role.assignable = true
consultant_role.issues_visibility = "all"
consultant_role.users_visibility = "all"
consultant_role.time_entries_visibility = "all"
consultant_role.permissions = [
  :view_project,
  :search_project,
  :view_issues,
  :add_issues,
  :edit_issues,
  :copy_issues,
  :manage_issue_relations,
  :manage_subtasks,
  :set_issues_private,
  :set_own_issues_private,
  :add_issue_notes,
  :edit_issue_notes,
  :edit_own_issue_notes,
  :view_private_notes,
  :set_notes_private,
  :delete_issues,
  :manage_public_queries,
  :save_queries,
  :view_gantt,
  :view_calendar,
  :log_time,
  :view_time_entries,
  :edit_time_entries,
  :edit_own_time_entries,
  :manage_wiki,
  :rename_wiki_pages,
  :delete_wiki_pages,
  :view_wiki_pages,
  :export_wiki_pages,
  :view_wiki_edits,
  :edit_wiki_pages,
  :delete_wiki_pages_attachments,
  :protect_wiki_pages,
  :manage_files,
  :view_files,
  :manage_documents,
  :view_documents,
  :manage_boards,
  :view_messages,
  :add_messages,
  :edit_messages,
  :edit_own_messages,
  :delete_messages,
  :delete_own_messages,
  :view_news,
  :manage_news,
  :comment_news
]
consultant_role.save!

statuses = [
  ["New", false],
  ["In Progress", false],
  ["Waiting on Client", false],
  ["Submitted", false],
  ["Interviewing", false],
  ["Offer", false],
  ["Closed", true]
].each_with_index.map do |(name, closed), index|
  IssueStatus.find_or_create_by!(name: name) do |status|
    status.is_closed = closed
    status.position = index + 1
  end
end

new_status = statuses.first

trackers = [
  "Intake",
  "Resume",
  "LinkedIn",
  "Applications",
  "Interview Prep",
  "Follow-up",
  "Offer"
].each_with_index.map do |name, index|
  Tracker.find_or_create_by!(name: name) do |tracker|
    tracker.default_status = new_status
    tracker.position = index + 1
  end
end

trackers.each do |tracker|
  statuses.each do |old_status|
    statuses.each do |new_status|
      WorkflowTransition.find_or_create_by!(
        tracker_id: tracker.id,
        role_id: consultant_role.id,
        old_status_id: old_status.id,
        new_status_id: new_status.id,
        author: false,
        assignee: false
      )
    end
  end
end

field_specs = [
  ["Target Role", "string"],
  ["Target Companies", "text"],
  ["Seniority", "list", ["IC", "Lead", "Manager", "Director", "Executive"]],
  ["Resume Version", "string"],
  ["Application Deadline", "date"],
  ["Interview Date", "date"],
  ["Current Stage", "list", statuses.map(&:name)]
]

field_specs.each_with_index do |(name, format, values), index|
  field = IssueCustomField.find_or_initialize_by(name: name)
  field.field_format = format
  field.possible_values = values if values
  field.is_required = false
  field.is_for_all = true
  field.searchable = true
  field.position = index + 1
  field.trackers = trackers
  field.save!
end

project = Project.find_or_initialize_by(identifier: "sample-jane-doe-career-search")
project.name = "Sample: Jane Doe Career Search"
project.description = "Sample career-consulting engagement covering intake, resume positioning, applications, interview prep, and offer follow-up."
project.is_public = false
project.trackers = trackers
project.enabled_module_names = %w[
  issue_tracking
  time_tracking
  news
  documents
  files
  wiki
  repository
  boards
  calendar
  gantt
]
project.save!

member = Member.find_or_initialize_by(project: project, user: admin)
member.roles = [consultant_role]
member.save!

priority = IssuePriority.default || IssuePriority.first
unless priority
  priority = IssuePriority.create!(
    name: "Normal",
    position: 1,
    is_default: true,
    active: true
  )
end

def create_issue(project, tracker_name, status_name, priority, subject, description, due_date = nil)
  tracker = Tracker.find_by!(name: tracker_name)
  status = IssueStatus.find_by!(name: status_name)
  issue = Issue.find_or_initialize_by(project: project, subject: subject)
  issue.tracker = tracker
  issue.status = status
  issue.priority = priority
  issue.author = User.find_by_login("admin") || User.where(admin: true).first
  issue.assigned_to = issue.author
  issue.description = description
  issue.due_date = due_date if due_date
  issue.save!
  issue
end

create_issue(
  project,
  "Intake",
  "In Progress",
  priority,
  "Complete positioning intake",
  "Capture target roles, compensation range, constraints, preferred industries, and existing search assets.",
  Date.today + 2
)

create_issue(
  project,
  "Resume",
  "Waiting on Client",
  priority,
  "Revise resume for senior product manager roles",
  "Rewrite summary, tighten impact bullets, and produce one ATS-focused version plus one networking version.",
  Date.today + 5
)

create_issue(
  project,
  "LinkedIn",
  "New",
  priority,
  "Update LinkedIn headline and About section",
  "Align LinkedIn positioning with resume narrative and target role keywords.",
  Date.today + 6
)

create_issue(
  project,
  "Applications",
  "Submitted",
  priority,
  "Submit application: Acme Health",
  "Track posting, referral path, tailored resume version, and follow-up owner.",
  Date.today + 7
)

create_issue(
  project,
  "Interview Prep",
  "Interviewing",
  priority,
  "Prepare STAR stories for leadership interview",
  "Create six reusable stories covering conflict, launch impact, prioritization, stakeholder management, ambiguity, and failure recovery.",
  Date.today + 10
)

create_issue(
  project,
  "Offer",
  "Offer",
  priority,
  "Draft negotiation plan",
  "Compare base, equity, bonus, benefits, start date, and remote policy. Prepare counteroffer language.",
  Date.today + 14
)

wiki = project.wiki || Wiki.create!(project: project, start_page: "Engagement")
page = WikiPage.find_or_initialize_by(wiki: wiki, title: "Engagement")
content = page.content || WikiContent.new(page: page)
content.text = <<~TEXT
  h1. Jane Doe Career Search

  h2. Operating cadence

  * Weekly strategy review on Mondays
  * Async resume/application updates as issues
  * Interview prep notes stored on linked issues

  h2. Current targets

  * Senior Product Manager
  * Group Product Manager
  * Healthtech, fintech, and B2B SaaS

  h2. CRM convention

  Use issues for all client-visible work. Use status, due date, tracker, and custom fields to keep the consulting pipeline queryable.
TEXT
content.author = admin
content.save!

puts "Seeded project: #{project.name}"
puts "Project URL path: /projects/#{project.identifier}"
