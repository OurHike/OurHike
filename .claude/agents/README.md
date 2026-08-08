Agent manifests live under .claude/agents/*. Each agent has a YAML and JSON manifest describing its persona, capabilities, inputs, outputs, and recommended checks.

How to add an agent

1. Create a folder under .claude/agents/<agent-name>
2. Add <agent-name>-agent-manifest.yaml and <agent-name>-agent-manifest.json (both optional, YAML preferred)
3. Manifests should include: id, name, short_description, long_description, persona, primary_goals, capabilities, inputs_expected, outputs_and_artifacts, and next_steps.
4. If the agent requires CI checks, add workflow entries under .github/workflows and document required secrets in .github/expected-settings.yml.

How agents are used

- These manifests are documentation and can be used by automation: CI checks, PR templates, and chat/bot integrations.
- For now, Money Man is enforced through the costs-check workflow. Other agents are used as documentation for reviewers and to design further automation.

Registering an agent with a runtime

If you have an agent runtime (bot or cloud agent), map the manifest fields to the runtime schema and register the agent. Provide an install instruction here if needed.

Guidance for reviewers

- Look for the relevant agent in the PR checklist in .github/pull_request_template.md and request that agent's review where applicable.
- If an agent suggests an action (e.g., add COSTS.md), include that in reviewer comments and block merge until resolved.
