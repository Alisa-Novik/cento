#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parent.parent
QUESTIONNAIRE_ROOT = ROOT_DIR / "workspace" / "runs" / "crm-questionnaire"
CRM_ROOT = ROOT_DIR / "workspace" / "runs" / "crm-app"
INTAKE_ROOT = ROOT_DIR / "workspace" / "runs" / "career-intake"
DOCS_PATH = ROOT_DIR / "docs" / "crm-module.md"
INTAKE_DOCS_PATH = ROOT_DIR / "docs" / "career-intake.md"
REDMINE_DOCS_PATH = ROOT_DIR / "docs" / "redmine-integration.md"
TEMPLATE_DIR = ROOT_DIR / "templates" / "crm"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento"
REDMINE_CONFIG_PATH = CONFIG_DIR / "redmine.json"
LOG_DIR = ROOT_DIR / "logs" / "crm"
DEFAULT_PROFILE = "career-consulting"
QUESTIONNAIRE_VERSION = "1.0"
CRM_STATE_VERSION = "1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47865
PORT_SPAN = 12
LOG_FILE: Path | None = None
REQUEST_LOG: list[dict[str, str]] = []
REQUEST_LOCK = threading.Lock()
REQUEST_LOG_LIMIT = 50

SOURCE_KINDS = {
    "telegram": "Telegram conversation with consultant",
    "linkedin": "LinkedIn profile",
    "resume": "Resume or CV",
    "cover-letter": "Existing cover letter",
    "job-description": "Target job description",
    "company": "Target company notes",
    "notes": "Consultant notes",
    "other": "Other supporting material",
}

CAREER_ARTIFACTS = [
    {
        "id": "intake-synthesis",
        "title": "Candidate intake synthesis",
        "description": "Normalize raw inputs into a concise candidate brief, open questions, risks, and strongest positioning angles.",
    },
    {
        "id": "resume-grammar-conciseness-review",
        "title": "Resume review: grammar and conciseness",
        "description": "Find grammar issues, wordiness, repeated claims, unclear bullets, and low-signal phrasing.",
    },
    {
        "id": "resume-impact-ats-review",
        "title": "Resume review: impact and ATS alignment",
        "description": "Assess role fit, measurable impact, keyword coverage, structure, and missing evidence.",
    },
    {
        "id": "linkedin-profile-review",
        "title": "LinkedIn profile review",
        "description": "Review headline, about section, experience framing, keywords, social proof, and recruiter scan quality.",
    },
    {
        "id": "top-5-cover-letter-pack",
        "title": "Cover letters for top 5 target companies",
        "description": "Produce one tailored cover-letter direction per selected company, with company-specific proof points and caveats.",
    },
    {
        "id": "interview-prep-brief",
        "title": "Interview preparation brief",
        "description": "Create likely questions, story bank gaps, positioning themes, and preparation priorities.",
    },
    {
        "id": "client-action-plan",
        "title": "Client action plan",
        "description": "Turn findings into a prioritized consulting plan with next steps, homework, and decision points.",
    },
]

ARTIFACT_TRACKER_HINTS = {
    "intake-synthesis": "Intake",
    "resume-grammar-conciseness-review": "Resume",
    "resume-impact-ats-review": "Resume",
    "linkedin-profile-review": "LinkedIn",
    "top-5-cover-letter-pack": "Applications",
    "interview-prep-brief": "Interview Prep",
    "client-action-plan": "Follow-up",
}


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class Question:
    key: str
    prompt: str
    kind: str
    choices: tuple[Choice, ...] = ()
    optional: bool = False
    help_text: str = ""


QUESTIONS: tuple[Question, ...] = (
    Question(
        key="consultant_name",
        prompt="What name should this CRM use for you internally?",
        kind="text",
        help_text="Example: Alisa Novik",
    ),
    Question(
        key="business_name",
        prompt="What business or brand name should be shown on the CRM?",
        kind="text",
        optional=True,
        help_text="Press Enter to skip if you want to decide later.",
    ),
    Question(
        key="business_model",
        prompt="Which operating model fits you best today?",
        kind="single",
        choices=(
            Choice("solo", "Solo consultant"),
            Choice("small_practice", "Small practice or boutique team"),
            Choice("agency", "Agency-style service business"),
            Choice("hybrid", "Mix of consulting, products, and workshops"),
        ),
    ),
    Question(
        key="primary_goal",
        prompt="What is the main job for the first CRM version?",
        kind="single",
        choices=(
            Choice("client_tracking", "Track prospects and active clients cleanly"),
            Choice("delivery_workflow", "Run service delivery and follow-ups"),
            Choice("sales_pipeline", "Improve lead conversion and sales visibility"),
            Choice("knowledge_base", "Centralize notes, documents, and templates"),
        ),
    ),
    Question(
        key="client_segments",
        prompt="Which client segments matter most?",
        kind="multi",
        choices=(
            Choice("students", "Students and recent grads"),
            Choice("early_career", "Early-career professionals"),
            Choice("mid_career", "Mid-career professionals"),
            Choice("executives", "Senior leaders and executives"),
            Choice("career_changers", "Career changers"),
            Choice("tech_professionals", "Tech professionals"),
            Choice("immigrants", "Immigrants, expats, and relocators"),
            Choice("general_job_seekers", "General job seekers"),
        ),
    ),
    Question(
        key="services",
        prompt="Which services should the CRM support?",
        kind="multi",
        choices=(
            Choice("resume_cv", "Resume or CV writing"),
            Choice("linkedin", "LinkedIn profile optimization"),
            Choice("interview", "Interview coaching"),
            Choice("job_search", "Job search strategy"),
            Choice("salary", "Salary negotiation"),
            Choice("career_transition", "Career transition planning"),
            Choice("personal_brand", "Personal branding"),
            Choice("offer_review", "Offer review"),
        ),
    ),
    Question(
        key="engagement_model",
        prompt="How do clients usually buy from you?",
        kind="multi",
        choices=(
            Choice("single_session", "One-off sessions"),
            Choice("multi_session_package", "Multi-session coaching packages"),
            Choice("async_review", "Async document reviews"),
            Choice("retainer", "Retainers or ongoing advisory"),
            Choice("group_workshop", "Group workshops or cohorts"),
        ),
    ),
    Question(
        key="lead_sources",
        prompt="Where do most leads come from or where should the CRM track them?",
        kind="multi",
        choices=(
            Choice("referrals", "Referrals"),
            Choice("linkedin_inbound", "LinkedIn inbound"),
            Choice("linkedin_outbound", "LinkedIn outreach"),
            Choice("website", "Website or landing pages"),
            Choice("social_media", "Other social media"),
            Choice("workshops", "Workshops or webinars"),
            Choice("partners", "Partnerships and communities"),
            Choice("marketplaces", "Freelance marketplaces"),
        ),
    ),
    Question(
        key="pipeline_template",
        prompt="Which pipeline shape is the best starting point?",
        kind="single",
        choices=(
            Choice("simple", "Simple: Lead, Qualified, Proposal, Won, Lost"),
            Choice("coaching", "Coaching: Inquiry, Discovery, Proposal, Paid, Active, Complete, Follow-up"),
            Choice("content_heavy", "Content-heavy: Audience, Lead, Call, Offer, Client, Alumni"),
        ),
    ),
    Question(
        key="communication_channels",
        prompt="Which communication channels should be visible in the CRM?",
        kind="multi",
        choices=(
            Choice("email", "Email"),
            Choice("phone", "Phone"),
            Choice("sms", "SMS"),
            Choice("whatsapp", "WhatsApp"),
            Choice("telegram", "Telegram"),
            Choice("linkedin", "LinkedIn messages"),
            Choice("zoom", "Zoom"),
            Choice("google_meet", "Google Meet"),
        ),
    ),
    Question(
        key="integrations",
        prompt="Which integrations are worth planning for early?",
        kind="multi",
        optional=True,
        choices=(
            Choice("gmail", "Gmail"),
            Choice("google_calendar", "Google Calendar"),
            Choice("google_drive", "Google Drive"),
            Choice("notion", "Notion"),
            Choice("stripe", "Stripe"),
            Choice("calendly", "Calendly"),
            Choice("zoom", "Zoom"),
            Choice("slack", "Slack"),
        ),
    ),
    Question(
        key="documents_to_track",
        prompt="Which deliverables or records should be attached to contacts and deals?",
        kind="multi",
        choices=(
            Choice("resume", "Resume versions"),
            Choice("cover_letter", "Cover letters"),
            Choice("linkedin_profile", "LinkedIn profile drafts"),
            Choice("interview_notes", "Interview notes"),
            Choice("action_plan", "Action plans"),
            Choice("contracts", "Contracts and agreements"),
            Choice("invoices", "Invoices and payments"),
            Choice("session_notes", "Session notes"),
        ),
    ),
    Question(
        key="must_have_features",
        prompt="Which features are must-haves for the CRM MVP?",
        kind="multi",
        choices=(
            Choice("contacts", "Contact database"),
            Choice("pipeline", "Pipeline or deal tracking"),
            Choice("tasks", "Tasks and reminders"),
            Choice("notes", "Timeline notes"),
            Choice("templates", "Reusable templates"),
            Choice("forms", "Intake forms"),
            Choice("analytics", "Dashboards and analytics"),
            Choice("client_portal", "Client-facing portal"),
        ),
    ),
    Question(
        key="automation_level",
        prompt="How much automation do you want in version one?",
        kind="single",
        choices=(
            Choice("manual", "Mostly manual, with strong structure"),
            Choice("assisted", "Some automation for reminders and status updates"),
            Choice("automated", "As automated as practical from the start"),
        ),
    ),
    Question(
        key="reporting_focus",
        prompt="What should reports focus on?",
        kind="multi",
        choices=(
            Choice("pipeline_health", "Pipeline health"),
            Choice("revenue", "Revenue and package sales"),
            Choice("lead_source", "Lead source attribution"),
            Choice("conversion", "Conversion rates"),
            Choice("client_progress", "Client progress and outcomes"),
            Choice("utilization", "Time and workload utilization"),
        ),
    ),
    Question(
        key="privacy_level",
        prompt="How sensitive is the client data you expect to keep?",
        kind="single",
        choices=(
            Choice("basic", "Basic business data only"),
            Choice("elevated", "Sensitive coaching notes and career history"),
            Choice("strict", "High sensitivity, privacy-first handling required"),
        ),
    ),
    Question(
        key="launch_preference",
        prompt="What build style should I optimize for after this questionnaire?",
        kind="single",
        choices=(
            Choice("mvp_fast", "Fast MVP first"),
            Choice("balanced", "Balanced MVP with room to grow"),
            Choice("custom_foundation", "More custom foundation, even if slower"),
        ),
    ),
    Question(
        key="special_notes",
        prompt="Any special notes, constraints, or non-negotiables?",
        kind="text",
        optional=True,
        help_text="Examples: bilingual support, local-only storage, client portal later.",
    ),
)

PIPELINE_STAGE_LIBRARY = {
    "simple": [
        {"id": "lead", "label": "Lead", "accent": "#C97A21", "description": "Raw incoming opportunity."},
        {"id": "qualified", "label": "Qualified", "accent": "#4A8F6D", "description": "Clear fit and timing."},
        {"id": "proposal", "label": "Proposal", "accent": "#25557A", "description": "Offer is in motion."},
        {"id": "won", "label": "Won", "accent": "#274C3D", "description": "Client engaged."},
        {"id": "lost", "label": "Lost", "accent": "#7A3A35", "description": "Not moving forward now."},
    ],
    "coaching": [
        {"id": "inquiry", "label": "Inquiry", "accent": "#C97A21", "description": "Initial interest and context."},
        {"id": "discovery", "label": "Discovery", "accent": "#9B5D2E", "description": "Intro call or needs review."},
        {"id": "proposal", "label": "Proposal", "accent": "#25557A", "description": "Package or scope prepared."},
        {"id": "paid", "label": "Paid", "accent": "#43726A", "description": "Deposit or payment confirmed."},
        {"id": "active", "label": "Active", "accent": "#3E6953", "description": "Delivery in progress."},
        {"id": "complete", "label": "Complete", "accent": "#215145", "description": "Core work delivered."},
        {"id": "follow_up", "label": "Follow-up", "accent": "#6A6B8A", "description": "Reactivation or alumni care."},
    ],
    "content_heavy": [
        {"id": "audience", "label": "Audience", "accent": "#CC7C2B", "description": "Top-of-funnel attention and audience capture."},
        {"id": "lead", "label": "Lead", "accent": "#9D5C35", "description": "Named inbound person or inquiry."},
        {"id": "call", "label": "Call", "accent": "#2F6485", "description": "Consultation or fit call staged."},
        {"id": "offer", "label": "Offer", "accent": "#56795B", "description": "Offer package or proposal shared."},
        {"id": "client", "label": "Client", "accent": "#255044", "description": "Active paid client relationship."},
        {"id": "alumni", "label": "Alumni", "accent": "#786D8F", "description": "Past clients for referrals and reactivation."},
    ],
}


class CRMError(RuntimeError):
    pass


@dataclass
class ServerContext:
    profile: str
    host: str
    port: int


def log_line(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    line = f"[{timestamp}] {message}"
    print(line, file=sys.stderr, flush=True)
    if LOG_FILE is not None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def init_log_file() -> None:
    global LOG_FILE
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-crm.log"
    latest = LOG_DIR / "latest.log"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(LOG_FILE.name)
    except OSError:
        pass


def add_profile_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help=f"Profile slug or name. Default: {DEFAULT_PROFILE}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cento CRM module for questionnaire capture, app bootstrap, and self-hosted local CRM.")
    subparsers = parser.add_subparsers(dest="command")

    questionnaire = subparsers.add_parser("questionnaire", help="Run or resume the CRM questionnaire.")
    add_profile_argument(questionnaire)
    questionnaire.add_argument("--reset", action="store_true", help="Start this profile from scratch.")

    show = subparsers.add_parser("show", help="Print the saved CRM questionnaire summary.")
    add_profile_argument(show)

    paths = subparsers.add_parser("paths", help="Print questionnaire and CRM app paths.")
    add_profile_argument(paths)

    docs = subparsers.add_parser("docs", help="Print the CRM module documentation.")
    add_profile_argument(docs)

    init_cmd = subparsers.add_parser("init", help="Bootstrap the CRM app state from the questionnaire.")
    add_profile_argument(init_cmd)
    init_cmd.add_argument("--force", action="store_true", help="Overwrite the existing CRM state for this profile.")

    serve = subparsers.add_parser("serve", help="Run the local self-hosted CRM server.")
    add_profile_argument(serve)
    serve.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host. Default: {DEFAULT_HOST}")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port. Default: {DEFAULT_PORT}")
    serve.add_argument("--open", action="store_true", help="Open the CRM in the default browser.")

    integration = subparsers.add_parser("integration", help="Show registered future CRM integrations.")
    add_profile_argument(integration)
    integration.add_argument("--provider", default="telegram", help="Integration provider placeholder. Default: telegram")
    integration.add_argument("--person", help="Career-intake person for provider workflows such as Redmine.")
    integration.add_argument("--start-workflow", action="store_true", help="Start provider workflow from generated intake artifacts.")
    integration.add_argument("--redmine-url", default="", help="Redmine base URL. Default: REDMINE_URL or http://localhost:47874.")
    integration.add_argument("--api-key", default="", help="Redmine API key. Default: REDMINE_API_KEY or ~/.config/cento/redmine.json.")
    integration.add_argument("--dry-run", action="store_true", help="Plan integration changes without writing to the provider.")

    intake = subparsers.add_parser("intake", help="Manage career-client intake dossiers and artifact plans.")
    intake_subparsers = intake.add_subparsers(dest="intake_command")

    intake_init = intake_subparsers.add_parser("init", help="Create or update a person intake dossier.")
    intake_init.add_argument("--person", required=True, help="Person or client name.")
    intake_init.add_argument("--target-role", default="", help="Primary target role or role family.")
    intake_init.add_argument("--target-companies", default="", help="Comma-separated top target companies.")
    intake_init.add_argument("--notes", default="", help="Short positioning or context notes.")

    intake_add = intake_subparsers.add_parser("add", help="Attach a raw source to a person intake dossier.")
    intake_add.add_argument("--person", required=True, help="Person or client name.")
    intake_add.add_argument("--kind", required=True, choices=sorted(SOURCE_KINDS), help="Source kind.")
    intake_add.add_argument("--file", help="Path to a source file to copy into the dossier.")
    intake_add.add_argument("--text", help="Inline source text to save into the dossier.")
    intake_add.add_argument("--title", default="", help="Human-readable source title.")
    intake_add.add_argument("--url", default="", help="Optional source URL.")

    intake_plan = intake_subparsers.add_parser("plan", help="Generate the artifact plan and Codex-ready prompts for a dossier.")
    intake_plan.add_argument("--person", required=True, help="Person or client name.")
    intake_plan.add_argument("--force", action="store_true", help="Regenerate existing prompt files.")

    intake_show = intake_subparsers.add_parser("show", help="Print a dossier summary.")
    intake_show.add_argument("--person", required=True, help="Person or client name.")

    intake_paths = intake_subparsers.add_parser("paths", help="Print dossier paths.")
    intake_paths.add_argument("--person", required=True, help="Person or client name.")

    return parser.parse_args()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or DEFAULT_PROFILE


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def resolve_questionnaire_paths(profile_name: str) -> tuple[str, Path, Path, Path]:
    profile_slug = slugify(profile_name)
    profile_dir = QUESTIONNAIRE_ROOT / profile_slug
    answers_path = profile_dir / "answers.json"
    summary_path = profile_dir / "summary.md"
    return profile_slug, profile_dir, answers_path, summary_path


def resolve_app_paths(profile_name: str) -> tuple[str, Path, Path]:
    profile_slug = slugify(profile_name)
    app_dir = CRM_ROOT / profile_slug
    state_path = app_dir / "state.json"
    return profile_slug, app_dir, state_path


def resolve_intake_paths(person_name: str) -> tuple[str, Path, Path, Path, Path, Path]:
    person_slug = slugify(person_name)
    dossier_dir = INTAKE_ROOT / person_slug
    manifest_path = dossier_dir / "manifest.json"
    sources_dir = dossier_dir / "sources"
    artifacts_dir = dossier_dir / "artifacts"
    prompts_dir = dossier_dir / "prompts"
    return person_slug, dossier_dir, manifest_path, sources_dir, artifacts_dir, prompts_dir


def read_json(path: Path, fallback: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def next_source_id(manifest: dict[str, Any], kind: str) -> str:
    existing = [item.get("id", "") for item in manifest.get("sources", []) if isinstance(item, dict)]
    prefix = f"source-{slugify(kind)}-"
    numbers = []
    for source_id in existing:
        if source_id.startswith(prefix):
            suffix = source_id[len(prefix):]
            if suffix.isdigit():
                numbers.append(int(suffix))
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def source_extension(path: Path | None, kind: str) -> str:
    if path and path.suffix:
        return path.suffix
    if kind in {"telegram", "notes", "company", "job-description"}:
        return ".md"
    return ".txt"


def load_intake_manifest(person_name: str, require_exists: bool = True) -> tuple[str, Path, dict[str, Any]]:
    person_slug, dossier_dir, manifest_path, _sources_dir, _artifacts_dir, _prompts_dir = resolve_intake_paths(person_name)
    manifest = read_json(manifest_path, {})
    if not isinstance(manifest, dict) or not manifest:
        if require_exists:
            raise CRMError(f"No intake dossier found for '{person_slug}'. Run `cento crm intake init --person ...` first.")
        manifest = {
            "schema_version": "1.0",
            "person": {
                "slug": person_slug,
                "name": person_name,
                "target_role": "",
                "target_companies": [],
                "notes": "",
            },
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sources": [],
            "artifact_plan": [],
        }
    return person_slug, dossier_dir, manifest


def save_intake_manifest(person_name: str, manifest: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    person_slug, _dossier_dir, manifest_path, _sources_dir, _artifacts_dir, _prompts_dir = resolve_intake_paths(person_name)
    manifest["schema_version"] = "1.0"
    manifest["updated_at"] = now_iso()
    manifest.setdefault("created_at", now_iso())
    manifest.setdefault("person", {})["slug"] = person_slug
    write_json(manifest_path, manifest)
    INTAKE_ROOT.mkdir(parents=True, exist_ok=True)
    latest = INTAKE_ROOT / "latest.json"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(manifest_path.relative_to(latest.parent))
    except OSError:
        shutil.copy2(manifest_path, latest)
    return manifest, manifest_path


def init_intake_dossier(person_name: str, target_role: str = "", target_companies: str = "", notes: str = "") -> tuple[dict[str, Any], Path]:
    person_slug, dossier_dir, _manifest_path, sources_dir, artifacts_dir, prompts_dir = resolve_intake_paths(person_name)
    _slug, _dir, manifest = load_intake_manifest(person_name, require_exists=False)
    dossier_dir.mkdir(parents=True, exist_ok=True)
    sources_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    person = manifest.setdefault("person", {})
    person["slug"] = person_slug
    person["name"] = person_name
    if target_role:
        person["target_role"] = target_role
    else:
        person.setdefault("target_role", "")
    if target_companies:
        person["target_companies"] = split_csv(target_companies)
    else:
        person.setdefault("target_companies", [])
    if notes:
        person["notes"] = notes
    else:
        person.setdefault("notes", "")
    manifest.setdefault("sources", [])
    manifest.setdefault("artifact_plan", [])
    return save_intake_manifest(person_name, manifest)


def add_intake_source(person_name: str, kind: str, file_path: str | None, text: str | None, title: str = "", url: str = "") -> tuple[dict[str, Any], Path]:
    if bool(file_path) == bool(text):
        raise CRMError("Provide exactly one of --file or --text.")
    person_slug, _dossier_dir, manifest_path, sources_dir, _artifacts_dir, _prompts_dir = resolve_intake_paths(person_name)
    _slug, _dir, manifest = load_intake_manifest(person_name, require_exists=True)
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_id = next_source_id(manifest, kind)
    source_path: Path
    source_bytes: bytes
    original_path = ""
    if file_path:
        original = Path(file_path).expanduser()
        if not original.exists():
            raise CRMError(f"Source file does not exist: {original}")
        source_path = sources_dir / f"{source_id}{source_extension(original, kind)}"
        source_bytes = original.read_bytes()
        original_path = str(original)
    else:
        source_path = sources_dir / f"{source_id}{source_extension(None, kind)}"
        source_bytes = (text or "").encode("utf-8")
    source_path.write_bytes(source_bytes)
    record = {
        "id": source_id,
        "kind": kind,
        "kind_label": SOURCE_KINDS[kind],
        "title": title or SOURCE_KINDS[kind],
        "path": str(source_path.relative_to(manifest_path.parent)),
        "original_path": original_path,
        "url": url,
        "bytes": len(source_bytes),
        "added_at": now_iso(),
    }
    manifest.setdefault("sources", []).append(record)
    save_intake_manifest(person_slug, manifest)
    return manifest, source_path


def source_summary(manifest: dict[str, Any]) -> str:
    sources = manifest.get("sources", [])
    if not sources:
        return "No sources attached yet."
    lines = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        lines.append(
            f"- `{source.get('id', '')}` {source.get('kind_label', source.get('kind', 'source'))}: "
            f"{source.get('title', '')} ({source.get('path', '')})"
        )
    return "\n".join(lines) or "No sources attached yet."


def build_artifact_plan(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    source_kinds = {source.get("kind") for source in manifest.get("sources", []) if isinstance(source, dict)}
    person = manifest.get("person", {})
    target_companies = person.get("target_companies") if isinstance(person, dict) else []
    plan = []
    for artifact in CAREER_ARTIFACTS:
        item = dict(artifact)
        item["status"] = "planned"
        item["output_path"] = f"artifacts/{item['id']}.md"
        item["prompt_path"] = f"prompts/{item['id']}.md"
        if item["id"].startswith("resume") and "resume" not in source_kinds:
            item["status"] = "blocked"
            item["blocked_reason"] = "Attach a resume source first."
        if item["id"] == "linkedin-profile-review" and "linkedin" not in source_kinds:
            item["status"] = "blocked"
            item["blocked_reason"] = "Attach a LinkedIn profile source first."
        if item["id"] == "top-5-cover-letter-pack" and not target_companies:
            item["status"] = "needs-targets"
            item["blocked_reason"] = "Add target companies through intake init."
        plan.append(item)
    return plan


def render_artifact_plan_markdown(manifest: dict[str, Any], plan: list[dict[str, Any]]) -> str:
    person = manifest.get("person", {})
    target_companies = person.get("target_companies", []) if isinstance(person, dict) else []
    lines = [
        "# Career Intake Artifact Plan",
        "",
        f"- person: `{person.get('name', '')}`",
        f"- target_role: `{person.get('target_role', '')}`",
        f"- target_companies: `{', '.join(target_companies) if target_companies else 'not set'}`",
        f"- generated_at: `{now_iso()}`",
        "",
        "## Sources",
        "",
        source_summary(manifest),
        "",
        "## Artifact Queue",
        "",
    ]
    for item in plan:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- id: `{item['id']}`",
                f"- status: `{item['status']}`",
                f"- output: `{item['output_path']}`",
                f"- prompt: `{item['prompt_path']}`",
                f"- purpose: {item['description']}",
            ]
        )
        if item.get("blocked_reason"):
            lines.append(f"- blocker: {item['blocked_reason']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_codex_prompt(manifest: dict[str, Any], artifact: dict[str, Any]) -> str:
    person = manifest.get("person", {})
    target_companies = person.get("target_companies", []) if isinstance(person, dict) else []
    sources = source_summary(manifest)
    return (
        f"# Codex Prompt: {artifact['title']}\n\n"
        "You are working inside the local `cento` career-consulting ecosystem.\n"
        "Use only the dossier sources listed below unless the operator explicitly provides more context.\n"
        "Do not invent facts. Mark missing information as an open question.\n\n"
        "## Candidate Context\n\n"
        f"- name: {person.get('name', '')}\n"
        f"- target_role: {person.get('target_role', '') or 'not specified'}\n"
        f"- target_companies: {', '.join(target_companies) if target_companies else 'not specified'}\n"
        f"- notes: {person.get('notes', '') or 'none'}\n\n"
        "## Dossier Sources\n\n"
        f"{sources}\n\n"
        "## Requested Artifact\n\n"
        f"- id: `{artifact['id']}`\n"
        f"- title: {artifact['title']}\n"
        f"- goal: {artifact['description']}\n"
        f"- write output to: `{artifact['output_path']}`\n\n"
        "## Output Requirements\n\n"
        "- Start with a concise executive summary.\n"
        "- Separate evidence-backed findings from assumptions.\n"
        "- Include concrete edits, examples, or next actions where relevant.\n"
        "- Add an `Open Questions` section for missing data.\n"
        "- Keep the artifact client-useful, direct, and specific.\n"
    )


def generate_intake_plan(person_name: str, force: bool = False) -> tuple[dict[str, Any], Path]:
    person_slug, dossier_dir, manifest = load_intake_manifest(person_name, require_exists=True)
    _slug, _dossier_dir, manifest_path, _sources_dir, artifacts_dir, prompts_dir = resolve_intake_paths(person_slug)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    plan = build_artifact_plan(manifest)
    manifest["artifact_plan"] = plan
    plan_path = dossier_dir / "artifact-plan.md"
    plan_path.write_text(render_artifact_plan_markdown(manifest, plan), encoding="utf-8")
    for artifact in plan:
        prompt_path = dossier_dir / artifact["prompt_path"]
        if prompt_path.exists() and not force:
            continue
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(render_codex_prompt(manifest, artifact), encoding="utf-8")
        output_path = dossier_dir / artifact["output_path"]
        if not output_path.exists():
            output_path.write_text(
                f"# {artifact['title']}\n\nStatus: `{artifact['status']}`\n\nGenerated artifact content goes here.\n",
                encoding="utf-8",
            )
    save_intake_manifest(person_slug, manifest)
    return manifest, plan_path


def show_intake(person_name: str) -> int:
    person_slug, dossier_dir, manifest = load_intake_manifest(person_name, require_exists=True)
    person = manifest.get("person", {})
    print(f"person: {person.get('name', person_slug)}")
    print(f"slug: {person_slug}")
    print(f"dossier: {dossier_dir}")
    print(f"target_role: {person.get('target_role', '')}")
    print(f"target_companies: {', '.join(person.get('target_companies', []))}")
    print(f"sources: {len(manifest.get('sources', []))}")
    print(f"artifacts: {len(manifest.get('artifact_plan', []))}")
    return 0


def show_intake_paths(person_name: str) -> int:
    person_slug, dossier_dir, manifest_path, sources_dir, artifacts_dir, prompts_dir = resolve_intake_paths(person_name)
    print(f"person: {person_slug}")
    print(f"dossier_dir: {dossier_dir}")
    print(f"manifest_json: {manifest_path}")
    print(f"sources_dir: {sources_dir}")
    print(f"artifacts_dir: {artifacts_dir}")
    print(f"prompts_dir: {prompts_dir}")
    print(f"artifact_plan_md: {dossier_dir / 'artifact-plan.md'}")
    print(f"latest_intake_json: {INTAKE_ROOT / 'latest.json'}")
    return 0


class RedmineAPIError(CRMError):
    pass


class RedmineClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Redmine-API-Key": self.api_key,
        }
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                data = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RedmineAPIError(f"Redmine API {method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RedmineAPIError(f"Could not reach Redmine at {self.base_url}: {exc}") from exc
        if not data:
            return {}
        try:
            parsed = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RedmineAPIError(f"Redmine returned non-JSON for {method} {path}.") from exc
        return parsed if isinstance(parsed, dict) else {}

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", path, payload)


def redmine_config(redmine_url: str = "", api_key: str = "") -> tuple[str, str]:
    payload = read_json(REDMINE_CONFIG_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    base_url = redmine_url or os.environ.get("REDMINE_URL") or str(payload.get("url") or "http://localhost:47874")
    key = api_key or os.environ.get("REDMINE_API_KEY") or str(payload.get("api_key") or "")
    if not key:
        raise CRMError(
            "Missing Redmine API key. Set REDMINE_API_KEY or write ~/.config/cento/redmine.json with {'url': 'http://localhost:47874', 'api_key': '...'}."
        )
    return base_url.rstrip("/"), key


def artifact_tracker_name(artifact_id: str) -> str:
    return ARTIFACT_TRACKER_HINTS.get(artifact_id, "Intake")


def redmine_identifier(value: str) -> str:
    ident = slugify(value)
    ident = re.sub(r"[^a-z0-9-]", "-", ident).strip("-")
    return ident[:80] or "career-intake"


def redmine_project_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    person = manifest.get("person", {})
    name = str(person.get("name") or "Career Intake")
    target_role = str(person.get("target_role") or "")
    companies = ", ".join(person.get("target_companies") or [])
    description = [
        f"Career-intake workflow for {name}.",
        f"Target role: {target_role or 'not specified'}.",
        f"Target companies: {companies or 'not specified'}.",
        "",
        "Created from cento career-intake generated artifacts.",
    ]
    return {
        "project": {
            "name": f"{name} Career Workflow",
            "identifier": redmine_identifier(f"career-{person.get('slug') or name}"),
            "description": "\n".join(description),
            "is_public": False,
            "enabled_module_names": ["issue_tracking", "wiki", "documents", "files", "calendar", "gantt"],
        }
    }


def redmine_issue_description(manifest: dict[str, Any], artifact: dict[str, Any], dossier_dir: Path) -> str:
    person = manifest.get("person", {})
    companies = ", ".join(person.get("target_companies") or [])
    sources = source_summary(manifest)
    return "\n".join(
        [
            artifact.get("description", ""),
            "",
            f"Candidate: {person.get('name', '')}",
            f"Target role: {person.get('target_role', '') or 'not specified'}",
            f"Target companies: {companies or 'not specified'}",
            "",
            f"Cento artifact output: {dossier_dir / artifact.get('output_path', '')}",
            f"Cento prompt: {dossier_dir / artifact.get('prompt_path', '')}",
            "",
            "Sources:",
            sources,
        ]
    )


def redmine_tracker_map(client: RedmineClient) -> dict[str, int]:
    payload = client.get("/trackers.json")
    trackers = payload.get("trackers", [])
    if not isinstance(trackers, list):
        return {}
    return {str(tracker.get("name")): int(tracker.get("id")) for tracker in trackers if tracker.get("name") and tracker.get("id")}


def redmine_default_tracker_id(trackers: dict[str, int], preferred: str) -> int:
    if preferred in trackers:
        return trackers[preferred]
    if "Intake" in trackers:
        return trackers["Intake"]
    if trackers:
        return next(iter(trackers.values()))
    raise RedmineAPIError("No Redmine trackers are available. Seed or configure Redmine trackers first.")


def ensure_redmine_project_trackers(client: RedmineClient, project_identifier: str, trackers: dict[str, int]) -> None:
    if not trackers:
        return
    wanted = [
        trackers[name]
        for name in ("Intake", "Resume", "LinkedIn", "Applications", "Interview Prep", "Follow-up", "Offer")
        if name in trackers
    ]
    if not wanted:
        wanted = list(trackers.values())
    client.put(f"/projects/{project_identifier}.json", {"project": {"tracker_ids": wanted}})


def ensure_redmine_project(client: RedmineClient, manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = redmine_project_payload(manifest)
    identifier = payload["project"]["identifier"]
    try:
        existing = client.get(f"/projects/{identifier}.json")
        project = existing.get("project", {})
        return identifier, project if isinstance(project, dict) else {}
    except RedmineAPIError as exc:
        if "HTTP 404" not in str(exc):
            raise
    created = client.post("/projects.json", payload)
    project = created.get("project", {})
    return identifier, project if isinstance(project, dict) else {}


def start_redmine_workflow(person_name: str, redmine_url: str = "", api_key: str = "", dry_run: bool = False) -> dict[str, Any]:
    person_slug, dossier_dir, manifest = load_intake_manifest(person_name, require_exists=True)
    if not manifest.get("artifact_plan"):
        manifest, _plan_path = generate_intake_plan(person_slug, force=False)
    plan = [item for item in manifest.get("artifact_plan", []) if isinstance(item, dict)]
    if not plan:
        raise CRMError("No artifact plan exists for this intake dossier.")

    project_payload = redmine_project_payload(manifest)
    project_identifier = project_payload["project"]["identifier"]
    planned_issues = [
        {
            "subject": artifact.get("title", artifact.get("id", "Career artifact")),
            "tracker": artifact_tracker_name(str(artifact.get("id", ""))),
            "status": artifact.get("status", "planned"),
            "artifact_id": artifact.get("id", ""),
            "output_path": artifact.get("output_path", ""),
        }
        for artifact in plan
    ]
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "person": person_slug,
            "project_identifier": project_identifier,
            "project": project_payload["project"],
            "issues": planned_issues,
        }

    base_url, key = redmine_config(redmine_url, api_key)
    client = RedmineClient(base_url, key)
    _identifier, project = ensure_redmine_project(client, manifest)
    trackers = redmine_tracker_map(client)
    ensure_redmine_project_trackers(client, project_identifier, trackers)

    integration_state = manifest.setdefault("integrations", {}).setdefault("redmine", {})
    issue_ids = integration_state.setdefault("issue_ids", {})
    created_issues = []
    for artifact in plan:
        artifact_id = str(artifact.get("id", ""))
        if artifact_id in issue_ids:
            created_issues.append({"artifact_id": artifact_id, "issue_id": issue_ids[artifact_id], "status": "exists"})
            continue
        tracker_name = artifact_tracker_name(artifact_id)
        issue_payload = {
            "issue": {
                "project_id": project_identifier,
                "tracker_id": redmine_default_tracker_id(trackers, tracker_name),
                "subject": str(artifact.get("title") or artifact_id),
                "description": redmine_issue_description(manifest, artifact, dossier_dir),
            }
        }
        created = client.post("/issues.json", issue_payload)
        issue = created.get("issue", {})
        issue_id = issue.get("id")
        if issue_id:
            issue_ids[artifact_id] = issue_id
        created_issues.append({"artifact_id": artifact_id, "issue_id": issue_id, "status": "created", "tracker": tracker_name})

    integration_state.update(
        {
            "url": base_url,
            "project_identifier": project_identifier,
            "project_id": project.get("id"),
            "started_at": now_iso(),
            "issue_ids": issue_ids,
        }
    )
    save_intake_manifest(person_slug, manifest)
    return {
        "ok": True,
        "dry_run": False,
        "person": person_slug,
        "redmine_url": base_url,
        "project_identifier": project_identifier,
        "project_id": project.get("id"),
        "issues": created_issues,
    }


def option_map(question: Question) -> dict[str, Choice]:
    return {choice.value: choice for choice in question.choices}


def answer_exists(value: Any, kind: str) -> bool:
    if kind == "multi":
        return isinstance(value, list) and bool(value)
    return value not in ("", None)


def extract_existing_answer(payload: dict[str, Any], question: Question) -> Any:
    answers = payload.get("answers", {})
    record = answers.get(question.key, {})
    if not isinstance(record, dict):
        return None
    if question.kind == "multi":
        values = record.get("values", [])
        return values if isinstance(values, list) else None
    return record.get("value")


def hydrate_answers(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated: dict[str, Any] = {}
    for question in QUESTIONS:
        value = extract_existing_answer(payload, question)
        hydrated[question.key] = value if value is not None else ([] if question.kind == "multi" else "")
    return hydrated


def humanize_answer(question: Question, value: Any) -> str:
    if not answer_exists(value, question.kind):
        return "not answered"
    if question.kind == "text":
        return str(value)
    options = option_map(question)
    if question.kind == "single":
        return options.get(str(value), Choice(str(value), str(value))).label
    labels = [options[item].label for item in value if item in options]
    return ", ".join(labels) if labels else ", ".join(str(item) for item in value)


def format_answer_record(question: Question, value: Any) -> dict[str, Any]:
    if question.kind == "single":
        choice = option_map(question).get(str(value))
        return {"kind": "single", "value": str(value), "label": choice.label if choice else str(value)}
    if question.kind == "multi":
        options = option_map(question)
        values = [str(item) for item in value]
        labels = [options[item].label for item in values if item in options]
        return {"kind": "multi", "values": values, "labels": labels}
    return {"kind": "text", "value": str(value)}


def load_questionnaire_payload(profile_name: str) -> dict[str, Any]:
    _profile_slug, _profile_dir, answers_path, _summary_path = resolve_questionnaire_paths(profile_name)
    payload = read_json(answers_path, {})
    return payload if isinstance(payload, dict) else {}


def build_questionnaire_payload(profile_slug: str, answers: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    baseline = previous or {}
    return {
        "schema_version": QUESTIONNAIRE_VERSION,
        "project_type": "career-consulting-crm",
        "profile": profile_slug,
        "created_at": baseline.get("created_at") or now_iso(),
        "updated_at": now_iso(),
        "question_count": len(QUESTIONS),
        "answers": {
            question.key: format_answer_record(question, answers.get(question.key, [] if question.kind == "multi" else ""))
            for question in QUESTIONS
        },
    }


def build_questionnaire_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# CRM Questionnaire Summary",
        "",
        f"- profile: `{payload.get('profile', DEFAULT_PROFILE)}`",
        f"- updated_at: `{payload.get('updated_at', '')}`",
        f"- schema_version: `{payload.get('schema_version', QUESTIONNAIRE_VERSION)}`",
        "",
    ]
    answers = payload.get("answers", {})
    for question in QUESTIONS:
        record = answers.get(question.key, {})
        if question.kind == "single":
            rendered = record.get("label", "")
        elif question.kind == "multi":
            rendered = ", ".join(record.get("labels", []))
        else:
            rendered = record.get("value", "")
        lines.append(f"## {question.prompt}")
        lines.append("")
        lines.append(rendered or "(blank)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_questionnaire_latest(answers_path: Path, summary_path: Path) -> None:
    QUESTIONNAIRE_ROOT.mkdir(parents=True, exist_ok=True)
    for pointer, target in (
        (QUESTIONNAIRE_ROOT / "latest.json", answers_path),
        (QUESTIONNAIRE_ROOT / "latest.md", summary_path),
    ):
        try:
            if pointer.exists() or pointer.is_symlink():
                pointer.unlink()
            pointer.symlink_to(target.relative_to(pointer.parent))
        except OSError:
            shutil.copy2(target, pointer)


def save_questionnaire_profile(profile_slug: str, answers: dict[str, Any], previous: dict[str, Any], answers_path: Path, summary_path: Path) -> dict[str, Any]:
    payload = build_questionnaire_payload(profile_slug, answers, previous)
    write_json(answers_path, payload)
    summary_path.write_text(build_questionnaire_summary(payload), encoding="utf-8")
    update_questionnaire_latest(answers_path, summary_path)
    return payload


def render_question_header(index: int, total: int, question: Question, current: Any) -> None:
    print()
    print(f"[{index}/{total}] {question.prompt}")
    if question.help_text:
        print(f"  {question.help_text}")
    if answer_exists(current, question.kind):
        print(f"  Current: {humanize_answer(question, current)}")


def prompt_single(question: Question, current: Any) -> str:
    for idx, choice in enumerate(question.choices, start=1):
        marker = " (current)" if current == choice.value else ""
        print(f"  {idx}. {choice.label}{marker}")
    prompt = "Choose one number"
    if answer_exists(current, question.kind):
        prompt += " or press Enter to keep current"
    prompt += ": "
    while True:
        raw = input(prompt).strip()
        if not raw and answer_exists(current, question.kind):
            return str(current)
        if raw.isdigit():
            number = int(raw)
            if 1 <= number <= len(question.choices):
                return question.choices[number - 1].value
        print("Please enter one of the listed numbers.")


def prompt_multi(question: Question, current: Any) -> list[str]:
    current_set = set(current or [])
    for idx, choice in enumerate(question.choices, start=1):
        marker = " (current)" if choice.value in current_set else ""
        print(f"  {idx}. {choice.label}{marker}")
    prompt = "Choose numbers separated by commas"
    if question.optional:
        prompt += ", or enter 0 for none"
    if answer_exists(current, question.kind):
        prompt += ", or press Enter to keep current"
    prompt += ": "
    while True:
        raw = input(prompt).strip()
        if not raw and answer_exists(current, question.kind):
            return list(current)
        if raw == "0" and question.optional:
            return []
        items = [item.strip() for item in raw.split(",") if item.strip()]
        if not items:
            if question.optional:
                return []
            print("Please select at least one option.")
            continue
        if not all(item.isdigit() for item in items):
            print("Use numbers separated by commas, like 1,3,5.")
            continue
        indexes = [int(item) for item in items]
        if not all(1 <= index <= len(question.choices) for index in indexes):
            print("One or more selections are outside the listed range.")
            continue
        values: list[str] = []
        seen: set[str] = set()
        for index in indexes:
            value = question.choices[index - 1].value
            if value not in seen:
                values.append(value)
                seen.add(value)
        return values


def prompt_text(question: Question, current: Any) -> str:
    prompt = "Enter text"
    if question.optional:
        prompt += " or press Enter to leave blank"
    elif answer_exists(current, question.kind):
        prompt += " or press Enter to keep current"
    prompt += ": "
    while True:
        raw = input(prompt)
        if raw.strip():
            return raw.strip()
        if answer_exists(current, question.kind):
            return str(current)
        if question.optional:
            return ""
        print("This field is required.")


def prompt_for_answer(index: int, total: int, question: Question, current: Any) -> Any:
    render_question_header(index, total, question, current)
    if question.kind == "single":
        return prompt_single(question, current)
    if question.kind == "multi":
        return prompt_multi(question, current)
    if question.kind == "text":
        return prompt_text(question, current)
    raise ValueError(f"Unsupported question kind: {question.kind}")


def choose_questionnaire_mode(has_saved_answers: bool) -> str:
    if not has_saved_answers:
        return "all"
    print("Existing answers were found for this profile.")
    print("  1. Continue from unanswered questions")
    print("  2. Review every question")
    print("  3. Start over")
    print("  4. Exit")
    while True:
        raw = input("Choose a mode: ").strip()
        if raw == "1":
            return "unanswered"
        if raw == "2":
            return "all"
        if raw == "3":
            return "reset"
        if raw == "4":
            return "exit"
        print("Please enter 1, 2, 3, or 4.")


def run_questionnaire(profile_name: str, reset: bool = False) -> int:
    profile_slug, _profile_dir, answers_path, summary_path = resolve_questionnaire_paths(profile_name)
    previous = {} if reset else load_questionnaire_payload(profile_name)
    answers = hydrate_answers(previous)
    has_saved_answers = any(answer_exists(answers[question.key], question.kind) for question in QUESTIONS)
    mode = "reset" if reset else choose_questionnaire_mode(has_saved_answers)

    if mode == "exit":
        print("No changes made.")
        return 0
    if mode == "reset":
        previous = {}
        answers = hydrate_answers(previous)

    questions_to_ask = list(QUESTIONS)
    if mode == "unanswered":
        questions_to_ask = [question for question in QUESTIONS if not answer_exists(answers[question.key], question.kind)]
        if not questions_to_ask:
            print("All questions are already answered for this profile.")
            return show_summary(profile_name)

    print()
    print("Cento CRM questionnaire")
    print(f"Profile: {profile_slug}")
    print(f"Answers file: {answers_path}")
    print("Answers are saved after every question.")

    total = len(questions_to_ask)
    for index, question in enumerate(questions_to_ask, start=1):
        current = answers.get(question.key, [] if question.kind == "multi" else "")
        answers[question.key] = prompt_for_answer(index, total, question, current)
        previous = save_questionnaire_profile(profile_slug, answers, previous, answers_path, summary_path)

    print()
    print("Questionnaire saved.")
    return show_summary(profile_name)


def show_summary(profile_name: str) -> int:
    _profile_slug, _profile_dir, _answers_path, summary_path = resolve_questionnaire_paths(profile_name)
    if not summary_path.exists():
        print(f"No saved summary found for profile '{slugify(profile_name)}'.", file=sys.stderr)
        return 1
    print(summary_path.read_text(encoding="utf-8"))
    return 0


def questionnaire_answer_labels(payload: dict[str, Any], key: str) -> list[str]:
    record = payload.get("answers", {}).get(key, {})
    if not isinstance(record, dict):
        return []
    return list(record.get("labels", []))


def questionnaire_answer_values(payload: dict[str, Any], key: str) -> list[str]:
    record = payload.get("answers", {}).get(key, {})
    if not isinstance(record, dict):
        return []
    return list(record.get("values", []))


def questionnaire_answer_text(payload: dict[str, Any], key: str) -> str:
    record = payload.get("answers", {}).get(key, {})
    if not isinstance(record, dict):
        return ""
    return str(record.get("value", ""))


def build_service_templates(service_labels: list[str]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for label in service_labels:
        slug = slugify(label)
        templates.append(
            {
                "id": f"template-{slug}",
                "title": f"{label} kickoff brief",
                "service": label,
                "channel": "Email",
                "body": f"Thanks for reaching out about {label.lower()}. This template is ready for discovery, scope confirmation, timeline alignment, and next-step scheduling.",
            }
        )
    if not templates:
        templates.append(
            {
                "id": "template-general-discovery",
                "title": "General discovery brief",
                "service": "General",
                "channel": "Email",
                "body": "Use this for a first client response, discovery framing, and the next action you want the prospect to take.",
            }
        )
    return templates


def build_intake_forms(segment_labels: list[str], service_labels: list[str]) -> list[dict[str, Any]]:
    forms = [
        {
            "id": "form-discovery-intake",
            "title": "Discovery intake",
            "purpose": "Collect baseline career context before the first call.",
            "status": "active",
            "fields": [
                "Current role and target role",
                "Urgency and timeline",
                "Main blocker",
                "Top 3 desired outcomes",
            ],
        },
        {
            "id": "form-service-fit",
            "title": "Service-fit intake",
            "purpose": "Route prospects into the right package or session type.",
            "status": "active",
            "fields": [
                "Which service is most urgent",
                "Preferred support mode",
                "Budget comfort",
                "Current materials available",
            ],
        },
    ]
    if any("Immigrants" in label for label in segment_labels):
        forms.append(
            {
                "id": "form-relocation-context",
                "title": "Relocation and work authorization",
                "purpose": "Capture relocation, language, and work authorization context without overcomplicating the MVP.",
                "status": "draft",
                "fields": [
                    "Target country or market",
                    "Current work authorization status",
                    "Language confidence",
                    "Relocation constraints",
                ],
            }
        )
    if any("Interview" in label for label in service_labels):
        forms.append(
            {
                "id": "form-interview-brief",
                "title": "Interview prep brief",
                "purpose": "Collect target role, interviewer context, and concern areas before coaching.",
                "status": "active",
                "fields": [
                    "Target role and company",
                    "Interview stage",
                    "Concern areas",
                    "Stories to prepare",
                ],
            }
        )
    return forms


def build_pipeline_stages(template_value: str) -> list[dict[str, Any]]:
    return [dict(stage) for stage in PIPELINE_STAGE_LIBRARY.get(template_value, PIPELINE_STAGE_LIBRARY["simple"])]


def bootstrap_crm_state(profile_name: str, force: bool = False) -> tuple[dict[str, Any], Path]:
    questionnaire = load_questionnaire_payload(profile_name)
    if not questionnaire:
        raise CRMError("Complete the questionnaire before bootstrapping the CRM app.")

    profile_slug, app_dir, state_path = resolve_app_paths(profile_name)
    if state_path.exists() and not force:
        payload = read_json(state_path, {})
        if isinstance(payload, dict) and payload:
            return payload, state_path

    consultant_name = questionnaire_answer_text(questionnaire, "consultant_name") or "Cento CRM"
    business_name = questionnaire_answer_text(questionnaire, "business_name") or consultant_name
    service_labels = questionnaire_answer_labels(questionnaire, "services")
    service_values = questionnaire_answer_values(questionnaire, "services")
    segment_labels = questionnaire_answer_labels(questionnaire, "client_segments")
    lead_source_labels = questionnaire_answer_labels(questionnaire, "lead_sources")
    channel_labels = questionnaire_answer_labels(questionnaire, "communication_channels")
    integration_labels = questionnaire_answer_labels(questionnaire, "integrations")
    reporting_labels = questionnaire_answer_labels(questionnaire, "reporting_focus")
    engagement_labels = questionnaire_answer_labels(questionnaire, "engagement_model")
    must_have_labels = questionnaire_answer_labels(questionnaire, "must_have_features")
    document_labels = questionnaire_answer_labels(questionnaire, "documents_to_track")
    pipeline_template = questionnaire_answer_text(questionnaire, "pipeline_template") or "simple"
    automation_label = questionnaire.get("answers", {}).get("automation_level", {}).get("label", "")
    launch_label = questionnaire.get("answers", {}).get("launch_preference", {}).get("label", "")
    special_notes = questionnaire_answer_text(questionnaire, "special_notes")

    stages = build_pipeline_stages(pipeline_template)
    state = {
        "schema_version": CRM_STATE_VERSION,
        "profile": profile_slug,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "questionnaire_ref": {
            "updated_at": questionnaire.get("updated_at", ""),
            "path": str(resolve_questionnaire_paths(profile_name)[2]),
        },
        "branding": {
            "crm_name": consultant_name,
            "practice_name": business_name,
            "motto": "Local-first career consulting CRM, embedded in cento.",
        },
        "settings": {
            "business_model": questionnaire.get("answers", {}).get("business_model", {}).get("label", ""),
            "primary_goal": questionnaire.get("answers", {}).get("primary_goal", {}).get("label", ""),
            "pipeline_template": pipeline_template,
            "automation_level": automation_label,
            "launch_preference": launch_label,
            "special_notes": special_notes,
            "privacy_scope": "out-of-scope-for-mvp",
        },
        "catalogs": {
            "services": [{"id": value, "label": label} for value, label in zip(service_values, service_labels)],
            "client_segments": segment_labels,
            "lead_sources": lead_source_labels,
            "channels": channel_labels,
            "integrations": integration_labels,
            "reporting_focus": reporting_labels,
            "engagement_models": engagement_labels,
            "must_have_features": must_have_labels,
            "documents_to_track": document_labels,
        },
        "pipeline": {
            "stages": stages,
            "cards": [],
        },
        "contacts": [],
        "tasks": [],
        "notes": [
            {
                "id": "note-bootstrap",
                "type": "system",
                "title": "CRM bootstrap completed",
                "body": "The CRM state was generated from the saved cento questionnaire and is ready for live data.",
                "created_at": now_iso(),
            }
        ],
        "templates": build_service_templates(service_labels),
        "forms": build_intake_forms(segment_labels, service_labels),
        "highlights": [
            {"title": "Client segments", "value": ", ".join(segment_labels) or "Not defined"},
            {"title": "Lead sources", "value": ", ".join(lead_source_labels) or "Not defined"},
            {"title": "Must-have features", "value": ", ".join(must_have_labels) or "Not defined"},
            {"title": "Automation", "value": automation_label or "Not defined"},
        ],
    }

    write_json(state_path, state)
    CRM_ROOT.mkdir(parents=True, exist_ok=True)
    latest = CRM_ROOT / "latest.json"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(state_path.relative_to(latest.parent))
    except OSError:
        shutil.copy2(state_path, latest)
    return state, state_path


def load_state(profile_name: str, ensure_exists: bool = True) -> tuple[dict[str, Any], Path]:
    if ensure_exists:
        return bootstrap_crm_state(profile_name, force=False)
    _profile_slug, _app_dir, state_path = resolve_app_paths(profile_name)
    payload = read_json(state_path, {})
    return payload if isinstance(payload, dict) else {}, state_path


def save_state(profile_name: str, state: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    profile_slug, app_dir, state_path = resolve_app_paths(profile_name)
    app_dir.mkdir(parents=True, exist_ok=True)
    state["profile"] = profile_slug
    state["schema_version"] = CRM_STATE_VERSION
    state["updated_at"] = now_iso()
    if not state.get("created_at"):
        state["created_at"] = now_iso()
    write_json(state_path, state)
    latest = CRM_ROOT / "latest.json"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(state_path.relative_to(latest.parent))
    except OSError:
        shutil.copy2(state_path, latest)
    return state, state_path


def show_paths(profile_name: str) -> int:
    q_profile, q_dir, q_answers, q_summary = resolve_questionnaire_paths(profile_name)
    a_profile, a_dir, a_state = resolve_app_paths(profile_name)
    print(f"profile: {q_profile}")
    print(f"questionnaire_dir: {q_dir}")
    print(f"answers_json: {q_answers}")
    print(f"summary_md: {q_summary}")
    print(f"crm_app_dir: {a_dir}")
    print(f"crm_state_json: {a_state}")
    print(f"latest_questionnaire_json: {QUESTIONNAIRE_ROOT / 'latest.json'}")
    print(f"latest_questionnaire_md: {QUESTIONNAIRE_ROOT / 'latest.md'}")
    print(f"latest_crm_state_json: {CRM_ROOT / 'latest.json'}")
    return 0


def show_docs() -> int:
    if not DOCS_PATH.exists():
        print(f"CRM docs file is missing: {DOCS_PATH}", file=sys.stderr)
        return 1
    print(DOCS_PATH.read_text(encoding="utf-8"))
    return 0


def show_combined_docs() -> int:
    status = show_docs()
    if status != 0:
        return status
    if INTAKE_DOCS_PATH.exists():
        print()
        print(INTAKE_DOCS_PATH.read_text(encoding="utf-8"))
    if REDMINE_DOCS_PATH.exists():
        print()
        print(REDMINE_DOCS_PATH.read_text(encoding="utf-8"))
    return 0


def show_integration_placeholder(profile_name: str, provider: str) -> int:
    _profile_slug, app_dir, state_path = resolve_app_paths(profile_name)
    provider_slug = slugify(provider) or "telegram"
    app_dir.mkdir(parents=True, exist_ok=True)
    report_path = app_dir / f"integration-{provider_slug}.md"
    lines = [
        "# CRM Integration Placeholder",
        "",
        f"- profile: `{slugify(profile_name)}`",
        f"- provider: `{provider_slug}`",
        f"- recorded_at: `{now_iso()}`",
        f"- crm_state_path: `{state_path}`",
        "",
        "This command path is registered now, but the live integration is intentionally deferred.",
        "Planned first provider: Telegram.",
        "",
        "Next implementation steps:",
        "- subscribe CRM events to outbound notifications",
        "- map CRM templates into Telegram-ready message bodies",
        "- configure chat routing and event filters",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Registered CRM integration placeholder for {provider_slug}.")
    print(f"Report: {report_path}")
    return 0


def handle_integration(args: argparse.Namespace) -> int:
    provider = slugify(args.provider)
    if provider == "redmine" and args.start_workflow:
        if not args.person:
            raise CRMError("--person is required for Redmine workflow start.")
        result = start_redmine_workflow(
            args.person,
            redmine_url=args.redmine_url,
            api_key=args.api_key,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
        return 0
    return show_integration_placeholder(args.profile, args.provider)


def interactive_menu() -> int:
    if not sys.stdin.isatty():
        print("Use one of: questionnaire, show, paths, docs, init, serve, integration, intake", file=sys.stderr)
        return 1
    while True:
        print()
        print("Cento CRM module")
        print("  1. Start or resume questionnaire")
        print("  2. Show saved questionnaire summary")
        print("  3. Bootstrap CRM app state")
        print("  4. Serve CRM locally")
        print("  5. Show integration placeholder")
        print("  6. Show docs")
        print("  7. Show paths")
        print("  8. Exit")
        raw = input("Choose an action: ").strip()
        if raw == "1":
            return run_questionnaire(DEFAULT_PROFILE)
        if raw == "2":
            show_summary(DEFAULT_PROFILE)
            continue
        if raw == "3":
            state, state_path = bootstrap_crm_state(DEFAULT_PROFILE, force=False)
            print(f"CRM state ready at {state_path}")
            print(f"Pipeline stages: {', '.join(stage['label'] for stage in state.get('pipeline', {}).get('stages', []))}")
            continue
        if raw == "4":
            return run_server(DEFAULT_PROFILE, DEFAULT_HOST, DEFAULT_PORT, True)
        if raw == "5":
            show_integration_placeholder(DEFAULT_PROFILE, "telegram")
            continue
        if raw == "6":
            show_docs()
            continue
        if raw == "7":
            show_paths(DEFAULT_PROFILE)
            continue
        if raw == "8":
            print("Exiting.")
            return 0
        print("Please enter 1, 2, 3, 4, 5, 6, 7, or 8.")


def choose_port(host: str, preferred_port: int) -> int:
    for offset in range(PORT_SPAN):
        port = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
        return port
    raise CRMError(f"Could not bind a free port in range {preferred_port}-{preferred_port + PORT_SPAN - 1}.")


def request_log(method: str, path: str, status: int) -> None:
    with REQUEST_LOCK:
        REQUEST_LOG.append({"time": now_iso(), "method": method, "path": path, "status": str(status)})
        del REQUEST_LOG[:-REQUEST_LOG_LIMIT]


def read_static_file(name: str) -> bytes:
    target = TEMPLATE_DIR / name
    if not target.exists():
        raise FileNotFoundError(name)
    return target.read_bytes()


def content_type_for(path: str) -> str:
    if path.endswith('.css'):
        return 'text/css; charset=utf-8'
    if path.endswith('.js'):
        return 'application/javascript; charset=utf-8'
    if path.endswith('.json'):
        return 'application/json; charset=utf-8'
    return 'text/html; charset=utf-8'


def api_payload(profile_name: str) -> dict[str, Any]:
    state, state_path = load_state(profile_name, ensure_exists=True)
    questionnaire = load_questionnaire_payload(profile_name)
    _profile_slug, _q_dir, q_answers, q_summary = resolve_questionnaire_paths(profile_name)
    return {
        "ok": True,
        "profile": slugify(profile_name),
        "state": state,
        "questionnaire": {
            "updated_at": questionnaire.get("updated_at", ""),
            "summary_path": str(q_summary),
            "answers_path": str(q_answers),
        },
        "paths": {
            "state_path": str(state_path),
            "latest_state_path": str(CRM_ROOT / 'latest.json'),
        },
    }


def parse_request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get('Content-Length', '0') or '0')
    raw = handler.rfile.read(length) if length else b'{}'
    try:
        payload = json.loads(raw.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise CRMError(f"Invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise CRMError("Request body must be a JSON object.")
    return payload


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)
    request_log(handler.command, handler.path, status)


def file_response(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)
    request_log(handler.command, handler.path, status)


def build_handler(context: ServerContext) -> type[BaseHTTPRequestHandler]:
    class CRMHandler(BaseHTTPRequestHandler):
        server_version = 'cento-crm/1.0'

        def log_message(self, fmt: str, *args: Any) -> None:
            log_line(f"{self.client_address[0]} {fmt % args}")

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == '/api/state':
                    profile = parse_qs(parsed.query).get('profile', [context.profile])[0]
                    json_response(self, 200, api_payload(profile))
                    return
                if parsed.path == '/api/request-log':
                    with REQUEST_LOCK:
                        payload = {"ok": True, "requests": list(REQUEST_LOG)}
                    json_response(self, 200, payload)
                    return
                if parsed.path in ('/', '/index.html'):
                    body = read_static_file('index.html')
                    file_response(self, 200, body, 'text/html; charset=utf-8')
                    return
                if parsed.path == '/styles.css':
                    body = read_static_file('styles.css')
                    file_response(self, 200, body, 'text/css; charset=utf-8')
                    return
                if parsed.path == '/app.js':
                    body = read_static_file('app.js')
                    file_response(self, 200, body, 'application/javascript; charset=utf-8')
                    return
                if parsed.path == '/docs':
                    body = DOCS_PATH.read_bytes()
                    file_response(self, 200, body, 'text/markdown; charset=utf-8')
                    return
                json_response(self, 404, {"ok": False, "error": f"Unknown path: {parsed.path}"})
            except FileNotFoundError as exc:
                json_response(self, 404, {"ok": False, "error": f"Missing static asset: {exc}"})
            except CRMError as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": f"Unexpected server error: {exc}"})

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                if parsed.path == '/api/init':
                    payload = parse_request_json(self)
                    profile = payload.get('profile', context.profile)
                    force = bool(payload.get('force', False))
                    state, state_path = bootstrap_crm_state(str(profile), force=force)
                    json_response(self, 200, {"ok": True, "state": state, "state_path": str(state_path)})
                    return
                if parsed.path == '/api/save':
                    payload = parse_request_json(self)
                    profile = str(payload.get('profile', context.profile))
                    state = payload.get('state')
                    if not isinstance(state, dict):
                        raise CRMError('Missing state object.')
                    saved_state, state_path = save_state(profile, state)
                    json_response(self, 200, {"ok": True, "state": saved_state, "state_path": str(state_path)})
                    return
                if parsed.path == '/api/integrations/redmine/start-workflow':
                    payload = parse_request_json(self)
                    person = str(payload.get('person') or '')
                    if not person:
                        raise CRMError('Missing person.')
                    result = start_redmine_workflow(
                        person,
                        redmine_url=str(payload.get('redmine_url') or ''),
                        api_key=str(payload.get('api_key') or ''),
                        dry_run=bool(payload.get('dry_run', False)),
                    )
                    json_response(self, 200, result)
                    return
                json_response(self, 404, {"ok": False, "error": f"Unknown path: {parsed.path}"})
            except CRMError as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": f"Unexpected server error: {exc}"})

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

    return CRMHandler


def run_server(profile_name: str, host: str, preferred_port: int, should_open: bool) -> int:
    bootstrap_crm_state(profile_name, force=False)
    init_log_file()
    port = choose_port(host, preferred_port)
    context = ServerContext(profile=slugify(profile_name), host=host, port=port)
    server = ThreadingHTTPServer((host, port), build_handler(context))
    url = f"http://{host}:{port}/"
    log_line(f"CRM server starting for profile '{context.profile}' on {url}")
    print(f"CRM server running at {url}")
    print(f"Profile: {context.profile}")
    print(f"State: {resolve_app_paths(profile_name)[2]}")
    print('Press Ctrl+C to stop.')
    if should_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print()
        log_line('CRM server interrupted by user.')
    finally:
        server.server_close()
        log_line('CRM server stopped.')
    return 0


def main() -> int:
    args = parse_args()
    try:
        if args.command == 'questionnaire':
            return run_questionnaire(args.profile, reset=args.reset)
        if args.command == 'show':
            return show_summary(args.profile)
        if args.command == 'paths':
            return show_paths(args.profile)
        if args.command == 'docs':
            return show_combined_docs()
        if args.command == 'init':
            state, state_path = bootstrap_crm_state(args.profile, force=args.force)
            print(f"CRM state ready at {state_path}")
            print(f"Views: overview, pipeline, contacts, tasks, studio")
            print(f"Pipeline stages: {', '.join(stage['label'] for stage in state.get('pipeline', {}).get('stages', []))}")
            return 0
        if args.command == 'serve':
            return run_server(args.profile, args.host, args.port, args.open)
        if args.command == 'integration':
            return handle_integration(args)
        if args.command == 'intake':
            if args.intake_command == 'init':
                _manifest, manifest_path = init_intake_dossier(
                    args.person,
                    target_role=args.target_role,
                    target_companies=args.target_companies,
                    notes=args.notes,
                )
                print(f"Career intake dossier ready at {manifest_path}")
                return show_intake(args.person)
            if args.intake_command == 'add':
                _manifest, source_path = add_intake_source(
                    args.person,
                    args.kind,
                    args.file,
                    args.text,
                    title=args.title,
                    url=args.url,
                )
                print(f"Added source: {source_path}")
                return show_intake(args.person)
            if args.intake_command == 'plan':
                _manifest, plan_path = generate_intake_plan(args.person, force=args.force)
                print(f"Generated artifact plan: {plan_path}")
                return show_intake(args.person)
            if args.intake_command == 'show':
                return show_intake(args.person)
            if args.intake_command == 'paths':
                return show_intake_paths(args.person)
            print("Use one of: init, add, plan, show, paths", file=sys.stderr)
            return 1
        return interactive_menu()
    except CRMError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
