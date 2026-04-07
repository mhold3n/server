import { Type } from "@sinclair/typebox"
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry"
import {
  createDevplaneClient,
  formatForText,
  summarizeStatus,
} from "./src/operator-client.js"

function resolveConfig(api: unknown): { baseUrl?: string; requestTimeoutMs?: number } {
  const candidate =
    typeof api === "object" && api !== null
      ? (
          "pluginConfig" in api
            ? (api as { pluginConfig?: unknown }).pluginConfig
            : "getConfig" in api &&
                typeof (api as { getConfig?: () => unknown }).getConfig === "function"
              ? (api as { getConfig: () => unknown }).getConfig()
              : (api as { config?: unknown }).config
        )
      : undefined
  if (typeof candidate === "object" && candidate !== null) {
    return candidate as { baseUrl?: string; requestTimeoutMs?: number }
  }
  return {}
}

function textResult(value: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: formatForText(value),
      },
    ],
    details: value,
  }
}

export default definePluginEntry({
  id: "birtha-devplane",
  name: "Birtha DevPlane",
  description:
    "Operator plugin for Birtha development-plane project, task, run, dossier, and publish control.",
  register(api) {
    const client = createDevplaneClient(resolveConfig(api))

    api.registerTool(
      {
        name: "devplane_list_projects",
        label: "devplane_list_projects",
        description: "List registered Birtha development-plane projects.",
        parameters: Type.Object({}),
        async execute() {
          return textResult(await client.listProjects())
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_register_project",
        label: "devplane_register_project",
        description: "Register an external git checkout with the Birtha control plane.",
        parameters: Type.Object({
          name: Type.String(),
          canonical_repo_path: Type.String(),
          default_branch: Type.Optional(Type.String()),
          remote_name: Type.Optional(Type.String()),
          github_owner: Type.Optional(Type.String()),
          github_repo: Type.Optional(Type.String()),
        }),
        async execute(_id, params) {
          return textResult(await client.registerProject(params))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_submit_task",
        label: "devplane_submit_task",
        description: "Submit a code-development task to the Birtha control plane.",
        parameters: Type.Object({
          project_id: Type.String(),
          user_intent: Type.String(),
          repo_ref_hint: Type.Optional(Type.String()),
          context: Type.Optional(Type.Record(Type.String(), Type.Any())),
          risk_hints: Type.Optional(Type.Array(Type.String())),
        }),
        async execute(_id, params) {
          return textResult(await client.submitTask(params))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_answer_clarifications",
        label: "devplane_answer_clarifications",
        description: "Answer clarification questions for a pending Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
          answers: Type.Array(
            Type.Object({
              question_id: Type.String(),
              answer: Type.String(),
            }),
          ),
        }),
        async execute(_id, params) {
          return textResult(
            await client.answerClarifications(params.task_id, params.answers),
          )
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_get_task",
        label: "devplane_get_task",
        description: "Inspect the latest control-plane state for a Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.getTask(params.task_id))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_get_run",
        label: "devplane_get_run",
        description: "Inspect the latest control-plane state for a Birtha run.",
        parameters: Type.Object({
          run_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.getRun(params.run_id))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_get_dossier",
        label: "devplane_get_dossier",
        description: "Fetch the dossier for a Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.getDossier(params.task_id))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_publish_task",
        label: "devplane_publish_task",
        description: "Publish a Birtha task branch and optionally create a PR.",
        parameters: Type.Object({
          task_id: Type.String(),
          commit_message: Type.Optional(Type.String()),
          push: Type.Optional(Type.Boolean()),
          create_pr: Type.Optional(Type.Boolean()),
          pr_title: Type.Optional(Type.String()),
          pr_body: Type.Optional(Type.String()),
          remote_name: Type.Optional(Type.String()),
        }),
        async execute(_id, params) {
          const { task_id, ...payload } = params
          return textResult(await client.publishTask(task_id, payload))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_cancel_task",
        label: "devplane_cancel_task",
        description: "Cancel the active run for a Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.cancelTask(params.task_id))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_retry_task",
        label: "devplane_retry_task",
        description: "Force a new internal execution run for a Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.retryTask(params.task_id))
        },
      },
      { optional: true },
    )

    api.registerTool(
      {
        name: "devplane_inspect_workspace",
        label: "devplane_inspect_workspace",
        description: "Resolve the current workspace path and run metadata for a Birtha task.",
        parameters: Type.Object({
          task_id: Type.String(),
        }),
        async execute(_id, params) {
          return textResult(await client.inspectWorkspace(params.task_id))
        },
      },
      { optional: true },
    )

    api.registerCommand({
      name: "devplane-status",
      description: "Summarize Birtha development-plane projects, tasks, and runs.",
      handler: async () => {
        const [projects, tasks, runs] = await Promise.all([
          client.listProjects(),
          client.listTasks(),
          client.listRuns(),
        ])
        return {
          text: summarizeStatus(projects, tasks, runs),
        }
      },
    })
  },
})
