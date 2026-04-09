import { fileURLToPath } from "node:url"
import { defineConfig } from "vitest/config"

const openMultiAgentPath = fileURLToPath(
  new URL(
    "../../../merged claude leak/packages/open-multi-agent/dist/index.js",
    import.meta.url,
  ),
)

export default defineConfig({
  resolve: {
    alias: {
      "@server/open-multi-agent": openMultiAgentPath,
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
})
