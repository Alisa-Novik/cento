# Run Pipeline Compatibility Scenario

Open this URL after the app is running. It should land on the Run Pipeline modal
with the prompt already filled into `operator-thoughts`:

```text
http://127.0.0.1:47910/issues/new?prompt=Build%20a%20hard%20proreq%20plan%20from%20these%20operator%20notes%20and%20keep%20the%20frontend%20screenshot%20lane%20muted.
```

Click `Run pipeline`.

Expected result:

- Browser redirects to `/dev-pipeline-studio#pipeline-flow`.
- Execution Flow shows the hard-proreq route.
- No Taskstream issue is created for the prompt.
- The run records the five hard-proreq inputs: operator thoughts, generated Cento context, muted UI screenshot request, GPT Pro backend schema, and backend work handoff.
- Run artifacts appear under `workspace/runs/dev-pipeline-studio/docs-pages/latest/execution/hard-proreq/<run-id>/`.

For retries, change the prompt text before clicking `Run pipeline` so the run history is easy to distinguish.
