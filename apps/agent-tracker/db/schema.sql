create table if not exists issues (
  id integer primary key,
  subject text not null default '',
  status text not null default '',
  priority text not null default '',
  assignee text not null default '',
  category text not null default '',
  done_ratio integer not null default 0,
  story_points real not null default 0,
  spent_time real not null default 0,
  due_date text not null default '',
  created_on text not null default '',
  updated_on text not null default '',
  description text not null default '',
  acceptance_criteria text not null default '',
  source text not null default 'redmine',
  migrated_at text not null default ''
);

create table if not exists notes (
  id integer primary key,
  issue_id integer not null,
  author text not null default '',
  created_on text not null default '',
  note text not null default '',
  source text not null default 'redmine',
  foreign key(issue_id) references issues(id)
);

create table if not exists attachments (
  id integer primary key,
  issue_id integer not null,
  filename text not null default '',
  path text not null default '',
  size integer not null default 0,
  mime_type text not null default '',
  digest text not null default '',
  created_on text not null default '',
  description text not null default '',
  author text not null default '',
  source text not null default 'redmine',
  foreign key(issue_id) references issues(id)
);

create table if not exists validation_evidences (
  id integer primary key,
  issue_id integer not null,
  label text not null default '',
  path text not null default '',
  url text not null default '',
  created_on text not null default '',
  source text not null default 'redmine',
  note text not null default '',
  foreign key(issue_id) references issues(id),
  unique(issue_id, path)
);

create table if not exists status_history (
  id integer primary key,
  issue_id integer not null,
  actor text not null default '',
  changed_on text not null default '',
  old_status text not null default '',
  new_status text not null default '',
  source text not null default 'redmine',
  foreign key(issue_id) references issues(id)
);

create index if not exists idx_issues_status on issues(status);
create index if not exists idx_issues_updated_on on issues(updated_on);
create index if not exists idx_notes_issue on notes(issue_id);
create index if not exists idx_attachments_issue on attachments(issue_id);
create index if not exists idx_validation_evidences_issue on validation_evidences(issue_id);
create index if not exists idx_status_history_issue on status_history(issue_id);
