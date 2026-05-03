# Manifest-Driven Web App

<p><strong>Idea:</strong> Cento Docs, and eventually the broader Cento web app, could be generated from manifests and event streams rather than hand-wired page-by-page behavior.</p>

<p>Instead of running Cento ad hoc for every docs page or custom web surface, Cento would define clear processes, artifacts, boundaries, scopes, and acceptance rules. The web app would then autowire Taskstream execution results, Factory outputs, build receipts, validation evidence, and deliverables into Docs.</p>

<p>This mirrors the autonomous development system direction: manifest first, owned scope, explicit artifacts, deterministic validation, receipts, and evidence-backed rendering.</p>

<p>Docs pages would become views over durable manifests and event streams. A page could declare what it reads, what artifacts it displays, what commands it references, what evidence is required, and which boundaries it must not cross.</p>

<p>Ad hoc Docs functionality could still exist, but it should be manifest-shaped where practical: inputs, outputs, allowed commands, owned paths, validation rules, and render targets should be explicit.</p>

<p>The long-term goal is <strong>zero-AI or close-to-zero-AI regeneration</strong> for Docs and possibly the entire Cento web app. Cento should be able to regenerate large parts of the app from manifests, receipts, and event streams without asking an AI model to reinterpret intent every time.</p>

<p>This is not a commitment to implement the web app exactly this way. It is a design direction worth preserving: make the web app a deterministic projection of Cento's manifest-driven operating system, not a collection of manually maintained one-off pages.</p>

<p>Possible future primitives: docs manifest, page manifest, render manifest, command manifest, artifact manifest, event-stream binding, Taskstream result binding, Factory run binding, validation receipt binding, and build receipt binding.</p>

<p>Useful acceptance question: could this page be regenerated from declared inputs and receipts without hidden context?</p>
